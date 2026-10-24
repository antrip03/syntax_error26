"""M3 (Kaggle driver): serve the base model with SGLang on GPU 1, run R0 baselines on val for every scaffold,
sample pass rates on a train subset, then run CuratorKIT curation (raw vs curated sets).
usage: python scripts/m3_baseline.py --model Qwen/Qwen2.5-1.5B-Instruct --tasks /kaggle/input/finseries-tasks"""
import argparse
import glob
import json
import os
import subprocess
import time

import numpy as np

from finseries.adapters.curatorkit_adapter import curate
from finseries.adapters.sglang_client import SGLangClient
from finseries.eval import run_eval
from finseries.serve import sglang_server
from finseries.tasks.generate import read_jsonl

ARMS = ["flat", "chunk", "event"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--tasks", default="/kaggle/input/finseries-tasks")
    ap.add_argument("--out", default="/kaggle/working/m3")
    ap.add_argument("--val-limit", type=int, default=400)
    ap.add_argument("--passrate-tasks", type=int, default=300)
    ap.add_argument("--passrate-n", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    hits = glob.glob("/kaggle/input/**/val.jsonl", recursive=True)   # mount path differs between Kaggle UI versions
    if hits:
        a.tasks = os.path.dirname(hits[0])
    print("tasks dir:", a.tasks, flush=True)
    assert os.path.exists(f"{a.tasks}/val.jsonl"), f"no val.jsonl under /kaggle/input: {os.listdir('/kaggle/input')}"
    summary = {"model": a.model}
    t0 = time.time()
    sglang_server.install()
    print(f"sglang installed {time.time() - t0:.0f}s", flush=True)
    val = read_jsonl(f"{a.tasks}/val.jsonl")[:a.val_limit]
    train = read_jsonl(f"{a.tasks}/train.jsonl")
    sub = [train[i] for i in np.random.default_rng(0).permutation(len(train))[:a.passrate_tasks]]
    with sglang_server.server(a.model) as url:
        client = SGLangClient(url, concurrency=96)
        for arm in ARMS:
            t1 = time.time()
            _, m = run_eval.run(val, arm, client, f"{a.out}/R0_{arm}_val", n=1, temperature=0.0, max_tokens=1024)
            summary[f"R0_{arm}"] = m["overall"]
            print(f"R0 {arm}: acc={m['overall']['accuracy']:.3f} parse={m['overall']['parse_rate']:.3f} "
                  f"stepvalid={m['overall']['step_validity']:.3f} tok={m['overall']['mean_tokens']:.0f} ({time.time() - t1:.0f}s)", flush=True)
        rates = {}
        for arm in ARMS:
            t1 = time.time()
            rows, _ = run_eval.run(sub, arm, client, f"{a.out}/passrate_{arm}_train", n=a.passrate_n, temperature=0.7, max_tokens=768, seed=11)
            by = {}
            for r in rows:
                by.setdefault(r["id"], []).append(r["correct"])
            for i, v in by.items():
                rates.setdefault(i, {})[arm] = float(np.mean(v))
            allp = [float(np.mean(v)) for v in by.values()]
            summary[f"passrate_{arm}"] = {"mean": float(np.mean(allp)), "frac_zero": float(np.mean([p == 0 for p in allp])),
                                          "frac_band_20_80": float(np.mean([0.2 <= p <= 0.8 for p in allp]))}
            print(f"passrate {arm}: {summary[f'passrate_{arm}']} ({time.time() - t1:.0f}s)", flush=True)
    json.dump(rates, open(f"{a.out}/pass_rates.json", "w"))
    sub_path = f"{a.out}/train_subset.jsonl"
    with open(sub_path, "w") as f:
        f.writelines(json.dumps(t.to_json()) + "\n" for t in sub)
    summary["curation"] = {"raw": curate(sub_path, f"{a.out}/curated_raw")}
    for arm in ARMS:
        summary["curation"][arm] = curate(sub_path, f"{a.out}/curated_{arm}", arm=arm, pass_rates=rates)
    json.dump(summary, open(f"{a.out}/summary.json", "w"), indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str))
