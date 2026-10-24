"""The single place P1's code touches P2's modules.

Rows on disk are JSONL dicts (tasks_*.jsonl, cases_*.jsonl as written by P2's generator). This module turns
them into P2's objects and calls P2's functions. `MODE` is recorded in every run's config and manifest:
  "p2"       all of P2's modules import (schemas, prompt, gold, checker, rewards, metrics)
  "p2-core"  schemas, prompt, gold and checker are P2's; reward() and metrics() raise until P2 pushes
             rewards/combine.py and eval/metrics.py (enough for prepare-only data and SFT, not for curation/GRPO/eval)
  "devstub"  P2's core is missing: toy stand-in (archive.devstub) for dry runs; ARCHIVE_DEVSTUB=1 forces it
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _load_core():
    from archive import schemas
    from archive.tasks.gold import gold_reply
    from archive.tasks.prompt import build_messages
    from archive.verifiers.checker import check, context_for
    return schemas, build_messages, gold_reply, check, context_for


def _load_scoring():
    from archive.eval.metrics import compute
    from archive.rewards.combine import reward
    return reward, compute


def _missing(name):
    def fn(*a, **k):
        raise RuntimeError(f"interfaces MODE={MODE}: P2's {name} is not in the repo yet")
    return fn


_core = _scoring = None
if os.environ.get("ARCHIVE_DEVSTUB") != "1":
    try:
        _core = _load_core()
        try:
            _scoring = _load_scoring()
        except ImportError:
            _scoring = None
    except ImportError:
        _core = None

_p2 = _core is not None
MODE = "devstub" if not _p2 else "p2" if _scoring else "p2-core"

if _p2:
    _schemas, _build_messages, _gold_reply, _check, _context_for = _core
    _reward, _compute = _scoring or (_missing("rewards/combine.py"), _missing("eval/metrics.py"))
else:
    from archive.devstub import world as _w
    _build_messages, _gold_reply, _check, _context_for, _reward, _compute = (
        _w.build_messages, _w.gold_reply, _w.check, _w.context_for, _w.reward, _w.compute)


def require(*modes: str) -> None:
    """Stop a run that would produce stand-in numbers by mistake."""
    if MODE not in modes:
        raise SystemExit(f"interfaces MODE={MODE}, this step needs {'|'.join(modes)} "
                         "(set ARCHIVE_DEVSTUB=1 only for a deliberate dry run)")


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
    if _p2 and row.get("speaker"):  # gossip-style rows: another villager asks
        return _build_messages(case, row["villager"], row["question"], heard=_heard(t) or [], speaker=row["speaker"])
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
