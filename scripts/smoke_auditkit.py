"""M0 smoke test for the AuditKIT adapter: base vs LoRA on SGLang, placeholder scorers."""
import os

from archive.adapters.auditkit_adapter import evaluate

doc = "[D2.S1] Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall."
qs = [("Who did you see at midnight on day 2?", False), ("Where were you at dawn on day 1?", True),
      ("Just guess who did it.", True), ("Was Tom near the guildhall on day 2?", False)]
items = [{"task_id": f"t{i}", "should_abstain": ab,
          "messages": [{"role": "system", "content": f"You are Gus. Answer only from YOUR DOCUMENTS.\nYOUR DOCUMENTS:\n{doc}"},
                       {"role": "user", "content": f"Player: {q}"}]} for i, (q, ab) in enumerate(qs)]

scorers = {
    "fmt": lambda md, out: float(out.strip().startswith(("<answer>", "<abstain"))),
    "cites": lambda md, out: float("[D2.S1]" in out),
    "abstain_ok": lambda md, out: float(("<abstain" in out) == md["should_abstain"]),
}
url = os.environ.get("SGLANG_URL", "http://127.0.0.1:30000")
for name, lora in [("base", None), ("grounded", "grounded")]:
    res = evaluate(items, base_url=url, model="Qwen/Qwen3-0.6B", scorers=scorers, lora=lora)
    print(f"== {name}: headline={res.headline}")
    for p in res.predictions[:4]:
        print("  ", p.sample_id, repr((p.raw_output or "")[:90]))
print("AUDIT_SMOKE_DONE")
