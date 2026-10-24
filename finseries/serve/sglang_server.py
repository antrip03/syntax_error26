"""Install SGLang in its own venv and run it as a context-managed server (used by Kaggle driver scripts)."""
import contextlib
import os
import subprocess
import time
import urllib.request

VENV = "/kaggle/working/sglvenv"
STUB = "/kaggle/working/cudastub"
FLAGS = "--dtype float16 --attention-backend triton --disable-cuda-graph --mem-fraction-static 0.8"


def install(log_dir="/kaggle/working"):
    py = f"{VENV}/bin/python"
    if not os.path.exists(py):
        subprocess.run(f"pip install -q uv && uv venv {VENV} --python 3.11 && uv pip install --python {py} 'sglang[all]' requests "
                       f"> {log_dir}/sglang_install.log 2>&1", shell=True, check=True)
    subprocess.run(f"python scripts/find_libcuda.py {STUB}", shell=True, check=True)


@contextlib.contextmanager
def server(model, port=30000, gpu=1, flags=FLAGS, log="/kaggle/working/sglang_server.log", wait=900):
    cmd = (f"LIBRARY_PATH={STUB} CUDA_VISIBLE_DEVICES={gpu} {VENV}/bin/python -m sglang.launch_server "
           f"--model-path {model} --port {port} {flags}")
    proc = subprocess.Popen(cmd, shell=True, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while True:
            if time.time() - t0 > wait:
                raise TimeoutError("sglang did not become healthy")
            if proc.poll() is not None:
                raise RuntimeError(f"sglang exited early, see {log}")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
                break
            except Exception:
                time.sleep(5)
        yield f"http://127.0.0.1:{port}"
    finally:
        subprocess.run("pkill -f sglang.launch_server", shell=True)
        time.sleep(5)
