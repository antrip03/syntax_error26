"""Event detectors: moving-average crossovers and threshold breaches.

Both counts are ADDITIVE over consecutive windows (a crossover at day t is attributed to the window
containing t and looks one day back globally), which lets scaffolds decompose a window into pieces.
"""
import numpy as np


def count_breach(r, a, b, thr):
    """Days t in [a, b] with |r[t]| > thr (bps)."""
    return int(np.sum(np.abs(np.asarray(r)[a:b + 1]) > thr))


def _up_flags(c, fast, slow):
    """up[t] = SMA_fast(level) > SMA_slow(level), exact integer comparison; False before t = slow-1."""
    c = np.asarray(c, dtype=np.int64)
    n = len(c)
    cs = np.concatenate([[0], np.cumsum(c)])
    up = np.zeros(n, dtype=bool)
    for t in range(slow - 1, n):
        f = cs[t + 1] - cs[t + 1 - fast]
        s = cs[t + 1] - cs[t + 1 - slow]
        up[t] = f * slow > s * fast
    return up


def count_cross(c, a, b, fast, slow):
    """Number of days t in [a, b], t >= slow, where sign(SMA_fast - SMA_slow) of the level flips vs t-1."""
    up = _up_flags(c, fast, slow)
    lo_t = max(a, slow)
    if lo_t > b:
        return 0
    return int(np.sum(up[lo_t:b + 1] != up[lo_t - 1:b]))
