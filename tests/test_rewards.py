import numpy as np
import pytest

from finseries import scaffolds
from finseries.rewards import combine
from finseries.rewards.outcome import outcome_reward
from finseries.tasks import adversarial, generate as G
from tests.test_scaffolds import BUDGET, windows


@pytest.fixture(scope="module")
def tasks():
    return G.generate_split(windows(120, 60, 80, seed0=999000), 120, "test_adv", 5, budget=BUDGET)


@pytest.mark.parametrize("arm", ["flat", "chunk", "event"])
def test_adversarial_probes(tasks, arm):
    sc = scaffolds.get(arm)
    for t in tasks:
        for name, text, expect in adversarial.probes(sc, t):
            r = combine.compute(sc, t, text, n_tokens=300, bundle="outcome_process")
            if expect == "correct":
                assert r["outcome"] == 1.0, (name, t.id)
            else:
                assert r["outcome"] == 0.0, (name, t.id, r)
                assert r["total"] < 0.55, (name, t.id, r)   # no probe may collect a high total


def test_spam_process_is_gated(tasks):
    sc = scaffolds.get("flat")
    for t in tasks[:30]:
        spam = dict((n, x) for n, x, _ in adversarial.probes(sc, t))["spam_valid_steps"]
        assert combine.compute(sc, t, spam, 300)["process"] < 0.1


def test_outcome_decay(tasks):
    sc = scaffolds.get("chunk")
    t = next(x for x in tasks if abs(x.answer) > 500)
    mk = lambda v: sc.parse(f"<think>\n</think>\n<answer>{v}</answer>")
    g = t.answer
    assert outcome_reward(t, mk(g)) == 1.0
    mid = outcome_reward(t, mk(g * 1.03))
    assert 0.0 < mid < 1.0
    assert outcome_reward(t, mk(g * 1.06)) == 0.0


def test_length_penalty_and_bundles(tasks):
    sc = scaffolds.get("flat")
    t = tasks[0]
    gold = sc.gold_trace(t)
    a = combine.compute(sc, t, gold, n_tokens=300, bundle="outcome_only")
    b = combine.compute(sc, t, gold, n_tokens=1024, bundle="outcome_process")
    assert a["total"] == pytest.approx(1.0) and b["length"] == pytest.approx(-0.2)
