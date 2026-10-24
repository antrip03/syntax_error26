# Thin Kaggle launcher: clone the repo, install, run the M3 driver. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
else:
    subprocess.run("cd repo && git pull", shell=True)
os.chdir("repo")
subprocess.run("pip install -q -e . curatorkit", shell=True)
args = os.environ.get("M3_ARGS", "")
sys.exit(subprocess.run(f"python scripts/m3_baseline.py {args}", shell=True).returncode)
