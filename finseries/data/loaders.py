"""Read prepared CSVs (date,close) of real prices -> integer-bps return arrays. Never fetches live data."""
import os

import numpy as np
import pandas as pd


def load_asset(path):
    """Returns (dates: np.ndarray[str] aligned with r, r: int64 bps array). r[t] = return from day t-1 to t."""
    df = pd.read_csv(path)
    close = df["close"].to_numpy(dtype=np.float64)
    r = np.rint(1e4 * (close[1:] / close[:-1] - 1.0)).astype(np.int64)
    dates = df["date"].astype(str).str.slice(0, 10).to_numpy()[1:]
    return dates, r


def load_real(cfg):
    """cfg = data.yaml['real'] -> {ticker: (dates, r)}"""
    out = {}
    for t in cfg["tickers"]:
        p = os.path.join(cfg["dir"], f"{t}.csv")
        if os.path.exists(p):
            out[t] = load_asset(p)
    if not out:
        raise FileNotFoundError(f"no prepared CSVs found in {cfg['dir']}; run scripts/prepare_data.py")
    return out
