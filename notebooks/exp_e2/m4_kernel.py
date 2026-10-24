# Thin Kaggle launcher: SFT format experiment e2 (chunk scaffold). No logic here.
import os
import subprocess
import sys

ARGS = "--arms chunk --variant e2 --stages train,merge,eval --n 1500"
os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets", shell=True)
sys.exit(subprocess.run(f"python scripts/m4_sft.py {ARGS}", shell=True).returncode)
