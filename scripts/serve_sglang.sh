#!/bin/bash
source "$(dirname "$0")/env.sh" serve
MODEL=${1:-Qwen/Qwen3-0.6B}; shift
exec "$(dirname "$0")/gpu.sh" python -m sglang.launch_server --model-path "$MODEL" \
  --host 127.0.0.1 --port ${SGLANG_PORT:-30000} --mem-fraction-static ${SGLANG_MEM:-0.3} "$@"
