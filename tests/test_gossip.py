"""Gossip (archive/npc/gossip.py): scheduling, memory, what gets remembered, clash hints, whole evenings."""
import json
import random
from pathlib import Path

import pytest

from archive.npc import gossip as G
from archive.npc.gossip import MAX_HEARD, Memory, Topic, clash_hints, knows, question_from, remember_reply, \
    run_evening, run_round, schedule, topics
from archive.schemas import Case, HeardItem
from archive.tasks.prompt import build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.parse import ABSTAIN
from archive.world.casegen import generate_case
from tests.npc_fakes import own_line_village

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
CASE = Case.model_validate(json.loads(FIXTURE.read_text()))

@pytest.mark.parametrize("mode", ["easy", "hard"])
@pytest.mark.parametrize("seed", range(30))
def test_schedule_rules(mode, seed):
    case = generate_case(seed, mode)
    plan = schedule(case, random.Random(seed))
    assert len(plan) == G.ROUNDS
    for rnd in plan:
        assert len(rnd) == G.PAIRS
        people = [p for a, r, _ in rnd for p in (a, r)]
        assert len(people) == len(set(people))
        for asker, responder, topic in rnd:
            assert asker != responder
            assert topic.value not in (asker, responder) or topic.kind == "night"
            unknown = [t for t in topics(case) if not knows(case, asker, t)
                       and (t.value not in (asker, responder) or t.kind == "night")]
            if unknown:
                assert not knows(case, asker, topic)

def test_topics_cover_the_brief_kinds():
    kinds = {t.kind for t in topics(CASE)}
    assert kinds == {"victim", "night", "place", "person"}
    assert knows(CASE, "nell", Topic("night", "", "the night of day 2"))
    assert not knows(CASE, "mara", Topic("place", "chapel", "the chapel"))
    assert knows(CASE, "gus", Topic("person", "tom", "Tom"))

def test_schedule_with_few_villagers_and_determinism():
    raw = json.loads(FIXTURE.read_text())
    keep = {"tom", "gus", "nell"}
    raw["villagers"] = [v for v in raw["villagers"] if v["id"] in keep]
    small = Case.model_validate(raw)
    plan = schedule(small, random.Random(0))
    assert all(len(r) == 1 for r in plan)
    assert schedule(CASE, random.Random(5)) == schedule(CASE, random.Random(5))

@pytest.mark.parametrize("raw, expected", [
    ("Where were you on the night of day 2?", "Where were you on the night of day 2?"),
    ('"Did you see Tom near the mill?" I ask.', "Did you see Tom near the mill?"),
    ("<think>hmm</think> Who was at the chapel? And why?", "Who was at the chapel?"),
    ("CLAIM: Tell me about Elsie.", "FALLBACK?"),
    ("", "FALLBACK?"),
    ("?", "FALLBACK?"),
])
def test_question_from(raw, expected):
    assert question_from(raw, "FALLBACK?") == expected

def test_memory_ids_cap_and_pins():
    m = Memory()
    pinned = m.add("nell", "traveller", 2, "Mara poisoned the well.", pin=True)
    for i in range(10):
        m.add("nell", "gus", 2, f"I was at the inn {i}.")
    ids = [h.id for h in m.of("nell")]
    assert len(ids) == MAX_HEARD and pinned.id in ids
    assert ids[-1] == "H11" and len(set(ids)) == len(ids)
    assert m.add("nell", "gus", 2, "   ") is None

def test_remember_reply_kinds():
    m = Memory()
    both = ("<answer>\nCLAIM: I saw Tom by the chapel at midnight on day 2. [D2.S1]\n"
            "CLAIM: I saw Bram stab Elsie at the inn. [D2.S1]\n</answer>")
    stored = remember_reply(CASE, m, "nell", "gus", both, 2)
    assert [h.facts for h in stored] == [["F4"], []]
    assert all(h.from_ == "gus" for h in stored)
    assert remember_reply(CASE, m, "nell", "gus", ABSTAIN, 2) == []
    prose = remember_reply(CASE, m, "nell", "gus", "Tom? <b>Saw him</b> near the chapel [D2.S1].", 2)
    assert len(prose) == 1 and prose[0].facts == [] and "<" not in prose[0].text and "[" not in prose[0].text

def test_a_remembered_line_can_be_repeated_with_its_facts():
    m = Memory()
    remember_reply(CASE, m, "nell", "gus", "<answer>\nCLAIM: I saw Tom by the chapel at midnight on day 2. [D2.S1]\n"
                                           "</answer>", 2)
    h = m.of("nell")[0]
    reply = f'<answer>\nCLAIM: Gus said: "I saw Tom by the chapel at midnight on day 2." [{h.id}]\n</answer>'
    res = check(reply, context_for(CASE, "nell", m.of("nell")))
    assert res.support_rate == 1.0 and res.claims[0].facts == ["F4"]

def test_clash_hint_when_heard_line_contradicts_own_records():
    alibi = HeardItem.model_validate({"id": "H1", "from": "tom", "day": 2, "text": "I stayed at the mill all night.",
                                      "facts": ["F2"]})
    hints = clash_hints(CASE, "nell", [alibi])
    assert hints == [{"listener": "nell", "speaker": "tom", "heard_id": "H1",
                      "text": "Nell looked puzzled by something Tom said."}]
    fine = HeardItem.model_validate({"id": "H2", "from": "tom", "day": 2, "text": "I shut the mill at sunset.",
                                     "facts": ["F1"]})
    assert clash_hints(CASE, "nell", [fine]) == [] and clash_hints(CASE, "mara", [alibi]) == []

@pytest.mark.parametrize("mode", ["easy", "hard"])
def test_run_evening(mode):
    case = generate_case(11, mode)
    calls = []
    village = own_line_village(case)

    def ask_many(batch):
        calls.append(len(batch))
        return village(batch)
    out = run_evening(case, ask_many, seed=3)
    assert len(out["events"]) == G.ROUNDS * G.PAIRS and calls == [G.PAIRS] * (2 * G.ROUNDS)
    for e in out["events"]:
        assert e["question"].endswith("?") and e["heard_ids"]
        assert all(h["from"] == e["responder"] for h in out["heard"][e["asker"]] if h["id"] in e["heard_ids"])
    for vid, items in out["heard"].items():
        assert len(items) <= MAX_HEARD
        for h in items:
            assert h["facts"]

def test_hard_evening_spreads_the_alibi_when_the_killer_talks():
    """Brief 4.5 Hard: the killer's alibi can spread as hearsay. When the killer answers with the alibi, the asker
    stores it with the alibi's (false) fact, so a later hearsay claim of it can be used on the contradiction board."""
    case = generate_case(2, "hard")
    alibi_sid, alibi = next((s.id, case.fact(s.facts[0])) for d in case.documents for s in d.sentences
                            if not case.fact(s.facts[0]).truth)
    m = Memory()
    reply = f"<answer>\nCLAIM: I was at the {alibi.args[1]} at night on day 2. [{alibi_sid}]\n</answer>"
    asker = next(v.id for v in case.villagers if v.id != case.killer)
    stored = remember_reply(case, m, asker, case.killer, reply, 2)
    assert stored and stored[0].facts == [alibi.id]

def test_prompts_with_a_full_memory_fit_the_budget():
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    except OSError as e:
        pytest.skip(f"tokenizer unavailable: {e}")
    worst = 0
    for case in (generate_case(s, m) for s in range(8) for m in ("easy", "hard")):
        mem = Memory()
        for v in case.villagers:
            for i in range(MAX_HEARD + 2):
                mem.add(v.id, case.villagers[(i + 1) % len(case.villagers)].id, 2,
                        "Day 2, midnight. I saw the scribe by the inn carrying a lantern near the chapel.")
        for v in case.villagers:
            msgs = build_messages(case, v.id, "What do you know about the night of day 2?", mem.of(v.id), speaker="Gus")
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            worst = max(worst, len(tok(text).input_ids))
    assert worst <= 1280, worst
