# Thin Kaggle launcher: SFT-model difficulty curation (chunk, e5). No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
sys.exit(subprocess.run(f"python scripts/m5_curate.py --arm chunk --variant e5 --adapter-name finseries-adapters", shell=True).returncode)
