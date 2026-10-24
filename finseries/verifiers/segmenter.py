"""Deterministic regime segmentation (the ground truth for the `event` scaffold).

RULE (fully specified, nothing learned):
  1. s[t] = population std of r over the trailing window r[max(0,t-4)..t]  (5 days; s[0] := s[1]).
  2. high-volatility day:  s[t] > 1.25 * median(s).   Label hv, otherwise lv.
  3. Take maximal runs of equal vol label. Repeatedly merge the FIRST run shorter than MIN_LEN=6 into its
     left neighbour (or right neighbour if it is the first run); merge adjacent equal-label runs.
  4. Trend label per segment from its summed return R over length L, sigma = population std of the full series:
        up if R >  0.5*sigma*sqrt(L),  down if R < -0.5*sigma*sqrt(L),  else flat.
A segment is (start, end, trend, vol) with inclusive 0-based bounds.
"""
from typing import NamedTuple

import numpy as np

W = 5
MIN_LEN = 6
HV_MULT = 1.25
TREND_K = 0.5


class Segment(NamedTuple):
    start: int
    end: int
    trend: str
    vol: str

    def text(self):
        return f"({self.start},{self.end},{self.trend},{self.vol})"


def rolling_std(r):
    r = np.asarray(r, dtype=np.float64)
    n = len(r)
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = np.std(r[max(0, t - W + 1):t + 1])
    if n > 1:
        s[0] = s[1]
    return s


def _runs(labels):
    runs = []
    for t, lab in enumerate(labels):
        if runs and runs[-1][2] == lab:
            runs[-1][1] = t
        else:
            runs.append([t, t, lab])
    return runs


def _merge_equal(runs):
    out = []
    for run in runs:
        if out and out[-1][2] == run[2]:
            out[-1][1] = run[1]
        else:
            out.append(list(run))
    return out


def segment(r):
    r = np.asarray(r, dtype=np.int64)
    n = len(r)
    if n == 0:
        return []
    s = rolling_std(r)
    thr = HV_MULT * float(np.median(s))
    labels = ["hv" if x > thr else "lv" for x in s]
    runs = _runs(labels)
    while len(runs) > 1:
        i = next((j for j, x in enumerate(runs) if x[1] - x[0] + 1 < MIN_LEN), None)
        if i is None:
            break
        if i > 0:
            runs[i - 1][1] = runs[i][1]
        else:
            runs[1][0] = runs[0][0]
        del runs[i]
        runs = _merge_equal(runs)
    sigma = float(np.std(r))
    segs = []
    for a, b, vol_lab in runs:
        total = float(np.sum(r[a:b + 1]))
        band = TREND_K * sigma * np.sqrt(b - a + 1)
        trend = "up" if total > band else "down" if total < -band else "flat"
        segs.append(Segment(a, b, trend, vol_lab))
    return segs


def boundary_f1(pred_starts, true_starts, tol=3):
    """F1 of predicted vs true change points (segment starts excluding index 0), matched within +-tol days."""
    pred, true = sorted(pred_starts), sorted(true_starts)
    used, tp = set(), 0
    for p in pred:
        for j, t in enumerate(true):
            if j not in used and abs(p - t) <= tol:
                used.add(j)
                tp += 1
                break
    prec = tp / len(pred) if pred else 1.0 if not true else 0.0
    rec = tp / len(true) if true else 1.0 if not pred else 0.0
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)
