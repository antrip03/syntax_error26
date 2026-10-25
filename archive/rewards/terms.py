"""Reward terms (brief 10.3), one pure function each: (reply, task, ctx, chk=None) -> float.

`ctx` is the villager's checker context and `chk` its CheckResult for the reply (computed when not given, so each
term can be called on its own; combine.py checks once and passes it to all of them).

correct  1 if the gold facts are among the reply's supported facts, or a correct abstain; 0 if cut off
support  share of supported claims; for an abstain: 1 if it was right to abstain, else 0
cite     share of cited ids whose line holds a gold fact (or that the gold cites); for an abstain: 1 if right, else 0
abstain  +1 correct abstain, -1 abstain on an answerable task, -1 any claim on a task that should be abstained
fmt      1 if the reply parsed
length   -0.2 * min(1, max(0, tokens - 200) / 56)

The abstain cases for support and cite were agreed with the team: a correct abstain scores like a perfect answer
(so P1's is_correct counts it), a wrong abstain scores 0 (explainer answer D = -0.05).
"""
from __future__ import annotations

import re

from archive.schemas import CheckResult, Task
from archive.verifiers.checker import VillagerContext, check

_PIECE = re.compile(r"[A-Za-z]+|\d|[^\sA-Za-z\d]")

def estimate_tokens(text: str) -> int:
    """Qwen3 token count without loading the tokenizer: words, digits and symbols each count one. Calibrated in
    tests/test_rewards.py to within about 10% on 180-280-token replies, the range where the length term acts."""
    return len(_PIECE.findall(text))

def _chk(reply: str, ctx: VillagerContext, chk: CheckResult | None) -> CheckResult:
    return chk if chk is not None else check(reply, ctx)

def gold_facts(task: Task) -> set[str]:
    return {f for c in task.gold.claims for f in c.facts}

def gold_cite_ids(task: Task) -> set[str]:
    """Ids the gold reply cites. A heard lie has no facts, but citing it with attribution is right
    (hearsay_conflict), so these count as relevant even without a gold fact behind them."""
    return {i for c in task.gold.claims for i in c.cites}

def supported_facts(chk) -> set[str]:
    """Facts behind the green claims (CheckResult or its dict)."""
    claims = chk.claims if hasattr(chk, "claims") else chk["claims"]
    get = (lambda c, k: getattr(c, k)) if hasattr(chk, "claims") else (lambda c, k: c[k])
    return {f for c in claims if get(c, "status") == "supported" for f in get(c, "facts")}

def truncated(reply: str) -> bool:
    """Cut off before </answer>: an answer was opened but never closed."""
    t = (reply or "").strip()
    return "<answer>" in t and not t.endswith("</answer>")

def is_correct(reply: str, task: Task, chk) -> bool:
    """The `correct` decision, from a CheckResult or its dict (metrics.py uses the dict form)."""
    abstained = chk.abstained if hasattr(chk, "abstained") else chk["abstained"]
    if truncated(reply):
        return False
    if task.gold.abstain:
        return bool(abstained)
    want = gold_facts(task)
    return bool(want) and want <= supported_facts(chk)

def correct(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None) -> float:
    return float(is_correct(reply, task, _chk(reply, ctx, chk)))

def support(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None) -> float:
    r = _chk(reply, ctx, chk)
    if r.abstained:
        return float(task.gold.abstain)
    return r.support_rate or 0.0

def cite(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None) -> float:
    r = _chk(reply, ctx, chk)
    if r.abstained:
        return float(task.gold.abstain)
    cited = [i for c in r.claims for i in c.cites]
    if not cited:
        return 0.0
    want, gold_cites = gold_facts(task), gold_cite_ids(task)
    return sum(bool(set(ctx.facts.get(i, [])) & want) or i in gold_cites for i in cited) / len(cited)

def abstain(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None) -> float:
    r = _chk(reply, ctx, chk)
    if task.gold.abstain:
        return 1.0 if r.abstained else (-1.0 if r.claims else 0.0)
    return -1.0 if r.abstained else 0.0

def fmt(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None) -> float:
    return float(_chk(reply, ctx, chk).parsed)

def length(reply: str, task: Task, ctx: VillagerContext, chk: CheckResult | None = None,
           n_tokens: int | None = None) -> float:
    tokens = n_tokens if n_tokens is not None else estimate_tokens(reply or "")
    return -0.2 * min(1.0, max(0.0, tokens - 200) / 56)
