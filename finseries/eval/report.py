"""M6 report: score every run's saved generations through AuditKit (final accuracy, step validity, format, soft outcome),
add our own breakdowns (family, length bucket, error propagation, tokens-vs-length), write metrics.json + summary.md.

python -m finseries.eval.report --out artifacts/results --run NAME ARM VARIANT DIR TAG [--run ...]
Each run reads DIR/<TAG>_<split>/{completions,rows}.jsonl for split in val, test_period, test_len."""
import argparse
import json
import os

import numpy as np

from ..adapters import auditkit_adapter as A
from ..tasks.generate import read_jsonl
from . import metrics

SPLITS = ["val", "test_period", "test_len"]


def _load(dirpath, tasks_dir, split):
    comps = {}
    for l in open(os.path.join(dirpath, "completions.jsonl")):
        d = json.loads(l)
        comps[d["id"]] = d["completion"]
    rows = [json.loads(l) for l in open(os.path.join(dirpath, "rows.jsonl"))]
    tasks = [t for t in read_jsonl(os.path.join(tasks_dir, f"{split}.jsonl")) if t.id in comps]
    return tasks, [comps[t.id] for t in tasks], rows


def ci(x, n=2000):
    lo, hi = metrics.bootstrap_ci(x, n)
    return f"[{lo:.3f}, {hi:.3f}]"


def run_report(name, arm, variant, root, tag, tasks_dir):
    out = {"name": name, "arm": arm, "splits": {}}
    for split in SPLITS:
        d = os.path.join(root, f"{tag}_{split}")
        if not os.path.exists(os.path.join(d, "completions.jsonl")):
            continue
        tasks, outs, rows = _load(d, tasks_dir, split)
        res = A.evaluate_precomputed(tasks, outs, arm, variant, name=f"{name}-{split}")
        rm = metrics.summarize(rows)
        acc = [r["correct"] for r in rows]
        out["splits"][split] = {
            "n": len(tasks), "auditkit": A.headline(res), "accuracy_ci95": ci(acc),
            "mean_tokens": rm["overall"]["mean_tokens"], "truncated_rate": rm["overall"]["truncated_rate"],
            "by_family": {k: round(v["accuracy"], 3) for k, v in rm["by_family"].items()},
            "by_op": {k: round(v["valid"], 3) for k, v in list(rm["by_op"].items())[:8]},
            "error_propagation": rm["error_propagation"], "tokens_vs_length_slope": rm.get("tokens_vs_length_slope"),
            "auditkit_fingerprint": res.fingerprint,
        }
    return out


def markdown(runs):
    L = ["# Results summary (greedy decoding; AuditKit-scored; item counts per cell shown)", ""]
    L += ["| run | scaffold | split | n | final accuracy [95% CI] | step validity | format | mean tokens |", "|---|---|---|---|---|---|---|---|"]
    for r in runs:
        for sp, v in r["splits"].items():
            h = v["auditkit"]
            L.append(f"| {r['name']} | {r['arm']} | {sp} | {v['n']} | {h['final_accuracy']:.3f} {v['accuracy_ci95']} | "
                     f"{h['step_validity']:.3f} | {h['format_ok']:.3f} | {v['mean_tokens']:.0f} |")
    L += ["", "## Length generalisation (accuracy on test_len minus accuracy on val)", "", "| run | val | test_len | drop |", "|---|---|---|---|"]
    for r in runs:
        s = r["splits"]
        if "val" in s and "test_len" in s:
            a, b = s["val"]["auditkit"]["final_accuracy"], s["test_len"]["auditkit"]["final_accuracy"]
            L.append(f"| {r['name']} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")
    L += ["", "## Token efficiency", "", "| run | split | accuracy per 1k tokens | tokens-vs-length slope |", "|---|---|---|---|"]
    for r in runs:
        for sp, v in r["splits"].items():
            apk = v["auditkit"]["final_accuracy"] / max(v["mean_tokens"] / 1000, 1e-9)
            L.append(f"| {r['name']} | {sp} | {apk:.3f} | {v['tokens_vs_length_slope']:.2f} |")
    L += ["", "## Accuracy by family (val)", ""]
    fams = sorted({f for r in runs for f in r["splits"].get("val", {}).get("by_family", {})})
    L += ["| run | " + " | ".join(fams) + " |", "|---|" + "---|" * len(fams)]
    for r in runs:
        bf = r["splits"].get("val", {}).get("by_family", {})
        L.append(f"| {r['name']} | " + " | ".join(f"{bf.get(f, float('nan')):.3f}" for f in fams) + " |")
    L += ["", "## Per-operation step validity (val)", ""]
    ops_ = sorted({o for r in runs for o in r["splits"].get("val", {}).get("by_op", {})})
    L += ["| run | " + " | ".join(ops_) + " |", "|---|" + "---|" * len(ops_)]
    for r in runs:
        bo = r["splits"].get("val", {}).get("by_op", {})
        L.append(f"| {r['name']} | " + " | ".join(f"{bo.get(o, float('nan')):.2f}" for o in ops_) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/results")
    ap.add_argument("--tasks-dir", default="artifacts/tasks")
    ap.add_argument("--run", nargs=5, action="append", metavar=("NAME", "ARM", "VARIANT", "DIR", "TAG"), required=True)
    a = ap.parse_args()
    runs = [run_report(n, arm, v, d, tag, a.tasks_dir) for n, arm, v, d, tag in a.run]
    os.makedirs(a.out, exist_ok=True)
    json.dump(runs, open(os.path.join(a.out, "metrics.json"), "w"), indent=1, default=str)
    open(os.path.join(a.out, "summary.md"), "w").write(markdown(runs))
    print(markdown(runs))
