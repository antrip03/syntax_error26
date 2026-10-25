"""M0 smoke test: 5 GRPO steps through AlignTune (TRL backend) on Qwen3-0.6B with a dummy custom reward."""
import json
import os
import time
from pathlib import Path

from aligntune.core.backend_factory import create_rl_trainer

OUT = Path(os.environ.get("P1_ROOT", "/tmp/archive_p1")) / "artifacts/smoke_grpo"
OUT.mkdir(parents=True, exist_ok=True)
data_path = OUT / "tiny.json"

docs = [
    ("Gus", "[D2.S1] Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall."),
    ("Nell", "[D3.S1] Day 2, midnight. Walked past the mill. It was dark and silent, no one inside."),
    ("Ivy", "[D5.S1] Day 2, evening to midnight. Mara here, waiting for her oven door to be mended."),
    ("Tom", "[D1.S1] Day 2. Shut the mill at sunset. Stayed at the mill all night grinding flour."),
]
questions = ["Where were you on day 2 at night?", "Who did you see at midnight?", "What do you know about Elsie?"]
rows = []
for name, doc in docs:
    for q in questions:
        rows.append({"prompt": [
            {"role": "system", "content": f"You are {name}. Answer only from YOUR DOCUMENTS, citing ids.\n"
                                          f"YOUR DOCUMENTS:\n{doc}"},
            {"role": "user", "content": f"Player: {q}"},
        ]})
with open(data_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

def short_reply_reward(completion, **kwargs):
    text = "".join(m.get("content", "") for m in completion) if isinstance(completion, list) else completion
    with open(OUT / "samples.txt", "a") as f:
        f.write(repr(text[:400]) + "\n")
    return 1.0 if len(text) < 200 else 0.0

trainer = create_rl_trainer(
    model_name="Qwen/Qwen3-0.6B",
    dataset_name=str(data_path),
    split="train",
    algorithm="grpo",
    backend="trl",
    output_dir=str(OUT / "run"),
    batch_size=4,
    gradient_accumulation_steps=1,
    num_generations=4,
    learning_rate=5e-6,
    max_steps=5,
    num_epochs=1,
    beta=0.04,
    max_prompt_length=512,
    max_completion_length=128,
    temperature=0.9,
    use_peft=True,
    lora_r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    lora_target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    rewards=[{"type": "custom", "params": {"function": short_reply_reward}, "weight": 1.0}],
    bf16=True,
    max_seq_length=640,
    logging_steps=1,
    save_steps=1000,
    seed=42,
    chat_template_kwargs={"enable_thinking": False},
)
print("chat_template_kwargs on GRPOConfig:", getattr(getattr(trainer, "grpo_config", None), "chat_template_kwargs", "n/a"))
t = time.time()
res = trainer.train()
print("GRPO_SMOKE_DONE", f"{time.time() - t:.1f}s", res)
