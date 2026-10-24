# Thin Kaggle launcher: clone the repo and run the M0 driver. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
else:
    subprocess.run("cd repo && git pull", shell=True)
os.chdir("repo")
subprocess.run("pip install -q -e .", shell=True)
stages = os.environ.get("M0_STAGES", "sglang")
sys.exit(subprocess.run(f"python scripts/m0_smoke.py --stages {stages}", shell=True).returncode)
