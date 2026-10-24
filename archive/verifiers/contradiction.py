"""Do two claims contradict each other? Computed from facts only, never judged by a model (brief sections 4.4, 9).

Location facts:
    at(p, place, t)          p was at place at t
    saw(o, p, place, t)      p (the person seen) was at place at t
    empty(place, t)          nobody was at place at t
Two location facts clash when they are at the same day and slot and either put the same person in two different
places, or put someone at a place another fact says was empty.

Door facts:
    door(place, open|locked, t)
Two door facts clash when they are about the same place at the same day and slot and give different states.

Claims are linked through `ClaimResult.facts`, which the checker fills for supported claims. For a hearsay claim
those are the heard item's source facts, so a hearsay claim traces back to the original fact.
"""
from __future__ import annotations

from typing import NamedTuple

from archive.schemas import Case, ClaimResult, Fact


class Location(NamedTuple):
    person: str | None  # None = nobody (an `empty` fact)
    place: str
    day: int
    slot: str


def locations(fact: Fact) -> list[Location]:
    """Where a fact puts people. Facts of other relations (argued, owes, ...) place nobody."""
    if fact.t is None:
        return []
    if fact.rel == "at":
        return [Location(fact.args[0], fact.args[1], fact.t.day, fact.t.slot)]
    if fact.rel == "saw":
        return [Location(fact.args[1], fact.args[2], fact.t.day, fact.t.slot)]
    if fact.rel == "empty":
        return [Location(None, fact.args[0], fact.t.day, fact.t.slot)]
    return []


def door_state(fact: Fact) -> tuple[str, str, int, str] | None:
    """(place, state, day, slot) for a door fact, else None."""
    if fact.rel != "door" or fact.t is None:
        return None
    return fact.args[0], fact.args[1], fact.t.day, fact.t.slot


def _name(case: Case, pid: str) -> str:
    names = case.lexicon.people.get(pid)
    return names[0] if names else pid


def facts_clash(case: Case, fa: Fact, fb: Fact) -> str | None:
    """Reason string if the two facts contradict, else None."""
    for a in locations(fa):
        for b in locations(fb):
            if (a.day, a.slot) != (b.day, b.slot):
                continue
            when = f"day {a.day} {a.slot}"
            if a.person and b.person and a.person == b.person and a.place != b.place:
                return f"{_name(case, a.person)}: {a.place} vs {b.place}, {when}"
            for x, y in ((a, b), (b, a)):
                if x.person and y.person is None and x.place == y.place:
                    return f"{_name(case, x.person)} at the {x.place}, but the {x.place} was empty, {when}"
    da, db = door_state(fa), door_state(fb)
    if da and db and da[0] == db[0] and da[2:] == db[2:] and da[1] != db[1]:
        return f"{da[0]} door: {da[1]} vs {db[1]}, day {da[2]} {da[3]}"
    return None


def _checkable(fact: Fact) -> bool:
    return bool(locations(fact)) or door_state(fact) is not None


def confirm(case: Case, claim_a: ClaimResult | dict, claim_b: ClaimResult | dict) -> tuple[bool, str]:
    """(confirmed, reason) for a link between two claims. Only supported (green) claims can be linked."""
    a, b = (c if isinstance(c, ClaimResult) else ClaimResult.model_validate(c) for c in (claim_a, claim_b))
    if a.status != "supported" or b.status != "supported":
        return False, "only supported claims can be linked"
    known = {f.id: f for f in case.facts}
    fa = [known[f] for f in a.facts if f in known]
    fb = [known[f] for f in b.facts if f in known]
    if not any(_checkable(f) for f in fa) or not any(_checkable(f) for f in fb):
        return False, "no contradiction: one of the claims says nothing about where anyone was or a door"
    for x in fa:
        for y in fb:
            if x.id != y.id and (reason := facts_clash(case, x, y)):
                return True, reason
    return False, "no contradiction: these claims can both be true"
