# Progress

## M1 + M2 (CPU, done locally)
- Works: ops registry, step checker, segmenter, synthetic generator, leak-free splits, 3 scaffolds with gold traces, 5 reward components + 2 bundles, adversarial probes. 41 tests pass.
- Numbers: gold traces 100% valid on 1000 tasks x 3 scaffolds; segmenter boundary F1 0.47 vs synthetic vol-class boundaries (tol 4); prompts ~520-590 tokens, gold completions mean 140-210.
- Next: M0 on Kaggle (SGLang on T4, AlignTune 5-step GRPO) -- needs GPU; then M3 baselines/curation.
- Known issues: prompt budget is ~600 tokens (not 512) at length 60-80 -- tokens/point is 3-4 plus ~250 instruction tokens; for drawdown tasks chunk needs (hi,lo,mdd) triples so it is NOT shorter than flat there (windowed ops: chunk 0.07 steps/pt vs flat 0.13).
