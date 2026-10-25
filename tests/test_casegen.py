"""Case generator, renderer and personas (archive/world/casegen.py, render.py, archive/tasks/personas.py)."""
import itertools
import json
import re
from pathlib import Path

import pytest

from archive.schemas import SLOTS, Case
from archive.tasks.personas import PERSONAS
from archive.tasks.prompt import build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.contradiction import facts_clash, locations
from archive.world.casegen import NEIGHBOURS, PRESETS, generate_case
from archive.world.lexicon import actions, vocab_for

SEEDS = range(40)
MODES = ["easy", "hard"]
CASES = {(m, s): generate_case(s, m) for m in MODES for s in SEEDS}
FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"

def visible(case):
    """(sentence, document) for every sentence that some prompt or the player can see."""
    return [(s, d) for d in case.documents if not d.withheld for s in d.sentences]

def visible_facts(case):
    return [case.fact(f) for s, _ in visible(case) for f in s.facts]

def owner_of(case, fact_id):
    return next(d.owner for s, d in visible(case) if fact_id in s.facts)

@pytest.mark.parametrize("key", sorted(CASES))
def test_case_shape_follows_the_preset(key):
    mode, seed = key
    case, p = CASES[key], PRESETS[mode]
    assert len(case.villagers) == p["villagers"]
    assert len({v.name for v in case.villagers}) == len({v.role for v in case.villagers}) == p["villagers"]
    assert case.victim not in {v.id for v in case.villagers}
    assert [d.id for d in case.documents if d.forged] == [case.villager(case.killer).docs[0]]
    assert sum(v.secret_topic is not None for v in case.villagers) == p["secrets"]
    assert case.villager(case.killer).model == p["killer_model"]
    assert len(case.solution.contradictions) == len(p["witnesses"])
    assert all(d <= p["days"] for f in case.facts if f.t for d in [f.t.day])

@pytest.mark.parametrize("key", sorted(CASES))
def test_lines_per_villager_and_one_fact_per_sentence(key):
    case = CASES[key]
    vocab = vocab_for(case)
    for v in case.villagers:
        own = [s for did in v.docs if not (d := case.doc(did)).withheld for s in d.sentences]
        assert 4 <= len(own) <= 8, (v.id, len(own))
    for s, d in visible(case):
        assert len(s.facts) == 1
        f = case.fact(s.facts[0])
        ents = vocab.extract(s.text, d.owner)
        if f.t:
            assert s.text.startswith(f"Day {f.t.day}, ")
            assert ("day", f.t.day) in ents and ("slot", f.t.slot) in ents
        assert not actions(s.text), s.text

@pytest.mark.parametrize("key", sorted(CASES))
def test_only_the_forged_alibi_creates_contradictions(key):
    case = CASES[key]
    facts = visible_facts(case)
    alibi = next(f for f in case.facts if not f.truth)
    clashes = [(a.id, b.id) for a, b in itertools.combinations(facts, 2) if facts_clash(case, a, b)]
    assert clashes and all(alibi.id in pair for pair in clashes)
    for a, b in case.solution.contradictions:
        assert facts_clash(case, case.fact(a), case.fact(b))
    witnesses = {owner_of(case, b) for _, b in case.solution.contradictions}
    assert len(witnesses) == len(case.solution.contradictions) and case.killer not in witnesses

@pytest.mark.parametrize("key", sorted(CASES))
def test_murder_time_is_consistent(key):
    case = CASES[key]
    mt = (case.murder_time.day, case.murder_time.slot)
    for f in visible_facts(case):
        for loc in locations(f):
            if (loc.day, loc.slot) != mt or not f.truth:
                continue
            assert loc.place != case.scene or loc.person == case.killer
            if f.rel != "empty":
                assert loc.place != case.fact(case.solution.contradictions[0][0]).args[1]
    after = [f for f in visible_facts(case) if f.t and (f.t.day, SLOTS.index(f.t.slot)) >
             (case.murder_time.day, SLOTS.index(case.murder_time.slot))]
    assert not any(case.victim in f.args[:2] for f in after if f.rel in ("at", "saw"))

@pytest.mark.parametrize("key", sorted(CASES))
def test_quoting_your_own_line_is_green(key):
    """The strongest renderer test: every visible line, quoted word for word as a claim, passes the checker.
    Easy "near" sightings name the scene ("next to the guildhall"), a fact place, so they are red by design."""
    case = CASES[key]
    for v in case.villagers:
        ctx = context_for(case, v.id)
        for sid, text in ctx.texts.items():
            res = check(f"<answer>\nCLAIM: {text} [{sid}]\n</answer>", ctx).claims[0]
            if ", next to the " in text:
                assert res.reason == "fact_mismatch", text
            else:
                assert res.status == "supported", (text, res.reason)

@pytest.mark.parametrize("mode", MODES)
def test_sightings_match_the_mode(mode):
    for seed in SEEDS:
        case = CASES[(mode, seed)]
        killer = case.villager(case.killer)
        for _, b in case.solution.contradictions:
            f = case.fact(b)
            if f.rel != "saw":
                continue
            text = next(s.text for s, _ in visible(case) if b in s.facts)
            assert f.args[2] == case.scene or f.args[2] in NEIGHBOURS[case.scene]
            if mode == "hard":
                assert f"the {killer.role}" in text and killer.name not in text
            else:
                assert killer.name in text

def test_deterministic_and_varied():
    assert generate_case(3, "hard").model_dump() == generate_case(3, "hard").model_dump()
    assert generate_case(3, "hard").model_dump() != generate_case(4, "hard").model_dump()
    assert len({CASES[("easy", s)].killer for s in SEEDS}) > 10

def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        generate_case(0, "normal")

def test_personas_hold_no_checkable_words():
    case = Case.model_validate(json.loads(FIXTURE.read_text()))
    vocab = vocab_for(case)
    assert len(set(PERSONAS)) == len(PERSONAS) >= 40
    for p in PERSONAS:
        assert vocab.extract(p) == set() and not actions(p), p
        assert not re.search(r"\b(he|she|they)\b", p)

def test_prompts_fit_the_token_budget():
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    except OSError as e:
        pytest.skip(f"tokenizer unavailable: {e}")
    heard = [{"id": f"H{i}", "from": "x", "day": 2, "text": "Day 2, midnight. I saw the miller by the chapel.",
              "facts": []} for i in range(1, 4)]
    worst = 0
    for key in itertools.islice(sorted(CASES), 0, None, 4):
        case = CASES[key]
        for v in case.villagers:
            msgs = build_messages(case, v.id, "Where were you on the night of the murder?", heard=heard)
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            worst = max(worst, len(tok(text).input_ids))
    assert worst <= 1280, worst
