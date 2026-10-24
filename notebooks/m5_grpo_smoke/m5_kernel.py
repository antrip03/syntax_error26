# Thin Kaggle launcher: GRPO smoke test (chunk, e5, 6 steps). No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
cmd = f"CUDA_VISIBLE_DEVICES=0 python scripts/m5_grpo.py --arm chunk --variant e5 --adapter-name chunk_e5 --steps 6 --n-tasks 64 --tag smoke"
sys.exit(subprocess.run(cmd, shell=True).returncode)
