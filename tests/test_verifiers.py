import numpy as np
import pytest

from finseries.data import synthetic
from finseries.verifiers import events, metrics, ops, segmenter

R = np.array([10, -20, 30, -40, 50, 5, -5, 100, -300, 20])  # hand-computed below
C = metrics.levels(R)  # 10 -10 20 -20 30 35 30 130 -170 -150


def test_levels_ret_vol():
    assert C.tolist() == [10, -10, 20, -20, 30, 35, 30, 130, -170, -150]
    assert metrics.ret(R, 2, 4) == 40
    assert metrics.vol(R, 0, 1) == pytest.approx(np.sqrt(100 + 400))
    assert metrics.mean_ret(R, 0, 3) == pytest.approx(-5.0)


def test_hi_lo_dd():
    assert metrics.hi(C, 0, 4) == 30 and metrics.lo(C, 0, 4) == -20
    # window 0..4 levels 10,-10,20,-20,30: peaks 10,10,20,20,30 -> dd 0,20,0,40,0
    assert metrics.mdd(C, 0, 4) == 40
    # whole series: peak 130 then -170 => 300
    assert metrics.mdd(C, 0, 9) == 300
    # dd on days 5..9 with peak taken from day 0 (level 35 at day5, peak 35 until day 7 -> 130) => 300
    assert metrics.dd(C, 5, 9, 0) == 300
    # same days with the peak starting at day 5: peaks 35,35,130,130,130 -> max dd = 300
    assert metrics.dd(C, 5, 6, 5) == 5
    # peak from day 0 (30 at day4 is lower than 35 at day5 so nothing changes) vs from day 3
    assert metrics.dd(C, 4, 6, 0) == 5


def test_breach_and_cross():
    assert events.count_breach(R, 0, 9, 30) == 4  # |40|,|50|,|100|,|300|
    c = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4], dtype=np.int64)
    # fast=2, slow=4: manual flags
    up = events._up_flags(c, 2, 4)
    sma2 = [np.mean(c[t - 1:t + 1]) for t in range(3, 12)]
    sma4 = [np.mean(c[t - 3:t + 1]) for t in range(3, 12)]
    manual = [f > s for f, s in zip(sma2, sma4)]
    assert up[3:].tolist() == manual
    n = sum(manual[i] != manual[i - 1] for i in range(1, len(manual)))
    assert events.count_cross(c, 0, 11, 2, 4) == n


def test_event_counts_are_additive():
    rng = np.random.default_rng(0)
    r = (rng.standard_normal(80) * 60).astype(int)
    c = metrics.levels(r)
    for a, m, b in [(0, 30, 79), (10, 45, 70)]:
        assert events.count_cross(c, a, b, 3, 8) == events.count_cross(c, a, m, 3, 8) + events.count_cross(c, m + 1, b, 3, 8)
        assert events.count_breach(r, a, b, 50) == events.count_breach(r, a, m, 50) + events.count_breach(r, m + 1, b, 50)


def test_drawdown_decomposition_identity():
    rng = np.random.default_rng(1)
    for _ in range(50):
        r = (rng.standard_normal(60) * 80).astype(int)
        s = ops.Series(r)
        cuts = sorted(rng.choice(np.arange(1, 59), 4, replace=False).tolist())
        edges = [0] + [c + 1 for c in cuts] + [60]
        pieces = [(edges[i], edges[i + 1] - 1) for i in range(len(edges) - 1)]
        vals = []
        for a, b in pieces:
            vals += [metrics.hi(s.c, a, b), metrics.lo(s.c, a, b), metrics.mdd(s.c, a, b)]
        assert ops.agg("mdd", vals) == metrics.mdd(s.c, 0, 59)
        assert max(metrics.dd(s.c, a, b, 0) for a, b in pieces) == metrics.mdd(s.c, 0, 59)


def test_agg_ops():
    assert ops.agg("sum", [1, 2, 3]) == 6 and ops.agg("diff", [5, 2]) == 3
    assert ops.agg("rss", [3, 4]) == 5 and ops.agg("argmax", [1, 9, 3]) == 1
    with pytest.raises(ops.OpError):
        ops.agg("diff", [1, 2, 3])


def test_window_validation():
    s = ops.Series(R)
    with pytest.raises(ops.OpError):
        ops.eval_prim(s, "ret", [5, 20])
    with pytest.raises(ops.OpError):
        ops.eval_prim(s, "ret", [5, 2])


def test_segmenter_deterministic_and_covers():
    ss = synthetic.generate(90, 5)
    a, b = segmenter.segment(ss.r), segmenter.segment(ss.r)
    assert a == b
    assert a[0].start == 0 and a[-1].end == 89
    assert all(x.end + 1 == y.start for x, y in zip(a, a[1:]))
    assert all(x.end - x.start + 1 >= segmenter.MIN_LEN for x in a) or len(a) == 1


def test_segmenter_recovers_synthetic_boundaries():
    f1s = []
    for seed in range(60):
        ss = synthetic.generate(120, 9000 + seed)
        segs = segmenter.segment(ss.r)
        f1s.append(segmenter.boundary_f1([g.start for g in segs[1:]], ss.vol_class_starts(), tol=4))
    mean = float(np.mean(f1s))
    print(f"\nsegmenter boundary F1 (vol-class boundaries, tol=4): {mean:.3f}")
    assert mean > 0.45
