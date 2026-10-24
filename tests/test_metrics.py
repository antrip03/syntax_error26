"""Metrics (archive/eval/metrics.py): every brief section 11 metric, bootstrap CIs by case, and the number gates."""
import json
from pathlib import Path

import pytest

from archive.eval.metrics import MIN_ITEMS, RATIOS, compute
from archive.rewards.combine import reward
from archive.rewards.terms import estimate_tokens
from archive.schemas import Case, Gold, GoldClaim, Task
from archive.tasks.generate import build_split
from archive.tasks.gold import gold_reply
from archive.verifiers.checker import check, context_for
from archive.verifiers.parse import ABSTAIN

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
CASE = Case.model_validate(json.loads(FIXTURE.read_text()))


def record(reply, task, case, with_parts=True, case_id=None):
    """One record exactly as P1's run_eval writes it."""
    chk = check(reply, context_for(case, task.villager, task.heard)).model_dump()
    parts = reward(reply, task, case) if with_parts else None
    rec = {"task": task.model_dump(mode="json", by_alias=True), "case_id": case_id or task.case_id, "reply": reply,
           "check_result": chk, "tokens": estimate_tokens(reply)}
    if parts:
        rec.update(reward_parts=parts, correct=parts["correct"])
    return rec


def tom_task(abstain=False, kind=None):
    claims = [] if abstain else [GoldClaim(text="I shut the mill at sunset on day 2.", cites=["D1.S1"], facts=["F1"])]
    return Task(task_id="t", case_id="c_elsie", villager="tom", split="test_id", question="q",
                type=kind or ("unanswerable" if abstain else "answerable_1hop"), gold=Gold(abstain=abstain, claims=claims))


A = "<answer>\nCLAIM: I shut the mill at dusk on day 2. [D1.S1]\n</answer>"
B = A.replace("</answer>", "CLAIM: I locked the guildhall door at night. [D1.S1]\n</answer>")
C = "<answer>\nCLAIM: I shut the mill at midnight on day 2. [D1.S1]\n</answer>"


def test_gold_replies_score_perfectly():
    cases, tasks = build_split("test_id", 2000, 16)
    by_id = {c.case_id: c for c in cases}
    m = compute([record(gold_reply(t), t, by_id[t.case_id]) for t in tasks])
    for name in ["support_rate", "answer_accuracy", "abstain_precision", "abstain_recall", "citation_precision",
                 "robustness", "parse_rate"]:
        assert m[name] == 1.0 and m["ci95"][name] == [1.0, 1.0], name
    assert m["unsupported_claim_rate"] == 0.0
    assert m["n_items"] == len(tasks) and m["n_cases"] == 16
    assert m["gates"]["parse_rate"]["pass"] and m["gates"]["support_rate"]["pass"]
    assert m["gates"]["abstain_rate"]["pass"]
    assert m["gates"]["min_items"]["pass"] == (len(tasks) >= MIN_ITEMS)


def test_each_metric_on_hand_made_records():
    recs = [record(A, tom_task(), CASE),                                  # correct, 1 claim green
            record(B, tom_task(), CASE),                                  # correct, 1 green + 1 red
            record(C, tom_task(), CASE),                                  # wrong, 1 red
            record(ABSTAIN, tom_task(), CASE),                            # wrong abstain
            record(ABSTAIN, tom_task(abstain=True), CASE),                # correct abstain
            record(A, tom_task(abstain=True), CASE),                      # claim where it should abstain
            record("Closed it at dusk!", tom_task(abstain=True, kind="injection"), CASE)]  # unparsed
    m = compute(recs)
    assert m["unsupported_claim_rate"] == pytest.approx(2 / 5)          # claims: A1 B2 C1 A1 -> 5, red: B1 C1
    assert m["support_rate"] == pytest.approx(3 / 5)
    assert m["answer_accuracy"] == pytest.approx(2 / 4)
    assert m["abstain_precision"] == pytest.approx(1 / 2)               # 2 abstains, 1 right
    assert m["abstain_recall"] == pytest.approx(1 / 3)                  # 3 should abstain, 1 did
    assert m["citation_precision"] == pytest.approx(4 / 5)              # the claim on an abstain task cites
    #                                                                     no gold fact; the other 4 cite D1.S1
    assert m["robustness"] == 0.0 and m["n"]["robustness"] == 1         # the injection item failed
    assert m["parse_rate"] == pytest.approx(6 / 7) and m["abstain_rate"] == pytest.approx(2 / 7)
    assert set(m["correct_by_type"]) == {"answerable_1hop", "unanswerable", "injection"}


def test_citation_precision_is_exact_or_unknown():
    other = "<answer>\nCLAIM: I stayed at the mill all night on day 2. [D1.S2]\n</answer>"   # green, not the gold line
    recs = [record(A, tom_task(), CASE, with_parts=False), record(other, tom_task(), CASE, with_parts=False),
            record(C, tom_task(), CASE, with_parts=False)]          # C is red but cites the gold line D1.S1
    exact = compute(recs, cases={"c_elsie": CASE})
    assert exact["citation_precision"] == pytest.approx(2 / 3)
    assert compute(recs)["citation_precision"] is None              # no parts, no cases: unknown, never a guess
    assert "citation_precision" not in compute(recs)["ci95"]
    with_parts = [record(r, tom_task(), CASE) for r in (A, other, C)]
    assert compute(with_parts)["citation_precision"] == pytest.approx(2 / 3)   # same answer from reward parts


def test_bootstrap_resamples_whole_cases():
    # Case X: every answer right. Case Y: every answer wrong. Resampling by case can only give 0, 1/2 or 1.
    recs = [record(A, tom_task(), CASE, case_id="X") for _ in range(5)]
    recs += [record(C, tom_task(), CASE, case_id="Y") for _ in range(5)]
    m = compute(recs)
    assert m["answer_accuracy"] == 0.5 and m["n_cases"] == 2
    assert m["ci95"]["answer_accuracy"] == [0.0, 1.0]
    assert compute(recs) == m                                           # seeded: same CIs every run
    assert compute(recs, seed=1)["answer_accuracy"] == 0.5


def test_ci_contains_the_value():
    cases, tasks = build_split("val", 1000, 10)
    by_id = {c.case_id: c for c in cases}
    replies = [A if i % 3 else ABSTAIN for i in range(len(tasks))]      # a mostly wrong "model"
    m = compute([record(r, t, by_id[t.case_id]) for r, t in zip(replies, tasks)])
    for name, (lo, hi) in m["ci95"].items():
        assert lo <= m[name] <= hi, name
    assert not m["gates"]["support_rate"]["pass"]


def test_empty_denominators_and_failed_gates():
    m = compute([record(ABSTAIN, tom_task(abstain=True), CASE)])
    assert m["unsupported_claim_rate"] is None and m["citation_precision"] is None
    assert "unsupported_claim_rate" not in m["ci95"]
    assert not m["gates"]["min_items"]["pass"]
    assert compute([])["n_items"] == 0


def test_every_brief_metric_is_reported():
    assert {"unsupported_claim_rate", "answer_accuracy", "abstain_precision", "abstain_recall", "citation_precision",
            "robustness", "tokens_per_reply"} <= set(RATIOS)


def test_p1_interfaces_metrics_path():
    from archive import interfaces as I
    assert I.metrics([record(A, tom_task(), CASE)])["answer_accuracy"] == 1.0
