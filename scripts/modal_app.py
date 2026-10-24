"""Modal runner for fast SFT / eval experiments (budget-limited: keep jobs short).
  python -m modal run scripts/modal_app.py::exp --variant e2 --arm chunk [--n 1500 --epochs 2]
Training uses AlignTune SFT (A100, bf16, no 4-bit); evaluation serves the merged model with SGLang.
Outputs live in the Modal volume `finseries-out` (modal volume get finseries-out <path>)."""
import time

import modal

app = modal.App("finseries")
vol = modal.Volume.from_name("finseries-out", create_if_missing=True)
IGNORE = ["data_raw", "data_prepared", ".git", "**/__pycache__", "tests", "notebooks", "artifacts/results", "*.egg-info"]
RATES = {"A100-40GB": 2.10, "A10G": 1.10, "L4": 0.80, "L40S": 1.95}   # USD/hour, approximate list prices

train_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("aligntune", "curatorkit", "datasets", "pyyaml", "numpy", "pandas")
    .add_local_dir(".", "/root/repo", ignore=IGNORE)
)
sglang_image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .pip_install("sglang[all]", "requests", "pyyaml", "numpy", "pandas")
    .add_local_dir(".", "/root/repo", ignore=IGNORE)
)


def _sh(cmd, cwd="/root/repo"):
    import subprocess
    t0 = time.time()
    p = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    tail = (p.stdout + p.stderr)[-6000:]
    print(tail)
    return p.returncode, time.time() - t0, p.stdout


@app.function(gpu="A100-40GB", image=train_image, volumes={"/out": vol}, timeout=2400)
def sft(arm: str, variant: str, n: int, epochs: int, tag: str):
    rc, secs, out = _sh(f"python scripts/m4_sft.py --arms {arm} --variant {variant} --stages train,merge --n {n} --epochs {epochs} "
                        f"--hw a100 --tasks-dir /root/repo/artifacts/tasks --out /out/{tag}")
    vol.commit()
    return {"rc": rc, "secs": secs, "usd": secs / 3600 * RATES["A100-40GB"], "log_tail": out[-1500:]}


@app.function(gpu="L40S", image=sglang_image, volumes={"/out": vol}, timeout=1800)
def evaluate(arm: str, variant: str, tag: str, split: str = "val"):
    vol.reload()
    rc, secs, out = _sh(f"python scripts/eval_model.py --model /out/{tag}/merged_{arm} --arm {arm} --variant {variant} "
                        f"--tasks-dir /root/repo/artifacts/tasks --split {split} --out /out/{tag}/eval_{arm}_{split}")
    vol.commit()
    lines = [l for l in out.splitlines() if l.startswith(("EVAL", "BY_OP", "BY_FAMILY"))]
    return {"rc": rc, "secs": secs, "usd": secs / 3600 * RATES["L40S"], "summary": lines}


@app.local_entrypoint()
def exp(variant: str = "e2", arm: str = "chunk", n: int = 1500, epochs: int = 2, tag: str = "", skip_train: bool = False):
    tag = tag or f"{arm}_{variant}"
    total = 0.0
    if not skip_train:
        r = sft.remote(arm, variant, n, epochs, tag)
        total += r["usd"]
        print(f"[sft] rc={r['rc']} {r['secs']:.0f}s ~${r['usd']:.2f}")
        if r["rc"]:
            print(r["log_tail"])
            return
    r = evaluate.remote(arm, variant, tag)
    total += r["usd"]
    print(f"[eval] rc={r['rc']} {r['secs']:.0f}s ~${r['usd']:.2f}")
    print("\n".join(r["summary"]))
    print(f"[total GPU cost this run ~${total:.2f}]")
