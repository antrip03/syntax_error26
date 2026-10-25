"""Contradiction confirmation (archive/verifiers/contradiction.py) on the Elsie fixture.

Claims are built by hand with the facts the checker will attach to them once it exists.
"""
import json
from pathlib import Path

import pytest

from archive.schemas import Case, ClaimResult, Fact
from archive.verifiers.contradiction import confirm, facts_clash, locations

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"

@pytest.fixture(scope="module")
def case():
    return Case.model_validate(json.loads(FIXTURE.read_text()))

def green(facts, text="claim", cites=("D1.S1",)):
    return ClaimResult(text=text, cites=list(cites), status="supported", reason="ok", facts=facts)

TOM_MILL = green(["F2"], "I stayed at the mill all night on day 2.", ["D1.S2"])
GUS_CHAPEL = green(["F4"], "At midnight on day 2 I saw Tom by the chapel.", ["D2.S1"])
NELL_EMPTY = green(["F6"], "At midnight on day 2 the mill was dark and empty.", ["D3.S1"])
MARA_ARGUED = green(["F7"], "I argued with Elsie at noon on day 2.", ["D4.S1"])
IVY_MARA = green(["F8", "F9"], "Mara was at my smithy from evening to midnight on day 2.", ["D5.S1"])

def test_tom_mill_vs_gus_chapel_confirms(case):
    ok, reason = confirm(case, TOM_MILL, GUS_CHAPEL)
    assert ok and reason == "Tom: mill vs chapel, day 2 night"
    assert confirm(case, GUS_CHAPEL, TOM_MILL)[0]

def test_tom_mill_vs_nell_empty_mill_confirms(case):
    ok, reason = confirm(case, TOM_MILL, NELL_EMPTY)
    assert ok and reason == "Tom at the mill, but the mill was empty, day 2 night"

@pytest.mark.parametrize("a, b", [
    (MARA_ARGUED, IVY_MARA),
    (GUS_CHAPEL, NELL_EMPTY),
    (TOM_MILL, TOM_MILL),
    (green(["F10"]), GUS_CHAPEL),
    (green(["F1"]), GUS_CHAPEL),
])
def test_not_contradictions(case, a, b):
    ok, reason = confirm(case, a, b)
    assert not ok and reason.startswith("no contradiction")

def test_hearsay_claim_traces_back_to_original_fact(case):
    heard = green(["F2"], "Tom told me he stayed at the mill all night on day 2.", ["H1"])
    assert confirm(case, heard, GUS_CHAPEL) == (True, "Tom: mill vs chapel, day 2 night")

def test_red_claims_cannot_be_linked(case):
    red = ClaimResult(text="Tom was at the inn.", cites=["D2.S1"], status="unsupported", reason="entity_mismatch")
    assert confirm(case, red, GUS_CHAPEL) == (False, "only supported claims can be linked")

def test_accepts_plain_dicts(case):
    assert confirm(case, TOM_MILL.model_dump(), GUS_CHAPEL.model_dump())[0]

def test_fixture_solution_pairs_all_clash(case):
    for a, b in case.solution.contradictions:
        assert facts_clash(case, case.fact(a), case.fact(b))

def test_locations(case):
    assert locations(case.fact("F4"))[0].person == "tom"
    assert locations(case.fact("F6"))[0].person is None
    assert locations(case.fact("F11")) == [] and locations(case.fact("F7")) == []
    assert locations(case.fact("F12")) == []

def _with_locked_door(case, slot="night"):
    locked = Fact.model_validate({"id": "F99", "rel": "door", "args": ["guildhall", "locked"],
                                  "t": {"day": 2, "slot": slot}, "truth": False})
    return case.model_copy(update={"facts": [*case.facts, locked]})

def test_door_open_vs_locked_confirms(case):
    c = _with_locked_door(case)
    ok, reason = confirm(c, green(["F12"]), green(["F99"]))
    assert ok and reason == "guildhall door: open vs locked, day 2 night"

def test_door_states_in_different_slots_do_not_clash(case):
    c = _with_locked_door(case, slot="dusk")
    ok, reason = confirm(c, green(["F12"]), green(["F99"]))
    assert not ok and reason.startswith("no contradiction")

def test_door_vs_location_is_not_a_contradiction(case):
    ok, reason = confirm(case, green(["F12"]), GUS_CHAPEL)
    assert not ok and reason == "no contradiction: these claims can both be true"
