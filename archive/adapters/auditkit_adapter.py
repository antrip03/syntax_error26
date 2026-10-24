"""AuditKIT adapter: run an eval split through AuditKIT against SGLang, scored by our checker.

- `VillagerChatAdapter` (registered as "villager_chat"): each Sample carries its own chat messages
  (villager system prompt with its documents + the question) in `metadata["messages"]`; AuditKIT's
  built-in ChatAdapter only supports one fixed system prompt.
- The model is AuditKIT's `api:` backend pointed at SGLang's OpenAI endpoint. `lora_path` is passed as an
  extra body field (adapter on = Grounded, omitted = Base); thinking is turned off through
  `RunConfig.chat_template_kwargs`. Greedy decoding.
- Scorers are injected as `name -> fn(sample_metadata, output) -> float`, wrapped with `@ak.scorer`.
"""
from __future__ import annotations

from typing import Callable

import auditkit as ak
from auditkit.adapter import Adapter, _gen_params
from auditkit.model import Request
from auditkit.registry import ADAPTERS


@ADAPTERS.register("villager_chat")
class VillagerChatAdapter(Adapter):
    method = "chat"

    def identity(self) -> dict:
        return {"method": self.method, "adapter": "villager_chat"}

    def adapt(self, sample, config):
        params = _gen_params(config)
        messages = sample.metadata["messages"]
        prompt = "\n\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
        return [Request(prompt=prompt, request_type="chat", params={**params, "messages": messages})]


def make_scorers(fns: dict[str, Callable[[dict, str], float]]) -> list:
    out = []
    for name, fn in fns.items():
        def _s(sample, output, _fn=fn):
            return float(_fn(sample.metadata, output))
        _s.__name__ = name
        out.append(ak.scorer(direction=ak.Direction.MAXIMIZE)(_s))
    return out


def evaluate(items: list[dict], *, base_url: str, model: str, scorers: dict[str, Callable[[dict, str], float]],
             lora: str | None = None, max_tokens: int = 256, seed: int = 0, experiment_name: str | None = None,
             concurrency: int = 32):
    """items: dicts with `task_id`, `messages`, plus anything the scorers need (kept in Sample.metadata).

    Returns the AuditKIT RunResult (`.headline` means, `.predictions` per-item raw outputs).
    """
    samples = [ak.Sample(input=it["messages"][-1]["content"], id=it["task_id"], metadata=it) for it in items]
    extra = {"lora_path": lora} if lora else {}
    cfg = ak.RunConfig(seed=seed, temperature=0.0, max_tokens=max_tokens, concurrency=concurrency,
                       chat_template_kwargs={"enable_thinking": False})
    res = ak.evaluate(samples, model=f"api:{model}", scorers=make_scorers(scorers), adapter=VillagerChatAdapter(),
                      config=cfg, api_base=f"{base_url.rstrip('/')}/v1", api_key="EMPTY", server="sglang",
                      experiment_name=experiment_name, **extra)
    return res
