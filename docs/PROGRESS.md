# Progress

## P1 — M0 smoke tests (2026-10-24, T+~1.5h)
- Works on GPU 2 (Slurm job 2943): SGLang 0.5.9 serving Qwen3-0.6B with per-request LoRA; AlignTune SFT (20 steps, 9.5 s) and GRPO (5 steps, 14 s) via the TRL backend with a custom reward; SFT adapter served by SGLang produces our exact reply format.
- CuratorKIT pipeline (gold gate + pass-rate gate sampling through SGLang) and AuditKIT eval (api: backend + custom scorers + per-villager chat adapter) both run end to end on 0.6B.
- Fixes needed: torch repinned to 2.9.1+cu128 (driver 535); AlignTune custom rewards are per-sample; thinking must be disabled via `chat_template_kwargs`.
- Next: stub API (done) handed to P3; wait for P2's schemas/checker/prompt builder; write sglang_client, sft.py, grpo.py, run_eval.py against them; 1.7B timing run.
- Risk: untrained 0.6B almost never uses our format, so pass-rate band [0.2, 0.8] may drop most answerable tasks; re-check with 1.7B and the real prompt.

## P1 — pipeline scripts (2026-10-24, T+~2.5h)
- Written and dry-run end to end on 0.6B with stand-in data: `archive/train/{curate,sft,grpo}.py`, `archive/eval/run_eval.py`, `archive/adapters/{sglang_client,aligntune_adapter}.py`, `archive/interfaces.py`, configs for each stage.
- GRPO: starts from the R1 adapter (weights loaded into AlignTune's fresh LoRA), one reward function per part so every part is logged, abstain and reward-hacking guards, `--resume` from the latest checkpoint.
- GRPO timing on 1.7B: 9.7 s/step at crunch settings, so 100 steps is ~15-75 min depending on reply length.
- Known: on untrained models answerable tasks score pass rate 0, so the 0.2-0.8 band drops them; SFT reads gold_ok.jsonl by default. Abstain-heavy SFT data made the dry R1 abstain on everything: check val accuracy, not just parse/support, before GRPO.
- Next: swap in P2's modules when they land (no code change; interfaces.py switches automatically), run real curation + SFT on 1.7B.
