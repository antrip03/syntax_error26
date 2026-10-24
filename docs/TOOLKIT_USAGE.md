# Toolkit usage (what each toolkit actually did in the pipeline)

Filled in as milestones complete. Nothing below is claimed until it has run and produced reported numbers.

| Toolkit | Stage | Planned role | Status | Evidence (command, artifact, numbers) |
| --- | --- | --- | --- | --- |
| SGLang | serving / eval / curation sampling | OpenAI-compatible endpoint for base + tuned models | smoke-tested (M0) | Qwen2.5-0.5B served on a T4, chat completion answered; command in `finseries/serve/launch_sglang.sh`, see `docs/ENV_NOTES.md` |
| CuratorKIT | Stage 1 curation | verify + pass-rate difficulty filter on generated tasks | installs; runs inside AlignTune loader (M0) | schema gate + filter executed on our task dataset during AlignTune data loading; our own pass-rate curation still to do (M3) |
| AlignTune | Stage 2 SFT + GRPO | SFT warm-start, GRPO with our rewards (TRL fallback if custom rewards unsupported) | GRPO smoke-tested (M0) | 5 GRPO steps with custom reward callables (dummy + our verifier) on a T4, no OOM; SFT not yet tested |
| AuditKit | Stage 3 eval | benchmark runs through SGLang; custom evaluators if supported | installs (M0) | not yet used for evals (M6) |

## Fallbacks taken
None so far: AlignTune accepts custom reward callables, so no direct TRL GRPOTrainer path is needed.
