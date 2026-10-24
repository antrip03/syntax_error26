"""M3b (Kaggle driver): difficulty curation with the SFT model.
merge SFT adapter -> serve with SGLang (GPU1) -> sample N completions/task on train tasks -> pass rate per task ->
CuratorKIT pipeline (verifier gate + 20-80% pass-rate gate) -> raw vs curated task sets (+ manifests).
usage: python scripts/m5_curate.py --arm chunk --variant e5 --adapter DIR --tasks-dir DIR"""
import argparse
import glob
import json
import os

import numpy as np

from finseries.adapters.curatorkit_adapter import curate
from finseries.adapters.sglang_client import SGLangClient
from finseries.eval import run_eval
from finseries.serve import sglang_server
from finseries.tasks.generate import read_jsonl

VARIANTS = {"base": {}, "e4": {"trace_style": "scratch"}, "e5": {"trace_style": "scratch2"}}


def merge(base, adapter, dst):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.float16)
    m = PeftModel.from_pretrained(m, adapter).merge_and_unload()
    m.save_pretrained(dst, safe_serialization=True)
    AutoTokenizer.from_pretrained(base).save_pretrained(dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="chunk")
    ap.add_argument("--variant", default="e5")
    ap.add_argument("--base", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--tasks-dir", default="")
    ap.add_argument("--train-file", default="train.jsonl")
    ap.add_argument("--n-tasks", type=int, default=1500)
    ap.add_argument("--n-samples", type=int, default=8)
    ap.add_argument("--out", default="/kaggle/working/m5")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tasks_dir = a.tasks_dir or os.path.dirname(glob.glob("/kaggle/input/**/val.jsonl", recursive=True)[0])
    skw = VARIANTS[a.variant]
    merged = f"{a.out}/start_model"
    merge(a.base, a.adapter, merged)
    print("merged ->", merged, flush=True)
    sglang_server.install()
    train = read_jsonl(f"{tasks_dir}/{a.train_file}")
    sub = [train[i] for i in np.random.default_rng(3).permutation(len(train))[:a.n_tasks]]
    with sglang_server.server(merged) as url:
        rows, m = run_eval.run(sub, a.arm, SGLangClient(url, concurrency=128), f"{a.out}/passrate_{a.arm}", n=a.n_samples,
                               temperature=0.7, max_tokens=1000, seed=21, scaffold_kwargs=skw)
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r["correct"])
    rates = {i: {a.arm: float(np.mean(v))} for i, v in by.items()}
    allp = np.array([r[a.arm] for r in rates.values()])
    stats = {"n_tasks": len(allp), "mean_pass": float(allp.mean()), "frac_zero": float((allp == 0).mean()),
             "frac_one": float((allp == 1).mean()), "frac_band_20_80": float(((allp >= 0.2) & (allp <= 0.8)).mean()),
             "sampling_overall": m["overall"]}
    print("PASSRATE", json.dumps(stats, default=str), flush=True)
    sub_path = f"{a.out}/train_subset.jsonl"
    with open(sub_path, "w") as f:
        f.writelines(json.dumps(t.to_json()) + "\n" for t in sub)
    json.dump(rates, open(f"{a.out}/pass_rates.json", "w"))
    cur = {"raw": curate(sub_path, f"{a.out}/curated_raw"),
           "curated": curate(sub_path, f"{a.out}/curated_{a.arm}", arm=a.arm, pass_rates=rates)}
    json.dump({"stats": stats, "curation": cur}, open(f"{a.out}/summary.json", "w"), indent=1, default=str)
    print("CURATION", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "stage_counts"} for k, v in cur.items()}, default=str))
    # keep the output small: the merged model is rebuilt from the adapter wherever it is needed
    import shutil
    shutil.rmtree(merged, ignore_errors=True)
