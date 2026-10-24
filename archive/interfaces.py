"""The single place P1's code touches P2's modules.

Rows on disk are JSONL dicts (tasks_*.jsonl, cases_*.jsonl as written by P2's generator). This module turns
them into P2's objects and calls P2's functions. Until all of P2's modules import, it falls back to
archive.devstub (toy data) so the pipeline can be dry-run; set ARCHIVE_DEVSTUB=1 to force that.
`MODE` is recorded in every run's config so stand-in numbers are never mistaken for real ones.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _load_p2():
    from archive import schemas
    from archive.eval.metrics import compute
    from archive.rewards.combine import reward
    from archive.tasks.gold import gold_reply
    from archive.tasks.prompt import build_messages
    from archive.verifiers.checker import check, context_for
    return schemas, build_messages, gold_reply, check, context_for, reward, compute


if os.environ.get("ARCHIVE_DEVSTUB") == "1":
    _p2 = None
else:
    try:
        _p2 = _load_p2()
    except ImportError:
        _p2 = None

MODE = "p2" if _p2 else "devstub"

if _p2:
    _schemas, _build_messages, _gold_reply, _check, _context_for, _reward, _compute = _p2
else:
    from archive.devstub import world as _w
    _build_messages, _gold_reply, _check, _context_for, _reward, _compute = (
        _w.build_messages, _w.gold_reply, _w.check, _w.context_for, _w.reward, _w.compute)


def _dump(x):
    return x.model_dump() if hasattr(x, "model_dump") else x


def read_jsonl(path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def load_cases(path) -> dict:
    rows = read_jsonl(path)
    if _p2:
        return {r["case_id"]: _schemas.Case.model_validate(r) for r in rows}
    return {r["case_id"]: r for r in rows}


def task_obj(row: dict):
    return _schemas.Task.model_validate(row) if _p2 else row


def _heard(t):
    return getattr(t, "heard", None) if _p2 else t.get("heard", [])


def messages(row: dict, cases: dict) -> list[dict]:
    t = task_obj(row)
    case = cases[row["case_id"]]
    return _build_messages(case, row["villager"], row["question"], heard=_heard(t) or [])


def gold(row: dict) -> str:
    return _gold_reply(task_obj(row))


def check(reply: str, row: dict, cases: dict) -> dict:
    t = task_obj(row)
    ctx = _context_for(cases[row["case_id"]], row["villager"], heard=_heard(t) or [])
    return _dump(_check(reply, ctx))


def reward(reply: str, row: dict, cases: dict, bundle: str = "full") -> dict:
    return dict(_reward(reply, task_obj(row), cases[row["case_id"]], bundle=bundle))


def metrics(records: list[dict]) -> dict:
    return _compute(records)


def is_correct(parts: dict) -> bool:
    """A sampled reply 'passes' (for curation pass rates): correct, well-formed and fully supported (or a correct abstain)."""
    return parts.get("correct", 0) >= 1 and parts.get("fmt", 0) >= 1 and parts.get("support", 0) >= 1
