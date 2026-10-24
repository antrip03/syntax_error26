# Progress

## P1 — M0 smoke tests (2026-10-24, T+~1.5h)
- Works on GPU 2 (Slurm job 2943): SGLang 0.5.9 serving Qwen3-0.6B with per-request LoRA; AlignTune SFT (20 steps, 9.5 s) and GRPO (5 steps, 14 s) via the TRL backend with a custom reward; SFT adapter served by SGLang produces our exact reply format.
- CuratorKIT pipeline (gold gate + pass-rate gate sampling through SGLang) and AuditKIT eval (api: backend + custom scorers + per-villager chat adapter) both run end to end on 0.6B.
- Fixes needed: torch repinned to 2.9.1+cu128 (driver 535); AlignTune custom rewards are per-sample; thinking must be disabled via `chat_template_kwargs`.
- Next: stub API (done) handed to P3; wait for P2's schemas/checker/prompt builder; write sglang_client, sft.py, grpo.py, run_eval.py against them; 1.7B timing run.
- Risk: untrained 0.6B almost never uses our format, so pass-rate band [0.2, 0.8] may drop most answerable tasks; re-check with 1.7B and the real prompt.
