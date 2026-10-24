"""Extra SFT-only tasks (more unique examples beat more epochs). Real windows come from TRAIN blocks only; synthetic seeds are
in a range disjoint from every split. Writes artifacts/tasks/sft_extra.jsonl and asserts no series overlaps val/test_*."""
import hashlib
import json

import yaml

from finseries.data import loaders, splits, synthetic
from finseries.data.splits import Window
from finseries.tasks import generate as G

if __name__ == "__main__":
    cfg = yaml.safe_load(open("configs/data.yaml"))
    W = splits.build_windows(cfg, loaders.load_real(cfg["real"]))
    wins = [w for w in W["train"] if w.source == "real"]
    for i in range(3000):
        n = 60 + (i * 7) % 21
        wins.append(Window("train", "synthetic", "synth", 600000 + i, synthetic.generate(n, 600000 + i).r.tolist()))
    ts = G.generate_split(wins, 9000, "sft", 999, budget={"completion": 500, "prompt": 640})
    held = set()
    for sp in ("val", "test_id", "test_len", "test_period", "test_adv"):
        held |= {hashlib.sha1(json.dumps(t.series).encode()).hexdigest() for t in G.read_jsonl(f"artifacts/tasks/{sp}.jsonl")}
    leaked = [t.id for t in ts if hashlib.sha1(json.dumps(t.series).encode()).hexdigest() in held]
    assert not leaked, f"{len(leaked)} leaked series"
    G.write_jsonl(ts, "artifacts/tasks/sft_extra.jsonl")
    print(len(ts), "tasks;", sum(t.source == "synthetic" for t in ts), "synthetic")
