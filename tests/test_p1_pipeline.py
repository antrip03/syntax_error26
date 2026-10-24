"""Offline tests for P1 pipeline glue (no GPU, no server). Uses the devstub when P2's modules are absent."""
import random

import pytest

pytest.importorskip("transformers")  # P1 server envs only; skipped on P2/P3 laptops

from archive import interfaces as I
from archive.train.common import load_config
from archive.train.grpo import _key, _text
from archive.train.sft import stratified

pytestmark = pytest.mark.skipif(I.MODE != "devstub", reason="devstub-only checks; P2 has its own tests")


def _data():
    from archive.devstub.world import generate_case, generate_tasks
    case = generate_case(1)
    tasks = generate_tasks(case, "train", random.Random(0))
    for i, t in enumerate(tasks):
        t["task_id"] = f"t{i}"
    return {case["case_id"]: case}, tasks


def test_gold_replies_pass_checker_and_score_full_reward():
    cases, tasks = _data()
    for t in tasks:
        g = I.gold(t)
        c = I.check(g, t, cases)
        assert c["parsed"] and (c["abstained"] or c["support_rate"] == 1.0)
        assert I.is_correct(I.reward(g, t, cases))


def test_hallucination_is_unsupported():
    cases, tasks = _data()
    t = next(t for t in tasks if t["type"] == "answerable_1hop")
    cite = t["gold"]["claims"][0]["cites"][0]
    c = I.check(f"<answer>\nCLAIM: I saw a dragon at the moonlit tower. [{cite}]\n</answer>", t, cases)
    assert c["claims"][0]["status"] == "unsupported"
    assert I.check("<answer>\nCLAIM: I was at the mill. [D9.S9]\n</answer>", t, cases)["claims"][0]["reason"] == "bad_cite"


def test_wrong_abstain_is_penalised():
    cases, tasks = _data()
    t = next(t for t in tasks if t["type"] == "answerable_1hop")
    parts = I.reward('<abstain reason="not_in_records"/>', t, cases)
    assert parts["abstain"] == -1.0 and parts["correct"] == 0.0


def test_prompt_key_roundtrip_and_completion_text():
    cases, tasks = _data()
    m = I.messages(tasks[0], cases)
    assert _key(m) == _key([dict(x) for x in m])
    assert _text([{"role": "assistant", "content": "hi"}]) == "hi" and _text("hi") == "hi"


def test_stratified_keeps_type_mix():
    rows = [{"type": "a"}] * 60 + [{"type": "b"}] * 40
    out = stratified(rows, 50, 0)
    assert len(out) == 50 and sum(r["type"] == "a" for r in out) == 30


def test_config_overrides(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\nguards: {max_abstain: 0.6}\n")
    cfg = load_config(str(p), ["a=2", "guards.max_abstain=0.9", "splits=[x,y]", "lora=null"])
    assert cfg == {"a": 2, "guards": {"max_abstain": 0.9}, "splits": ["x", "y"], "lora": None}
