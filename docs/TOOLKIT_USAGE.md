# Toolkit usage

What each toolkit does for the reported numbers. Updated as work progresses; status per toolkit is marked.

## SGLang (0.5.9) — serving, curation sampling, evaluation, game
- Status: smoke-tested. Serves Qwen3 base + a LoRA adapter (`--enable-lora --lora-paths grounded=...`); the adapter is chosen per request with `"lora_path": "grounded"` (Base vs Grounded toggle, Liar mode on the same server).
- Planned use: CuratorKIT's sampling backend (OpenAI-compatible endpoint), AuditKIT's `api:` backend, and the game backend.

## AlignTune — SFT (R1) and GRPO (R3)
- Status: GRPO smoke test passes through `create_rl_trainer(algorithm="grpo", backend="trl", rewards=[{"type": "custom", ...}])` with a custom Python reward. No TRL fallback needed so far.
- Can: custom per-sample reward callables, LoRA, local JSONL datasets with chat-format prompts.
- Caveats found: the custom reward is called per completion (docs say batch); thinking mode needs `chat_template_kwargs` passed explicitly (see `ENV_NOTES.md`).
- SFT smoke test passes through `create_sft_trainer(backend="trl", completion_only_loss=True, use_peft=True)`; the adapter serves in SGLang unchanged.
- Planned: our checker-based reward (`archive/rewards/combine.py`) as the custom GRPO reward.

## CuratorKIT — data curation
- Status: smoke-tested (`scripts/smoke_curatorkit.py`): 5 tasks -> GoldCheckGate (1 broken gold dropped) -> PassRateGate (4 samples per task through CuratorKIT's `LiteLLMBackend` on SGLang, 8.7 s) -> curated JSONL + manifest. Adapter: `archive/adapters/curatorkit_adapter.py`.
- Can: `Pipeline` of readers, custom gates (`BaseGate.run(samples) -> (passed, rejected)`), custom generators, OpenAI-compatible LLM backend (points at our SGLang), exporters (messages, GRPO). `DataSample` carries `responses` and `reward_scores`.
- Cannot (built in): pass-rate filtering. Plan: a custom gate that samples N replies per task through CuratorKIT's LLM backend, scores them with our checker, and keeps tasks whose pass rate is in [0.2, 0.8]; a second custom gate verifies gold replies with the checker.

## AuditKIT — evaluation
- Status: smoke-tested (`scripts/smoke_auditkit.py`): Base vs LoRA on SGLang through `ak.evaluate(model="api:...", server="sglang")`, custom `@ak.scorer` metrics, greedy, thinking off via `RunConfig.chat_template_kwargs`, adapter chosen with an extra `lora_path` body field. Adapter: `archive/adapters/auditkit_adapter.py`.
- Can: custom scorers (our checker metrics plug in directly), OpenAI-compatible `api:` backend, per-sample predictions in `RunResult.predictions`.
- Added: `VillagerChatAdapter` (registered via AuditKIT's `ADAPTERS` registry) because the built-in `ChatAdapter` takes one fixed system prompt, and each villager needs its own documents in the system prompt.
