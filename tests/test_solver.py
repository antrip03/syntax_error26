"""Solver (archive/world/solver.py): fair cases pass; each kind of broken case fails with the right rule."""
import json
from pathlib import Path

import pytest

from archive.schemas import Case
from archive.world import casegen
from archive.world.casegen import generate_case
from archive.world.solver import solve

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"


def elsie() -> dict:
    return json.loads(FIXTURE.read_text())


def doc(raw, did):
    return next(d for d in raw["documents"] if d["id"] == did)


def rules(raw) -> set[str]:
    """Which pass rules a (possibly broken) case fails, e.g. {"a", "e"}."""
    return {f[1] for f in solve(Case.model_validate(raw)).failures}


# --- fair cases pass -------------------------------------------------------------------------------------------

def test_elsie_fixture_passes():
    r = solve(Case.model_validate(elsie()))
    assert r.passed, r.failures
    assert r.killer == "tom" and r.witnesses["tom"] == {"gus", "nell"}
    assert {frozenset(p) for p in r.contradictions} == {frozenset(("F2", "F4")), frozenset(("F2", "F6"))}


@pytest.mark.parametrize("mode", ["easy", "hard"])
@pytest.mark.parametrize("seed", range(100))
def test_generated_cases_pass(mode, seed):
    case = generate_case(seed, mode)
    r = solve(case)
    assert r.passed, r.failures
    assert r.killer == case.killer
    assert len(r.witnesses[case.killer]) == len(casegen.PRESETS[mode]["witnesses"])
    for v in case.villagers:  # rule (d), seen from the outside
        assert solve(case, [v.id]).killer is None


# --- broken cases fail, each with the rule it breaks ------------------------------------------------------------

def test_one_witness_is_not_enough():
    raw = elsie()
    doc(raw, "D3")["sentences"] = []                  # Nell's empty-mill line is gone
    assert rules(raw) == {"a", "f"}


def test_true_facts_that_clash_are_caught():
    raw = elsie()
    raw["facts"].append({"id": "F13", "rel": "saw", "args": ["bram", "mara", "inn"], "t": {"day": 2, "slot": "night"},
                         "truth": True})              # Ivy has Mara at the smithy then
    doc(raw, "D6")["sentences"].append({"id": "D6.S2", "facts": ["F13"], "text": "Day 2, night. I saw Mara at the inn."})
    assert rules(raw) == {"a", "e", "f"}             # Mara now has 2 witnesses too


def test_two_lines_from_one_witness_count_once():
    raw = elsie()
    nell_line = doc(raw, "D3")["sentences"].pop()
    doc(raw, "D2")["sentences"].append({**nell_line, "id": "D2.S2"})  # Gus holds both contradicting lines
    assert rules(raw) == {"a"}                        # Tom is contradicted by one witness only


def test_one_villager_plus_the_evidence_must_not_solve_it():
    raw = elsie()
    raw["facts"].append({"id": "F13", "rel": "at", "args": ["tom", "mill"], "t": {"day": 2, "slot": "night"},
                         "truth": False})
    e1 = doc(raw, "E1")
    e1["forged"] = True
    e1["sentences"].append({"id": "E1.S2", "facts": ["F13"], "text": "Day 2, night. Tom said he would be at the mill."})
    # Gus's log + Elsie's public diary already contradict Tom from 2 sources: the case is too easy.
    assert rules(raw) == {"d", "f"}


def test_missing_motive():
    raw = elsie()
    next(f for f in raw["facts"] if f["id"] == "F11")["args"] = ["mara", "elsie", "40 silver"]
    assert rules(raw) == {"c"}


def test_evidence_pointing_at_the_wrong_person():
    raw = elsie()
    raw["killer"] = raw["solution"]["killer"] = "mara"
    assert {"b", "c"} <= rules(raw)


def test_withheld_documents_are_never_read():
    raw = elsie()
    doc(raw, "D7")["withheld"] = False               # Tom's true notes become visible
    assert "e" in rules(raw)                          # his true guildhall line clashes with Gus's true sighting


def test_solution_must_list_the_contradictions_found():
    raw = elsie()
    raw["solution"]["contradictions"] = [["F2", "F4"]]
    assert rules(raw) == {"f"}


@pytest.mark.parametrize("mode", ["easy", "hard"])
def test_breaking_generated_cases_is_caught(mode):
    """On generated cases too: drop every witness line but one, and the case must fail."""
    for seed in range(20):
        raw = generate_case(seed, mode).model_dump(by_alias=True)
        witness_facts = [b for _, b in raw["solution"]["contradictions"]][1:]
        for d in raw["documents"]:
            d["sentences"] = [s for s in d["sentences"] if not set(s["facts"]) & set(witness_facts)]
        assert "a" in rules(raw)


# --- generate_case retries on solver failure ------------------------------------------------------------------

def test_generate_case_retries_then_gives_up(monkeypatch):
    real, calls = casegen.solve, []

    def fail_twice(case):
        calls.append(case.case_id)
        r = real(case)
        if len(calls) <= 2:
            r.failures = ["(x) forced failure"]
        return r

    monkeypatch.setattr(casegen, "solve", fail_twice)
    case = generate_case(5, "easy")
    assert len(calls) == 3 and case.model_dump() != casegen._build_case(5, "easy", "village", 0).model_dump()

    monkeypatch.setattr(casegen, "solve", lambda c: type(real(c))(killer=None, contradictions=[], failures=["(x)"]))
    with pytest.raises(RuntimeError):
        generate_case(5, "easy")
