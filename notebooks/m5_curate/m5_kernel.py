# Thin Kaggle launcher: SFT-model difficulty curation (chunk, e5). No logic here.
import glob
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
adapter = os.path.dirname(glob.glob("/kaggle/input/**/chunk_e5/adapter_model.safetensors", recursive=True)[0])
sys.exit(subprocess.run(f"python scripts/m5_curate.py --arm chunk --variant e5 --adapter {adapter}", shell=True).returncode)
