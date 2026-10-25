# Toolkit usage: what each toolkit actually did in the pipeline

Every statement below refers to something that ran and produced a number we report. Code lives under `finseries/adapters/`
(thin wrappers) and the Kaggle/Modal driver scripts under `scripts/`.

| Toolkit | Stage | What it did here | Where |
| --- | --- | --- | --- |
| **SGLang** | serving + eval + sampling | Served every model we evaluate (base Qwen2.5-1.5B, SFT-merged, GRPO-merged) behind its OpenAI-compatible endpoint; all evaluation generations, the pass-rate sampling for curation (8 samples/task, T=0.7) and the live-eval path of AuditKit go through it | `adapters/sglang_client.py`, `serve/sglang_server.py`, `serve/launch_sglang.sh` |
| **CuratorKIT** | Stage 1 data curation | (a) Inside AlignTune's data loader (schema gate / filter / format detection on every SFT and GRPO dataset). (b) Our own `curatorkit.Pipeline`: `TaskReader` -> `VerifierGate` (re-verifies every gold trace of all three scaffolds against the step checker and token budgets) -> `PassRateGate` (keeps tasks whose measured pass rate is in [0.2, 0.8]) -> exporter, with CuratorKIT's own manifest, `rejected.jsonl` and checksums | `adapters/curatorkit_adapter.py`, `scripts/m3_baseline.py`, `scripts/m5_curate.py` |
| **AlignTune** | Stage 2 training | SFT warm-start (`create_sft_trainer`, TRL backend, LoRA r=32; 4-bit QLoRA on T4, bf16 on A100) and GRPO (`create_rl_trainer(algorithm="grpo")`) with our verifier rewards passed as custom reward callables (one callable per reward component, so each is logged separately per step) | `scripts/m4_sft.py`, `finseries/train/grpo.py`, `scripts/m5_grpo.py` |
| **AuditKit** | Stage 3 evaluation | `auditkit.evaluate` scores every reported run: our deterministic verifier is plugged in as AuditKit scorers (`final_accuracy`, `step_validity`, `format_ok`, `outcome_reward`); AuditKit aggregates, fingerprints and records the runs. `evaluate_live` lets AuditKit drive generation through SGLang (used by the demo API); `evaluate_precomputed` scores generations that SGLang produced earlier (used for the tables) | `adapters/auditkit_adapter.py`, `eval/report.py` |

## Evidence per toolkit

### SGLang
* M0: Qwen2.5-0.5B served on a Kaggle T4 (GPU 1) and answered a chat request. Working command in `serve/launch_sglang.sh`; the fix needed
  on Kaggle was linking the driver `libcuda.so` for flashinfer's JIT (`scripts/find_libcuda.py`).
* M3: base Qwen2.5-1.5B baseline on 400 val tasks x 3 scaffolds (greedy) plus 3x300 tasks x 8 samples pass-rate sampling.
* M4/M5/M6: every SFT and GRPO result in `artifacts/results/summary.md` was generated through SGLang.
* Flags that worked on T4: `--dtype float16 --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.8`.

### CuratorKIT
* M3 (base model): the pipeline ran on a 300-task train subset: the verifier gate passed 300/300 gold traces; the pass-rate gate rejected
  all 300 as `too_hard` because the zero-shot base model scores 0% (it writes Python, not our step grammar). This is why curation was
  moved after SFT (see PROGRESS.md).
* SFT-model curation (`scripts/m5_curate.py`, Kaggle T4 + SGLang): chunk SFT model, 8 samples/task at T=0.7 on 1500 train tasks.
  Mean pass rate 22.6%; 54.7% of tasks never solved, 12.2% always solved, only 18% in the 20-80% band.
  CuratorKIT pipeline: verifier gate rejected 3/1500 (gold trace above the token budget); pass-rate gate kept 270 tasks
  (rejected: 1023 `too_hard`, 204 `too_easy`). Manifests and `rejected.jsonl` written by CuratorKIT are in `docs/results/curation/`.
* Why it matters: the same numbers explain the weak GRPO signal. With uncurated prompts about 70% of tasks give zero reward variance
  inside a group, so GRPO gets no gradient from them (`frac_reward_zero_std` was 0.5-1.0 in most R1/R5 steps).
* Inside AlignTune: the training logs show `SchemaGate`, `Filter`, format detection and normalisation steps from CuratorKIT for every dataset.

### AlignTune
* SFT: 1500-6000 gold-trace examples per scaffold; the final recipes are `flat_e5` and `chunk_e5` (see `docs/PROGRESS.md`).
* GRPO: custom reward callables are supported (`rewards=[{"type": fn, "weight": w}]`), so the direct-TRL fallback was **not** needed.
  Reward components are logged per step as `rewards/registry_r_<component>/mean`.
* Workarounds we had to add (all in our code, not by editing AlignTune): cast trainable LoRA parameters to fp32 on T4 (no bf16),
  pass `max_completion_length` (AlignTune's default 256 silently truncates completions), checkpoint-resume hook (verified).

### AuditKit
* `eval/report.py` calls `ak.evaluate(samples, model="precomputed", scorers=[...])` for every run/split in the results table; its headline
  numbers match our own metric code exactly on the self-test (accuracy 0.255, step validity 0.6817 on the chunk SFT validation run).
* The live path (`evaluate_live`) uses an SGLang-backed model callable.

## Honest limits
* AuditKit has no dedicated `sglang:` backend; SGLang is reached through a model callable. Custom metrics are implemented as AuditKit
  scorers, so they do run inside AuditKit.
* The SFT-model curation arrived too late to feed GRPO for R1-R3; GRPO used an uncurated random train subset. The curated-vs-raw ablation
  is therefore not reported.

## Fallbacks taken
None of the required toolkits was dropped. The direct TRL GRPO fallback was not needed.
