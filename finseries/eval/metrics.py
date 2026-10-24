"""Aggregate per-task eval rows into the headline metrics (see PROJECT_PLAN section 10)."""
import numpy as np


def bootstrap_ci(x, n=2000, seed=0):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, (n, len(x))).mean(1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def _agg(rows):
    if not rows:
        return {"n": 0}
    acc = [r["correct"] for r in rows]
    with_steps = [r["step_validity"] for r in rows if r["n_steps"] > 0]
    mean_tok = float(np.mean([r["n_tokens"] for r in rows]))
    return {
        "n": len(rows),
        "accuracy": float(np.mean(acc)), "accuracy_ci95": bootstrap_ci(acc),
        "mean_outcome": float(np.mean([r["outcome"] for r in rows])),
        "parse_rate": float(np.mean([r["parsed"] for r in rows])),
        "format": float(np.mean([r["format"] for r in rows])),
        "step_validity": float(np.mean([r["step_validity"] for r in rows])),
        "step_validity_given_steps": float(np.mean(with_steps)) if with_steps else 0.0,
        "mean_tokens": mean_tok,
        "truncated_rate": float(np.mean([r["truncated"] for r in rows])),
        "acc_per_1k_tokens": float(np.mean(acc) / max(mean_tok / 1000, 1e-9)),
    }


def length_bucket(n):
    return "<=100" if n <= 100 else "101-250" if n <= 250 else "251-400" if n <= 400 else ">400"


def error_propagation(rows):
    """P(final wrong | first invalid step at 0-based position j, capped at 9); only rows with an invalid step."""
    by = {}
    for r in rows:
        if r["first_invalid"] is not None:
            by.setdefault(min(r["first_invalid"], 9), []).append(not r["correct"])
    return {str(j): {"n": len(v), "p_wrong": float(np.mean(v))} for j, v in sorted(by.items())}


def summarize(rows):
    out = {"overall": _agg(rows), "error_propagation": error_propagation(rows)}
    for key in ("family", "depth"):
        out["by_" + key] = {str(k): _agg([r for r in rows if r[key] == k]) for k in sorted({r[key] for r in rows})}
    out["by_length"] = {b: _agg([r for r in rows if length_bucket(r["length"]) == b]) for b in sorted({length_bucket(r["length"]) for r in rows})}
    if len(rows) > 1:
        x = np.array([r["length"] for r in rows], float)
        y = np.array([r["n_tokens"] for r in rows], float)
        out["tokens_vs_length_slope"] = float(np.polyfit(x, y, 1)[0]) if x.std() > 0 else 0.0
    return out
