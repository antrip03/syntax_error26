#!/bin/bash
cd "$(dirname "$0")/.."
A=$(readlink -f artifacts/runs)
tmux has-session -t p1_sglang 2>/dev/null || tmux new-session -d -s p1_sglang \
  "scripts/serve_sglang.sh Qwen/Qwen3-1.7B --enable-lora --max-lora-rank 16 --lora-target-modules all --lora-paths r1b=$A/R1b/out r3=$A/R3/out 2>&1 | tee /tmp/archive_p1/logs/sglang_game.log"
tmux has-session -t p1_game 2>/dev/null || tmux new-session -d -s p1_game \
  "source scripts/env.sh serve && python -m uvicorn archive.serve.game_api:app --host 0.0.0.0 --port ${GAME_PORT:-8000} 2>&1 | tee /tmp/archive_p1/logs/game_api.log"
tmux has-session -t p1_web 2>/dev/null || tmux new-session -d -s p1_web \
  "python3 scripts/static_nocache.py ${WEB_PORT:-5173} game 2>&1 | tee /tmp/archive_p1/logs/game_web.log"
echo "game: http://localhost:${WEB_PORT:-5173}   api: http://localhost:${GAME_PORT:-8000}/health"
