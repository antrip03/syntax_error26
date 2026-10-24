# source scripts/env.sh [serve|train]
export P1_ROOT=/tmp/archive_p1
export HF_HOME=$P1_ROOT/hf
export UV_CACHE_DIR=$P1_ROOT/uvcache
export HF_HUB_OFFLINE=1
case "${1:-serve}" in
  serve) source $P1_ROOT/.venv/bin/activate ;;
  train) source $P1_ROOT/.venv-train/bin/activate ;;
esac
export PYTHONPATH=$HOME/rl/archive:$PYTHONPATH
