"""SGLang smoke test: one chat request with thinking off, optionally with a LoRA adapter."""
import argparse
import json
import time

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="http://127.0.0.1:30000")
ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
ap.add_argument("--lora", default=None, help="adapter name registered with --lora-paths")
args = ap.parse_args()

messages = [
    {"role": "system", "content": "You are Gus, the guard. Answer only from YOUR DOCUMENTS.\n"
     "YOUR DOCUMENTS:\n[D2.S1] Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall."},
    {"role": "user", "content": "Player: Who did you see on day 2 at midnight?"},
]
for name, lora in [("base", None), ("lora", args.lora)]:
    if name == "lora" and not lora:
        continue
    body = {
        "model": args.model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 64,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if lora:
        body["lora_path"] = lora
    t = time.time()
    r = httpx.post(f"{args.base_url}/v1/chat/completions", json=body, timeout=120)
    r.raise_for_status()
    out = r.json()
    print(f"[{name}] {time.time() - t:.2f}s tokens={out['usage']['completion_tokens']}")
    print(json.dumps(out["choices"][0]["message"]["content"]))
