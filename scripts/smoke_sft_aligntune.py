"""M0 smoke test: 20 SFT steps through AlignTune (TRL backend) on Qwen3-0.6B with completion-only loss.

Prompts are pre-rendered with the chat template (enable_thinking=False) so training matches
inference exactly; the completion is the gold reply (TRL appends EOS = <|im_end|>).
"""
import json
import os
import time
from pathlib import Path

from transformers import AutoTokenizer

from aligntune.core.backend_factory import create_sft_trainer

MODEL = "Qwen/Qwen3-0.6B"
OUT = Path(os.environ.get("P1_ROOT", "/tmp/archive_p1")) / "artifacts/smoke_sft"
OUT.mkdir(parents=True, exist_ok=True)
data_path = OUT / "tiny_sft.json"

tok = AutoTokenizer.from_pretrained(MODEL)
items = [
    ("Gus", "[D2.S1] Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall.",
     "Who did you see at midnight on day 2?",
     "<answer>\n# Ninth bell.\nCLAIM: At midnight on day 2 I saw Tom by the chapel wall. [D2.S1]\n</answer>"),
    ("Nell", "[D3.S1] Day 2, midnight. Walked past the mill. It was dark and silent, no one inside.",
     "Was anyone at the mill at midnight on day 2?",
     "<answer>\nCLAIM: At midnight on day 2 the mill was dark and no one was inside. [D3.S1]\n</answer>"),
    ("Ivy", "[D5.S1] Day 2, evening to midnight. Mara here, waiting for her oven door to be mended.",
     "Where were you on day 1 at dawn?",
     '<abstain reason="not_in_records"/>'),
]
with open(data_path, "w") as f:
    for i in range(40):
        name, doc, q, gold = items[i % len(items)]
        msgs = [{"role": "system", "content": f"You are {name}. Answer only from YOUR DOCUMENTS.\nYOUR DOCUMENTS:\n{doc}"},
                {"role": "user", "content": f"Player: {q}"}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        f.write(json.dumps({"prompt": prompt, "completion": gold}) + "\n")

trainer = create_sft_trainer(
    model_name=MODEL,
    dataset_name=str(data_path),
    split="train",
    backend="trl",
    output_dir=str(OUT / "run"),
    task_type="instruction_following",
    max_steps=20,
    batch_size=4,
    gradient_accumulation_steps=1,
    learning_rate=2e-4,
    max_seq_length=1280,
    use_peft=True,
    lora_r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    bf16=True,
    completion_only_loss=True,
    logging_steps=5,
    save_strategy="no",
    seed=42,
)
t = time.time()
res = trainer.train()
print("SFT_SMOKE_DONE", f"{time.time() - t:.1f}s", {k: res.get(k) for k in ("final_loss", "total_steps", "model_path")})
