"""Curation through CuratorKIT (serve env; needs SGLang serving the untrained model).

python -m archive.train.curate --config configs/curate.yaml [key=value ...]

Writes to <out_dir>:
  prepared.jsonl   input rows + messages + gold_reply
  gold_ok.jsonl    every task whose gold reply passes the checker (CuratorKIT GoldCheckGate)
  curated.jsonl    tasks kept by the pass-rate band / quotas (CuratorKIT PassRateGate), with sampled replies
  rejected.jsonl, manifest.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from archive import interfaces as I
from archive.adapters.curatorkit_adapter import curate, make_llm
from archive.train.common import load_config, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("overrides", nargs="*")
    args = ap.parse_args()
    cfg = load_config(args.config, args.overrides)
    out = Path(cfg["out_dir"])
    run_dir(cfg.get("run_id", "curate"), cfg)

    data = Path(cfg["data_dir"])
    cases, rows = {}, []
    for split in cfg.get("splits", ["train"]):
        cases.update(I.load_cases(data / f"cases_{split}.jsonl"))
        rows += I.read_jsonl(data / f"tasks_{split}.jsonl")
    if cfg.get("limit"):
        rows = rows[: cfg["limit"]]
    for r in rows:
        r["messages"] = I.messages(r, cases)
        r["gold_reply"] = I.gold(r)
    prepared = out / "prepared.jsonl"
    I.write_jsonl(prepared, rows)

    def gold_ok(row):
        c = I.check(row["gold_reply"], row, cases)
        return c["parsed"] and (c["abstained"] or (c["support_rate"] or 0) >= 1.0)

    def score(reply, row):
        return float(I.is_correct(I.reward(reply, row, cases)))

    llm = make_llm(cfg["sglang_url"], cfg["model"], lora=cfg.get("lora"), max_tokens=cfg.get("max_tokens", 256))
    manifest = curate(prepared, out, gold_ok=gold_ok, score=score, llm=llm, n=cfg.get("n", 4),
                      lo=cfg.get("lo", 0.2), hi=cfg.get("hi", 0.8), quota_types=cfg.get("quota_types"),
                      concurrency=cfg.get("concurrency", 32))

    rejected_gold = {r["task_id"] for r in I.read_jsonl(out / "rejected.jsonl") if r["reason"] == "gold_fails_checker"}
    gold_rows = [r for r in rows if r["task_id"] not in rejected_gold]
    I.write_jsonl(out / "gold_ok.jsonl", gold_rows)
    # Pass-rate histogram over everything that was sampled (band + rejected-out-of-band + quota).
    rates = [r["pass_rate"] for r in I.read_jsonl(out / "curated.jsonl")]
    rates += [r["pass_rate"] for r in I.read_jsonl(out / "rejected.jsonl") if r.get("pass_rate") is not None]
    manifest["gold_ok"] = len(gold_rows)
    manifest["gold_ok_by_type"] = Counter(r["type"] for r in gold_rows)
    manifest["pass_rate_histogram"] = Counter(round(x, 2) for x in rates)
    manifest["interfaces_mode"] = I.MODE
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps(manifest, indent=1, default=str))


if __name__ == "__main__":
    main()
