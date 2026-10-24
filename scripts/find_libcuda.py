"""Kaggle images ship the driver libcuda but not the libcuda.so linker name that flashinfer JIT (-lcuda) needs.
Locate the loaded driver library via /proc/self/maps and symlink it as <dir>/libcuda.so.  usage: find_libcuda.py <dir>"""
import os
import re
import sys

import torch

torch.zeros(1).cuda()
paths = sorted(set(re.findall(r"(/\S*libcuda\.so[.0-9]*)", open("/proc/self/maps").read())))
print("MAPS", paths)
d = sys.argv[1]
os.makedirs(d, exist_ok=True)
link = os.path.join(d, "libcuda.so")
if paths and not os.path.exists(link):
    os.symlink(paths[0], link)
print("LINK", link, "->", os.path.realpath(link) if os.path.exists(link) else "MISSING")
