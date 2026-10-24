"""Rejection-sampling fine-tuning (the plan's RLVR fallback), single-GPU box (L4 VM / Kaggle).
  sample : SGLang serves the SFT-merged model; N samples/task at T=0.8; keep only verified-correct completions
           (final answer in tolerance AND every step valid), at most --keep-per-task per task, shortest first
  train  : AlignTune SFT (LoRA) on the kept completions, starting from the SFT-merged model
Then evaluate with: python scripts/m5_grpo.py --skip-train --eval --tag <tag> ...   (merges <out>/<tag> onto start_model)
usage: python scripts/rft.py --arm flat --variant e5 --start-model DIR --tasks-dir DIR --out DIR --tag rftflat [--stages sample,train]"""
import argparse
import json
import os
import sys

sys.path.insert(0, ".")
import numpy as np

from finseries import scaffolds
from finseries.adapters.sglang_client import SGLangClient
from finseries.eval import run_eval
from finseries.scaffolds.base import SYSTEM
from finseries.tasks.generate import read_jsonl
from finseries.train.grpo import VARIANTS


def sample(a, skw):
    from finseries.serve import sglang_server
    train = read_jsonl(f"{a.tasks_dir}/train.jsonl")
    sub = [train[i] for i in np.random.default_rng(11).permutation(len(train))[:a.n_tasks]]
    sc = scaffolds.get(a.arm, **skw)
    with sglang_server.server(a.start_model) as url:
        client = SGLangClient(url, concurrency=192, timeout=1500)
        rows, m = run_eval.run(sub, a.arm, client, f"{a.out}/{a.tag}_samples", n=a.n_samples, temperature=0.8, max_tokens=1100,
                               seed=77, scaffold_kwargs=skw)
    comps = {}
    for l in open(f"{a.out}/{a.tag}_samples/completions.jsonl"):
        d = json.loads(l)
        comps[(d["id"], d["sample"])] = d["completion"]
    by = {}
    for r in rows:
        if r["correct"] and r["step_validity"] >= 0.999 and not r["truncated"]:
            by.setdefault(r["id"], []).append(r)
    tasks = {t.id: t for t in sub}
    kept = []
    for tid, rs in by.items():
        rs.sort(key=lambda r: r["n_tokens"])
        seen = set()
        for r in rs:
            text = comps[(tid, r["sample"])]
            if text in seen:
                continue
            seen.add(text)
            kept.append({"prompt": sc.build_prompt(tasks[tid]), "completion": text, "id": tid})
            if len([k for k in kept if k["id"] == tid]) >= a.keep_per_task:
                break
    with open(f"{a.out}/{a.tag}_rft_data.jsonl", "w") as f:
        f.writelines(json.dumps(k) + "\n" for k in kept)
    stats = {"tasks": len(sub), "samples": len(rows), "sample_accuracy": m["overall"]["accuracy"],
             "tasks_with_a_verified_sample": len(by), "kept": len(kept)}
    print("RFT_SAMPLE", json.dumps(stats), flush=True)
    json.dump(stats, open(f"{a.out}/{a.tag}_rft_stats.json", "w"))
    return kept


def train(a, kept):
    import torch
    import trl
    from datasets import Dataset

    from aligntune.core.backend_factory import create_sft_trainer
    orig = trl.SFTTrainer.train

    def patched(self, *x, **k):   # keep trainable LoRA params in fp32 (same guard as the SFT/GRPO drivers)
        for p in self.model.parameters():
            if p.requires_grad and p.dtype != torch.float32:
                p.data = p.data.float()
        return orig(self, *x, **k)
    trl.SFTTrainer.train = patched
    ds = Dataset.from_list([{"prompt": k["prompt"], "completion": k["completion"]} for k in kept])
    t = create_sft_trainer(
        model_name=a.start_model, dataset_name=ds, backend="trl", output_dir=f"{a.out}/{a.tag}", num_epochs=a.epochs,
        batch_size=2, gradient_accumulation_steps=8, learning_rate=1e-4, max_seq_length=1800, system_prompt=SYSTEM,
        precision=a.precision, use_gradient_checkpointing=True, use_lora=True, lora_r=32, lora_alpha=64,
        lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        save_steps=25, logging_steps=5, seed=42)
    t.train()
    print("RFT_TRAIN_OK", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="flat")
    ap.add_argument("--variant", default="e5")
    ap.add_argument("--start-model", required=True)
    ap.add_argument("--tasks-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="rft")
    ap.add_argument("--stages", default="sample,train")
    ap.add_argument("--n-tasks", type=int, default=1200)
    ap.add_argument("--n-samples", type=int, default=8)
    ap.add_argument("--keep-per-task", type=int, default=2)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--precision", default="bf16")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    skw = VARIANTS[a.variant]
    kept = None
    if "sample" in a.stages:
        kept = sample(a, skw)
    if "train" in a.stages:
        if kept is None:
            kept = [json.loads(l) for l in open(f"{a.out}/{a.tag}_rft_data.jsonl")]
        train(a, kept)
