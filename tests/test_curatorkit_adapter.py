import json

import pytest

pytest.importorskip("curatorkit")

from finseries.adapters.curatorkit_adapter import curate  # noqa: E402

TASKS = "artifacts/tasks/val.jsonl"


def test_curation_pipeline_runs_and_filters(tmp_path):
    ids = [json.loads(l)["id"] for l in open(TASKS)][:60]
    rates = {i: {"chunk": (k % 10) / 10.0} for k, i in enumerate(ids)}   # 0.0 .. 0.9
    small = tmp_path / "small.jsonl"
    small.write_text("".join(l for l in list(open(TASKS))[:60]))
    raw = curate(str(small), str(tmp_path / "raw"))
    assert raw["n_out"] == 60 and raw["n_rejected"] == 0
    cur = curate(str(small), str(tmp_path / "cur"), arm="chunk", pass_rates=rates, lo=0.2, hi=0.8)
    kept = [json.loads(l)["id"] for l in open(tmp_path / "cur" / "tasks.jsonl")]
    assert len(kept) == 6 * 7 and cur["rejected_by_reason"]["too_hard"] == 12 and cur["rejected_by_reason"]["too_easy"] == 6
    assert (tmp_path / "cur" / "manifest.json").exists() and (tmp_path / "cur" / "rejected.jsonl").exists()


def test_verifier_gate_rejects_corrupted_gold(tmp_path):
    rows = [json.loads(l) for l in list(open(TASKS))[:5]]
    rows[0]["answer"] = rows[0]["answer"] + 12345.0
    small = tmp_path / "bad.jsonl"
    small.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = curate(str(small), str(tmp_path / "o"))
    assert out["n_out"] == 4 and any(k.startswith("gold_trace_invalid") for k in out["rejected_by_reason"])
