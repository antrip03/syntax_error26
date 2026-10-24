# Environment notes (Kaggle T4 x2) -- M0 results

Kernel image (2026-10): Python 3.13, torch 2.11.0+cu128, transformers 5.16.1, peft 0.20.0, accelerate 1.14.0, datasets 4.8.5.
2x Tesla T4 15 GB, driver 580 / CUDA 13.0. Internet works when enabled for the kernel.

## SGLang (serving) -- WORKS
- Install in a separate py3.11 venv (`uv venv --python 3.11; uv pip install 'sglang[all]'`): sglang 0.5.22, torch 2.14.1, flashinfer 0.7.1. Keeps it away from the training env.
- Failed first: flashinfer JIT build `ld: cannot find -lcuda` (Kaggle has /usr/local/nvidia/lib64/libcuda.so.580.* but no `libcuda.so`).
  Fix: symlink the driver lib as `libcuda.so` in a dir and set `LIBRARY_PATH` to it (`scripts/find_libcuda.py`).
- Working flags (first candidate): `--dtype float16 --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.8`,
  on `CUDA_VISIBLE_DEVICES=1`. Not needed: the pytorch sampling backend / torch_native attention fallbacks.
- Command saved in `finseries/serve/launch_sglang.sh`.

## AlignTune 0.1.28 (GRPO) -- WORKS, no TRL fallback needed
- `pip install aligntune datasets` on the stock image; `create_rl_trainer(algorithm="grpo", backend="trl", ...)`.
- Custom reward callables are supported: `rewards=[{"type": fn, "weight": w}, ...]`; extra dataset columns reach `fn` as kwargs
  (needs `preserve_columns=["task_json"]`). Each reward logs as `rewards/registry_<name>/mean` per step.
- 5 GRPO steps, Qwen2.5-0.5B-Instruct, fp16, LoRA r16, 4 generations, 300 new tokens, gradient checkpointing: ~17 s/step on one T4, no OOM,
  with both a dummy reward and our real 4-component reward.
- AlignTune's dataset loader runs CuratorKIT (schema gate + filter) on the input -- a real integration.
- Dataset can be passed as a `datasets.Dataset` object. Warnings about torchao/Unsloth .so files are harmless (TRL backend).
- Not yet tested: 4-bit (QLoRA) loading, SFT entry point, 1.5B model, --resume, Unsloth backend.

## CuratorKIT 0.1.22 / AuditKit 1.1.3
- Both install with pip and import. Not yet exercised on our data (M3 / M6).
