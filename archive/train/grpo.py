"""GRPO -> R3 through AlignTune (train env), starting from the R1 adapter.

python -m archive.train.grpo --config configs/grpo.yaml [--resume] [key=value ...]

Reward = P2's reward(reply, task, case) parts, one AlignTune custom reward per part with the brief's weights
(R3 = 0.35 correct + 0.30 support + 0.10 cite + 0.15 abstain + 0.10 fmt + length). `abstained` is logged with
weight 0, and `leak` (-1 when a persona '#' line names something checkable, which the checker would not see)
has weight 0.10. Every TRL log line (all reward parts, KL, lengths, clip ratio) goes to logs.jsonl.
Guards (brief 10.3), checked on every log:
  - abstain rate above `guards.max_abstain` for `guards.patience` logs in a row -> stop;
  - over the last `guards.window` logs, total reward rising while `correct` falls -> stop (reward hacking).
Adapter ends up in artifacts/runs/<run_id>/out/; checkpoints every `save_every` steps there too.
"""
import argparse
import os
from collections import deque
from pathlib import Path

from transformers import TrainerCallback

from archive import interfaces as I
from archive.adapters import aligntune_adapter as AT
from archive.eval.gate import hash_leak
from archive.train.common import JsonlLog, load_config, run_dir

PARTS = ["correct", "support", "cite", "abstain", "fmt", "length", "leak"]


def _key(messages) -> tuple:
    return tuple((m["role"], m["content"]) for m in messages)


def _text(completion) -> str:
    if isinstance(completion, list):
        return "".join(m.get("content", "") for m in completion if isinstance(m, dict))
    return completion


class Guards(TrainerCallback):
    def __init__(self, logger, g: dict):
        self.logger, self.g = logger, g
        self.abst_run = 0
        self.hist = deque(maxlen=g.get("window", 20))

    def on_log(self, args, state, control, logs=None, **kw):
        logs = logs or {}
        self.logger(step=state.global_step, **logs)
        abst = logs.get("rewards/registry_abstained/mean")
        correct = logs.get("rewards/registry_correct/mean")
        total = logs.get("reward")
        if abst is not None:
            self.abst_run = self.abst_run + 1 if abst > self.g.get("max_abstain", 0.6) else 0
            if self.abst_run >= self.g.get("patience", 3):
                self._stop(control, state, f"abstain rate {abst:.2f} > {self.g.get('max_abstain', 0.6)} for {self.abst_run} logs")
        if correct is not None and total is not None:
            self.hist.append((total, correct))
            if len(self.hist) == self.hist.maxlen:
                h = len(self.hist) // 2
                old, new = list(self.hist)[:h], list(self.hist)[h:]
                d_total = sum(x[0] for x in new) / len(new) - sum(x[0] for x in old) / len(old)
                d_corr = sum(x[1] for x in new) / len(new) - sum(x[1] for x in old) / len(old)
                if d_total > self.g.get("min_delta", 0.02) and d_corr < -self.g.get("min_delta", 0.02):
                    self._stop(control, state, f"reward hacking: total +{d_total:.3f} while correct {d_corr:.3f}")

    def _stop(self, control, state, why):
        control.should_training_stop = True
        control.should_save = True
        self.logger(event="guard_stop", step=state.global_step, reason=why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("overrides", nargs="*")
    args = ap.parse_args()
    cfg = load_config(args.config, args.overrides)
    if os.environ.get("ARCHIVE_DEVSTUB") != "1":
        I.require("p2")
    d = run_dir(cfg["run_id"], cfg)
    logger = JsonlLog(d / "logs.jsonl")

    data_dir = Path(cfg["data_dir"])
    cases = {}
    for split in cfg.get("case_splits", ["train"]):
        cases.update(I.load_cases(data_dir / f"cases_{split}.jsonl"))
    rows = I.read_jsonl(cfg["prompts"])
    if cfg.get("limit"):
        rows = rows[: cfg["limit"]]
    by_prompt = {}
    for r in rows:
        r.setdefault("messages", I.messages(r, cases))
        by_prompt[_key(r["messages"])] = r
    I.write_jsonl(d / "grpo_prompts.json", [{"prompt": r["messages"]} for r in rows])
    logger(event="data", n_prompts=len(rows), interfaces_mode=I.MODE)

    cache: dict = {}

    def parts_for(completion, prompt):
        text = _text(completion)
        k = (_key(prompt), text)
        if k not in cache:
            if len(cache) > 50_000:
                cache.clear()
            row = by_prompt[_key(prompt)]
            parts = I.reward(text, row, cases, bundle=cfg.get("bundle", "full"))
            if "abstained" not in parts:
                parts["abstained"] = float(I.check(text, row, cases)["abstained"])
            parts["leak"] = -1.0 if hash_leak(text, cases[row["case_id"]]) else 0.0
            cache[k] = parts
        return cache[k]

    def make(part):
        def fn(completion, prompt=None, **kw):
            return float(parts_for(completion, prompt)[part])
        return fn

    weights = cfg.get("weights", {"correct": 0.35, "support": 0.30, "cite": 0.10, "abstain": 0.15, "fmt": 0.10, "length": 1.0,
                                  "leak": 0.10})
    rewards = [(p, make(p), weights[p]) for p in PARTS if p in weights] + [("abstained", make("abstained"), 0.0)]

    res = AT.grpo(d / "grpo_prompts.json", d / "out", cfg, rewards, init_adapter=cfg.get("init_adapter"),
                  resume=args.resume, callbacks=[Guards(logger, cfg.get("guards", {}))])
    logger(event="done", result={k: v for k, v in (res or {}).items() if k != "metrics"}, adapter=str(d / "out"))


if __name__ == "__main__":
    main()
