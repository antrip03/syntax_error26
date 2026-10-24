"""Build all task splits + manifest from configs/data.yaml and configs/tasks.yaml.  python scripts/make_tasks.py"""
import argparse
import hashlib
import json
import os
import subprocess

import yaml

from finseries.data import loaders, splits
from finseries.tasks import generate as G


def series_hash(t):
    return hashlib.sha1(json.dumps(t.series).encode()).hexdigest()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="configs/data.yaml")
    ap.add_argument("--tasks", default="configs/tasks.yaml")
    a = ap.parse_args()
    dcfg, tcfg = yaml.safe_load(open(a.data)), yaml.safe_load(open(a.tasks))
    W = splits.build_windows(dcfg, loaders.load_real(dcfg["real"]))
    assert splits.find_overlaps(W) == [], "window overlap between splits"
    out, by_split = tcfg["out_dir"], {}
    for i, (split, n) in enumerate(tcfg["n_tasks"].items()):
        budget = tcfg["budget"] if split in ("train", "val", "test_id", "test_period", "test_adv") else None
        ts = G.generate_split(W[split], n, split, tcfg["seed"] + i, budget=budget)
        G.write_jsonl(ts, os.path.join(out, f"{split}.jsonl"))
        by_split[split] = ts
        print(split, len(ts))
    owner = {}
    for split, ts in by_split.items():       # identical series must never appear in two splits
        for t in ts:
            h = series_hash(t)
            assert owner.setdefault(h, split) == split, f"series leaked between {owner[h]} and {split}"
    m = G.manifest(by_split)
    try:
        m["git"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        pass
    json.dump(m, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    yaml.safe_dump({"data": dcfg, "tasks": tcfg}, open(os.path.join(out, "config.yaml"), "w"))
