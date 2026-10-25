"""The GRPO reward (brief 10.3): all terms for one reply, and the weighted total.

    R3 (bundle="full")    = 0.35 correct + 0.30 support + 0.10 cite + 0.15 abstain + 0.10 fmt + length
    R2 (bundle="outcome") = 0.70 correct + 0.20 abstain + 0.10 fmt

P1 calls reward(reply, task, case) once per completion (archive/interfaces.py) and logs every part; its configs hold
the same weights. The reply is checked once and the result shared by all terms.
"""
from __future__ import annotations

from archive.rewards import terms
from archive.schemas import Case, Task
from archive.verifiers.checker import check, context_for

WEIGHTS = {
    "full": {"correct": 0.35, "support": 0.30, "cite": 0.10, "abstain": 0.15, "fmt": 0.10, "length": 1.0},
    "outcome": {"correct": 0.70, "abstain": 0.20, "fmt": 0.10},
}
PARTS = ["correct", "support", "cite", "abstain", "fmt", "length"]

def reward(reply: str, task, case: Case, bundle: str = "full", n_tokens: int | None = None) -> dict:
    """{total, correct, support, cite, abstain, fmt, length, abstained} for one reply. `task` is a Task or a task
    row dict; `n_tokens` is the real completion token count when the caller has it (else estimated)."""
    if bundle not in WEIGHTS:
        raise ValueError(f"bundle must be one of {sorted(WEIGHTS)}")
    task = task if isinstance(task, Task) else Task.model_validate(task)
    reply = reply or ""
    ctx = context_for(case, task.villager, heard=task.heard)
    chk = check(reply, ctx)
    parts = {name: getattr(terms, name)(reply, task, ctx, chk) for name in PARTS if name != "length"}
    parts["length"] = terms.length(reply, task, ctx, chk, n_tokens=n_tokens)
    parts["total"] = sum(w * parts[name] for name, w in WEIGHTS[bundle].items())
    parts["abstained"] = float(chk.abstained)
    return parts
