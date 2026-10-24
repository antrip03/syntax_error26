# FinSeries-RLVR (backend)

Small open LLM (Qwen2.5-1.5B-Instruct, QLoRA) trained with GRPO and programmatic verifiable rewards to reason over
financial time series, comparing a flat chain-of-thought control with two temporal-abstraction scaffolds
(`chunk`, `event`). The model analyses a GIVEN series; it never predicts the future. See `PROJECT_PLAN.md`.

## Status
M1 (data, verifiers, op registry) and M2 (tasks, scaffolds, gold traces, rewards) are implemented and tested on CPU.
M0 (toolkit smoke tests on Kaggle T4) and M3+ need GPU time: see `docs/PROGRESS.md`.

## Run
```
pip install -e . -r requirements-data.txt
python scripts/prepare_data.py          # once, needs internet; upload data_prepared/ as a Kaggle Dataset
python scripts/make_tasks.py            # writes artifacts/tasks/{train,val,test_*}.jsonl + manifest.json
python -m pytest                        # 40+ tests, CPU only
```

## Layout
`finseries/verifiers` op registry + step checker (single source of truth) | `finseries/scaffolds` flat / chunk / event |
`finseries/tasks` families + gold answers | `finseries/rewards` outcome/process/format/consistency/length |
`finseries/adapters` thin wrappers for CuratorKIT / AlignTune / SGLang / AuditKit (M0+) | `configs/` yaml.
