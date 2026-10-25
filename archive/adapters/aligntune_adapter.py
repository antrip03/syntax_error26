"""AlignTune wrapper for SFT (R1) and GRPO (R3), TRL backend, LoRA.

Hooks added around AlignTune (each found missing in the installed version, see docs/ENV_NOTES.md):
- extra HF callbacks (our JSONL log + guards): appended to the trainer's `get_hf_callbacks()`;
- `init_adapter`: AlignTune always builds a fresh LoRA, so after `setup_model()` we load R1's LoRA weights into
  it (same rank/targets required). With PEFT, TRL's KL reference is the base model with the adapter disabled,
  so `beta` pulls towards the base model, not R1;
- `resume`: after `setup_trainer()`, TRL's `train()` is called with `resume_from_checkpoint`;
- thinking off: `chat_template_kwargs={"enable_thinking": False}` passed through to GRPOConfig.
Custom rewards are per-sample: `fn(completion, prompt=..., **columns) -> float`. One function per reward part,
weighted by AlignTune, so TRL logs `rewards/registry_<part>/mean` for every part.
"""
from __future__ import annotations

import functools
import json
import logging
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

def _lora_kwargs(cfg: dict) -> dict:
    lora = cfg.get("lora", {})
    return {"use_peft": True, "lora_r": lora.get("r", 16), "lora_alpha": lora.get("alpha", 32),
            "lora_dropout": lora.get("dropout", 0.05), "lora_target_modules": lora.get("targets", LORA_TARGETS)}

def _add_callbacks(trainer, callbacks):
    if not callbacks:
        return
    orig = trainer.get_hf_callbacks
    trainer.get_hf_callbacks = lambda: list(orig()) + list(callbacks)

def _load_init_adapter(trainer, adapter_dir: str):
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file

    orig = trainer.setup_model

    @functools.wraps(orig)
    def setup_model(*a, **k):
        out = orig(*a, **k)
        cfg = json.loads((Path(adapter_dir) / "adapter_config.json").read_text())
        mine = trainer.model.peft_config["default"]
        if cfg["r"] != mine.r or set(cfg["target_modules"]) != set(mine.target_modules):
            raise ValueError(f"init adapter r/targets {cfg['r']}/{cfg['target_modules']} != trainer {mine.r}/{mine.target_modules}")
        res = set_peft_model_state_dict(trainer.model, load_file(str(Path(adapter_dir) / "adapter_model.safetensors")))
        unexpected = list(getattr(res, "unexpected_keys", []) or [])
        missing_lora = [k for k in (getattr(res, "missing_keys", []) or []) if "lora_" in k]
        if unexpected or missing_lora:
            raise RuntimeError(f"init adapter mismatch: unexpected={unexpected[:3]} missing={missing_lora[:3]}")
        log.info("loaded init adapter from %s", adapter_dir)
        print(f"[aligntune_adapter] init adapter loaded from {adapter_dir}", flush=True)
        return out

    trainer.setup_model = setup_model

def latest_checkpoint(out_dir: str) -> str | None:
    cks = sorted(Path(out_dir).glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
    return str(cks[-1]) if cks else None

def _resume(trainer, out_dir: str):
    ck = latest_checkpoint(out_dir)
    if not ck:
        print("[aligntune_adapter] --resume: no checkpoint found, starting fresh", flush=True)
        return
    orig = trainer.setup_trainer

    @functools.wraps(orig)
    def setup_trainer(*a, **k):
        out = orig(*a, **k)
        trainer.trainer.train = functools.partial(trainer.trainer.train, resume_from_checkpoint=ck)
        print(f"[aligntune_adapter] resuming from {ck}", flush=True)
        return out

    trainer.setup_trainer = setup_trainer

def sft(data_path: str, out_dir: str, cfg: dict, callbacks=(), init_adapter: str | None = None) -> dict:
    """data_path: JSONL of {"prompt": rendered chat-template string, "completion": gold reply}."""
    from aligntune.core.backend_factory import create_sft_trainer

    trainer = create_sft_trainer(
        model_name=cfg["model"], dataset_name=str(data_path), split="train", backend="trl", output_dir=str(out_dir),
        task_type="instruction_following", num_epochs=cfg.get("epochs", 1), max_steps=cfg.get("max_steps", -1),
        batch_size=cfg.get("batch", 8), gradient_accumulation_steps=cfg.get("grad_accum", 2),
        learning_rate=cfg.get("lr", 2e-4), max_seq_length=cfg.get("max_seq_len", 1280),
        completion_only_loss=True, bf16=True, logging_steps=cfg.get("log_every", 5),
        save_strategy="steps", save_steps=cfg.get("save_every", 50), save_total_limit=3,
        seed=cfg.get("seed", 0), **_lora_kwargs(cfg))
    _add_callbacks(trainer, callbacks)
    if init_adapter:
        _load_init_adapter(trainer, init_adapter)
    return trainer.train()

def grpo(data_path: str, out_dir: str, cfg: dict, rewards: list[tuple[str, Callable, float]],
         init_adapter: str | None = None, resume: bool = False, callbacks=()) -> dict:
    """data_path: JSONL of {"prompt": [chat messages]}. rewards: (name, fn, weight); fn(completion, **row) -> float."""
    from aligntune.core.backend_factory import create_rl_trainer

    specs = []
    for name, fn, w in rewards:
        fn.__name__ = name
        specs.append({"type": "custom", "params": {"function": fn}, "weight": float(w)})
    per_step = cfg.get("prompts_per_step", 4) * cfg.get("num_generations", 6)
    accum = cfg.get("grad_accum", 1)
    trainer = create_rl_trainer(
        model_name=cfg["model"], dataset_name=str(data_path), split="train", algorithm="grpo", backend="trl",
        output_dir=str(out_dir), batch_size=per_step // accum, gradient_accumulation_steps=accum,
        num_generations=cfg.get("num_generations", 6), learning_rate=cfg.get("lr", 5e-6),
        max_steps=cfg.get("max_steps", 100), num_epochs=cfg.get("epochs", 1000), beta=cfg.get("beta", 0.04),
        max_completion_length=cfg.get("max_completion_len", 192), temperature=cfg.get("temperature", 0.9),
        rewards=specs, bf16=True, use_gradient_checkpointing=cfg.get("grad_ckpt", False),
        max_seq_length=cfg.get("max_seq_len", 1280), logging_steps=1, save_steps=cfg.get("save_every", 25),
        save_total_limit=4, seed=cfg.get("seed", 0), chat_template_kwargs={"enable_thinking": False},
        **_lora_kwargs(cfg))
    if init_adapter:
        _load_init_adapter(trainer, init_adapter)
    if resume:
        _resume(trainer, out_dir)
    _add_callbacks(trainer, callbacks)
    return trainer.train()
