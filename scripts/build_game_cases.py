"""Build the finance game's cases from REAL model outputs.

Each "desk" in the game is one of our trained model stages. A case = one audit question about a real/synthetic return series;
every desk's saved completion is parsed and every step is recomputed by the deterministic verifier (finseries), which gives the
green/red badge, the "quote" (the recomputed value) and the cited tape rows. Nothing is invented: the game replays the models.

python scripts/build_game_cases.py --tasks artifacts/tasks/val.jsonl --desk NAME=PATH.jsonl ... --out game/data/cases.json
"""
import argparse
import json
import re
import sys

sys.path.insert(0, ".")
from finseries.tasks.generate import read_jsonl  # noqa: E402
from finseries.verifiers import steps as S  # noqa: E402
from finseries.verifiers.ops import Series, fmt  # noqa: E402

DESKS = {  # id -> (display name, building role key used by the map, persona, bio)
    "base": ("Barry Base", "miller", "untrained zero-shot model; writes code-like prose, no checkable steps",
             "The intern nobody trained. Confident, chatty, and rarely shows arithmetic you can check."),
    "e2big": ("Edie Early", "herbalist", "first SFT recipe; copies the format, fumbles the arithmetic",
              "Learned the filing format from examples but still adds in her head."),
    "e4": ("Eli Levels", "guard", "SFT with running levels for drawdowns",
           "Keeps a running level column, so drawdowns are mostly right. Sums are another matter."),
    "sftchunk": ("Chen Chunk", "baker", "SFT scaffold: ten-day chunk summaries",
                 "Summarises the tape in ten-day chunks and combines the summaries."),
    "sftflat": ("Fiona Flat", "blacksmith", "SFT scaffold: five-day windows, walks the whole tape",
                "Walks the tape five days at a time, writing every window down."),
    "r1flat": ("Rhea Reward", "priest", "GRPO from the flat SFT, outcome reward only",
               "Trained against the verifier itself: right answer or nothing."),
    "r2chunk": ("Rex Rewarded", "priest", "GRPO from the chunk SFT, outcome reward only", "Chunk summaries, trained on right answers."),
    "r3chunk": ("Rosa Process", "priest", "GRPO from the chunk SFT, outcome + process reward",
                "Chunk summaries, rewarded for every step that checks out."),
    "r5flat": ("Ravi Rigour", "priest", "GRPO from the flat SFT, outcome + process reward",
               "Walks the tape and is rewarded for each valid line."),
}
OP_WORD = {"ret": "return", "vol": "volatility", "mdd": "max drawdown", "dd": "drawdown", "hi": "high", "lo": "low",
           "count_breach": "breach count", "count_cross": "crossover count", "agg": "combine", "seg_stat": "segment stat"}


def rows_of(series, n=10):
    return [f"{i}| " + " ".join(str(int(x)) for x in series[i:i + n]) for i in range(0, len(series), n)]


def cites_for(step, series_len):
    """Tape rows (evidence sentence ids E1.S<k>, 1-based) the step reads from."""
    if step.name in ("agg", "seg_stat") or step.kind != "step":
        return []
    try:
        a, b = int(step.args[0]), int(step.args[1])
    except Exception:
        return []
    return [f"E1.S{r + 1}" for r in range(a // 10, min(b, series_len - 1) // 10 + 1)]


def call_key(step):
    return f"{step.name}({','.join(step.args)})" if step.kind == "step" else None


def desk_view(task, completion):
    series = Series(task.series)
    from finseries import scaffolds
    sc = scaffolds.get("chunk", trace_style="scratch2")
    pt = sc.parse(completion)
    S.check_steps(pt, series)
    claims = []
    for i, st in enumerate(pt.steps):
        if st.kind == "junk":
            continue
        call = call_key(st) or st.raw
        if st.kind == "step":
            exp = st.expected
            ok = st.valid
            quote = f"Verifier recompute: {call} = {fmt(exp)}" if exp is not None else f"Verifier: cannot recompute {call}"
            if not ok and exp is not None:
                quote += f"  (this desk wrote {fmt(st.value)})"
            claims.append({"idx": i, "text": st.raw, "call": call, "value": st.value, "status": "supported" if ok else "unsupported",
                           "reason": None if ok else ("duplicate_or_bad_reference" if exp is None else "value_mismatch"),
                           "quote": quote, "cites": cites_for(st, len(task.series)),
                           "expected": exp})
    n_valid = sum(c["status"] == "supported" for c in claims)
    first_lines = [l.strip() for l in completion.split("\n") if l.strip() and not l.strip().startswith(("<", "#"))][:4]
    return {"claims": claims, "n_steps": len(claims), "n_valid": n_valid, "answer": pt.answer,
            "final_ok": bool(pt.answer is not None and abs(pt.answer - task.answer) <= max(0.01 * abs(task.answer), task.tolerance_abs)),
            "parsed": bool(claims), "prose": first_lines, "n_tokens_est": len(completion) // 3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="artifacts/tasks/val.jsonl")
    ap.add_argument("--desk", action="append", required=True, help="NAME=path.jsonl (id,completion rows); NAME in DESKS")
    ap.add_argument("--out", default="game/data/cases.json")
    ap.add_argument("--max-cases", type=int, default=8)
    a = ap.parse_args()
    comps = {}
    for spec in a.desk:
        name, path = spec.split("=", 1)
        comps[name] = {}
        for l in open(path):
            d = json.loads(l)
            comps[name][d["id"]] = d["completion"]
    tasks = [t for t in read_jsonl(a.tasks) if all(t.id in c for c in comps.values())]
    cases = []
    for t in tasks:
        if t.family not in ("windowed_stats", "event_count", "running_drawdown") or t.depth > 3 or t.length > 80:
            continue
        views = {n: desk_view(t, comps[n][t.id]) for n in comps}
        good = [n for n, v in views.items() if v["final_ok"] and v["parsed"]]
        # culprit: a desk that LOOKS credible (parses, mostly valid steps) but gets the final figure wrong
        sus = [n for n, v in views.items() if not v["final_ok"] and v["parsed"] and v["n_steps"] >= 3 and v["n_valid"] < v["n_steps"]]
        if not good or not sus:
            continue
        culprit = min(sus, key=lambda n: views[n]["n_valid"] / max(views[n]["n_steps"], 1))
        # contradictions: the culprit's wrong step vs another desk's verified step for the same call
        pairs = []
        for c in views[culprit]["claims"]:
            if c["status"] == "supported" or c["expected"] is None:
                continue
            for n, v in views.items():
                if n == culprit:
                    continue
                for d in v["claims"]:
                    if d["call"] == c["call"] and d["status"] == "supported":
                        pairs.append({"culprit_idx": c["idx"], "other": n, "other_idx": d["idx"], "call": c["call"],
                                      "wrote": c["value"], "truth": c["expected"]})
        if len({p["call"] for p in pairs}) < 2:
            continue
        cases.append({"id": t.id, "family": t.family, "depth": t.depth, "question": t.question, "gold": t.answer,
                      "series": t.series, "tape_rows": rows_of(t.series), "culprit": culprit, "good": good, "pairs": pairs,
                      "desks": views})
    cases.sort(key=lambda c: (-len(c["good"]) * 0 + len(c["pairs"]), c["id"]))
    cases = cases[: a.max_cases]
    out = {"desks": {n: dict(zip(("name", "role", "persona", "bio"), DESKS[n])) for n in comps}, "cases": cases,
           "source": "real model outputs recomputed by the finseries verifier"}
    json.dump(out, open(a.out, "w"))
    print(f"{len(cases)} cases; desks={list(comps)}; culprits={[c['culprit'] for c in cases]}")


if __name__ == "__main__":
    main()
