"""M5 (Kaggle driver): GRPO from the SFT warm-start, then optional SGLang val eval of the result.
usage: python scripts/m5_grpo.py --arm chunk --variant e5 --adapter DIR --bundle outcome_process --steps 120 --eval
Training runs on GPU 0 (CUDA_VISIBLE_DEVICES=0); eval serves the merged result with SGLang on GPU 1."""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np

from finseries import scaffolds
from finseries.tasks.generate import read_jsonl
from finseries.train import grpo

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="chunk")
    ap.add_argument("--variant", default="e5")
    ap.add_argument("--base", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--adapter", default="")
    ap.add_argument("--adapter-name", default="")
    ap.add_argument("--tasks-file", default="", help="jsonl of GRPO prompts (curated); default: train.jsonl subset")
    ap.add_argument("--tasks-dir", default="")
    ap.add_argument("--n-tasks", type=int, default=400)
    ap.add_argument("--bundle", default="outcome_process")
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--max-new", type=int, default=1000)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--eval-only", action="store_true", help="skip GRPO; evaluate the SFT start model")
    ap.add_argument("--skip-train", action="store_true", help="evaluate the adapter already in --out/--tag")
    ap.add_argument("--time-budget-min", type=float, default=0)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--precision", default="fp16", help="fp16 on T4, bf16 on L4/A100")
    ap.add_argument("--tag", default="grpo")
    ap.add_argument("--out", default="/kaggle/working/m5")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.adapter_name:
        from finseries.train.adapters import find_adapter
        a.adapter = find_adapter(a.adapter_name)
    print('adapter:', a.adapter, flush=True)
    tasks_dir = a.tasks_dir or os.path.dirname(glob.glob("/kaggle/input/**/val.jsonl", recursive=True)[0])
    os.environ.setdefault("FINSERIES_SGL_LOG", f"{a.out}/sglang_server.log")
    skw = grpo.VARIANTS[a.variant]
    sc = scaffolds.get(a.arm, **skw)
    start = f"{a.out}/start_model"
    if not os.path.exists(f"{start}/config.json"):
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
        m = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.float16), a.adapter).merge_and_unload()
        m.save_pretrained(start, safe_serialization=True)
        AutoTokenizer.from_pretrained(a.base).save_pretrained(start)
        del m
    if a.tasks_file:
        rows = read_jsonl(a.tasks_file)
    else:
        allt = read_jsonl(f"{tasks_dir}/train.jsonl")
        rows = [allt[i] for i in np.random.default_rng(5).permutation(len(allt))[:a.n_tasks]]
    print(f"GRPO {a.arm}/{a.variant}/{a.bundle}: {len(rows)} prompts, {a.steps} steps", flush=True)
    out = f"{a.out}/{a.tag}"
    if not a.eval_only and not a.skip_train:
        grpo.run(start, rows, sc, a.bundle, out, a.steps, a.gens, a.batch, lr=a.lr, max_new=a.max_new, resume=a.resume,
                 time_budget_s=int(a.time_budget_min * 60), precision=a.precision)
        print("M5_GRPO_OK", a.tag, flush=True)
    if a.eval or a.eval_only:
        import shutil

        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        from finseries.adapters.sglang_client import SGLangClient
        from finseries.eval import run_eval
        from finseries.serve import sglang_server
        merged = start
        if not a.eval_only:
            ck = out if os.path.exists(f"{out}/adapter_model.safetensors") else sorted(
                glob.glob(f"{out}/checkpoint-*"), key=lambda p: int(p.rsplit("-", 1)[1]))[-1]
            print("evaluating adapter from", ck, flush=True)
            merged = f"{a.out}/{a.tag}_merged"
            m = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(start, dtype=torch.float16), ck).merge_and_unload()
            m.save_pretrained(merged, safe_serialization=True)
            AutoTokenizer.from_pretrained(a.base).save_pretrained(merged)
            del m
            shutil.copytree(ck, f"{a.out}/{a.tag}_adapter", dirs_exist_ok=True, ignore=shutil.ignore_patterns("optimizer.pt", "*.pt", "rng_state*"))
        sglang_server.install()
        plan = [("val", 300, 1500), ("test_period", 200, 1500), ("test_len", 60, 4000)]
        allm = {}
        with sglang_server.server(merged) as url:
            client = SGLangClient(url, concurrency=128, timeout=1500)
            for split, lim, mt in plan:
                ts = read_jsonl(f"{tasks_dir}/{split}.jsonl")[:lim]
                _, met = run_eval.run(ts, a.arm, client, f"{a.out}/{a.tag}_{split}", max_tokens=mt, scaffold_kwargs=skw)
                o = met["overall"]
                allm[split] = o
                print(f"EVAL {a.tag} {split}: n={o['n']} acc={o['accuracy']:.3f} parse={o['parse_rate']:.3f} "
                      f"stepvalid={o['step_validity']:.3f} tok={o['mean_tokens']:.0f}", flush=True)
                json.dump(allm, open(f"{a.out}/{a.tag}_eval.json", "w"), indent=1)
