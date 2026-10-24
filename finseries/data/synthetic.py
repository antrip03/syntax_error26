"""Regime-switching return generator with KNOWN true regime boundaries."""
from dataclasses import dataclass

import numpy as np

# name: (daily mean bps, daily sigma bps)
REGIMES = {
    "calm": (0.0, 30.0),
    "bull": (12.0, 45.0),
    "bear": (-18.0, 130.0),
    "rally_vol": (20.0, 110.0),
}
NAMES = list(REGIMES)
MEAN_DURATION = 18
MIN_DURATION = 8


@dataclass
class SynthSeries:
    r: np.ndarray
    starts: list      # true regime start indices (first is 0)
    regimes: list     # regime name per start

    def vol_class_starts(self, hv_sigma=100.0):
        """True change points (excluding 0) where the high/low-vol class flips -- what the segmenter can see."""
        out, prev = [], None
        for s, name in zip(self.starts, self.regimes):
            cls = REGIMES[name][1] >= hv_sigma
            if prev is not None and cls != prev:
                out.append(s)
            prev = cls
        return out


def generate(n, seed):
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    starts, regimes = [], []
    t, cur = 0, None
    while t < n:
        choices = [x for x in NAMES if x != cur]
        cur = choices[rng.integers(len(choices))]
        dur = MIN_DURATION + int(rng.geometric(1.0 / (MEAN_DURATION - MIN_DURATION)))
        dur = min(dur, n - t)
        mu, sig = REGIMES[cur]
        z = rng.standard_t(5, size=dur) / np.sqrt(5 / 3)   # unit-variance fat tails
        r[t:t + dur] = mu + sig * z
        starts.append(t)
        regimes.append(cur)
        t += dur
    return SynthSeries(np.rint(r).astype(np.int64), starts, regimes)
