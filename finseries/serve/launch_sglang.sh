#!/usr/bin/env bash
# UNVERIFIED on T4 -- M0 must confirm/adjust these flags and record the working command in docs/ENV_NOTES.md.
# usage: bash finseries/serve/launch_sglang.sh <model_path_or_hf_id> [port]   (run on GPU 1; GPU 0 is for training)
MODEL=${1:-Qwen/Qwen2.5-0.5B-Instruct}
PORT=${2:-30000}
CUDA_VISIBLE_DEVICES=${SERVE_GPU:-1} python -m sglang.launch_server \
  --model-path "$MODEL" --port "$PORT" --dtype float16 \
  --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.80
