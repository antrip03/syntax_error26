"""Make a randomly initialised LoRA adapter for SGLang LoRA smoke tests."""
import argparse

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
ap.add_argument("--out", required=True)
ap.add_argument("--rank", type=int, default=16)
args = ap.parse_args()

torch.manual_seed(0)
model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16)
cfg = LoraConfig(
    r=args.rank,
    lora_alpha=2 * args.rank,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    init_lora_weights=False,
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, cfg)
model.save_pretrained(args.out)
print("saved", args.out)
