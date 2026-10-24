"""M4 (Kaggle driver): SFT warm-start on gold traces through AlignTune, merge the LoRA, then evaluate with SGLang.
usage: python scripts/m4_sft.py --arms chunk,flat,event --stages train,merge,eval [--n 1500] [--max-steps -1] [--resume]"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import yaml

ARMS_ALL = ["chunk", "flat", "event"]


def gold_rows(tasks, arm, n):
    from finseries import scaffolds
    from finseries.scaffolds.base import SYSTEM  # noqa: F401
    sc = scaffolds.get(arm)
    return [{"prompt": sc.build_prompt(t), "completion": sc.gold_trace(t)} for t in tasks[:n]]


def train_arm(cfg, tasks, arm, out, max_steps, resume):
    from datasets import Dataset

    from aligntune.core.backend_factory import create_sft_trainer
    from finseries.scaffolds.base import SYSTEM

    ds = Dataset.from_list(gold_rows(tasks, arm, cfg["n_examples"]))
    kw = dict(
        model_name=cfg["model"], dataset_name=ds, backend="trl", output_dir=f"{out}/sft_{arm}",
        num_epochs=cfg["epochs"], batch_size=cfg["batch_size"], gradient_accumulation_steps=cfg["grad_accum"],
        learning_rate=cfg["learning_rate"], max_seq_length=cfg["max_seq_length"], system_prompt=SYSTEM,
        precision="fp16", use_gradient_checkpointing=True, use_lora=True, lora_r=cfg["lora_r"],
        lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], lora_alpha=cfg["lora_alpha"],
        quantization={"load_in_4bit": True, "bnb_4bit_compute_dtype": "float16"},
        save_steps=cfg["save_steps"], logging_steps=5, seed=cfg["seed"],
    )
    if max_steps > 0:
        kw["max_steps"] = max_steps
    if resume:
        ck = sorted(glob.glob(f"{out}/sft_{arm}/checkpoint-*"), key=lambda p: int(p.rsplit("-", 1)[1]))
        if ck:
            kw["resume_from_checkpoint"] = ck[-1]
            print("resuming from", ck[-1], flush=True)
    trainer = create_sft_trainer(**kw)
    trainer.train()
    print("M4_TRAIN_OK", arm, flush=True)


def merge_arm(cfg, arm, out):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    src = f"{out}/sft_{arm}"
    base = AutoModelForCausalLM.from_pretrained(cfg["model"], dtype=torch.float16)
    model = PeftModel.from_pretrained(base, src).merge_and_unload()
    dst = f"{out}/merged_{arm}"
    model.save_pretrained(dst, safe_serialization=True)
    AutoTokenizer.from_pretrained(cfg["model"]).save_pretrained(dst)
    print("M4_MERGE_OK", arm, dst, flush=True)


def eval_arm(arm, out, tasks_dir, limit):
    from finseries.adapters.sglang_client import SGLangClient
    from finseries.eval import run_eval
    from finseries.serve import sglang_server
    from finseries.tasks.generate import read_jsonl
    val = read_jsonl(f"{tasks_dir}/val.jsonl")[:limit]
    with sglang_server.server(f"{out}/merged_{arm}") as url:
        _, m = run_eval.run(val, arm, SGLangClient(url, concurrency=96), f"{out}/SFT_{arm}_val", max_tokens=1024)
    o = m["overall"]
    print(f"SFT {arm}: acc={o['accuracy']:.3f} parse={o['parse_rate']:.3f} stepvalid={o['step_validity']:.3f} "
          f"tok={o['mean_tokens']:.0f}", flush=True)
    return o


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="chunk,flat,event")
    ap.add_argument("--stages", default="train,merge,eval")
    ap.add_argument("--config", default="configs/sft.yaml")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--val-limit", type=int, default=400)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default="/kaggle/working/m4")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    if a.n:
        cfg["n_examples"] = a.n
    os.makedirs(a.out, exist_ok=True)
    hits = glob.glob("/kaggle/input/**/train.jsonl", recursive=True)
    tasks_dir = os.path.dirname(hits[0])
    from finseries.tasks.generate import read_jsonl
    train = read_jsonl(f"{tasks_dir}/train.jsonl")
    train = [train[i] for i in np.random.default_rng(cfg["seed"]).permutation(len(train))]
    try:
        git = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        git = "unknown"
    yaml.safe_dump({"sft": cfg, "git": git, "args": vars(a)}, open(f"{a.out}/config.yaml", "w"))
    stages, results = a.stages.split(","), {}
    if "eval" in stages:
        from finseries.serve import sglang_server
        sglang_server.install()
    for arm in a.arms.split(","):
        t0 = time.time()
        if "train" in stages:
            train_arm(cfg, train, arm, a.out, a.max_steps, a.resume)
        if "merge" in stages:
            merge_arm(cfg, arm, a.out)
        if "eval" in stages:
            results[arm] = eval_arm(arm, a.out, tasks_dir, a.val_limit)
        print(f"== {arm} done in {time.time() - t0:.0f}s", flush=True)
        json.dump(results, open(f"{a.out}/sft_results.json", "w"), indent=1)
    print(json.dumps(results, indent=1))
