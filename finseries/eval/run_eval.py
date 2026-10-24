"""Run one arm on one task file through SGLang and score it with the verifier rewards.
python -m finseries.eval.run_eval --tasks T.jsonl --arm chunk --url http://127.0.0.1:30000 --out artifacts/results/R0_chunk_val"""
import argparse
import json
import os

from .. import scaffolds
from ..adapters.sglang_client import SGLangClient
from ..rewards import combine
from ..rewards.outcome import is_correct
from ..scaffolds.base import SYSTEM
from ..tasks.generate import read_jsonl
from ..verifiers import steps as S
from . import metrics


def score(sc, task, gen, bundle="outcome_process"):
    comp = combine.compute(sc, task, gen.text, n_tokens=gen.n_tokens, bundle=bundle)
    pt = sc.parse(gen.text)
    sc.check_steps(pt, task)
    nv = sum(s.valid for s in pt.steps)
    return {
        "id": task.id, "family": task.family, "depth": task.depth, "length": task.length, "split": task.split,
        "correct": bool(is_correct(task, pt)), "outcome": comp["outcome"], "format": comp["format"], "parsed": comp["parsed"],
        "n_tokens": gen.n_tokens, "n_steps": pt.n_steps, "step_validity": nv / pt.n_steps if pt.n_steps else 0.0,
        "first_invalid": S.first_invalid(pt) if pt.n_steps else None,
        "truncated": bool(pt.truncated), "finish": gen.finish, "answer": pt.answer, "gold": task.answer,
    }


def run(tasks, arm, client, out_dir, n=1, temperature=0.0, max_tokens=1024, seed=0, bundle="outcome_process"):
    sc = scaffolds.get(arm)
    prompts = [sc.build_prompt(t) for t in tasks]
    gens = client.generate(SYSTEM, prompts, n=n, temperature=temperature, max_tokens=max_tokens, seed=seed)
    rows, raw = [], []
    for t, gl in zip(tasks, gens):
        for k, g in enumerate(gl):
            r = score(sc, t, g, bundle)
            r["sample"] = k
            rows.append(r)
            raw.append({"id": t.id, "sample": k, "completion": g.text})
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/rows.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    with open(f"{out_dir}/completions.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in raw)
    m = metrics.summarize(rows)
    json.dump(m, open(f"{out_dir}/metrics.json", "w"), indent=1)
    return rows, m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:30000")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    a = ap.parse_args()
    ts = read_jsonl(a.tasks)
    ts = ts[:a.limit] if a.limit else ts
    _, m = run(ts, a.arm, SGLangClient(a.url), a.out, a.n, a.temperature, a.max_tokens)
    print(json.dumps(m["overall"], indent=1))
