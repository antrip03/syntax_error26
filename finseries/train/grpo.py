"""GRPO through AlignTune with our verifiable rewards (one reward callable per component so each is logged per step).

AlignTune wraps each callable as a per-sample TRL reward; dataset columns listed in `preserve_columns` reach it as kwargs.
Rewards are CPU-only pure Python (finseries.rewards); the verifier and gold answers are never in the prompt.
"""
import glob
import json
import os
from collections import Counter

from ..rewards import combine
from ..scaffolds.base import SYSTEM
from ..tasks import templates as T
from ..tokens import approx_tokens

VARIANTS = {"base": {}, "e4": {"trace_style": "scratch"}, "e5": {"trace_style": "scratch2"}}
WEIGHTS = {"outcome_only": {"outcome": 0.90, "format": 0.10},
           "outcome_process": {"outcome": 0.50, "process": 0.25, "format": 0.10, "consistency": 0.15, "length": 1.0}}


def _text(c):
    return c if isinstance(c, str) else "".join(m.get("content", "") for m in c if isinstance(m, dict))


def make_reward(scaffold, bundle, component, token_budget):
    def fn(completion, task_json=None, **kw):
        text = _text(completion)
        task = T.Task.from_json(json.loads(task_json))
        comps = combine.compute(scaffold, task, text, n_tokens=int(approx_tokens(text) * 1.1), bundle=bundle,
                                token_budget=token_budget)
        return float(comps[component])
    fn.__name__ = f"r_{component}"
    return fn


def build_rewards(scaffold, bundle, token_budget=900):
    return [{"type": make_reward(scaffold, bundle, c, token_budget), "weight": w} for c, w in WEIGHTS[bundle].items()]


def patch_trainer(resume_dir=None, time_budget_s=0):
    """T4 has no bf16 -> keep trainable (LoRA) params in fp32 under fp16 autocast; add checkpoint resume."""
    import torch
    import trl
    orig = trl.GRPOTrainer.train

    def train(self, *a, **k):
        print("trainable dtypes:", dict(Counter(str(p.dtype) for p in self.model.parameters() if p.requires_grad)), flush=True)
        for p in self.model.parameters():
            if p.requires_grad and p.dtype != torch.float32:
                p.data = p.data.float()
        if time_budget_s:
            import time

            from transformers import TrainerCallback
            t0 = time.time()

            class _Budget(TrainerCallback):
                def on_step_end(self, args, state, control, **kw):
                    if time.time() - t0 > time_budget_s:
                        print(f"time budget reached at step {state.global_step}", flush=True)
                        control.should_training_stop = True
                        control.should_save = True
            self.add_callback(_Budget())
        ck = sorted(glob.glob(f"{resume_dir}/checkpoint-*"), key=lambda p: int(p.rsplit("-", 1)[1])) if resume_dir else []
        if ck and "resume_from_checkpoint" not in k:
            print("resuming from", ck[-1], flush=True)
            k["resume_from_checkpoint"] = ck[-1]
        return orig(self, *a, **k)
    trl.GRPOTrainer.train = train


def run(model_path, rows, scaffold, bundle, out_dir, steps, gens=4, batch=2, lr=1e-5, max_new=1000, max_seq=1800,
        save_steps=10, resume=False, beta=0.04, time_budget_s=0, lr_override=None):
    from datasets import Dataset

    from aligntune.core.backend_factory import create_rl_trainer
    patch_trainer(out_dir if resume else None, time_budget_s)
    ds = Dataset.from_list([{"prompt": scaffold.build_prompt(t), "task_json": json.dumps(t.to_json())} for t in rows])
    trainer = create_rl_trainer(
        model_name=model_path, dataset_name=ds, algorithm="grpo", backend="trl", output_dir=out_dir,
        max_steps=steps, num_epochs=1, batch_size=batch, num_generations=gens, learning_rate=lr,
        max_seq_length=max_seq, max_new_tokens=max_new, max_completion_length=max_new, max_prompt_length=800,
        gradient_accumulation_steps=4, rewards=build_rewards(scaffold, bundle, max_new),
        precision="fp16", use_gradient_checkpointing=True, use_lora=True, lora_r=32, lora_alpha=64,
        lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        logging_steps=1, save_steps=save_steps, preserve_columns=["task_json"], system_prompt=SYSTEM,
        temperature=0.8, beta=beta, seed=42)
    trainer.train()
    return out_dir
