#!/bin/bash
# Usage: scripts/serve_tts.sh   (run inside tmux) -> Kokoro villager voices on :8001
source "$(dirname "$0")/env.sh" tts
exec "$(dirname "$0")/gpu.sh" python -m uvicorn archive.serve.tts:app --host ${TTS_HOST:-127.0.0.1} --port ${TTS_PORT:-8001}
