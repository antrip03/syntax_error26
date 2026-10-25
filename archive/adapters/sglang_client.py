"""Async batched chat client for SGLang's OpenAI-compatible endpoint.

- Adapter selection per request: `lora="grounded"` (or any name registered with --lora-paths); None = base model.
- Thinking is always off (`chat_template_kwargs.enable_thinking=False`).
- Policy: greedy for eval (temperature 0), T=0.9 for sampling; a per-request seed makes sampling reproducible.
- Retries with exponential backoff on connection errors and 5xx.
"""
from __future__ import annotations

import asyncio
import os
import random

import httpx

DEFAULT_URL = os.environ.get("SGLANG_URL", "http://127.0.0.1:30000")
GREEDY = {"temperature": 0.0}
SAMPLE = {"temperature": 0.9, "top_p": 1.0}

class SGLangClient:
    def __init__(self, base_url: str = DEFAULT_URL, model: str = "Qwen/Qwen3-1.7B", concurrency: int = 64,
                 timeout: float = 180.0, retries: int = 4, headers: dict | None = None):
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.model, self.retries = model, retries
        self.sem = asyncio.Semaphore(concurrency)
        self.http = httpx.AsyncClient(timeout=timeout, headers=headers or {})

    async def chat(self, messages: list[dict], *, lora: str | None = None, max_tokens: int = 256,
                   temperature: float = 0.0, top_p: float | None = None, seed: int | None = None) -> dict:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                "chat_template_kwargs": {"enable_thinking": False}}
        if top_p is not None:
            body["top_p"] = top_p
        if seed is not None:
            body["seed"] = seed
        if lora:
            body["lora_path"] = lora
        async with self.sem:
            for attempt in range(self.retries + 1):
                try:
                    r = await self.http.post(self.url, json=body)
                    if r.status_code >= 500:
                        raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
                    r.raise_for_status()
                    out = r.json()
                    ch = out["choices"][0]
                    return {"text": ch["message"]["content"] or "", "finish_reason": ch.get("finish_reason"),
                            "completion_tokens": out["usage"]["completion_tokens"],
                            "prompt_tokens": out["usage"]["prompt_tokens"]}
                except (httpx.TransportError, httpx.HTTPStatusError):
                    if attempt == self.retries:
                        raise
                    await asyncio.sleep(2 ** attempt + random.random())

    async def chat_many(self, batch: list[list[dict]], **kw) -> list[dict]:
        seed = kw.pop("seed", None)
        return await asyncio.gather(*[self.chat(m, seed=None if seed is None else seed + i, **kw)
                                      for i, m in enumerate(batch)])

    async def aclose(self):
        await self.http.aclose()

def chat_many_sync(batch: list[list[dict]], *, base_url: str = DEFAULT_URL, model: str = "Qwen/Qwen3-1.7B",
                   concurrency: int = 64, **kw) -> list[dict]:
    async def _run():
        c = SGLangClient(base_url, model, concurrency)
        try:
            return await c.chat_many(batch, **kw)
        finally:
            await c.aclose()
    return asyncio.run(_run())
