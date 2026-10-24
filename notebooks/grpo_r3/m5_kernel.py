# Thin Kaggle launcher: GRPO r3chunk (chunk, outcome_process) with a wall-clock budget, then SGLang eval. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
cmd = ("PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_VISIBLE_DEVICES=0 python scripts/m5_grpo.py --arm chunk --variant e5 --adapter-name finseries-adapters "
       "--bundle outcome_process --steps 400 --time-budget-min 150 --n-tasks 600 --eval --tag r3chunk")
sys.exit(subprocess.run(cmd, shell=True).returncode)
