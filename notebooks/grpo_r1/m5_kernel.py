# Thin Kaggle launcher: GRPO r1flat (flat, outcome_only) with a wall-clock budget, then SGLang eval. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
cmd = ("CUDA_VISIBLE_DEVICES=0 python scripts/m5_grpo.py --arm flat --variant e5 --adapter-name finseries-flat-adapter "
       "--bundle outcome_only --steps 400 --time-budget-min 150 --n-tasks 600 --eval --tag r1flat")
sys.exit(subprocess.run(cmd, shell=True).returncode)
