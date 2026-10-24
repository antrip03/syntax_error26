"""M0 driver, run INSIDE a Kaggle GPU kernel (T4 x2, internet on). Each stage is isolated; results -> /kaggle/working/m0/.
usage: python scripts/m0_smoke.py [--stages env,sglang,aligntune,curatorkit,auditkit]"""
import argparse
import json
import os
import subprocess
import time
import urllib.request

OUT = "/kaggle/working/m0"
os.makedirs(OUT, exist_ok=True)
RESULTS = {}


def sh(cmd, log, timeout=1800, env=None):
    t0 = time.time()
    with open(f"{OUT}/{log}.log", "w") as f:
        p = subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env={**os.environ, **(env or {})})
    print(f"[{log}] rc={p.returncode} {time.time() - t0:.0f}s", flush=True)
    return p.returncode


def tail(log, n=25):
    try:
        return "".join(open(f"{OUT}/{log}.log").readlines()[-n:])
    except Exception:
        return ""


def save():
    json.dump(RESULTS, open(f"{OUT}/results.json", "w"), indent=1)


def stage_env():
    sh("nvidia-smi; python -V; pip list 2>/dev/null | grep -i -E '^(torch|transformers|trl|peft|bitsandbytes|accelerate|datasets|unsloth|sglang|vllm|numpy) '", "env")
    RESULTS["env"] = tail("env", 40)


CANDIDATES = [
    "--dtype float16 --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.8",
    "--dtype float16 --attention-backend triton --sampling-backend pytorch --disable-cuda-graph --mem-fraction-static 0.7",
    "--dtype float16 --attention-backend torch_native --sampling-backend pytorch --disable-cuda-graph --mem-fraction-static 0.7",
]


def stage_sglang(model="Qwen/Qwen2.5-0.5B-Instruct"):
    py = "/kaggle/working/sglvenv/bin/python"
    if not os.path.exists(py):
        rc = sh("pip install -q uv && uv venv /kaggle/working/sglvenv --python 3.11 && "
                "uv pip install --python /kaggle/working/sglvenv/bin/python 'sglang[all]' requests", "sglang_install", 2400)
        if rc:
            RESULTS["sglang"] = {"install": "FAILED", "tail": tail("sglang_install")}
            return
    res = {"install": "ok", "attempts": []}
    # Kaggle images ship the driver libcuda.so.1 but no libcuda.so linker stub; flashinfer JIT links with -lcuda.
    sh("python scripts/find_libcuda.py /kaggle/working/cudastub; find / -name 'libcuda.so*' -not -path '/proc/*' 2>/dev/null", "cudastub")
    res["cudastub"] = tail("cudastub", 5)
    for i, flags in enumerate(CANDIDATES):
        cmd = f"LIBRARY_PATH=/kaggle/working/cudastub CUDA_VISIBLE_DEVICES=1 {py} -m sglang.launch_server --model-path {model} --port 30000 {flags}"
        logf = open(f"{OUT}/sglang_server_{i}.log", "w")
        srv = subprocess.Popen(cmd, shell=True, stdout=logf, stderr=subprocess.STDOUT)
        ok, answer = False, None
        for _ in range(120):
            time.sleep(5)
            if srv.poll() is not None:
                break
            try:
                urllib.request.urlopen("http://127.0.0.1:30000/health", timeout=3)
                body = {"model": model, "messages": [{"role": "user", "content": "What is 17+25? Answer with the number only."}],
                        "temperature": 0, "max_tokens": 16}
                req = urllib.request.Request("http://127.0.0.1:30000/v1/chat/completions", data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
                answer = json.loads(urllib.request.urlopen(req, timeout=60).read())["choices"][0]["message"]["content"]
                ok = True
                break
            except Exception:
                continue
        subprocess.run("pkill -f sglang.launch_server", shell=True)
        time.sleep(5)
        res["attempts"].append({"flags": flags, "ok": ok, "answer": answer, "tail": "" if ok else tail(f"sglang_server_{i}", 30)})
        if ok:
            res["working_command"] = f"python -m sglang.launch_server --model-path {model} --port 30000 {flags}"
            break
    RESULTS["sglang"] = res


def stage_aligntune():
    if sh("pip install -q aligntune datasets 2>&1 | tail -3; python -c 'import aligntune; print(aligntune.__file__)'", "aligntune_install", 1800):
        RESULTS["aligntune"] = {"install": "FAILED", "tail": tail("aligntune_install")}
        return
    res = {}
    for kind in ("dummy", "real"):
        rc = sh(f"CUDA_VISIBLE_DEVICES=0 python scripts/m0_grpo_smoke.py --reward {kind}", f"grpo_{kind}", 2400)
        res[kind] = {"rc": rc, "ok": "M0_GRPO_OK" in tail(f"grpo_{kind}", 200), "tail": tail(f"grpo_{kind}", 40)}
    RESULTS["aligntune"] = res


def stage_curatorkit():
    rc = sh("pip install -q curatorkit && python -c 'import curatorkit; print(getattr(curatorkit, \"__version__\", \"ok\"))'", "curatorkit", 900)
    RESULTS["curatorkit"] = {"rc": rc, "tail": tail("curatorkit", 10)}


def stage_auditkit():
    rc = sh("pip install -q auditkit && python -c 'import auditkit as ak; print(getattr(ak, \"__version__\", \"ok\"))'", "auditkit", 900)
    RESULTS["auditkit"] = {"rc": rc, "tail": tail("auditkit", 10)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="env,sglang,aligntune,curatorkit,auditkit")
    a = ap.parse_args()
    for s in a.stages.split(","):
        try:
            globals()[f"stage_{s}"]()
        except Exception as e:  # keep going: one run should report on every toolkit
            RESULTS[s] = {"exception": repr(e)}
        save()
    print(json.dumps(RESULTS, indent=1)[:6000])
