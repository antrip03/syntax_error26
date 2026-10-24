"""One-off: download daily adjusted closes with yfinance into data_prepared/<TICKER>.csv (date,close).
Run locally (needs internet), then upload data_prepared/ as a Kaggle Dataset. Never called at runtime."""
import argparse
import os

import yaml

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))["real"]
    import yfinance as yf
    os.makedirs(cfg["dir"], exist_ok=True)
    for t in cfg["tickers"]:
        d = yf.download(t, start=cfg["start"], end=cfg["end"], progress=False, auto_adjust=True)
        close = d["Close"].squeeze().dropna()
        close.rename("close").to_csv(os.path.join(cfg["dir"], f"{t}.csv"), index_label="date")
        print(t, len(close), close.index[0].date(), close.index[-1].date())
