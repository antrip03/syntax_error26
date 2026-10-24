"""SFT -> R1 through AlignTune (train env).

python -m archive.train.sft --config configs/sft.yaml [key=value ...]

Data: rows with `messages` + `gold_reply` (curate.py's gold_ok.jsonl or curated.jsonl). Each prompt is rendered
with the Qwen3 chat template, thinking off, exactly as SGLang renders it at inference; the completion is the gold
reply, and only completion tokens carry loss. Examples are sampled stratified by task type.
Adapter ends up in artifacts/runs/<run_id>/out/.
"""
import argparse
import random
from collections import defaultdict

from transformers import AutoTokenizer, TrainerCallback

from archive import interfaces as I
from archive.adapters import aligntune_adapter as AT
from archive.train.common import JsonlLog, load_config, run_dir


def stratified(rows, n, seed):
    if not n or n >= len(rows):
        return rows
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in rows:
        by[r["type"]].append(r)
    for g in by.values():
        rng.shuffle(g)
    out = []
    for t, g in by.items():
        out += g[: round(n * len(g) / len(rows))]
    rng.shuffle(out)
    return out[:n]


class LogCB(TrainerCallback):
    def __init__(self, logger):
        self.logger = logger

    def on_log(self, args, state, control, logs=None, **kw):
        self.logger(step=state.global_step, **(logs or {}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("overrides", nargs="*")
    args = ap.parse_args()
    cfg = load_config(args.config, args.overrides)
    d = run_dir(cfg["run_id"], cfg)
    logger = JsonlLog(d / "logs.jsonl")

    tok = AutoTokenizer.from_pretrained(cfg["model"])
    rows = stratified(I.read_jsonl(cfg["data"]), cfg.get("n_examples"), cfg.get("seed", 0))
    data, too_long = [], 0
    for r in rows:
        prompt = tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        if len(tok(prompt + r["gold_reply"]).input_ids) + 1 > cfg.get("max_seq_len", 1280):
            too_long += 1
            continue
        data.append({"prompt": prompt, "completion": r["gold_reply"], "type": r["type"]})
    I.write_jsonl(d / "sft_data.json", [{"prompt": x["prompt"], "completion": x["completion"]} for x in data])
    logger(event="data", n=len(data), dropped_too_long=too_long,
           by_type={t: sum(x["type"] == t for x in data) for t in sorted({x["type"] for x in data})})
    res = AT.sft(d / "sft_data.json", d / "out", cfg, callbacks=[LogCB(logger)])
    logger(event="done", result={k: v for k, v in (res or {}).items() if k != "metrics"}, adapter=str(d / "out"))


if __name__ == "__main__":
    main()
