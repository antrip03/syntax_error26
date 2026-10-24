"""Scaffold interface + the shared trace-building engine.

All scaffolds solve the same program (tasks/templates.py). They differ only in:
  * header lines (window=w / chunk=k / <segments> block),
  * how a region [a,b] is COVERED by pieces (fixed small windows / fixed chunks / canonical segments),
  * how drawdown pieces are summarised (flat: one dd() per window; chunk/event: hi,lo,mdd triples + agg(mdd)).
"""
from ..data.serialize import serialize
from ..verifiers import ops, steps
from ..verifiers.steps import ParsedTrace

SYSTEM = (
    "You analyse a GIVEN return series (never predict the future). Reason in verifiable steps, one per line: "
    "`S<k>: <op>(<args>) = <value>`; free text only on lines starting with `#`."
)
OPS_HELP = (
    "Ops (inclusive windows; level = running sum of returns from day 0): ret(a,b) sum; vol(a,b) sqrt(sum of squares); "
    "hi/lo(a,b) max/min level; mdd(a,b) max drawdown in window; dd(a,b,s) drawdown on a..b, peak from day s; "
    "count_breach(a,b,thr) days |r|>thr; count_cross(a,b,fast,slow) MA crossovers; seg_stat(i,op) op on segment i; "
    "agg(sum|max|min|mean|diff|rss|mdd,S<j>,..) over earlier steps (diff=first-second, rss=root sum of squares, "
    "mdd=(hi,lo,mdd) triples)."
)
SEGMENT_RULE = (
    "Segmentation: s[t]=std of last 5 returns; hv if s[t]>1.25*median(s) else lv; runs <6 days merge into the left "
    "neighbour (first run: right); trend up/down if summed return beyond +-0.5*sigma*sqrt(len), sigma=std of all, else flat."
)
FORMAT = "Output `<think>` steps `</think>` then `<answer>NUMBER</answer>`."


class Builder:
    """Accumulates step lines; every value comes from the op registry, never typed by hand."""

    def __init__(self, series):
        self.s, self.lines, self.vals, self.k = series, [], {}, 0

    def _emit(self, call, value):
        self.k += 1
        self.vals[self.k] = float(value)
        self.lines.append(f"S{self.k}: {call} = {ops.fmt(value)}")
        return self.k

    def prim(self, name, *args):
        v = ops.eval_prim(self.s, name, list(args))
        return self._emit(f"{name}({','.join(str(a) for a in args)})", v)

    def agg(self, op, refs):
        v = ops.agg(op, [self.vals[r] for r in refs])
        return self._emit(f"agg({op},{','.join(f'S{r}' for r in refs)})", v)


class Scaffold:
    id = "base"
    declares = ""         # which header the format reward requires: window | chunk | segments

    # ---- to override ----
    def header(self, task, series):
        return []

    def cover(self, series, a, b, seg_idx):
        """Consecutive pieces [(pa, pb, full_seg_idx_or_-1)] covering [a, b]."""
        raise NotImplementedError

    summary_mdd = True    # False: one dd() per piece (flat)

    def extra_prompt(self, task):
        return ""

    # ---- shared ----
    def build_prompt(self, task):
        sel = task.meta.get("selector")
        parts = [serialize(task.series), "Question: " + task.question, OPS_HELP]
        if sel:
            parts.insert(2, SEGMENT_RULE)
        extra = self.extra_prompt(task)
        if extra:
            parts.append(extra)
        parts.append(FORMAT)
        return "\n".join(parts)

    def _prim_piece(self, B, prim, pa, pb, seg):
        op = prim["op"]
        if seg >= 0 and op in ops.SEG_OPS:
            return B.prim("seg_stat", seg, op)  # printed as seg_stat(i,op) -> handled below
        if op == "count_breach":
            return B.prim(op, pa, pb, prim["thr"])
        if op == "count_cross":
            return B.prim(op, pa, pb, prim["fast"], prim["slow"])
        return B.prim(op, pa, pb)

    def _region(self, B, prim, a, b, seg_idx, series):
        pieces = self.cover(series, a, b, seg_idx)
        op = prim["op"]
        if op == "mdd":
            if not self.summary_mdd:
                refs = [B.prim("dd", pa, pb, a) for pa, pb, _ in pieces]
                return refs[0] if len(refs) == 1 else B.agg("max", refs)
            if len(pieces) == 1:
                return self._prim_piece(B, prim, *pieces[0])
            triples = []
            for pa, pb, sg in pieces:
                for o in ("hi", "lo", "mdd"):
                    triples.append(self._prim_piece(B, {"op": o}, pa, pb, sg))
            return B.agg("mdd", triples)
        refs = [self._prim_piece(B, prim, *p) for p in pieces]
        if len(refs) == 1:
            return refs[0]
        return B.agg("rss" if op == "vol" else "sum", refs)

    def gold_trace(self, task):
        series = task.get_series()
        B = Builder(series)
        prog = task.program
        lines = list(self.header(task, series))
        sel = task.meta.get("selector")
        if sel and not self.declares == "segments":
            lines.append("# regions: " + " ".join(f"{a}-{b}" for a, b, _ in prog["regions"]))
        refs = [self._region(B, prog["prim"], a, b, sg, series) for a, b, sg in prog["regions"]]
        if prog["combine"] is not None:
            B.agg(prog["combine"], refs)
        body = "\n".join(lines + B.lines)
        ans = ops.fmt(B.vals[B.k])
        return f"<think>\n{body}\n</think>\n<answer>{ans}</answer>"

    def parse(self, completion) -> ParsedTrace:
        return steps.parse_completion(completion)

    def check_steps(self, parsed, task):
        return steps.check_steps(parsed, task.get_series())

    def final_answer(self, parsed):
        return parsed.answer

    def header_ok(self, parsed):
        """Does the completion declare this scaffold's required header?"""
        return True
