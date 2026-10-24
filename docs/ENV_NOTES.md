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
| `/tmp/archive_p1/.venv-train` (train) | AlignTune (editable, from source), TRL 1.7.1, transformers 5.20, PEFT 0.21 | Unpinned install pulled **torch 2.11+cu130, which cannot use this GPU** ("driver too old"). Must be repinned to a cu12x torch before training. CPU work (e.g. making a dummy adapter) is fine. |

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

## Failed / gotchas
- `sglang[all]` unpinned resolves to a CUDA 13 build. Pin `==0.5.9`.
- `--lora-paths` with a directory that does not exist is treated as an HF repo id and fails with "Repo id must be in the form...".
