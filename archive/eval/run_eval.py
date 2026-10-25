"""Evaluate a run (R0/R1/R3) on one or more splits through AuditKIT + SGLang (serve env).

python -m archive.eval.run_eval --config configs/eval.yaml run_id=R1 lora=r1 [splits=[test_id,test_adv]] [limit=20]

SGLang must already serve the base model with the adapters registered (scripts/serve_eval.sh), so all runs share
one server and one prompt; only the adapter differs (lora=null for R0). Greedy, max 256 tokens.
Per split writes artifacts/runs/<run_id>/eval_<split>/:
  records.jsonl  {task, case_id, reply, check_result, reward_parts, correct, tokens}
  metrics.json   P2's compute(records) + AuditKIT headline + interfaces mode
  transcripts.json  first 10 items (for replay mode)
"""
import argparse
import os
import json
from pathlib import Path

from transformers import AutoTokenizer

from archive import interfaces as I
from archive.adapters.auditkit_adapter import evaluate
from archive.train.common import load_config, run_dir

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("overrides", nargs="*")
    args = ap.parse_args()
    cfg = load_config(args.config, args.overrides)
    if os.environ.get("ARCHIVE_DEVSTUB") != "1":
        I.require("p2")
    d = run_dir(cfg["run_id"], cfg)
    tok = AutoTokenizer.from_pretrained(cfg["model"])
    data = Path(cfg["data_dir"])

    for split in cfg.get("splits", ["test_id", "test_adv"]):
        cases = I.load_cases(data / f"cases_{split}.jsonl")
        rows = I.read_jsonl(data / f"tasks_{split}.jsonl")
        if cfg.get("limit"):
            rows = rows[: cfg["limit"]]
        by_id = {}
        for r in rows:
            r["messages"] = I.messages(r, cases)
            by_id[r["task_id"]] = r

        cache = {}

        def parts(md, out):
            k = (md["task_id"], out)
            if k not in cache:
                row = by_id[md["task_id"]]
                cache[k] = (I.check(out, row, cases), I.reward(out, row, cases))
            return cache[k]

        scorers = {
            "parsed": lambda md, out: float(parts(md, out)[0]["parsed"]),
            "support_rate": lambda md, out: float(parts(md, out)[0]["support_rate"] or 0.0),
            "abstained": lambda md, out: float(parts(md, out)[0]["abstained"]),
            "correct": lambda md, out: float(parts(md, out)[1]["correct"]),
        }
        items = [{"task_id": r["task_id"], "messages": r["messages"]} for r in rows]
        res = evaluate(items, base_url=cfg["sglang_url"], model=cfg["model"], scorers=scorers, lora=cfg.get("lora"),
                       max_tokens=cfg.get("max_tokens", 256), seed=cfg.get("seed", 0),
                       concurrency=cfg.get("concurrency", 32), experiment_name=f"{cfg['run_id']}_{split}")

        records = []
        for p in res.predictions:
            row = by_id[p.sample_id]
            reply = p.raw_output or ""
            chk, rw = parts({"task_id": p.sample_id}, reply)
            task = {k: v for k, v in row.items() if k != "messages"}
            records.append({"task": task, "case_id": row["case_id"], "reply": reply, "check_result": chk,
                            "reward_parts": rw, "correct": rw["correct"], "tokens": len(tok(reply).input_ids)})
        out = d / f"eval_{split}"
        out.mkdir(parents=True, exist_ok=True)
        I.write_jsonl(out / "records.jsonl", records)
        m = {"metrics": I.metrics(records), "auditkit_headline": res.headline, "n": len(records),
             "run_id": cfg["run_id"], "lora": cfg.get("lora"), "split": split, "interfaces_mode": I.MODE}
        (out / "metrics.json").write_text(json.dumps(m, indent=2, default=str))
        transcripts = [{"task_id": r["task"]["task_id"], "villager": r["task"]["villager"], "question": r["task"]["question"],
                        "reply": r["reply"], "claims": r["check_result"]["claims"]} for r in records[:10]]
        (out / "transcripts.json").write_text(json.dumps(transcripts, indent=2, default=str))
        print(json.dumps({"split": split, **m}, indent=1, default=str), flush=True)

if __name__ == "__main__":
    main()
