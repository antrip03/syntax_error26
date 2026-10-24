"""Completion parser and step checker (scaffold independent).

Layout of a completion:
    <think>
    [window=5 | chunk=10 header]            (optional per scaffold)
    [<segments> i:(s,e,trend,vol) ... </segments>]
    # free text lines are ignored
    S1: ret(0,4) = 12
    ...
    </think>
    <answer>NUMBER or ABSTAIN</answer>
"""
import math
import re
from dataclasses import dataclass, field
from typing import Optional

from . import ops

STEP_RE = re.compile(r"^S(\d+)\s*:\s*([a-z_]+)\((.*)\)\s*=\s*(-?\d+(?:\.\d+)?)\s*$")
SEG_RE = re.compile(r"^(\d+)\s*:\s*\((\d+),(\d+),(up|down|flat),(hv|lv)\)\s*$")
HEADER_RE = re.compile(r"^(window|chunk)\s*=\s*(\d+)\s*$")
REF_RE = re.compile(r"^S(\d+)$")
STEP_REL_TOL = 0.01
STEP_ABS_TOL = 0.51  # printed values are rounded to 1 decimal


@dataclass
class Step:
    k: Optional[int]
    name: str
    args: list
    value: Optional[float]
    raw: str
    kind: str = "step"       # step | seg | junk
    valid: bool = False
    reason: str = ""
    expected: Optional[float] = None      # value recomputed by the verifier (for UI / API)


@dataclass
class ParsedTrace:
    text: str
    has_think: bool = False
    has_answer: bool = False
    truncated: bool = False
    multi_answer: bool = False
    header: dict = field(default_factory=dict)
    has_segments_block: bool = False
    steps: list = field(default_factory=list)
    answer_raw: Optional[str] = None
    answer: Optional[float] = None       # None when absent/unparseable
    abstain: bool = False

    @property
    def n_steps(self):
        return len(self.steps)


def parse_completion(text):
    pt = ParsedTrace(text=text)
    m = re.search(r"<think>(.*?)</think>", text, re.S)
    if m:
        pt.has_think = True
        body = m.group(1)
    elif "<think>" in text:
        body = text.split("<think>", 1)[1]
    else:
        body = ""
    answers = re.findall(r"<answer>(.*?)</answer>", text, re.S)
    pt.has_answer = len(answers) >= 1
    pt.multi_answer = len(answers) > 1
    pt.truncated = "<think>" in text and "</answer>" not in text
    if len(answers) == 1 and m and text.find("<answer>") >= m.end():
        a = answers[0].strip()
        pt.answer_raw = a
        if a.upper() == "ABSTAIN":
            pt.abstain = True
        elif re.fullmatch(r"-?\d+(?:\.\d+)?", a):
            pt.answer = float(a)
    in_seg = False
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "<segments>":
            in_seg, pt.has_segments_block = True, True
            continue
        if line == "</segments>":
            in_seg = False
            continue
        if in_seg:
            g = SEG_RE.match(line)
            if g:
                i, s, e, tr, vl = g.groups()
                pt.steps.append(Step(int(i), "seg", [int(s), int(e), tr, vl], None, line, kind="seg"))
            else:
                pt.steps.append(Step(None, "junk", [], None, line, kind="junk"))
            continue
        h = HEADER_RE.match(line)
        if h and not pt.header:
            pt.header = {h.group(1): int(h.group(2))}
            continue
        g = STEP_RE.match(line)
        if g:
            k, name, argstr, val = g.groups()
            args = [a.strip() for a in argstr.split(",")] if argstr.strip() else []
            pt.steps.append(Step(int(k), name, args, float(val), line))
        else:
            pt.steps.append(Step(None, "junk", [], None, line, kind="junk"))
    return pt


def _close(pred, true):
    return abs(pred - true) <= max(STEP_REL_TOL * abs(true), STEP_ABS_TOL)


def check_steps(pt, series):
    """Mark every Step valid/invalid in place (recomputing from `series`); return list of bools."""
    vals = {}          # step number -> the model's stated value (agg steps check against these)
    seen = set()
    expect_k, expect_seg = 1, 0
    for st in pt.steps:
        try:
            if st.kind == "junk":
                raise ops.OpError("unparseable line")
            if st.kind == "seg":
                if st.k != expect_seg:
                    raise ops.OpError("segment ids must be 0,1,2,..")
                expect_seg += 1
                if st.k >= len(series.segs) or tuple(st.args) != tuple(series.segs[st.k]):
                    raise ops.OpError("segment differs from the rule")
                st.valid = True
                continue
            if st.k != expect_k:
                raise ops.OpError(f"expected S{expect_k}")
            expect_k += 1
            vals[st.k] = st.value
            if st.name == "agg":
                if len(st.args) < 2 or st.args[0] not in ops.AGG_OPS:
                    raise ops.OpError("bad agg")
                refs = []
                for a in st.args[1:]:
                    g = REF_RE.match(a)
                    if not g or int(g.group(1)) >= st.k or int(g.group(1)) not in vals:
                        raise ops.OpError("bad reference")
                    refs.append(vals[int(g.group(1))])
                true = ops.agg(st.args[0], refs)
                key = ("agg",) + tuple(st.args)
            else:
                if st.name == "seg_stat":
                    args = [int(st.args[0]), st.args[1]]
                else:
                    args = [int(a) for a in st.args]
                true = ops.eval_prim(series, st.name, args)
                key = (st.name,) + tuple(st.args)
            st.expected = float(true)
            if key in seen:
                raise ops.OpError("duplicate step")
            seen.add(key)
            if not math.isfinite(true) or not _close(st.value, true):
                raise ops.OpError(f"value {st.value} != {ops.fmt(true)}")
            st.valid = True
        except (ops.OpError, ValueError, IndexError) as e:
            st.valid, st.reason = False, str(e)
    return [s.valid for s in pt.steps]


def first_invalid(pt):
    for j, s in enumerate(pt.steps):
        if not s.valid:
            return j
    return None
