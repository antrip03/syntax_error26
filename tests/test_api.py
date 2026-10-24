import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from finseries import scaffolds  # noqa: E402
from finseries.serve import api  # noqa: E402
from finseries.tasks.generate import read_jsonl  # noqa: E402


def test_analyze_verifies_gold_and_flags_tampering(monkeypatch):
    t = read_jsonl("artifacts/tasks/val.jsonl")[3]
    sc = scaffolds.get("chunk", trace_style="scratch2")
    gold = sc.gold_trace(t)

    class G:  # fake generation
        def __init__(self, text):
            self.text, self.n_tokens, self.finish = text, 100, "stop"

    cl = TestClient(api.app)
    monkeypatch.setattr(api.client, "generate", lambda *a, **k: [[G(gold)]])
    r = cl.post("/analyze", json={"series": t.series, "question": t.question, "arm": "chunk"}).json()
    assert r["verified"] and r["answer"] == pytest.approx(t.answer, abs=0.6) and all(s["valid"] for s in r["steps"])
    bad = gold.replace("S1:", "S1:", 1)
    lines = gold.split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("S1:"))
    head, val = lines[i].rsplit("= ", 1)
    lines[i] = head + "= " + str(int(float(val)) + 500)
    monkeypatch.setattr(api.client, "generate", lambda *a, **k: [[G("\n".join(lines))]])
    r2 = cl.post("/analyze", json={"series": t.series, "question": t.question, "arm": "chunk"}).json()
    assert not r2["verified"] and not r2["steps"][[s["text"].startswith("S1:") for s in r2["steps"]].index(True)]["valid"]
    assert r2["steps"][[s["text"].startswith("S1:") for s in r2["steps"]].index(True)]["expected"] is not None


def test_examples_and_health():
    cl = TestClient(api.app)
    assert cl.get("/health").json() == {"ok": True}
    ex = cl.get("/examples?limit=2&split=val").json()
    assert len(ex) == 2 and "series" in ex[0] and "gold_answer" in ex[0]
