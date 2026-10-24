"""Locate a LoRA adapter shipped as a Kaggle dataset (extracted folder or a .zip) -> directory with adapter_model.safetensors."""
import glob
import os
import zipfile


def find_adapter(name, search="/kaggle/input", dst="/kaggle/working/adapters"):
    hits = glob.glob(f"{search}/**/{name}/adapter_model.safetensors", recursive=True)
    if hits:
        return os.path.dirname(hits[0])
    flat = glob.glob(f"{search}/**/adapter_model.safetensors", recursive=True)   # dataset root holds the adapter files
    pick = [p for p in flat if name in p] or (flat if len(flat) == 1 else [])      # `name` = folder or dataset slug
    if pick:
        return os.path.dirname(pick[0])
    zips = glob.glob(f"{search}/**/{name}.zip", recursive=True)
    if zips:
        out = os.path.join(dst, name)
        os.makedirs(out, exist_ok=True)
        zipfile.ZipFile(zips[0]).extractall(out)
        inner = glob.glob(f"{out}/**/adapter_model.safetensors", recursive=True)
        if inner:
            return os.path.dirname(inner[0])
    raise FileNotFoundError(f"adapter {name} not found under {search}: {os.listdir(search)}")
