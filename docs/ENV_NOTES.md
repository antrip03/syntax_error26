# Environment notes

## Server
- Host `vitallab1`: 4x RTX A6000 48 GB, NVIDIA driver 535.309.01 (CUDA 12.2). **No CUDA 13 builds** (they need driver >= 580).
- GPUs are shared and allocated through Slurm. We hold GPU 2 with a long-running Slurm job (`sbatch --gres=gpu:1 --time=0 --wrap="sleep infinity"`, job 2943). Run GPU work inside it with `scripts/gpu.sh <cmd>` (`srun --jobid=2943 --overlap`). Inside the job, the GPU is `cuda:0`.
- `/home` is almost full (about 12 GB free). Venvs, HF cache, data and checkpoints live in `/tmp/archive_p1` (232 GB free, **not backed up**). `data_raw/`, `data_prepared/` and `artifacts/` in the repo are symlinks into it. Copy final adapters off `/tmp`.

## Environments (uv, Python 3.11)
`source scripts/env.sh serve|train` sets `HF_HOME=/tmp/archive_p1/hf`, `HF_HUB_OFFLINE=1`, `PYTHONPATH` and activates the venv.

| venv | contents | notes |
| --- | --- | --- |
| `/tmp/archive_p1/.venv` (serve) | `sglang[all]==0.5.9`, torch 2.9.1+cu128, transformers 4.57, CuratorKIT (editable, from source), `auditkit[requests]` (from source), fastapi, httpx | torch cu128 runs fine on driver 535 (minor-version compatibility). PEFT import fails here (torchao 0.9 pinned by sglang), so do not build adapters in this env. |
| `/tmp/archive_p1/.venv-train` (train) | AlignTune (editable, from source), torch 2.9.1+cu128, TRL 1.7.1, transformers 5.20, PEFT 0.21 | Unpinned install pulled torch 2.11+cu130 ("driver too old"). Fixed: `uv pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu128`, then `uv pip uninstall vllm xformers torchao` (vllm/xformers need torch>=2.10; PEFT refuses torchao<0.16 and torchao>=0.16 needs newer torch). `uv pip check` still lists aligntune's torchao/xformers requirement; harmless for the TRL backend. |

Toolkit sources are cloned in `/tmp/archive_p1/src/{aligntune,CuratorKIT,AuditKIT}`.

Pin notes (from AuditKIT `docs/SGLANG.md`): sglang 0.5.10 is the last CUDA 12 build; 0.5.11+ needs CUDA 13. 0.5.9 is the last on transformers 4.x.

## Models
`Qwen/Qwen3-0.6B` and `Qwen/Qwen3-1.7B` downloaded to `/tmp/archive_p1/hf`.

## SGLang (working)
```
scripts/serve_sglang.sh Qwen/Qwen3-0.6B                       # base only; port 30000, --mem-fraction-static 0.3
scripts/serve_sglang.sh Qwen/Qwen3-0.6B --enable-lora --max-lora-rank 16 \
    --lora-target-modules all --lora-paths grounded=/path/to/adapter
python scripts/smoke_sglang.py --lora grounded
```
- Thinking off: request body `"chat_template_kwargs": {"enable_thinking": false}` (verified: no `<think>` in output).
- Adapter selection per request: body field `"lora_path": "grounded"` (verified), or `"model": "<base>:grounded"` (supported in `serving_base.py`, not tested). Omit both for the base model.
- Measured on 0.6B: about 0.1 s for an 11-token reply; startup about 60 s.

## AlignTune GRPO smoke test (working)
`scripts/gpu.sh python scripts/smoke_grpo_aligntune.py` (train env): 5 GRPO steps, Qwen3-0.6B, LoRA r16, 4 prompts x 4 generations, `backend="trl"`, local JSONL dataset with conversational `prompt` column, dummy custom reward. 14 s for 5 steps, no OOM, reward varies and loss is non-zero.

Gotchas found:
- **Custom reward contract differs from the docs.** The installed `RewardBridge` wraps `{"type": "custom", "params": {"function": f}}` as a per-sample scorer: `f(completion, **row_columns) -> float`, where `completion` is a list of chat messages for conversational datasets. Returning a list raises `TypeError ... expected float or None`.
- **Thinking mode:** AlignTune's `enable_thinking=False` default only writes a dataset column that TRL 1.7 ignores, so Qwen3 still emitted `<think>`. Fix: pass `chat_template_kwargs={"enable_thinking": False}` to `create_rl_trainer`; AlignTune copies extra keys onto `GRPOConfig`.
- `max_prompt_length` is not forwarded (TRL 1.7 removed it); keep prompts short ourselves.

## Failed / gotchas
- `sglang[all]` unpinned resolves to a CUDA 13 build. Pin `==0.5.9`.
- `--lora-paths` with a directory that does not exist is treated as an HF repo id and fails with "Repo id must be in the form...".
