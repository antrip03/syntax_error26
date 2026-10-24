"""Temporal, leakage-free split logic.

Pre-cutoff history of every asset is tiled in blocks of `block_len` days; each block belongs to exactly ONE of
train / val / test_id / test_len, so windows of different splits never overlap in time. test_period windows are
drawn only from data AFTER the cutoff (includes the 2020 crash and 2022). Synthetic series use disjoint seed ranges.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import synthetic

SPLITS = ["train", "val", "test_id", "test_len", "test_period", "test_adv"]


@dataclass
class Window:
    split: str
    source: str                 # real | synthetic
    asset: str                  # ticker or "synth"
    start: int                  # index into the asset's r array (real) or synthetic seed (synthetic)
    r: list
    start_date: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @property
    def span(self):
        return (self.asset, self.start, self.start + len(self.r) - 1) if self.source == "real" else None


def _assign_blocks(real, cfg, rng):
    blocks = []
    cutoff = cfg["train_cutoff"]
    for asset, (dates, r) in sorted(real.items()):
        n_pre = int(np.sum(dates < cutoff))
        for k in range(n_pre // cfg["block_len"]):
            blocks.append((asset, k * cfg["block_len"], (k + 1) * cfg["block_len"]))
    order = rng.permutation(len(blocks))
    names = list(cfg["block_split_frac"])
    fr = np.array([cfg["block_split_frac"][n] for n in names])
    bounds = np.round(np.cumsum(fr / fr.sum()) * len(blocks)).astype(int)
    out = {n: [] for n in names}
    for rank, bi in enumerate(order):
        out[names[int(np.searchsorted(bounds, rank, side="right"))]].append(blocks[bi])
    return out


def _sample_len(rng, lo_hi):
    return int(rng.integers(lo_hi[0], lo_hi[1] + 1))


def build_windows(cfg, real):
    """cfg = full data.yaml. Returns {split: [Window]}."""
    rc, sc = cfg["real"], cfg["splits"]
    rng = np.random.default_rng(cfg["seed"])
    blocks = _assign_blocks(real, rc, rng)
    out = {s: [] for s in SPLITS}
    for split, bl in blocks.items():
        for asset, b0, b1 in bl:
            dates, r = real[asset]
            for _ in range(sc[split]["real_windows_per_block"]):
                L = _sample_len(rng, sc[split]["len"])
                st = int(rng.integers(b0, b1 - L + 1))
                out[split].append(Window(split, "real", asset, st, r[st:st + L].tolist(), str(dates[st])))
    for asset, (dates, r) in sorted(real.items()):          # test_period: strictly after the cutoff
        idx0 = int(np.sum(dates < rc["train_cutoff"]))
        m = sc["test_period"]["real_windows_per_asset"]
        for j in range(m):
            L = _sample_len(rng, sc["test_period"]["len"])
            lo = idx0 + int(j * (len(r) - idx0 - L) / max(m - 1, 1))
            st = int(np.clip(lo + rng.integers(0, 20), idx0, len(r) - L))
            out["test_period"].append(Window("test_period", "real", asset, st, r[st:st + L].tolist(), str(dates[st])))
    for split in ["train", "val", "test_id", "test_len", "test_adv"]:
        base = cfg["synthetic"]["seed_base"][split]
        for i in range(sc[split].get("synthetic", 0)):
            L = _sample_len(rng, sc[split]["len"])
            ss = synthetic.generate(L, base + i)
            out[split].append(Window(split, "synthetic", "synth", base + i, ss.r.tolist(),
                                     meta={"starts": ss.starts, "regimes": ss.regimes}))
    return out


def find_overlaps(windows_by_split):
    """Pairs of real windows from DIFFERENT splits that overlap in time on the same asset."""
    spans = [(w.split, *w.span) for ws in windows_by_split.values() for w in ws if w.source == "real"]
    bad = []
    by_asset = {}
    for sp, asset, a, b in spans:
        by_asset.setdefault(asset, []).append((a, b, sp))
    for asset, lst in by_asset.items():
        lst.sort()
        for i, (a, b, sp) in enumerate(lst):
            for a2, b2, sp2 in lst[i + 1:]:
                if a2 > b:
                    break
                if sp != sp2:
                    bad.append((asset, sp, (a, b), sp2, (a2, b2)))
    return bad
