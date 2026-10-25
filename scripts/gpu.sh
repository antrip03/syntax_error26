#!/bin/bash
GPU_JOB=${GPU_JOB:-2943}
exec srun --jobid="$GPU_JOB" --overlap "$@"
