"""CuratorKIT adapter (Stage 1): runs our task set through a real curatorkit Pipeline.

Steps (all executed by curatorkit.pipeline.Pipeline, which also writes manifest.json, rejected.jsonl, dataset card):
  TaskReader     JSONL tasks -> DataSample (task json kept in metadata)
  VerifierGate   our deterministic verifier: gold trace of every arm must parse, pass the step checker and match the
                 gold answer, and fit the token budgets  (rejects with a structured reason)
  PassRateGate   difficulty filter: keep tasks whose measured base-model pass rate lies in [lo, hi]
  JsonlExporter  curated tasks -> JSONL
CuratorKIT does the orchestration, rejection bookkeeping, provenance and manifests; the domain checks are plugged in as gates.
"""
import json
import os
from pathlib import Path

from curatorkit.interfaces import BaseExporter, BaseGate, BaseReader
from curatorkit.pipeline import Pipeline
from curatorkit.schema import DataSample, ProvenanceRecord, RejectedSample

from .. import scaffolds
from ..tasks import templates as T
from ..tokens import approx_tokens

VERSION = "1"


def _prov(step, **notes):
    return ProvenanceRecord(step_name=step, step_version=VERSION, config_hash="", notes=notes)


def _reject(sample, step, reason):
    r = RejectedSample(**sample.model_dump(), rejection_reason=reason, rejecting_step=step)
    r.append_provenance(_prov(step, reason=reason))
    return r


class TaskReader(BaseReader):
    def __init__(self, path, pass_rates=None):
        self.path, self.pass_rates = path, pass_rates or {}

    def read(self):
        out, rej = [], []
        for line in open(self.path):
            d = json.loads(line)
            s = DataSample(id=d["id"], source_uri=str(self.path), instruction=d["question"], task_type="prompt_only",
                           metadata={"task_json": line.strip(), "pass_rate": self.pass_rates.get(d["id"], {})})
            s.append_provenance(_prov("TaskReader", split=d["split"], family=d["family"]))
            out.append(s)
        return out, rej


class VerifierGate(BaseGate):
    def __init__(self, arms=("flat", "chunk", "event"), completion_budget=480, prompt_budget=600):
        self.arms, self.cb, self.pb = arms, completion_budget, prompt_budget

    def run(self, samples):
        ok, bad = [], []
        for s in samples:
            task = T.Task.from_json(json.loads(s.metadata["task_json"]))
            reason = None
            for arm in self.arms:
                sc = scaffolds.get(arm)
                text = sc.gold_trace(task)
                pt = sc.parse(text)
                if not all(sc.check_steps(pt, task)) or abs(sc.final_answer(pt) - task.answer) > 0.51:
                    reason = f"gold_trace_invalid:{arm}"
                elif approx_tokens(text) > self.cb:
                    reason = f"above_max_tokens:{arm}"
                elif approx_tokens(sc.build_prompt(task)) > self.pb:
                    reason = f"prompt_above_max_tokens:{arm}"
                if reason:
                    break
            if reason:
                bad.append(_reject(s, "VerifierGate", reason))
            else:
                s.append_provenance(_prov("VerifierGate", arms=list(self.arms)))
                ok.append(s)
        return ok, bad


class PassRateGate(BaseGate):
    """Keep tasks whose sampled pass rate for `arm` is in [lo, hi]: always-solved / never-solved tasks give GRPO no signal."""

    def __init__(self, arm, lo=0.2, hi=0.8):
        self.arm, self.lo, self.hi = arm, lo, hi

    def run(self, samples):
        ok, bad = [], []
        for s in samples:
            p = s.metadata["pass_rate"].get(self.arm)
            if p is None:
                bad.append(_reject(s, "PassRateGate", "missing_pass_rate"))
            elif p < self.lo:
                bad.append(_reject(s, "PassRateGate", f"too_hard:{p:.3f}"))
            elif p > self.hi:
                bad.append(_reject(s, "PassRateGate", f"too_easy:{p:.3f}"))
            else:
                s.append_provenance(_prov("PassRateGate", arm=self.arm, pass_rate=p))
                ok.append(s)
        return ok, bad


class JsonlExporter(BaseExporter):
    def __init__(self, name="tasks.jsonl"):
        self.name = name

    def export(self, samples, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / self.name, "w") as f:
            for s in samples:
                f.write(s.metadata["task_json"] + "\n")


def curate(tasks_path, out_dir, arm=None, pass_rates=None, lo=0.2, hi=0.8, arms=("flat", "chunk", "event")):
    """Run the CuratorKIT pipeline. With `arm` + `pass_rates` the difficulty filter is applied (curated set);
    without them only the verifier gate runs (the 'raw' set). Returns {n_in, n_out, rejected_by_reason}."""
    steps = [TaskReader(tasks_path, pass_rates), VerifierGate(arms)]
    if arm is not None:
        steps.append(PassRateGate(arm, lo, hi))
    steps.append(JsonlExporter())
    res = Pipeline(steps, output_dir=Path(out_dir)).run()
    from curatorkit.manifest import ProvenanceManifest   # curatorkit's own manifest + rejected.jsonl + checksums
    man = ProvenanceManifest(res, f"finseries-{arm or 'raw'}-{lo}-{hi}", Path(out_dir))
    man.write()
    man.write_rejected_sidecar()
    man.write_checksums(list(Path(out_dir).glob("*.jsonl")) + list(Path(out_dir).glob("*.json")))
    reasons = {}
    for r in res.rejected:
        key = r.rejection_reason.split(":")[0] + (":" + r.rejection_reason.split(":")[1] if r.rejection_reason.startswith(("gold", "above")) else "")
        reasons[key] = reasons.get(key, 0) + 1
    summary = {"n_out": len(res.passed), "n_rejected": len(res.rejected), "rejected_by_reason": reasons,
               "stage_counts": {k: v for k, v in (res.stage_counts or {}).items()} if isinstance(res.stage_counts, dict) else str(res.stage_counts)}
    json.dump(summary, open(os.path.join(out_dir, "finseries_curation_summary.json"), "w"), indent=1, default=str)
    return summary
