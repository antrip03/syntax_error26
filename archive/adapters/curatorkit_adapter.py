"""CuratorKIT adapter: gold verification + pass-rate filtering of villager tasks.

The curation runs as a CuratorKIT `Pipeline`:
  JSONLReader -> GoldCheckGate -> PassRateGate -> MessagesExporter-free JSONL dump
- GoldCheckGate drops tasks whose gold reply does not pass our checker.
- PassRateGate samples N replies per task from the untrained model through CuratorKIT's own
  LLM backend (LiteLLM -> SGLang's OpenAI endpoint), scores each with our checker-based scorer,
  stores them in `DataSample.responses` / `reward_scores`, and keeps tasks whose pass rate is in
  [lo, hi]. Tasks whose type is in `quota_types` (abstain-style) bypass the band and are kept by
  quota so the type mix survives filtering.
Scorers are injected (`gold_ok(task) -> bool`, `score(reply, task) -> float in [0, 1]`) so this module
does not depend on the checker's internals.
"""
from __future__ import annotations

import json
import random
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from curatorkit.connectors.jsonl import JSONLReader
from curatorkit.interfaces import BaseGate
from curatorkit.llm.litellm import LiteLLMBackend
from curatorkit.pipeline import Pipeline
from curatorkit.schema import DataSample, RejectedSample


def _task_to_sample(row: dict) -> DataSample:
    return DataSample(
        id=row.get("task_id") or str(uuid.uuid4()),
        source_uri=f"case:{row.get('case_id', '?')}",
        instruction=row.get("question", ""),
        output=row.get("gold_reply", ""),
        task_type="instruction_following",
        metadata={"task": row},
    )


def _reject(s: DataSample, reason: str, step: str) -> RejectedSample:
    return RejectedSample(**s.model_dump(), rejection_reason=reason, rejecting_step=step)


class GoldCheckGate(BaseGate):
    def __init__(self, gold_ok: Callable[[dict], bool]):
        self.gold_ok = gold_ok

    def run(self, samples):
        passed, rejected = [], []
        for s in samples:
            (passed if self.gold_ok(s.metadata["task"]) else rejected).append(s)
        return passed, [_reject(s, "gold_fails_checker", "GoldCheckGate") for s in rejected]


class PassRateGate(BaseGate):
    def __init__(self, llm: LiteLLMBackend, score: Callable[[str, dict], float], n: int = 4,
                 lo: float = 0.2, hi: float = 0.8, quota_types: dict[str, float] | None = None,
                 concurrency: int = 32, max_tokens: int = 256, temperature: float = 0.9, seed: int = 0):
        self.llm, self.score, self.n = llm, score, n
        self.lo, self.hi = lo, hi
        self.quota_types = quota_types or {}
        self.concurrency, self.max_tokens, self.temperature = concurrency, max_tokens, temperature
        self.rng = random.Random(seed)

    def _sample(self, s: DataSample) -> DataSample:
        task = s.metadata["task"]
        replies = [self.llm.generate(task["messages"], temperature=self.temperature, max_tokens=self.max_tokens).text
                   for _ in range(self.n)]
        scores = [float(self.score(r, task)) for r in replies]
        s.responses, s.reward_scores = replies, scores
        s.metadata["pass_rate"] = sum(scores) / len(scores)
        return s

    def run(self, samples):
        with ThreadPoolExecutor(self.concurrency) as ex:
            samples = list(ex.map(self._sample, samples))
        passed, rejected, by_quota = [], [], defaultdict(list)
        for s in samples:
            ttype = s.metadata["task"].get("type")
            if ttype in self.quota_types:
                by_quota[ttype].append(s)
            elif self.lo <= s.metadata["pass_rate"] <= self.hi:
                passed.append(s)
            else:
                rejected.append(_reject(s, f"pass_rate_out_of_band:{s.metadata['pass_rate']:.2f}", "PassRateGate"))
        # Quota types: quota_types[t] is t's target share of the FINAL set, so with B in-band items and
        # total quota share Q, type t keeps q_t * B / (1 - Q) items, preferring harder ones (lower pass rate).
        # If nothing is in band (tiny/smoke runs) quota types are kept in full.
        total_q = sum(self.quota_types.values())
        n_band = len(passed)
        for ttype, group in by_quota.items():
            want = round(self.quota_types[ttype] * n_band / max(1e-9, 1 - total_q)) if n_band else len(group)
            group.sort(key=lambda s: (s.metadata["pass_rate"], self.rng.random()))
            passed += group[:want]
            rejected += [_reject(s, "over_quota", "PassRateGate") for s in group[want:]]
        return passed, rejected


def make_llm(base_url: str, model: str, lora: str | None = None, max_tokens: int = 256) -> LiteLLMBackend:
    extra = {"chat_template_kwargs": {"enable_thinking": False}}
    if lora:
        extra["lora_path"] = lora
    return LiteLLMBackend(model=f"openai/{model}", api_base=f"{base_url.rstrip('/')}/v1", api_key="EMPTY",
                          max_tokens=max_tokens, extra_body=extra)


def curate(tasks_jsonl: str | Path, out_dir: str | Path, *, gold_ok, score, llm: LiteLLMBackend, n: int = 4,
           lo: float = 0.2, hi: float = 0.8, quota_types: dict[str, float] | None = None,
           concurrency: int = 32) -> dict:
    """Run the curation pipeline. Input rows need `task_id, case_id, type, question, messages, gold_reply`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    reader = JSONLReader(tasks_jsonl, preprocessing_fn=_task_to_sample)
    pipe = Pipeline([reader, GoldCheckGate(gold_ok),
                     PassRateGate(llm, score, n=n, lo=lo, hi=hi, quota_types=quota_types, concurrency=concurrency)],
                    output_dir=out_dir)
    result = pipe.run()
    with open(out_dir / "curated.jsonl", "w") as f:
        for s in result.passed:
            f.write(json.dumps(s.metadata["task"] | {"pass_rate": s.metadata["pass_rate"],
                                                     "samples": s.responses, "sample_scores": s.reward_scores}) + "\n")
    with open(out_dir / "rejected.jsonl", "w") as f:
        for r in result.rejected:
            f.write(json.dumps({"task_id": r.id, "reason": r.rejection_reason, "step": r.rejecting_step,
                                "pass_rate": r.metadata.get("pass_rate")}) + "\n")
    manifest = {
        "input": sum(1 for _ in open(tasks_jsonl)),
        "kept": len(result.passed),
        "kept_by_type": Counter(s.metadata["task"].get("type") for s in result.passed),
        "rejected_by_reason": Counter(r.rejection_reason.split(":")[0] for r in result.rejected),
        "stage_counts": result.stage_counts,
        "wall_clock_seconds": result.wall_clock_seconds,
        "params": {"n": n, "lo": lo, "hi": hi, "quota_types": quota_types},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest
