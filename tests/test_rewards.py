"""Rewards (archive/rewards/terms.py, combine.py): the explainer's A to F answers, then every term on its own."""
import json
from pathlib import Path

import pytest

from archive.rewards import terms
from archive.rewards.combine import WEIGHTS, reward
from archive.schemas import Case, GoldClaim, Gold, Task
from archive.verifiers.checker import check, context_for
from archive.verifiers.parse import ABSTAIN

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
H1 = {"id": "H1", "from": "tom", "day": 2, "text": "I stayed at the mill all night.", "facts": ["F2"]}

@pytest.fixture(scope="module")
def case():
    return Case.model_validate(json.loads(FIXTURE.read_text()))

def task(villager="tom", claims=(("I shut the mill at sunset on day 2.", "D1.S1", "F1"),), heard=(), kind=None):
    gold = Gold(abstain=not claims, claims=[GoldClaim(text=t, cites=[c], facts=[f]) for t, c, f in claims])
    return Task(task_id="t", case_id="c_elsie", villager=villager, split="train", heard=list(heard),
                type=kind or ("answerable_1hop" if claims else "unanswerable"), question="q", gold=gold)

A = "<answer>\nCLAIM: I shut the mill at dusk on day 2. [D1.S1]\n</answer>"
B = A.replace("</answer>", "CLAIM: I locked the guildhall door at night. [D1.S1]\n</answer>")
C = "<answer>\nCLAIM: I shut the mill at midnight on day 2. [D1.S1]\n</answer>"
D = ABSTAIN
E = "Closed it at dusk, as usual!"

@pytest.mark.parametrize("reply, n_tokens, total, parts", [
    (A, None, 0.85, dict(correct=1, support=1, cite=1, abstain=0, fmt=1, length=0)),
    (B, None, 0.70, dict(correct=1, support=0.5, cite=1, abstain=0, fmt=1, length=0)),
    (C, None, 0.20, dict(correct=0, support=0, cite=1, abstain=0, fmt=1, length=0)),
    (D, None, -0.05, dict(correct=0, support=0, cite=0, abstain=-1, fmt=1, length=0)),
    (E, None, 0.00, dict(correct=0, support=0, cite=0, abstain=0, fmt=0, length=0)),
    (A, 228, 0.75, dict(correct=1, support=1, cite=1, abstain=0, fmt=1, length=-0.1)),
])
def test_explainer_answers_a_to_f(case, reply, n_tokens, total, parts):
    r = reward(reply, task(), case, n_tokens=n_tokens)
    assert r["total"] == pytest.approx(total)
    assert {k: r[k] for k in parts} == pytest.approx(parts)

def test_f_with_estimated_tokens(case):
    long_a = A.replace("<answer>\n", "<answer>\n# " + "Flour, flour, so much flour in the mill today. " * 17 + "\n")
    est = terms.estimate_tokens(long_a)
    assert 220 <= est <= 236
    assert reward(long_a, task(), case)["total"] == pytest.approx(0.75, abs=0.03)

def test_outcome_bundle(case):
    assert reward(A, task(), case, bundle="outcome")["total"] == pytest.approx(0.80)
    assert reward(D, task(), case, bundle="outcome")["total"] == pytest.approx(-0.10)
    assert set(WEIGHTS["outcome"]) == {"correct", "abstain", "fmt"}
    with pytest.raises(ValueError):
        reward(A, task(), case, bundle="nope")

def test_correct_abstain_scores_like_a_perfect_answer(case):
    t = task(claims=())
    r = reward(D, t, case)
    assert (r["correct"], r["support"], r["cite"], r["abstain"], r["fmt"]) == (1, 1, 1, 1, 1)
    assert r["total"] == pytest.approx(1.0) and r["abstained"] == 1.0

def test_claims_on_an_abstain_task(case):
    r = reward(A, task(claims=()), case)
    assert r["abstain"] == -1 and r["correct"] == 0 and r["support"] == 1
    assert reward(E, task(claims=()), case)["abstain"] == 0

def test_correct_needs_every_gold_fact(case):
    t = task("ivy", claims=(("Mara was at the smithy in the evening on day 2.", "D5.S1", "F8"),
                            ("Mara was at the smithy at midnight on day 2.", "D5.S1", "F9")))
    both = "<answer>\nCLAIM: Mara was at the smithy from evening to midnight on day 2. [D5.S1]\n</answer>"
    one = "<answer>\nCLAIM: Mara was at the smithy at midnight on day 2. [D5.S1]\n</answer>"
    assert reward(both, t, case)["correct"] == 1 and reward(one, t, case)["correct"] == 0

def test_hearsay_is_correct_through_the_heard_fact(case):
    t = task("nell", claims=(('Tom said: "I stayed at the mill all night."', "H1", "F2"),), heard=[H1])
    good = '<answer>\nCLAIM: Tom said: "I stayed at the mill all night." [H1]\n</answer>'
    unattributed = "<answer>\nCLAIM: Tom stayed at the mill all night. [H1]\n</answer>"
    assert reward(good, t, case)["total"] == pytest.approx(0.85)
    assert reward(unattributed, t, case)["correct"] == 0

def test_cite_counts_every_cited_id(case):
    other = "<answer>\nCLAIM: I stayed at the mill all night on day 2. [D1.S2]\n</answer>"
    assert reward(other, task(), case)["cite"] == 0
    mixed = A.replace("</answer>", "CLAIM: I stayed at the mill all night on day 2. [D1.S2]\n</answer>")
    assert reward(mixed, task(), case)["cite"] == pytest.approx(0.5)
    hidden = "<answer>\nCLAIM: I went to the guildhall. [D7.S1]\n</answer>"
    assert reward(hidden, task(), case)["cite"] == 0

def test_truncated_reply_is_never_correct(case):
    cut = "<answer>\nCLAIM: I shut the mill at dusk on day 2. [D1.S1]\nCLAIM: I sta"
    assert terms.truncated(cut) and not terms.truncated(A) and not terms.truncated(D)
    assert reward(cut, task(), case)["correct"] == 0

@pytest.mark.parametrize("tokens, value", [(0, 0), (200, 0), (228, -0.1), (256, -0.2), (900, -0.2)])
def test_length(case, tokens, value):
    assert reward(A, task(), case, n_tokens=tokens)["length"] == pytest.approx(value)

def test_terms_work_alone_and_are_pure(case):
    t = task()
    ctx = context_for(case, "tom")
    chk = check(B, ctx)
    for name in ["correct", "support", "cite", "abstain", "fmt", "length"]:
        f = getattr(terms, name)
        assert f(B, t, ctx) == f(B, t, ctx, chk) == f(B, t, ctx)

def test_dict_rows_and_empty_replies(case):
    row = task().model_dump(mode="json", by_alias=True)
    assert reward(A, row, case)["total"] == pytest.approx(0.85)
    assert reward("", row, case)["total"] == 0 and reward(None, row, case)["fmt"] == 0

def test_token_estimate_is_calibrated():
    transformers = pytest.importorskip("transformers")
    try:
        tok = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B")
    except OSError as e:
        pytest.skip(f"tokenizer unavailable: {e}")
    import random
    rng = random.Random(3)
    lines = ["# Ah, the flour everywhere, so sorry!", "CLAIM: I saw Tom by the chapel at midnight on day 2. [D2.S1]",
             'CLAIM: Gus said: "I saw the scribe by the inn at night on day 2." [H1]', "# Hm. Cold night.",
             "CLAIM: Mara was at the smithy from evening to midnight on day 2. [D5.S1]"]
    for _ in range(100):
        text = "<answer>\n" + "\n".join(rng.choice(lines) for _ in range(rng.randint(10, 16))) + "\n</answer>"
        real = len(tok(text).input_ids)
        if 180 <= real <= 280:
            assert abs(terms.estimate_tokens(text) - real) / real <= 0.12, (real, terms.estimate_tokens(text))

def test_p1_interfaces_now_use_p2_modules(case):
    from archive import interfaces as I
    assert I.MODE == "p2"
    row = task().model_dump(mode="json", by_alias=True)
    parts = I.reward(A, row, {"c_elsie": case})
    assert parts["total"] == pytest.approx(0.85) and I.is_correct(parts)
    assert I.is_correct(I.reward(D, task(claims=()).model_dump(mode="json"), {"c_elsie": case}))
    assert not I.is_correct(I.reward(C, row, {"c_elsie": case}))
    assert I.gold(row).startswith("<answer>")
