"""Detective bot (archive/npc/detective_bot.py): it names the killer from good answers and is never fooled by bad ones."""
import json
from pathlib import Path

import pytest

from archive.npc.detective_bot import NIGHT_Q, _wrap, gold_ask, judge, plan, play, solve_rate
from archive.schemas import Case
from archive.tasks.prompt import build_liar_messages, build_messages
from archive.verifiers.parse import ABSTAIN
from archive.world.casegen import generate_case

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
CASE = Case.model_validate(json.loads(FIXTURE.read_text()))

def villager_of(case, msgs):
    return next(v.id for v in case.villagers if msgs[0]["content"].startswith(f"You are {v.name},"))

def village(case, override):
    """A gold village where override(vid, question, gold_reply) can change any answer."""
    gold = gold_ask(case)

    def ask_many(batch):
        good = gold(batch)
        return [override(villager_of(case, m), m[1]["content"].split(": ", 1)[1], g) for m, g in zip(batch, good)]
    return ask_many

def test_names_tom_on_the_fixture():
    r = play(CASE, gold_ask(CASE))
    assert (r.accused, r.solved, r.caught) == ("tom", True, True)
    assert r.witnesses == {"tom": ["gus", "nell"]}
    assert sorted(c["facts"] for c in r.confirmed) == [["F2", "F4"], ["F2", "F6"]]
    assert r.table["tom"]["day 2 night"] == ["mill", "chapel"] and r.table["(nobody)"]["day 2 night"] == ["mill"]
    assert r.killer_red_share == 0.0 and sum(r.red.values()) == 0

@pytest.mark.parametrize("mode", ["easy", "hard"])
@pytest.mark.parametrize("seed", range(100))
def test_solves_every_generated_case_with_a_perfect_village(mode, seed):
    case = generate_case(seed, mode)
    r = play(case, gold_ask(case))
    assert r.solved and r.accused == case.killer, (r.accused, r.witnesses)
    assert len(r.witnesses[case.killer]) >= 2
    assert set(r.witnesses) == {case.killer}

def test_plan_asks_the_murder_slot_and_both_sides():
    case = generate_case(0, "easy")
    qs = {q for _, q in plan(case)}
    assert {"Where were you at dusk on day 2?", "Where were you at night on day 2?",
            "Where were you at dawn on day 3?", f"Who did you see near the {case.scene}?", NIGHT_Q} == qs
    assert len(plan(case)) == 5 * len(case.villagers)
    hard = generate_case(0, "hard")
    assert "Where were you at dawn on day 3?" not in {q for _, q in plan(hard)}

def test_liar_killer_is_caught_but_not_solved():
    case = generate_case(4, "hard")
    lie = "I was home asleep all night, I swear. Ask anyone. Maybe Fenn did it."
    r = play(case, village(case, lambda v, q, g: lie if v == case.killer else g),
             prompt_for=lambda c, v, q: build_liar_messages(c, v, q) if v == c.killer else build_messages(c, v, q))
    assert r.caught and not r.solved
    assert r.killer_red_share == 1.0 and not r.confirmed

def test_village_that_always_abstains():
    r = play(CASE, lambda batch: [ABSTAIN] * len(batch))
    assert r.accused is None and not r.solved and not r.caught and r.killer_red_share is None

def test_village_that_rambles_in_prose():
    r = play(CASE, lambda batch: ["Oh, what a terrible night. Everyone is so scared."] * len(batch))
    assert not r.solved and not r.confirmed and r.accused is None

def test_invented_claims_change_nothing():
    junk = "\nCLAIM: I saw Bram stab Elsie at the inn at midnight on day 2. [D1.S1]"
    r = play(CASE, village(CASE, lambda v, q, g: g.replace("\n</answer>", junk + "\n</answer>")
                           if g.startswith("<answer>") and v != "tom" else g))
    assert (r.accused, r.solved) == ("tom", True) and r.red["gus"] > 0

def test_a_missing_witness():
    easy = generate_case(1, "easy")
    one = next(b for _, b in easy.solution.contradictions)
    owner = next(d.owner for d in easy.documents for s in d.sentences if one in s.facts)
    r = play(easy, village(easy, lambda v, q, g: ABSTAIN if v == owner else g))
    assert r.solved
    hard = generate_case(1, "hard")
    one = next(b for _, b in hard.solution.contradictions)
    owner = next(d.owner for d in hard.documents for s in d.sentences if one in s.facts)
    r = play(hard, village(hard, lambda v, q, g: ABSTAIN if v == owner else g))
    assert r.caught and not r.solved and len(r.confirmed) == 1

def test_killer_who_abstains_about_the_night_leaves_no_contradiction():
    r = play(CASE, village(CASE, lambda v, q, g: ABSTAIN if v == "tom" else g))
    assert r.accused is None and not r.solved

def two_suspects(motive_for_tom=True) -> Case:
    """Mara also gets a forged alibi, contradicted by Ivy's ledger and by a new sighting from Bram."""
    raw = json.loads(FIXTURE.read_text())
    raw["facts"] += [{"id": "F13", "rel": "at", "args": ["mara", "inn"], "t": {"day": 2, "slot": "night"}, "truth": False},
                     {"id": "F14", "rel": "saw", "args": ["bram", "mara", "chapel"], "t": {"day": 2, "slot": "night"},
                      "truth": True}]
    d4 = next(d for d in raw["documents"] if d["id"] == "D4")
    d4["forged"] = True
    d4["sentences"].append({"id": "D4.S2", "facts": ["F13"], "text": "Day 2, night. I was at the inn."})
    d6 = next(d for d in raw["documents"] if d["id"] == "D6")
    d6["sentences"].append({"id": "D6.S2", "facts": ["F14"], "text": "Day 2, midnight. I saw Mara by the chapel."})
    if not motive_for_tom:
        next(f for f in raw["facts"] if f["id"] == "F11")["args"] = ["gus", "elsie", "40 silver"]
    return Case.model_validate(raw)

def test_equal_witnesses_broken_by_motive():
    case = two_suspects()
    r = play(case, gold_ask(case))
    assert r.witnesses["tom"] == ["gus", "nell"] and r.witnesses["mara"] == ["bram", "ivy"]
    assert r.accused == "tom"

def test_without_motive_more_contradictions_win():
    case = two_suspects(motive_for_tom=False)
    r = play(case, gold_ask(case))
    assert r.accused == "mara" and not r.caught

def test_one_batch_and_reply_count_is_checked():
    calls = []

    def ask_many(batch):
        calls.append(len(batch))
        return [ABSTAIN] * len(batch)
    play(CASE, ask_many)
    assert calls == [len(plan(CASE))]
    with pytest.raises(ValueError):
        play(CASE, lambda batch: [ABSTAIN])

def test_judge_from_a_reply_dict_and_determinism():
    gold = gold_ask(CASE)
    qs = plan(CASE)
    replies = dict(zip(qs, gold([build_messages(CASE, v, q) for v, q in qs])))
    a, b = judge(CASE, replies), judge(CASE, replies)
    assert (a.accused, a.confirmed, a.table) == (b.accused, b.confirmed, b.table)
    assert len(a.transcript) == len(qs)

def test_wrap_turns_prose_into_unsourced_claims():
    assert _wrap("I was home. Ask Gus!\nMara did it.") == \
        "<answer>\nCLAIM: I was home.\nCLAIM: Ask Gus!\nCLAIM: Mara did it.\n</answer>"
    assert _wrap("") == "" and _wrap("   ") == ""

def test_solve_rate_and_ci():
    results = [play(c, gold_ask(c)) for c in (generate_case(s, "easy") for s in range(10))]
    results += [play(CASE, lambda b: [ABSTAIN] * len(b)) for _ in range(10)]
    s = solve_rate(results)
    assert s["cases"] == 20 and s["solved_rate"] == 0.5 and s["caught_rate"] == 0.5
    lo, hi = s["solved_ci95"]
    assert lo < 0.5 < hi and 0 <= lo and hi <= 1
    assert solve_rate([]) == {"cases": 0}

def test_bot_prompts_fit_the_token_budget():
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    except OSError as e:
        pytest.skip(f"tokenizer unavailable: {e}")
    worst = 0
    for case in (generate_case(s, m) for s in range(6) for m in ("easy", "hard")):
        for v, q in plan(case)[::3]:
            text = tok.apply_chat_template(build_messages(case, v, q), tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
            worst = max(worst, len(tok(text).input_ids))
    assert worst <= 1280, worst

def test_play_returns_a_plain_dict():
    r = play(CASE, gold_ask(CASE))
    assert isinstance(r, dict) and r["accused"] == r.accused == "tom"
    back = json.loads(json.dumps(r))
    assert back["solved"] is True and back["witnesses"] == {"tom": ["gus", "nell"]}
    with pytest.raises(AttributeError):
        r.no_such_key
