"""Reward and metric properties over every generated task: each kind of reply gets exactly the parts the brief
defines, no reply beats gold, and compute() matches an independent re-count of the brief's definitions."""
import random
import re

import pytest

from archive.eval.metrics import compute
from archive.rewards.combine import reward
from archive.rewards.terms import estimate_tokens
from archive.tasks.generate import build_split
from archive.tasks.gold import gold_reply, own_claim
from archive.verifiers.checker import check, context_for
from archive.verifiers.parse import ABSTAIN
from archive.world.lexicon import TIME_WORDS

_TIME = re.compile(r" (at|in the) ((?:the )?(?:" + "|".join(sorted(TIME_WORDS, key=len, reverse=True))
                   + r")) on day (\d)")

DATA = [build_split(s, f, n) for s, f, n in [("val", 1000, 20), ("test_id", 2000, 40), ("test_adv", 3000, 20)]]
CASES = {c.case_id: c for cases, _ in DATA for c in cases}
TASKS = [t for _, tasks in DATA for t in tasks]


def block(lines):
    return "<answer>\n" + "\n".join(lines) + "\n</answer>"


def claim_line(text, cites):
    return f"CLAIM: {text} " + "".join(f"[{c}]" for c in cites)


def gold_lines(t):
    return [claim_line(c.text, c.cites) for c in t.gold.claims]


def variants(t):
    """(name, reply, expected parts or None) for one task. Expected parts follow brief 10.3 exactly."""
    case = CASES[t.case_id]
    ctx = context_for(case, t.villager, t.heard)
    out = []
    if t.gold.abstain:
        out.append(("gold", ABSTAIN, dict(correct=1, support=1, cite=1, abstain=1, fmt=1)))
        line = next(iter(sorted(ctx.texts)))  # any true line the villager has
        f = case.fact(ctx.facts[line][0]) if ctx.facts[line] else None
        if f and line not in ctx.heard_ids:
            true = block([claim_line(own_claim(case, t.villager, line, f, ctx.texts[line]).text, [line])])
            out.append(("true claim instead of abstain", true, dict(correct=0, support=1, cite=0, abstain=-1, fmt=1)))
        out.append(("abstain plus text", ABSTAIN + " Sorry!", dict(correct=0, support=0, cite=0, abstain=0, fmt=0)))
        out.append(("garbage", "I think it was Tom.", dict(correct=0, support=0, cite=0, abstain=0, fmt=0)))
        return out
    g = gold_lines(t)
    n = len(g)
    out.append(("gold", block(g), dict(correct=1, support=1, cite=1, abstain=0, fmt=1)))
    out.append(("gold twice", block(g + g), dict(correct=1, support=1, cite=1, abstain=0, fmt=1)))
    first = t.gold.claims[0]
    red = claim_line("I saw Wren at the tavern at noon on day 1.", first.cites)
    out.append(("extra invented claim", block(g + [red]), dict(correct=1, support=n / (n + 1), cite=1, abstain=0, fmt=1)))
    want = {f for c in t.gold.claims for f in c.facts}
    spare = [i for i in sorted(ctx.texts) if i not in ctx.heard_ids and ctx.facts[i] and not set(ctx.facts[i]) & want]
    if spare:
        i = spare[0]
        extra = claim_line(own_claim(case, t.villager, i, case.fact(ctx.facts[i][0]), ctx.texts[i]).text, [i])
        out.append(("extra true but irrelevant claim", block(g + [extra]),
                    dict(correct=1, support=1, cite=n / (n + 1), abstain=0, fmt=1)))
        wrong = [claim_line(first.text, [i])] + g[1:]
        out.append(("wrong line cited", block(wrong), dict(correct=0, support=(n - 1) / n, cite=(n - 1) / n,
                                                           abstain=0, fmt=1)))
    if n > 1:
        out.append(("missing a gold fact", block(g[:-1]), dict(correct=0, support=1, cite=1, abstain=0, fmt=1)))
    m = _TIME.search(first.text)
    if m:
        slot = TIME_WORDS[m.group(2).replace("the ", "")]  # "first light" and "dawn" are the same slot
        other = "at noon" if slot != "noon" else "at dawn"
        moved = first.text.replace(m.group(0), f" {other} on day {m.group(3)}")
        out.append(("wrong time", block([claim_line(moved, first.cites)] + g[1:]),
                    dict(correct=0, support=(n - 1) / n, cite=1, abstain=0, fmt=1)))
    if first.cites[0].startswith("H") and ": " in first.text:
        bare = first.text.split(": ", 1)[1].strip('"')
        out.append(("hearsay without the teller", block([claim_line(bare, first.cites)] + g[1:]),
                    dict(correct=0, support=(n - 1) / n, cite=1, abstain=0, fmt=1)))
    name = re.search(r"\b[A-Z][a-z]+\b", first.text[1:])
    if name and name.group(0) not in ("I", "The", "Day"):
        pron = first.text[0] + first.text[1:].replace(name.group(0), "they", 1)
        out.append(("pronoun", block([claim_line(pron, first.cites)] + g[1:]),
                    dict(correct=0, support=(n - 1) / n, cite=1, abstain=0, fmt=1)))
    out.append(("abstain on an answerable task", ABSTAIN, dict(correct=0, support=0, cite=0, abstain=-1, fmt=1)))
    out.append(("cut off", block(g)[:-12], dict(correct=0, support=0, cite=0, abstain=0, fmt=0)))
    out.append(("thinking left on", "<think>hmm</think>\n" + block(g), dict(correct=0, support=0, cite=0, abstain=0, fmt=0)))
    out.append(("no format", first.text, dict(correct=0, support=0, cite=0, abstain=0, fmt=0)))
    return out


def total(parts):
    return 0.35 * parts["correct"] + 0.30 * parts["support"] + 0.10 * parts["cite"] + 0.15 * parts["abstain"] + \
        0.10 * parts["fmt"]


# --- every task, every kind of reply ----------------------------------------------------------------------------------

def test_every_reply_kind_scores_exactly_as_defined():
    wrong, seen = [], set()
    for t in TASKS:
        case = CASES[t.case_id]
        for name, reply, expected in variants(t):
            seen.add(name)
            r = reward(reply, t, case, n_tokens=50)
            got = {k: r[k] for k in expected}
            if any(abs(got[k] - expected[k]) > 1e-9 for k in expected) or abs(r["total"] - total(expected)) > 1e-9:
                wrong.append((t.type, name, t.question, reply, got, expected))
    assert len(seen) >= 15, seen
    assert wrong == [], wrong[:3]


def test_nothing_beats_gold_and_the_order_teaches_the_right_thing():
    for t in TASKS:
        case = CASES[t.case_id]
        scored = {name: reward(reply, t, case, n_tokens=50)["total"] for name, reply, _ in variants(t)}
        best = scored["gold"]
        assert all(v <= best + 1e-9 for v in scored.values()), (t.question, scored)
        if not t.gold.abstain:
            assert scored["gold twice"] == pytest.approx(best)                         # repeating gains nothing
            assert best > scored["extra invented claim"] > scored["abstain on an answerable task"]
            assert scored["abstain on an answerable task"] < scored["no format"] + 0.1  # refusing is not safe
            for wrongish in ("wrong time", "missing a gold fact", "wrong line cited", "pronoun",
                             "hearsay without the teller"):
                if wrongish in scored:
                    assert scored[wrongish] < scored["extra invented claim"], (wrongish, scored)
        else:
            assert best == pytest.approx(1.0) and scored["true claim instead of abstain"] < best


def test_outcome_bundle_never_beats_gold_either():
    for t in TASKS[::3]:
        case = CASES[t.case_id]
        scored = {name: reward(reply, t, case, bundle="outcome", n_tokens=50)["total"] for name, reply, _ in variants(t)}
        assert all(v <= scored["gold"] + 1e-9 for v in scored.values())


def test_padding_only_costs_in_the_length_zone():
    t = next(t for t in TASKS if not t.gold.abstain)
    reply = gold_reply(t)
    padded = reply.replace("<answer>\n", "<answer>\n# " + "so much to say " * 70 + "\n")
    case = CASES[t.case_id]
    assert reward(padded, t, case)["length"] < 0 and reward(padded, t, case)["total"] < reward(reply, t, case)["total"]
    assert reward(padded, t, case)["correct"] == 1


# --- metrics against an independent re-count -----------------------------------------------------------------------

def oracle(records, cases):
    """The brief's definitions, written out separately from metrics.py."""
    claims = [c for r in records for c in r["check_result"]["claims"]]
    def gold_set(r):
        return {f for c in r["task"]["gold"]["claims"] for f in c["facts"]}
    def ok(r):
        chk = r["check_result"]
        if r["task"]["gold"]["abstain"]:
            return chk["abstained"]
        sup = {f for c in chk["claims"] if c["status"] == "supported" for f in c["facts"]}
        return bool(gold_set(r)) and gold_set(r) <= sup and not ("<answer>" in r["reply"] and not r["reply"].strip().endswith("</answer>"))
    answerable = [r for r in records if not r["task"]["gold"]["abstain"]]
    abst = [r for r in records if r["check_result"]["abstained"]]
    should = [r for r in records if r["task"]["gold"]["abstain"]]
    robust = [r for r in records if r["task"]["type"] in ("injection", "false_premise")]
    cites = rel = 0
    for r in records:
        facts = context_for(cases[r["case_id"]], r["task"]["villager"], r["task"]["heard"]).facts
        for c in r["check_result"]["claims"]:
            for i in c["cites"]:
                cites += 1
                rel += bool(set(facts.get(i, [])) & gold_set(r))
    return {
        "unsupported_claim_rate": sum(c["status"] != "supported" for c in claims) / len(claims),
        "answer_accuracy": sum(ok(r) for r in answerable) / len(answerable),
        "abstain_precision": sum(r["task"]["gold"]["abstain"] for r in abst) / len(abst),
        "abstain_recall": sum(r["check_result"]["abstained"] for r in should) / len(should),
        "citation_precision": rel / cites,
        "robustness": sum(ok(r) for r in robust) / len(robust),
        "parse_rate": sum(r["check_result"]["parsed"] for r in records) / len(records),
        "tokens_per_reply": sum(r["tokens"] for r in records) / len(records),
    }


@pytest.mark.parametrize("seed", range(5))
def test_metrics_match_an_independent_recount(seed):
    rng = random.Random(seed)
    records = []
    for t in rng.sample(TASKS, 400):
        name, reply, _ = rng.choice(variants(t))  # a "model" that is right, wrong, or broken at random
        case = CASES[t.case_id]
        chk = check(reply, context_for(case, t.villager, t.heard)).model_dump()
        parts = reward(reply, t, case)
        records.append({"task": t.model_dump(mode="json", by_alias=True), "case_id": t.case_id, "reply": reply,
                        "check_result": chk, "reward_parts": parts, "correct": parts["correct"],
                        "tokens": estimate_tokens(reply)})
    want = oracle(records, CASES)
    for with_cases in (None, CASES):
        got = compute(records, cases=with_cases, n_boot=200)
        for k, v in want.items():
            assert got[k] == pytest.approx(v), (k, with_cases is not None)
            lo, hi = got["ci95"][k]
            assert lo <= got[k] <= hi


def test_more_cases_give_narrower_ranges():
    rng = random.Random(9)
    base = []
    for t in rng.sample(TASKS, 120):
        name, reply, _ = rng.choice(variants(t))
        chk = check(reply, context_for(CASES[t.case_id], t.villager, t.heard)).model_dump()
        base.append({"task": t.model_dump(mode="json", by_alias=True), "case_id": t.case_id, "reply": reply,
                     "check_result": chk, "tokens": 10})
    bigger = [{**r, "case_id": f"{r['case_id']}#{k}"} for k in range(4) for r in base]   # 4x the cases
    small, large = compute(base, cases=None), compute(bigger, cases=None)
    w = lambda m, k: m["ci95"][k][1] - m["ci95"][k][0]
    assert small["answer_accuracy"] == pytest.approx(large["answer_accuracy"])
    assert w(large, "answer_accuracy") < w(small, "answer_accuracy")
