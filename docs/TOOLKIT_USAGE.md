# Toolkit usage (what each toolkit actually did in the pipeline)

Filled in as milestones complete. Nothing below is claimed until it has run and produced reported numbers.

| Toolkit | Stage | Planned role | Status | Evidence (command, artifact, numbers) |
| --- | --- | --- | --- | --- |
| SGLang | serving / eval / curation sampling | OpenAI-compatible endpoint for base + tuned models | not started (M0) | - |
| CuratorKIT | Stage 1 curation | verify + pass-rate difficulty filter on generated tasks | not started (M3) | - |
| AlignTune | Stage 2 SFT + GRPO | SFT warm-start, GRPO with our rewards (TRL fallback if custom rewards unsupported) | not started (M0/M4/M5) | - |
| AuditKit | Stage 3 eval | benchmark runs through SGLang; custom evaluators if supported | not started (M6) | - |

## Fallbacks taken
None yet.
