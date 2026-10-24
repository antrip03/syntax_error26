"""FastAPI backend for the later UI. Generation is proxied through SGLang; correctness is recomputed deterministically.

POST /analyze {series: [int bps], question: str, arm: flat|chunk|event} ->
    {answer, steps: [{text, valid, expected}], tokens, verified, truncated}
GET  /examples  -> saved test cases (series, question, arm, gold answer)
GET  /health
Env: SGLANG_URL (default http://127.0.0.1:30000), FINSERIES_VARIANT (default e5), FINSERIES_EXAMPLES (jsonl of tasks).
The model analyses the GIVEN series only; nothing here predicts the future.
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .. import scaffolds
from ..adapters.sglang_client import SGLangClient
from ..scaffolds.base import SYSTEM
from ..tasks.generate import read_jsonl
from ..tasks.templates import Task
from ..verifiers.ops import Series

VARIANTS = {"base": {}, "e4": {"trace_style": "scratch"}, "e5": {"trace_style": "scratch2"}}
app = FastAPI(title="FinSeries-RLVR")
client = SGLangClient(os.environ.get("SGLANG_URL", "http://127.0.0.1:30000"))


class AnalyzeRequest(BaseModel):
    series: list[int]
    question: str
    arm: str = "chunk"
    max_tokens: int = 1500


def _task(series, question):
    return Task(id="api", split="api", family="adhoc", depth=0, length=len(series), series=list(series), program={},
                question=question, answer=float("nan"))


def analyze_text(series, question, arm, completion, n_tokens):
    """Parse + verify a completion for an arbitrary series (no gold answer needed)."""
    if arm not in scaffolds.REGISTRY:
        raise HTTPException(400, f"unknown arm {arm}")
    sc = scaffolds.get(arm, **VARIANTS[os.environ.get("FINSERIES_VARIANT", "e5")])
    pt = sc.parse(completion)
    from ..verifiers import steps as S
    S.check_steps(pt, Series(series))
    steps = [{"text": s.raw, "valid": bool(s.valid), "expected": s.expected} for s in pt.steps]
    ops_steps = [s for s in pt.steps if s.kind == "step"]
    last_ok = bool(ops_steps) and ops_steps[-1].valid and pt.answer is not None and \
        abs(pt.answer - ops_steps[-1].value) <= max(0.005 * abs(ops_steps[-1].value), 0.051)
    verified = bool(steps) and all(s["valid"] for s in steps) and last_ok and not pt.truncated
    return {"answer": pt.answer, "abstain": pt.abstain, "steps": steps, "tokens": n_tokens, "verified": verified,
            "truncated": pt.truncated}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    sc = scaffolds.get(req.arm, **VARIANTS[os.environ.get("FINSERIES_VARIANT", "e5")])
    if len(req.series) < 5:
        raise HTTPException(400, "series too short")
    prompt = sc.build_prompt(_task(req.series, req.question))
    g = client.generate(SYSTEM, [prompt], n=1, temperature=0.0, max_tokens=req.max_tokens)[0][0]
    if g.finish.startswith("error"):
        raise HTTPException(502, f"generation failed: {g.finish}")
    return analyze_text(req.series, req.question, req.arm, g.text, g.n_tokens)


@app.get("/examples")
def examples(limit: int = 10, split: str = "test_period"):
    path = os.environ.get("FINSERIES_EXAMPLES", f"artifacts/tasks/{split}.jsonl")
    if not os.path.exists(path):
        raise HTTPException(404, f"no examples file {path}")
    return [{"id": t.id, "series": t.series, "question": t.question, "family": t.family, "depth": t.depth,
             "gold_answer": t.answer, "asset": t.asset, "start_date": t.meta.get("start_date")}
            for t in read_jsonl(path)[:limit]]
