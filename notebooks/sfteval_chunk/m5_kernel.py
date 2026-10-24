# Thin Kaggle launcher: SFT-only evaluation (chunk) on val/test_period/test_len through SGLang. No logic here.
import os
import subprocess
import sys

os.chdir("/kaggle/working")
if not os.path.exists("repo"):
    subprocess.run("git clone --depth 1 https://github.com/antrip03/syntax_error26 repo", shell=True, check=True)
os.chdir("repo")
subprocess.run("pip install -q -e . aligntune curatorkit datasets peft", shell=True)
cmd = "python scripts/m5_grpo.py --arm chunk --variant e5 --adapter-name finseries-adapters --eval-only --tag sftchunk"
sys.exit(subprocess.run(cmd, shell=True).returncode)
