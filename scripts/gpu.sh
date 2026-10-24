#!/bin/bash
# Run a command on our reserved A6000 (inside the Slurm GPU-hold job).
# Usage: scripts/gpu.sh <command...>   (set GPU_JOB to override the job id)
GPU_JOB=${GPU_JOB:-2943}
exec srun --jobid="$GPU_JOB" --overlap "$@"
