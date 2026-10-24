#!/bin/bash
# Serve the base model plus every finished adapter, so R0/R1/R3 eval share one server (run inside tmux).
# Usage: scripts/serve_eval.sh [model]     adapters picked up from artifacts/runs/{R1,R1a,R1b,R3,R3b}/out if present
cd "$(dirname "$0")/.."
MODEL=${1:-Qwen/Qwen3-1.7B}
LORAS=()
for r in R1 R1a R1b R3 R3b; do
  d=artifacts/runs/$r/out
  [ -f "$d/adapter_model.safetensors" ] && LORAS+=("$(echo $r | tr A-Z a-z)=$(readlink -f $d)")
done
EXTRA=()  # SGLANG_EXTRA="--lora-backend triton" adds server flags (the default LoRA kernel crashed once under mixed-adapter load)
[ ${#LORAS[@]} -gt 0 ] && EXTRA=(--enable-lora --max-lora-rank 16 --lora-target-modules all --lora-paths "${LORAS[@]}")
echo "serving $MODEL with adapters: ${LORAS[*]:-none}"
exec scripts/serve_sglang.sh "$MODEL" "${EXTRA[@]}" ${SGLANG_EXTRA:-}
