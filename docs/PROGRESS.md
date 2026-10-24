# Progress

## M1 + M2 (CPU, done locally)
- Works: ops registry, step checker, segmenter, synthetic generator, leak-free splits, 3 scaffolds with gold traces, 5 reward components + 2 bundles, adversarial probes. 41 tests pass.
- Numbers: gold traces 100% valid on 1000 tasks x 3 scaffolds; segmenter boundary F1 0.47 vs synthetic vol-class boundaries (tol 4); prompts ~520-590 tokens, gold completions mean 140-210.
- Next: M0 on Kaggle (SGLang on T4, AlignTune 5-step GRPO) -- needs GPU; then M3 baselines/curation.
- Known issues: prompt budget is ~600 tokens (not 512) at length 60-80 -- tokens/point is 3-4 plus ~250 instruction tokens; for drawdown tasks chunk needs (hi,lo,mdd) triples so it is NOT shorter than flat there (windowed ops: chunk 0.07 steps/pt vs flat 0.13).

## M0 (Kaggle T4 x2, done)
- Works: SGLang serves Qwen2.5-0.5B on GPU 1 (after libcuda link fix); AlignTune GRPO 5 steps on GPU 0 with custom verifier rewards, ~17 s/step, no OOM; CuratorKIT and AuditKit install.
- Numbers: base 0.5B scores 0 on all four reward components on chunk tasks (expected, no format knowledge); every completion hit the 256-300 token cap.
- Next: M3 -- serve base 1.5B via SGLang, R0 baselines on val, CuratorKIT/pass-rate curation; need the task files on Kaggle (upload as a Dataset).
- Known issues: AlignTune SFT, 4-bit loading, 1.5B memory and resume are untested; Kaggle image is Python 3.13 / torch 2.11, SGLang needs its own py3.11 venv.
