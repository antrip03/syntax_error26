"""Shared OP REGISTRY: the single source of truth for tasks, gold traces, step checking and rewards.

Step grammar (one line each):   S<k>: <op>(<args>) = <value>
  primitive ops (integer args):
    ret(a,b) vol(a,b) mean_ret(a,b) hi(a,b,s) lo(a,b,s) mdd(a,b) dd(a,b,s)   (levels counted from day s: C_t - C_{s-1})
    count_breach(a,b,thr) count_cross(a,b,fast,slow)
    seg_stat(i,op)      op in {ret,vol,mdd} applied to canonical segment i
  aggregation over the model's OWN earlier step values:
    agg(<agg_op>, S<j>, S<k>, ...)   agg_op in {sum,max,min,mean,diff,rss,argmax,mdd}
"""
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import events, metrics
from .segmenter import segment


class OpError(ValueError):
    pass


class Series:
    """A return series in integer bps plus cached derived arrays."""

    def __init__(self, r):
        self.r = np.asarray(r, dtype=np.int64)
        self.c = metrics.levels(self.r)
        self.n = len(self.r)
        self._segs = None

    @property
    def segs(self):
        if self._segs is None:
            self._segs = segment(self.r)
        return self._segs


def _win(s, a, b):
    if not (0 <= a <= b < s.n):
        raise OpError(f"window [{a},{b}] outside series of {s.n}")


def _ret(s, a, b): _win(s, a, b); return metrics.ret(s.r, a, b)
def _vol(s, a, b): _win(s, a, b); return metrics.vol(s.r, a, b)
def _mean(s, a, b): _win(s, a, b); return metrics.mean_ret(s.r, a, b)
def _base(s, st):
    """Level baseline: C_{st-1} (0 for st == 0), so hi/lo are cumulative returns counted from day st."""
    return int(s.c[st - 1]) if st > 0 else 0


def _hi(s, a, b, st):
    _win(s, a, b)
    if not 0 <= st <= a:
        raise OpError("hi start must satisfy 0 <= s <= a")
    return metrics.hi(s.c, a, b) - _base(s, st)


def _lo(s, a, b, st):
    _win(s, a, b)
    if not 0 <= st <= a:
        raise OpError("lo start must satisfy 0 <= s <= a")
    return metrics.lo(s.c, a, b) - _base(s, st)
def _mdd(s, a, b): _win(s, a, b); return metrics.mdd(s.c, a, b)


def _dd(s, a, b, st):
    _win(s, a, b)
    if not 0 <= st <= a:
        raise OpError("dd start must satisfy 0 <= s <= a")
    return metrics.dd(s.c, a, b, st)


def _breach(s, a, b, thr): _win(s, a, b); return events.count_breach(s.r, a, b, thr)


def _cross(s, a, b, fast, slow):
    _win(s, a, b)
    if not 1 <= fast < slow:
        raise OpError("need 1 <= fast < slow")
    return events.count_cross(s.c, a, b, fast, slow)


SEG_OPS = ("ret", "vol", "mdd")


def _seg_stat(s, i, op):
    if not 0 <= i < len(s.segs):
        raise OpError(f"no segment {i}")
    if op not in SEG_OPS:
        raise OpError(f"bad seg op {op}")
    g = s.segs[i]
    return PRIMS[op].fn(s, g.start, g.end)


@dataclass(frozen=True)
class Prim:
    name: str
    nargs: int
    fn: Callable


PRIMS = {p.name: p for p in [
    Prim("ret", 2, _ret), Prim("vol", 2, _vol), Prim("mean_ret", 2, _mean), Prim("hi", 3, _hi),
    Prim("lo", 3, _lo), Prim("mdd", 2, _mdd), Prim("dd", 3, _dd), Prim("count_breach", 3, _breach),
    Prim("count_cross", 4, _cross), Prim("seg_stat", 2, _seg_stat),
]}

AGG_OPS = ("sum", "max", "min", "mean", "diff", "rss", "argmax", "mdd")


def agg(op, vals):
    """Aggregate a list of numbers. `mdd` takes (hi, lo, mdd) triples of consecutive pieces."""
    v = [float(x) for x in vals]
    if not v:
        raise OpError("empty agg")
    if op == "sum": return sum(v)
    if op == "max": return max(v)
    if op == "min": return min(v)
    if op == "mean": return sum(v) / len(v)
    if op == "diff":
        if len(v) != 2:
            raise OpError("diff needs exactly 2 values")
        return v[0] - v[1]
    if op == "rss": return float(np.sqrt(sum(x * x for x in v)))
    if op == "argmax": return float(int(np.argmax(v)))
    if op == "mdd":
        if len(v) % 3:
            raise OpError("agg(mdd) needs (hi,lo,mdd) triples")
        peak, best = None, 0.0
        for h, l, m in zip(v[0::3], v[1::3], v[2::3]):
            best = max(best, m)
            if peak is not None:
                best = max(best, peak - l)
            peak = h if peak is None else max(peak, h)
        return best
    raise OpError(f"unknown agg op {op}")


def eval_prim(series, name, args):
    """Evaluate primitive `name` on already-typed args (ints; seg_stat's second arg is a str)."""
    if name not in PRIMS:
        raise OpError(f"unknown op {name}")
    p = PRIMS[name]
    if len(args) != p.nargs:
        raise OpError(f"{name} takes {p.nargs} args")
    return p.fn(series, *args)


def fmt(x):
    """Canonical number text for a step value."""
    x = float(x)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.1f}"
