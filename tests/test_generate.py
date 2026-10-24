"""Task generator and gold replies (archive/tasks/generate.py, gold.py), end to end on every split.

The gold tests are the most important in the project: SFT copies these strings, CuratorKIT drops tasks whose gold
fails the checker, and the reward compares against gold facts.
"""
import json
import re
from collections import Counter

import pytest

from archive.schemas import SLOTS, Case, Task
from archive.tasks.generate import ADV_MIX, MIX, SPLITS, build_split, main
from archive.tasks.gold import gold_reply
from archive.tasks.prompt import build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.parse import ABSTAIN, parse
from archive.world.lexicon import actions, negations, pronouns

DATA = {split: build_split(split, first, n) for split, (first, n) in SPLITS.items()}
ALL = [(split, t) for split, (_, tasks) in DATA.items() for t in tasks]
CASES = {c.case_id: c for cases, _ in DATA.values() for c in cases}
ABSTAIN_TYPES = {"unanswerable", "other_npc", "injection"}
_CLAIM_LINE = re.compile(r'^CLAIM: [A-Z].*[.!?]"? (\[[A-Z]\d+(\.S\d+)?\])+$')


def _check(t):
    return check(gold_reply(t), context_for(CASES[t.case_id], t.villager, t.heard))


# --- every gold reply passes the checker ------------------------------------------------------------------------

def test_every_gold_reply_passes_the_checker():
    failures = []
    for split, t in ALL:
        r = _check(t)
        if t.gold.abstain:
            ok = r.parsed and r.abstained
        else:
            ok = (r.parsed and not r.abstained and r.support_rate == 1.0
                  and [c.facts for c in r.claims] == [c.facts for c in t.gold.claims]
                  and [c.cites for c in r.claims] == [c.cites for c in t.gold.claims])
        if not ok:
            failures.append((split, t.type, t.question, gold_reply(t), [(c.status, c.reason) for c in r.claims]))
    assert len(ALL) > 2000
    assert failures == []


# --- every gold reply follows the prompt's format and claim rules -----------------------------------------------

def test_gold_replies_follow_every_format_rule():
    for _, t in ALL:
        reply = gold_reply(t)
        if t.gold.abstain:
            assert reply == ABSTAIN  # rule 19: exactly the line, nothing else
            continue
        lines = reply.split("\n")
        assert lines[0] == "<answer>" and lines[-1] == "</answer>"            # rules 11, 12
        body = lines[1:-1]
        assert body and all(ln.startswith("CLAIM: ") for ln in body)          # rules 13, 14, 15; no '#' lines
        assert all(_CLAIM_LINE.match(ln) for ln in body), body                # rule 16: ends with its ID(s)
        assert parse(reply).ok


def test_gold_claims_follow_every_claim_rule():
    for _, t in ALL:
        for c in t.gold.claims:
            text = c.text
            assert not pronouns(text), text                                   # rule 5
            assert " and " not in text and "," not in text, text              # rule 14: one fact
            assert not negations(text), text                                  # rule 9
            assert not actions(text), text                                    # rule 8
            assert len(c.cites) == 1 and len(c.facts) == 1, text              # one sentence, one fact
            if c.cites[0].startswith("H"):                                    # rule 17: names the teller
                teller = next(h for h in t.heard if h.id == c.cites[0])
                name = CASES[t.case_id].lexicon.people[teller.from_][0]
                assert text.startswith(f"{name} said: ") or text.startswith(f"{name} told me "), text


def test_gold_copies_the_lines_time_words():
    """Rule 7: 'Day 2, midnight.' in the line -> 'at midnight' in the claim, never a different time word."""
    words = {"dawn", "first light", "morning", "noon", "midday", "afternoon", "dusk", "sunset", "evening", "night",
             "midnight", "ninth bell"}
    for _, t in ALL:
        ctx = context_for(CASES[t.case_id], t.villager, t.heard)
        for c in t.gold.claims:
            m = re.match(r"^Day \d+, ([a-z ]+)\.", ctx.texts[c.cites[0]])
            if m:
                said = {w for w in words if re.search(rf"\b{w}\b", c.text)} - {"night"} | (
                    {"night"} if re.search(r"\bat night\b", c.text) else set())
                assert said == {m.group(1)}, (c.text, ctx.texts[c.cites[0]])


# --- types, mix and abstain correctness ---------------------------------------------------------------------------

@pytest.mark.parametrize("split", ["train", "val", "test_id", "test_game"])
def test_type_mix_matches_the_brief(split):
    tasks = DATA[split][1]
    counts = Counter(t.type for t in tasks)
    for kind, share in MIX.items():
        assert abs(counts[kind] / len(tasks) - share) <= 0.05, (kind, counts[kind] / len(tasks))


def test_adversarial_split():
    tasks = DATA["test_adv"][1]
    assert len(tasks) >= 200 and {t.type for t in tasks} == set(ADV_MIX)
    assert len(DATA["test_id"][1]) >= 200


def test_abstain_types_abstain_and_answer_types_answer():
    for _, t in ALL:
        if t.type in ABSTAIN_TYPES:
            assert t.gold.abstain, t.question
        elif t.type in {"answerable_1hop", "answerable_multihop", "hearsay", "hearsay_plus_own", "unreliable_doc"}:
            assert not t.gold.abstain and t.gold.claims, t.question
        if t.type == "answerable_multihop":
            assert len(t.gold.claims) >= 2
        if t.type == "hearsay_plus_own":
            assert [c.cites[0][0] == "H" for c in t.gold.claims] == [True, False]


def test_abstain_questions_really_have_no_answer():
    """Re-derive from the documents, independently of the generator: nothing the villager can see answers it."""
    for _, t in ALL:
        if not t.gold.abstain:
            continue
        case = CASES[t.case_id]
        ctx = context_for(case, t.villager, t.heard)
        facts = [case.fact(f) for fs in ctx.facts.values() for f in fs]
        m = re.search(r"(at|in the) (dawn|morning|noon|afternoon|dusk|night) on day (\d)", t.question)
        if m and t.type == "unanswerable":
            day, slot = int(m.group(3)), m.group(2)
            assert not any(f.t and (f.t.day, f.t.slot) == (day, slot) for f in facts), t.question
        if t.type == "other_npc":
            who = next(pid for pid, names in case.lexicon.people.items() if names[0] in t.question)
            assert not any(who in f.args for f in facts), t.question
        if "Do you owe anyone money" in t.question:
            assert not any(f.rel == "owes" and f.args[0] == t.villager for f in facts)


def test_unreliable_doc_is_the_killers_forged_alibi():
    for _, t in ALL:
        if t.type == "unreliable_doc":
            case = CASES[t.case_id]
            assert t.villager == case.killer
            assert not case.fact(t.gold.claims[0].facts[0]).truth


def test_false_premise_is_corrected_or_abstained():
    kinds = Counter()
    for _, t in ALL:
        if t.type == "false_premise":
            kinds["corrected" if not t.gold.abstain else "abstain"] += 1
            if not t.gold.abstain:  # the place in the question is not the place in the answer
                asked = re.search(r"at the ([a-z ]+?) (at|in the) ", t.question).group(1)
                assert asked not in t.gold.claims[0].text
    assert kinds["corrected"] > 50 and kinds["abstain"] > 50


def test_hearsay_plus_own_includes_the_brief_showcase():
    """Some witnesses hear the killer's alibi next to their own contradicting line."""
    showcase = 0
    for _, t in ALL:
        if t.type == "hearsay_plus_own":
            case = CASES[t.case_id]
            if t.heard[0].from_ == case.killer and not case.fact(t.heard[0].facts[0]).truth:
                showcase += 1
                own = t.gold.claims[1].facts[0]
                assert any(own in pair for pair in map(set, case.solution.contradictions))
    assert showcase > 0


# --- splits, rows and determinism -------------------------------------------------------------------------------

def test_no_case_crosses_splits():
    seen = {}
    for split, (cases, tasks) in DATA.items():
        ids = {c.case_id for c in cases}
        assert len(ids) == len(cases)
        assert {t.case_id for t in tasks} <= ids
        for cid in ids:
            assert cid not in seen, (cid, seen.get(cid), split)
            seen[cid] = split
    assert len({t.task_id for _, t in ALL}) == len(ALL)


def test_half_easy_half_hard():
    for cases, _ in DATA.values():
        modes = Counter(c.difficulty for c in cases)
        assert abs(modes["easy"] - modes["hard"]) <= 1


def test_rows_round_trip_like_p1_reads_them():
    for _, t in ALL[:300]:
        row = json.loads(json.dumps(t.model_dump(mode="json", by_alias=True)))
        assert all("from" in h for h in row["heard"])
        assert gold_reply(row) == gold_reply(Task.model_validate(row))   # dict rows work too


def test_deterministic():
    a = build_split("val", *SPLITS["val"])
    b = build_split("val", *SPLITS["val"])
    assert [t.model_dump() for t in a[1]] == [t.model_dump() for t in b[1]]


def test_command_writes_p1s_layout(tmp_path):
    small = {"train": (0, 4), "val": (1000, 2), "test_id": (2000, 2), "test_adv": (3000, 2), "test_game": (4000, 2)}
    import archive.tasks.generate as g
    g.write_all(tmp_path, small)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    for split in small:
        cases = [Case.model_validate(json.loads(x)) for x in (tmp_path / f"cases_{split}.jsonl").read_text().splitlines()]
        tasks = [Task.model_validate(json.loads(x)) for x in (tmp_path / f"tasks_{split}.jsonl").read_text().splitlines()]
        assert manifest[split]["cases"] == len(cases) and manifest[split]["tasks"] == len(tasks)
        assert sum(manifest[split]["by_type"].values()) == len(tasks)


def test_main_runs(tmp_path, monkeypatch):
    import archive.tasks.generate as g
    monkeypatch.setattr(g, "SPLITS", {"train": (0, 2)})
    monkeypatch.setattr(g.write_all, "__defaults__", ({"train": (0, 2)},))
    main(["--out", str(tmp_path)])
    assert (tmp_path / "tasks_train.jsonl").exists()


# --- prompt and training length budget ----------------------------------------------------------------------------

def test_prompt_and_gold_fit_the_sequence_budget():
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    except OSError as e:
        pytest.skip(f"tokenizer unavailable: {e}")
    worst_prompt = worst_total = 0
    for _, t in ALL[::7]:
        msgs = build_messages(CASES[t.case_id], t.villager, t.question, heard=t.heard)
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        n = len(tok(prompt).input_ids)
        worst_prompt = max(worst_prompt, n)
        worst_total = max(worst_total, n + len(tok(gold_reply(t)).input_ids) + 1)
    assert worst_prompt <= 1280, worst_prompt
    assert worst_total <= 1536, worst_total   # P1's SFT drops rows longer than max_seq_len


# --- configs/data.yaml (TASKS_P2: python -m archive.tasks.generate --config configs/data.yaml) ---------------------

def test_data_config_matches_the_defaults():
    from pathlib import Path
    from archive.tasks.generate import TASKS_PER_CASE, load_config
    out, splits = load_config(Path(__file__).parents[1] / "configs" / "data.yaml")
    assert out == Path("data_prepared")
    assert {k: v[:2] for k, v in splits.items()} == SPLITS
    assert splits["test_adv"][2] == TASKS_PER_CASE["test_adv"] and splits["train"][2] == 14


def test_bad_configs_are_rejected(tmp_path):
    from archive.tasks.generate import load_config
    overlap = tmp_path / "overlap.yaml"
    overlap.write_text("splits:\n  train: {first_seed: 0, cases: 50}\n  val: {first_seed: 40, cases: 5}\n")
    with pytest.raises(ValueError, match="overlap"):
        load_config(overlap)
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text("splits:\n  trian: {first_seed: 0, cases: 5}\n")
    with pytest.raises(ValueError, match="unknown split"):
        load_config(unknown)


def test_main_with_config_and_out_override(tmp_path):
    cfg = tmp_path / "data.yaml"
    cfg.write_text(f"out: {tmp_path / 'from_config'}\ntasks_per_case: 5\n"
                   "splits:\n  train: {first_seed: 0, cases: 2}\n  val: {first_seed: 1000, cases: 2}\n")
    main(["--config", str(cfg)])
    m = json.loads((tmp_path / "from_config" / "manifest.json").read_text())
    assert set(m) == {"train", "val"} and m["train"]["cases"] == 2 and m["train"]["tasks"] <= 10
    main(["--config", str(cfg), "--out", str(tmp_path / "override")])
    assert (tmp_path / "override" / "tasks_val.jsonl").exists()
    with pytest.raises(SystemExit):
        main([])
