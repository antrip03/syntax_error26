"""Solver (brief 5.4): reads every visible document like a perfect player and judges whether a case is fair.

Contradictions are found with the game's own rule (contradiction.facts_clash), so "solvable by the solver" means
"solvable on the contradiction board". Withheld documents are never read, just as no player can see them.

A case passes only if all of these hold:
(a) exactly one villager has contradictions from at least 2 different witnesses (the documents' owners);
(b) that villager is the killer;
(c) a visible motive fact (owes / argued) links killer and victim;
(d) no single villager's documents (plus the public evidence) are enough to name anyone;
(e) every contradiction involves a false (forged) fact: no accidental true-vs-true clash;
(f) the contradictions found are exactly the case's listed solution.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from archive.schemas import Case, Fact
from archive.verifiers.contradiction import facts_clash, locations

MOTIVE_RELATIONS = {"owes", "argued"}


@dataclass
class SolveResult:
    killer: str | None                                   # the single villager with 2+ witnesses, if exactly one
    contradictions: list[tuple[str, str]]                # clashing visible fact pairs
    witnesses: dict[str, set[str]] = field(default_factory=dict)  # suspect -> owners of contradicting documents
    failures: list[str] = field(default_factory=list)    # broken pass rules; filled for a full solve only

    @property
    def passed(self) -> bool:
        return not self.failures


def _visible(case: Case, villager_ids) -> dict[str, tuple[Fact, str]]:
    """fact id -> (fact, owner of the document it is written in), over the chosen villagers' visible documents
    and the evidence documents."""
    docs = set(case.evidence_docs)
    for v in case.villagers:
        if villager_ids is None or v.id in villager_ids:
            docs |= set(v.docs)
    out = {}
    for d in case.documents:
        if d.id in docs and not d.withheld:
            for s in d.sentences:
                for fid in s.facts:
                    out[fid] = (case.fact(fid), d.owner)
    return out


def _suspects(fa: Fact, fb: Fact) -> set[str]:
    """Who a clash is about: the person in two places, or the person at a place said to be empty."""
    pa = {loc.person for loc in locations(fa) if loc.person}
    pb = {loc.person for loc in locations(fb) if loc.person}
    return (pa & pb) if pa and pb else (pa | pb)


def solve(case: Case, villager_ids=None) -> SolveResult:
    """Read the documents of `villager_ids` (default: every villager) plus the evidence and name the killer.
    With the default, also checks every pass rule and lists the broken ones in `failures`."""
    seen = _visible(case, villager_ids)
    pairs, witnesses = [], {}
    for (ia, (fa, oa)), (ib, (fb, ob)) in itertools.combinations(sorted(seen.items()), 2):
        if not facts_clash(case, fa, fb):
            continue
        pairs.append((ia, ib))
        for p in _suspects(fa, fb):
            witnesses.setdefault(p, set()).update({oa, ob} - {p})
    villagers = {v.id for v in case.villagers}
    strong = sorted(p for p, ws in witnesses.items() if len(ws) >= 2 and p in villagers)
    result = SolveResult(killer=strong[0] if len(strong) == 1 else None, contradictions=pairs, witnesses=witnesses)
    if villager_ids is None:
        result.failures = _failures(case, result, seen, strong)
    return result


def _failures(case: Case, r: SolveResult, seen: dict, strong: list[str]) -> list[str]:
    fails = []
    if len(strong) != 1:
        fails.append(f"(a) {len(strong)} villagers have contradictions from 2+ witnesses: {strong}")
    elif r.killer != case.killer:
        fails.append(f"(b) the evidence points at {r.killer}, but the killer is {case.killer}")
    motive = seen.get(case.solution.motive, (None, None))[0]
    if not (motive and motive.rel in MOTIVE_RELATIONS and {case.killer, case.victim} <= set(motive.args[:2])):
        fails.append(f"(c) no visible motive fact links {case.killer} and {case.victim}")
    for v in case.villagers:
        alone = solve(case, [v.id])
        if alone.killer is not None:
            fails.append(f"(d) {v.id}'s documents alone name {alone.killer}")
    for a, b in r.contradictions:
        if case.fact(a).truth and case.fact(b).truth:
            fails.append(f"(e) true facts {a} and {b} clash")
    found = {frozenset(p) for p in r.contradictions}
    listed = {frozenset(p) for p in case.solution.contradictions}
    if found != listed:
        fails.append(f"(f) contradictions found {sorted(map(sorted, found))} != solution "
                     f"{sorted(map(sorted, listed))}")
    return fails
