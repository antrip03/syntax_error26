"""M0: 5 GRPO steps through AlignTune on a tiny model with (a) a dummy reward, (b) our real verifiable reward.
usage: python scripts/m0_grpo_smoke.py --reward dummy|real [--model Qwen/Qwen2.5-0.5B-Instruct] [--steps 5]"""
import argparse
import json
import sys

sys.path.insert(0, ".")
from datasets import Dataset

from finseries import scaffolds
from finseries.data import synthetic
from finseries.data.splits import Window
from finseries.rewards import combine
from finseries.scaffolds.base import SYSTEM
from finseries.tasks import generate as G
from finseries.tasks import templates as T


def make_rows(n, arm, seed=1):
    sc = scaffolds.get(arm)
    wins = [Window("train", "synthetic", "synth", seed * 1000 + i, synthetic.generate(70, seed * 1000 + i).r.tolist())
            for i in range(60)]
    tasks = G.generate_split(wins, n, "train", seed, budget={"completion": 480, "prompt": 600})
    return [{"prompt": SYSTEM + "\n\n" + sc.build_prompt(t), "task_json": json.dumps(t.to_json())} for t in tasks]


def text_of(c):
    if isinstance(c, str):
        return c
    return "".join(m.get("content", "") for m in c if isinstance(m, dict))


def real_reward(arm, component):
    sc = scaffolds.get(arm)

    def fn(completion, task_json=None, **kw):
        t = T.Task.from_json(json.loads(task_json))
        return float(combine.compute(sc, t, text_of(completion), bundle="outcome_process")[component])
    fn.__name__ = f"r_{component}"
    return fn


def dummy_reward(completion, **kw):
    return min(len(text_of(completion)) / 400.0, 1.0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reward", default="dummy")
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--arm", default="chunk")
    ap.add_argument("--steps", type=int, default=5)
    ap.add_argument("--out", default="/kaggle/working/m0/grpo_out")
    ap.add_argument("--gens", type=int, default=4)
    a = ap.parse_args()
    from aligntune.core.backend_factory import create_rl_trainer

    ds = Dataset.from_list(make_rows(32, a.arm))
    if a.reward == "dummy":
        rewards = [{"type": dummy_reward, "weight": 1.0}]
    else:
        w = {"outcome": 0.5, "process": 0.25, "format": 0.1, "consistency": 0.15}
        rewards = [{"type": real_reward(a.arm, k), "weight": v} for k, v in w.items()]
    trainer = create_rl_trainer(
        model_name=a.model, dataset_name=ds, algorithm="grpo", backend="trl", output_dir=a.out,
        max_steps=a.steps, num_epochs=1, batch_size=a.gens, num_generations=a.gens, learning_rate=1e-5,
        max_seq_length=1100, max_new_tokens=300, rewards=rewards, precision="fp16", use_gradient_checkpointing=True,
        lora_r=16, logging_steps=1, save_steps=a.steps, preserve_columns=["task_json"],
    )
    trainer.train()
    print("M0_GRPO_OK", a.reward)
