#!/usr/bin/env bash
# VERIFIED on Kaggle T4 x2 (M0, sglang 0.5.22, torch 2.14.1, flashinfer 0.7.1, py3.11 venv):
# Qwen2.5-0.5B-Instruct served on GPU 1 and answered "17+25" -> 42 via /v1/chat/completions.
# usage: bash finseries/serve/launch_sglang.sh <model_path_or_hf_id> [port]   (GPU 0 is for training)
MODEL=${1:-Qwen/Qwen2.5-0.5B-Instruct}
PORT=${2:-30000}
STUB=${CUDA_STUB_DIR:-/kaggle/working/cudastub}
# Kaggle ships the driver libcuda but no libcuda.so linker name; flashinfer JIT links with -lcuda.
python scripts/find_libcuda.py "$STUB"
LIBRARY_PATH="$STUB" CUDA_VISIBLE_DEVICES=${SERVE_GPU:-1} python -m sglang.launch_server \
  --model-path "$MODEL" --port "$PORT" --dtype float16 \
  --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.8
