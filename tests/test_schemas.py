"""Schemas + the hand-written Elsie fixture (brief sections 4.3 and 6)."""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archive.schemas import RELATIONS, Case, CheckResult, HeardItem, Task

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
PERSON_ROLES = {"person", "observer", "other", "debtor", "creditor"}

@pytest.fixture
def raw():
    return json.loads(FIXTURE.read_text())

@pytest.fixture
def case(raw):
    return Case.model_validate(raw)

def test_fixture_loads_and_roundtrips(case):
    assert Case.model_validate_json(case.model_dump_json()) == case
    assert [v.id for v in case.villagers] == ["tom", "gus", "nell", "mara", "ivy", "bram"]

def test_killer_has_forged_alibi_and_withheld_notes(case):
    alibi = case.fact("F2")
    assert (alibi.rel, alibi.args, alibi.truth) == ("at", ["tom", "mill"], False)
    assert case.doc("D1").forged and case.doc("D1").owner == "tom"
    real = case.doc("D7")
    assert real.withheld and real.owner == "tom" and real.id in case.villager("tom").docs
    assert case.fact("F3").args == ["tom", case.scene] and case.fact("F3").t == case.murder_time
    assert {d.owner for d in case.documents if d.forged or d.withheld} == {"tom"}

def test_solution_contradictions_are_about_the_killer_at_murder_time(case):
    for a, b in case.solution.contradictions:
        fa, fb = case.fact(a), case.fact(b)
        assert fa.t == fb.t == case.murder_time
        assert not (fa.truth and fb.truth), "every contradiction involves a forged fact (brief 5.4e)"
    owners = {d.owner for d in case.documents for s in d.sentences
              for pair in case.solution.contradictions for f in pair if f in s.facts and d.owner != "tom"}
    assert owners == {"gus", "nell"}

def test_motive_links_killer_and_victim(case):
    m = case.fact(case.solution.motive)
    assert m.rel == "owes" and m.args[:2] == [case.killer, case.victim]
    assert any(m.id in s.facts for e in case.evidence_docs for s in case.doc(e).sentences)

def test_red_herring_mara_is_cleared_by_ivy(case):
    assert case.fact("F7").rel == "argued" and case.fact("F7").args == ["mara", case.victim]
    alibi = [f for f in case.facts if f.rel == "at" and f.args[0] == "mara" and f.t == case.murder_time]
    assert alibi and alibi[0].truth and alibi[0].args[1] != case.scene
    assert any(alibi[0].id in s.facts for s in case.doc("D5").sentences)

def test_people_in_facts_are_known_names(case):
    for f in case.facts:
        for role, arg in zip(RELATIONS[f.rel], f.args):
            if role in PERSON_ROLES:
                assert arg in case.lexicon.people, (f.id, arg)
            elif role == "place":
                assert arg in case.lexicon.places, (f.id, arg)

@pytest.mark.parametrize("breakage", [
    lambda r: r["documents"][0]["sentences"][0].update(facts=["F99"]),
    lambda r: r["documents"][0].update(forged=False),
    lambda r: r["documents"][1]["sentences"][0].update(id="D1.S9"),
    lambda r: r["facts"][0].update(args=["tom"]),
    lambda r: r["facts"][10].update(t={"day": 2, "slot": "noon"}),
    lambda r: r["facts"][0].update(t={"day": 2, "slot": "midnight"}),
    lambda r: r["villagers"][1].update(docs=["D42"]),
    lambda r: r.update(killer="gus"),
    lambda r: r["solution"].update(motive="F99"),
    lambda r: r["lexicon"]["people"].pop("elsie"),
    lambda r: r.update(surprise=1),
])
def test_broken_cases_are_rejected(raw, breakage):
    bad = copy.deepcopy(raw)
    breakage(bad)
    with pytest.raises(ValidationError):
        Case.model_validate(bad)

def test_heard_item_uses_from_on_disk():
    h = HeardItem.model_validate({"id": "H1", "from": "tom", "day": 2, "text": "I was at the mill all night.",
                                  "facts": ["F2"]})
    assert h.from_ == "tom"
    assert h.model_dump()["from"] == "tom" and json.loads(h.model_dump_json())["from"] == "tom"

def test_task_accepts_pipeline_rows_and_keeps_extra_keys():
    row = {"task_id": "t1", "case_id": "c_elsie", "villager": "tom", "type": "answerable_1hop", "split": "train",
           "question": "When did you shut the mill on day 2?",
           "gold": {"abstain": False, "claims": [{"text": "I shut the mill at dusk on day 2.", "cites": ["D1.S1"],
                                                  "facts": ["F1"]}]},
           "heard": [{"id": "H1", "from": "gus", "day": 2, "text": "Saw Tom by the chapel.", "facts": ["F4"]}],
           "messages": [{"role": "user", "content": "Player: hi"}], "gold_reply": "<answer>...</answer>"}
    t = Task.model_validate(row)
    assert t.heard[0].from_ == "gus" and t.model_dump()["gold_reply"] == row["gold_reply"]
    with pytest.raises(ValidationError):
        Task.model_validate({**row, "type": "made_up_type"})

def test_check_result_dumps_to_plain_dict():
    r = CheckResult(parsed=True, support_rate=0.5, claims=[
        {"text": "I shut the mill at dusk.", "cites": ["D1.S1"], "status": "supported", "reason": "ok", "facts": ["F1"]},
        {"text": "Then I went to the inn.", "cites": ["D1.S1"], "status": "unsupported", "reason": "entity_mismatch"}])
    d = r.model_dump()
    assert d["claims"][1]["facts"] == [] and d["abstained"] is False
