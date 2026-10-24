"""AuditKit adapter (Stage 3): AuditKit runs the evaluation (orchestration, scoring, aggregation, bootstrap stats, run
fingerprint) and our deterministic verifier supplies the scorers (final accuracy, step validity, format, soft outcome).

Two entry points, both through `auditkit.evaluate`:
  evaluate_live(...)         AuditKit calls the model through a `list[str] -> list[str]` callable backed by SGLang
  evaluate_precomputed(...)  generations already produced through SGLang are attached as `actual_output`; AuditKit scores them
"""
import json

import auditkit as ak

from .. import scaffolds
from ..rewards.format import format_reward
from ..rewards.outcome import is_correct, outcome_reward
from ..scaffolds.base import SYSTEM
from ..tasks import templates as T

VARIANTS = {"base": {}, "e4": {"trace_style": "scratch"}, "e5": {"trace_style": "scratch2"}}


def _ctx(sample):
    md = sample.metadata
    task = T.Task.from_json(json.loads(md["task_json"]))
    sc = scaffolds.get(md["arm"], **VARIANTS[md["variant"]])
    return task, sc


def _parsed(sample, output):
    task, sc = _ctx(sample)
    pt = sc.parse(output)
    sc.check_steps(pt, task)
    return task, sc, pt


@ak.scorer(direction=ak.Direction.MAXIMIZE, name="final_accuracy")
def final_accuracy(sample, output):
    task, sc, pt = _parsed(sample, output)
    return float(is_correct(task, pt))


@ak.scorer(direction=ak.Direction.MAXIMIZE, name="outcome_reward")
def outcome(sample, output):
    task, sc, pt = _parsed(sample, output)
    return float(outcome_reward(task, pt))


@ak.scorer(direction=ak.Direction.MAXIMIZE, name="step_validity")
def step_validity(sample, output):
    task, sc, pt = _parsed(sample, output)
    return (sum(s.valid for s in pt.steps) / pt.n_steps) if pt.n_steps else 0.0


@ak.scorer(direction=ak.Direction.MAXIMIZE, name="format_ok")
def format_ok(sample, output):
    task, sc, pt = _parsed(sample, output)
    return float(format_reward(sc, pt))


SCORERS = [final_accuracy, step_validity, format_ok, outcome]


def to_samples(tasks, arm, variant, prompts=None, outputs=None):
    sc = scaffolds.get(arm, **VARIANTS[variant])
    out = []
    for i, t in enumerate(tasks):
        md = {"task_json": json.dumps(t.to_json()), "arm": arm, "variant": variant, "family": t.family, "depth": t.depth,
              "length": t.length}
        s = ak.Sample(input=prompts[i] if prompts else sc.build_prompt(t), target=str(t.answer), id=t.id,
                      task=t.family, metadata=md, tags=[t.family, f"depth{t.depth}"])
        if outputs is not None:
            s.actual_output = outputs[i]
        out.append(s)
    return out


def evaluate_precomputed(tasks, outputs, arm, variant, name=None):
    return ak.evaluate(to_samples(tasks, arm, variant, outputs=outputs), model="precomputed", scorers=SCORERS,
                       experiment_name=name)


def evaluate_live(tasks, client, arm, variant, max_tokens=1500, name=None):
    """AuditKit drives generation: the model callable batches prompts through SGLang (greedy)."""
    def model(prompts):
        return [g[0].text for g in client.generate(SYSTEM, prompts, n=1, temperature=0.0, max_tokens=max_tokens)]
    return ak.evaluate(to_samples(tasks, arm, variant), model=model, scorers=SCORERS, experiment_name=name)


def headline(result):
    return {k: round(float(v), 4) for k, v in result.headline.items()}
