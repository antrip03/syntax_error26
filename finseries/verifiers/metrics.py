"""Pure numpy, deterministic metrics on integer basis-point return arrays.

Conventions (documented once, used everywhere):
  * r[t]  = return of day t in integer basis points.
  * c[t]  = cumulative level = sum(r[0..t]); c[-1] is 0 by definition (additive, not compounded).
  * windows [a, b] are 0-based and INCLUSIVE.
"""
import numpy as np


def levels(r):
    return np.cumsum(np.asarray(r, dtype=np.int64))


def ret(r, a, b):
    """Cumulative (summed) return over [a, b], in bps."""
    return int(np.sum(np.asarray(r)[a:b + 1]))


def mean_ret(r, a, b):
    return float(np.mean(np.asarray(r)[a:b + 1]))


def vol(r, a, b):
    """Realized volatility over [a, b]: sqrt(sum of squared returns), in bps."""
    x = np.asarray(r)[a:b + 1].astype(np.float64)
    return float(np.sqrt(np.sum(x * x)))


def hi(c, a, b):
    """Highest cumulative level inside [a, b] (levels measured from the series start)."""
    return int(np.max(c[a:b + 1]))


def lo(c, a, b):
    return int(np.min(c[a:b + 1]))


def dd(c, a, b, s):
    """Largest drawdown reached at any t in [a, b], with the running peak taken over [s, t] (s <= a)."""
    seg = np.asarray(c[s:b + 1])
    peak = np.maximum.accumulate(seg)
    return int(np.max((peak - seg)[a - s:]))


def mdd(c, a, b):
    """Max drawdown of the window [a, b] (peak taken inside the window), in bps."""
    return dd(c, a, b, a)
