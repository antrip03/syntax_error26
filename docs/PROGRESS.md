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

## M4 SFT (1500 gold traces/arm, 2 epochs, QLoRA r32) -- first results: format learned, values not
- Works: AlignTune SFT on T4 (~15 s/step, 47 min/arm), merge, SGLang eval on val (400). Parse rate: chunk 99.8%, flat 99.5%, event 96.8%; well-formed step lines 97-99.5%.
- Numbers (val, greedy): chunk acc 6.8% / step validity 23%; flat 5.0% / 32%; event 4.8% / 12%. Plan target (step validity >= 90%) NOT met.
- Diagnosis: validity by op is ~1-6% for ret/vol/hi/lo/mdd/dd (counts 26-64%, agg 64-67% since it only checks the model's own numbers). Inspection shows right magnitude, wrong digits, and even single-entry lookups wrong (ret(15,15) = -55 vs true 93): the model cannot fetch r[i] from packed rows nor do multi-term arithmetic in one step.
- Next: experiments on chunk with (e1) per-value indexed series ("15:93"), (e2) indexed + scratch copy of window values in `#` lines before ret/vol/count steps, (e3) index every 5th + scratch. Prompt budget rises to ~830 tokens for e1/e2 (max_seq_length 1400).
- Known: event segments are 1% valid (rolling-std segmentation rule is too hard to execute in-head); vol (sqrt of sum of squares) and level ops (hi/lo/dd) likely need a simpler definition or a level scratchpad if e2 does not fix them.

## SFT recipe search (chunk, val 400, greedy) -- Modal A100 (~$1/run) + Kaggle T4
| run | data | format | acc | step validity | notes |
| --- | --- | --- | --- | --- | --- |
| M4 base (T4) | 1500x2ep | rows, plain | 6.8% | 23% | format learned (parse 99.8%), values wrong |
| e1 (T4) | 1500x2 | indexed series | 5.0% | 24% | indexing alone does not help |
| e2 (T4) | 1500x2 | indexed + copy lines | 5.8% | 28% | |
| e3 (T4) | 1500x2 | index5 + copy lines | 5.2% | 21% | |
| e2 big (Modal) | 3000x4ep | indexed + copy | 11.5% | 39% | more training helps; hi/lo ~1% (levels from day 0), ret 19%, vol 21%, count_breach 74% |
| e4 (Modal) | 6000x2ep (sft_extra) | rows + copy + region-relative levels | 15.2% | 50.3% | hi/lo 49%, mdd 46%, running_drawdown acc 26%; ret 20%, vol 25% |
| e5 (Modal) | 6000x2ep | e4 + running sums cs/ss, breach flags | pending | pending | testing whether 2-operand additions fix ret/vol |
Changes made along the way: hi/lo now take a start day s and count levels from it (no prefix sum from day 0); extra SFT-only tasks (9000, train-block real windows + disjoint synthetic seeds, no series overlap with val/test). Prompt/completion budgets no longer ~512: scratch traces average 280-370 tokens, max ~840; training seq 1600. Modal spend so far ~ $2.1-2.6 of $5.58 (one early run died on a local network drop, cost unknown).
