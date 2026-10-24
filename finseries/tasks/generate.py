"""Builds task JSONL (series, question, gold answer, tolerances) from windows. Gold = tasks.templates.solve()."""
import json
import os
from collections import Counter

import numpy as np

from .. import scaffolds
from ..tokens import approx_tokens
from ..verifiers.ops import Series
from . import templates as T

DEPTHS = {
    "windowed_stats": [1, 2, 3, 4],
    "running_drawdown": [1, 2, 3, 4],
    "event_count": [1, 2, 3, 4],
    "regime_conditional": [2, 3],
    "compositional": [2, 3, 4],
}


def _windows(rng, n, depth, cap, min_len=6):
    """`depth` distinct inclusive windows with total length about <= cap."""
    per = max(min_len, cap // depth)
    out = []
    for _ in range(50):
        if len(out) == depth:
            break
        L = int(rng.integers(min_len, min(per, n) + 1))
        a = int(rng.integers(0, n - L + 1))
        w = (a, a + L - 1)
        if all(w[1] < o[0] or w[0] > o[1] for o in out):   # disjoint: overlapping windows would repeat sub-steps
            out.append(w)
    return out if len(out) == depth else None


def _prim(rng, series, family, depth, ops_pool):
    op = ops_pool[int(rng.integers(len(ops_pool)))]
    p = {"op": op}
    if op == "count_breach":
        sd = float(np.std(series.r))
        p["thr"] = int(max(10, round(sd * float(rng.uniform(1.0, 1.8)) / 10) * 10))
    if op == "count_cross":
        p["fast"], p["slow"] = 3, 8
    return p


def _build_program(rng, series, family, depth, cap):
    n = series.n
    meta = {}
    if family in ("windowed_stats", "running_drawdown", "event_count"):
        pool = {"windowed_stats": ["ret", "vol"], "running_drawdown": ["mdd"],
                "event_count": ["count_breach", "count_cross"]}[family]
        prim = _prim(rng, series, family, depth, pool)
        if family == "running_drawdown" and depth == 1:
            wins = [(0, n - 1)]
        else:
            wins = _windows(rng, n, depth, cap if family != "event_count" or depth > 1 else cap + 15)
        if wins is None:
            return None
        if depth == 1:
            comb = None
        elif depth == 2:
            comb = str(rng.choice(["diff", "max"] if prim["op"] != "count_cross" else ["diff", "sum"]))
        else:
            comb = str(rng.choice({"vol": ["max", "min", "rss"], "ret": ["max", "min", "sum"],
                                   "mdd": ["max", "min"], "count_breach": ["sum", "max"],
                                   "count_cross": ["sum", "max"]}[prim["op"]]))
        return {"prim": prim, "regions": [[a, b, -1] for a, b in wins], "combine": comb}, meta
    segs = series.segs
    if family == "regime_conditional":
        sel = str(rng.choice(["hv", "lv"]))
        prim = _prim(rng, series, family, depth, ["mdd"] if depth == 3 else ["ret", "vol", "count_breach"])
        idx = [i for i, g in enumerate(segs) if g.vol == sel]
        if not idx or len(idx) > 5 or sum(segs[i].end - segs[i].start + 1 for i in idx) > cap:
            return None
        comb = None if len(idx) == 1 else {"ret": "sum", "vol": "rss", "count_breach": "sum", "mdd": "max"}[prim["op"]]
        meta["selector"] = ("the high-volatility (hv) segments" if sel == "hv" else "the low-volatility (lv) segments")
        return {"prim": prim, "regions": [[segs[i].start, segs[i].end, i] for i in idx], "combine": comb}, meta
    if family == "compositional":
        trends = {2: [str(rng.choice(["up", "down", "flat"]))], 3: ["up", "down"], 4: ["up", "down", "flat"]}[depth]
        picked = []
        for tr in trends:
            cand = [i for i, g in enumerate(segs) if g.trend == tr]
            if not cand:
                return None
            picked.append(max(cand, key=lambda i: (segs[i].end - segs[i].start, -i)))
        if len(set(picked)) < len(picked) or sum(segs[i].end - segs[i].start + 1 for i in picked) > cap:
            return None
        prim = _prim(rng, series, family, depth, ["mdd", "mdd", "ret", "vol", "count_breach"])
        comb = {2: None, 3: "diff", 4: str(rng.choice(["max", "min"]))}[depth]
        names = [f"the longest {t} segment" for t in trends]
        if depth == 2:
            sel = names[0]
        elif depth == 3:
            sel = f"{names[0]} minus the same quantity over {names[1]}"
        else:
            sel = f"each of {names[0]}, {names[1]} and {names[2]}, taking the {'largest' if comb == 'max' else 'smallest'}"
        meta["selector"] = sel
        return {"prim": prim, "regions": [[segs[i].start, segs[i].end, i] for i in picked], "combine": comb}, meta
    raise ValueError(family)


def make_task(win, family, depth, rng, split, idx, budget=None, arms=("flat", "chunk", "event")):
    """Returns a Task, or None if the draw is unusable (caller retries). `budget` = {completion, prompt}."""
    series = Series(win.r)
    n = series.n
    cap = (45 if n <= 100 else 150) if budget else 10 ** 6
    built = _build_program(rng, series, family, depth, cap)
    if built is None:
        return None
    prog, meta = built
    ans = T.solve(series, prog)
    tol_abs, soft_abs = T.tolerances(prog)
    if prog["prim"]["op"] == "count_cross" and ans == 0 and rng.random() < 0.7:
        return None  # keep zero-answers rare
    task = T.Task(
        id=f"{split}-{idx:06d}", split=split, family=family, depth=depth, length=n, series=list(win.r),
        program=prog, question=T.question_text(family, prog, meta), answer=ans, tolerance_abs=tol_abs,
        soft_abs=soft_abs, source=win.source, asset=win.asset, seed=int(win.start), meta=meta)
    task.meta["start_date"] = win.start_date
    for arm in arms:  # gold traces must be perfect; budgets apply to the train distribution only
        sc = scaffolds.get(arm)
        text = sc.gold_trace(task)
        pt = sc.parse(text)
        ok = all(sc.check_steps(pt, task)) and abs(sc.final_answer(pt) - ans) <= 0.51
        if not ok:
            raise AssertionError(f"gold trace invalid for {arm} on {task.id}: {text}")
        if budget and approx_tokens(text) > budget["completion"]:
            return None
        if budget and approx_tokens(sc.build_prompt(task)) > budget["prompt"]:
            return None
    return task


def generate_split(windows, n_tasks, split, seed, budget=None, families=None):
    rng = np.random.default_rng(seed)
    fams = families or list(DEPTHS)
    out, attempts = [], 0
    order = rng.permutation(len(windows))
    while len(out) < n_tasks and attempts < n_tasks * 60:
        fam = fams[len(out) % len(fams)]
        depth = int(rng.choice(DEPTHS[fam]))
        win = windows[int(order[attempts % len(order)])]
        attempts += 1
        t = make_task(win, fam, depth, rng, split, len(out), budget)
        if t is not None:
            out.append(t)
    return out


def write_jsonl(tasks, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for t in tasks:
            f.write(json.dumps(t.to_json()) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [T.Task.from_json(json.loads(l)) for l in f]


def manifest(tasks_by_split):
    m = {}
    for split, ts in tasks_by_split.items():
        m[split] = {
            "n": len(ts),
            "family": dict(Counter(t.family for t in ts)),
            "depth": dict(Counter(t.depth for t in ts)),
            "source": dict(Counter(t.source for t in ts)),
            "length": {"min": min((t.length for t in ts), default=0), "max": max((t.length for t in ts), default=0)},
        }
    return m
