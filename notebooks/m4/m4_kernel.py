# Thin Kaggle launcher: clone the repo, install, run the M4 SFT driver. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
else:
    subprocess.run("cd repo && git pull", shell=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets", shell=True)
args = open("notebooks/m4/args.txt").read().strip() if os.path.exists("notebooks/m4/args.txt") else ""
sys.exit(subprocess.run(f"python scripts/m4_sft.py {args}", shell=True).returncode)
