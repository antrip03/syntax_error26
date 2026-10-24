"""Task families, the Task record, and the scaffold-independent PROGRAM that defines each gold answer.

program = {
  "prim":    {"op": ret|vol|mdd|count_breach|count_cross, "thr": int, "fast": int, "slow": int},
  "regions": [[a, b, seg_idx_or_-1], ...],      # inclusive windows the primitive is applied to
  "combine": None | sum | rss | max | min | diff   # how region values are merged (None: exactly one region)
}
The gold answer is `solve(series, program)`: a direct evaluation through the op registry. Scaffolds only
change HOW the model is asked to arrive at it (window walk, chunk summaries, segments).
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

from ..verifiers import ops

FAMILIES = ["windowed_stats", "running_drawdown", "event_count", "regime_conditional", "compositional"]
COUNT_OPS = ("count_breach", "count_cross")
TOL_REL = 0.01
SOFT_REL = 0.05


@dataclass
class Task:
    id: str
    split: str
    family: str
    depth: int
    length: int
    series: list
    program: dict
    question: str
    answer: float
    tolerance_rel: float = TOL_REL
    tolerance_abs: float = 1.0
    soft_abs: float = 3.0
    source: str = "synthetic"
    asset: str = ""
    seed: int = 0
    meta: dict = field(default_factory=dict)

    def to_json(self):
        return asdict(self)

    @staticmethod
    def from_json(d):
        return Task(**d)

    def get_series(self):
        s = getattr(self, "_series_obj", None)
        if s is None:
            s = ops.Series(self.series)
            object.__setattr__(self, "_series_obj", s)
        return s


def region_value(series, prim, a, b):
    op = prim["op"]
    if op == "count_breach":
        return ops.eval_prim(series, op, [a, b, prim["thr"]])
    if op == "count_cross":
        return ops.eval_prim(series, op, [a, b, prim["fast"], prim["slow"]])
    return ops.eval_prim(series, op, [a, b])


def solve(series, program):
    vals = [region_value(series, program["prim"], a, b) for a, b, _ in program["regions"]]
    if program["combine"] is None:
        assert len(vals) == 1
        return float(vals[0])
    return float(ops.agg(program["combine"], vals))


def tolerances(program):
    """(tolerance_abs, soft_abs): counts must be exact; other values get a small absolute floor (bps)."""
    if program["prim"]["op"] in COUNT_OPS:
        return 0.5, 0.5
    return 1.0, 3.0


# ---------- natural language ----------
_STAT = {
    "ret": "the cumulative return (sum of daily returns, in bps)",
    "vol": "the realized volatility (square root of the sum of squared daily returns, in bps)",
    "mdd": "the maximum drawdown (largest fall from a running peak of the cumulative return, in bps)",
}


def _stat_phrase(prim):
    op = prim["op"]
    if op == "count_breach":
        return f"the number of days with |return| > {prim['thr']} bps"
    if op == "count_cross":
        return (f"the number of crossovers between the {prim['fast']}-day and {prim['slow']}-day moving averages "
                f"of the cumulative return")
    return _STAT[op]


def _win(a, b):
    return f"days {a}..{b}"


def question_text(family, program, extra=None):
    prim, regs, comb = program["prim"], program["regions"], program["combine"]
    stat = _stat_phrase(prim)
    sel = (extra or {}).get("selector")
    if sel:
        return f"Using the segmentation rule, compute {stat} over {sel}."
    wins = ", ".join(_win(a, b) for a, b, _ in regs)
    if comb is None:
        return f"Compute {stat} over {wins}."
    if comb == "diff":
        return f"Compute {stat} over {_win(*regs[0][:2])} minus the same quantity over {_win(*regs[1][:2])}."
    word = {"sum": "total", "max": "largest", "min": "smallest", "rss": "combined"}[comb]
    return f"Compute the {word} value of {stat} taken over each of these windows: {wins}."
