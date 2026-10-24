"""Write toy data in P2's on-disk layout: <out>/{cases,tasks}_{split}.jsonl + manifest.json.

python -m archive.devstub.generate --out /tmp/archive_p1/data_devstub
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path

from archive.devstub.world import generate_case, generate_tasks
from archive.interfaces import write_jsonl

SPLITS = {"train": (0, 30), "val": (1000, 5), "test_id": (2000, 10), "test_adv": (3000, 5), "test_game": (4000, 5)}

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args()
out = Path(args.out)
manifest = {}
for split, (base, n) in SPLITS.items():
    rng = random.Random(base)
    cases = [generate_case(base + i) for i in range(n)]
    tasks = [t for c in cases for t in generate_tasks(c, split, rng)]
    for i, t in enumerate(tasks):
        t["task_id"] = f"t_{split}_{i:05d}"
    write_jsonl(out / f"cases_{split}.jsonl", cases)
    write_jsonl(out / f"tasks_{split}.jsonl", tasks)
    manifest[split] = {"cases": len(cases), "tasks": len(tasks), "by_type": Counter(t["type"] for t in tasks)}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest))
