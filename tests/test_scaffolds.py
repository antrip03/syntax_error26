import numpy as np
import pytest

from finseries import scaffolds
from finseries.data import synthetic
from finseries.rewards import combine
from finseries.rewards.outcome import is_correct
from finseries.scaffolds.base import SYSTEM
from finseries.tasks import generate as G
from finseries.tasks import templates as T
from finseries.tokens import count_tokens

ARMS = ["flat", "chunk", "event"]
BUDGET = {"completion": 480, "prompt": 600}


class W:  # minimal window
    def __init__(self, r, i):
        self.r, self.source, self.asset, self.start, self.start_date = r, "synthetic", "synth", i, None


def windows(n, lo, hi, seed0=777000):
    rng = np.random.default_rng(seed0)
    return [W(synthetic.generate(int(rng.integers(lo, hi + 1)), seed0 + i).r.tolist(), seed0 + i) for i in range(n)]


@pytest.fixture(scope="module")
def tasks():
    return G.generate_split(windows(500, 60, 80), 1000, "train", 3, budget=BUDGET)


def test_enough_tasks_and_coverage(tasks):
    assert len(tasks) == 1000
    assert {t.family for t in tasks} == set(G.DEPTHS)
    assert {t.depth for t in tasks} == {1, 2, 3, 4}


@pytest.mark.parametrize("arm", ARMS)
def test_gold_traces_perfect(tasks, arm):
    sc = scaffolds.get(arm)
    for t in tasks:
        text = sc.gold_trace(t)
        pt = sc.parse(text)
        assert pt.has_think and pt.has_answer and not pt.truncated
        assert all(sc.check_steps(pt, t)), (t.id, text)
        assert abs(sc.final_answer(pt) - t.answer) <= max(0.51, t.tolerance_abs)
        assert is_correct(t, pt)
        assert sc.header_ok(pt)


@pytest.mark.parametrize("arm", ARMS)
def test_gold_rewards_are_maximal(tasks, arm):
    sc = scaffolds.get(arm)
    for t in tasks[:200]:
        r = combine.compute(sc, t, sc.gold_trace(t), n_tokens=300, bundle="outcome_process")
        assert r["outcome"] == r["process"] == r["format"] == r["consistency"] == 1.0
        assert r["total"] == pytest.approx(1.0)


@pytest.mark.parametrize("arm", ARMS)
def test_prompt_and_completion_budget(tasks, arm):
    sc = scaffolds.get(arm)
    sys_tokens = count_tokens(SYSTEM)
    for t in tasks[:150]:
        n = count_tokens(sc.build_prompt(t)) + sys_tokens
        assert n <= 640, (t.id, n)
        assert count_tokens(sc.gold_trace(t)) <= 520


def _slopes(family):
    ws = windows(40, 250, 500, seed0=888000)
    tasks = [G.make_task(w, family, 1, np.random.default_rng(i), "test_len", i) for i, w in enumerate(ws)]
    stats = {}
    for arm in ARMS:
        sc = scaffolds.get(arm)
        xs = np.array([t.length for t in tasks])
        ys = np.array([sum(1 for s in sc.parse(sc.gold_trace(t)).steps if s.kind == "step") for t in tasks])
        stats[arm] = (round(float(np.polyfit(xs, ys, 1)[0]), 3), float(ys.mean()))
    return stats


def test_step_count_scaling():
    """flat ~ length/5 steps, chunk ~ length/10, event ~ number of regimes (sub-linear in length)."""
    stats = _slopes("windowed_stats")
    print("windowed_stats steps-vs-length slope / mean:", stats)
    assert stats["flat"][0] > stats["chunk"][0] > 0.05
    assert stats["event"][0] < stats["chunk"][0]
    # drawdown needs (hi,lo,mdd) triples per chunk, so chunk is not cheaper than flat there; reported, not asserted
    print("running_drawdown steps-vs-length slope / mean:", _slopes("running_drawdown"))


def test_answers_independent_of_scaffold(tasks):
    for t in tasks[:100]:
        assert T.solve(t.get_series(), t.program) == pytest.approx(t.answer)
