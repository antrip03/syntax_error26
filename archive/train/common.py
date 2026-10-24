"""Config loading, run folders and provenance shared by curate/sft/grpo/eval."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def load_config(path: str, overrides: list[str] | None = None) -> dict:
    """YAML config plus `key.sub=value` overrides (values parsed as YAML)."""
    cfg = yaml.safe_load(Path(path).read_text()) or {}
    for o in overrides or []:
        key, _, val = o.partition("=")
        node = cfg
        *parents, leaf = key.split(".")
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = yaml.safe_load(val)
    return cfg


def git_hash() -> str:
    try:
        h = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet"]).returncode != 0
        return h + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def run_dir(run_id: str, cfg: dict, root: str | None = None) -> Path:
    """artifacts/runs/<run_id>/ with config.yaml, git_hash and the interfaces mode recorded."""
    from archive.interfaces import MODE
    d = Path(root or REPO / "artifacts" / "runs") / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(yaml.safe_dump({**cfg, "_interfaces_mode": MODE, "_argv": sys.argv}, sort_keys=False))
    (d / "git_hash").write_text(git_hash() + "\n")
    return d


class JsonlLog:
    def __init__(self, path: Path):
        self.f = open(path, "a", buffering=1)

    def __call__(self, **row):
        row = {"time": round(time.time(), 2), **row}
        self.f.write(json.dumps(row, default=str) + "\n")
        print(json.dumps(row, default=str), flush=True)
