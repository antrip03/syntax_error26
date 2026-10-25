#!/bin/bash
cd "$(dirname "$0")/.."
MODEL=${1:-Qwen/Qwen3-1.7B}
LORAS=()
for r in R1 R1a R1b R3 R3b; do
  d=artifacts/runs/$r/out
  [ -f "$d/adapter_model.safetensors" ] && LORAS+=("$(echo $r | tr A-Z a-z)=$(readlink -f $d)")
done
EXTRA=()
[ ${#LORAS[@]} -gt 0 ] && EXTRA=(--enable-lora --max-lora-rank 16 --lora-target-modules all --lora-paths "${LORAS[@]}")
echo "serving $MODEL with adapters: ${LORAS[*]:-none}"
exec scripts/serve_sglang.sh "$MODEL" "${EXTRA[@]}" ${SGLANG_EXTRA:-}
