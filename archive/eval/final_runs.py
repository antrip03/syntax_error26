"""Detective bot and planted-rumour runs (brief 11; TASKS_P1 T+8), Base vs Grounded, through SGLang (serve env).

python -m archive.eval.final_runs --grounded r3 [--bot-cases 30] [--rumour-runs 20] [--out artifacts/results]

Uses P2's archive/npc/detective_bot.py (play, solve_rate) and archive/npc/rumour.py (run, spread) unchanged; this
module only supplies `ask_many` against our server. Villages: base = adapter off, grounded = `--grounded`. On Hard
cases the killer runs on the base model with P2's liar prompt in both villages (brief 4.6 liar mode).
Cases: the first N test_game cases. Rumour: a false sighting of a non-killer villager at the scene on the murder
night, planted in another villager's memory as said by a traveller.
"""
import argparse
import asyncio
import json
import random
from pathlib import Path

from archive import interfaces as I
from archive.adapters.sglang_client import DEFAULT_URL, SGLangClient

_LORA = "_lora"  # marker on a message list's first dict: which adapter answers it (stripped before sending)


def make_ask_many(url: str, model: str, concurrency: int):
    def ask_many(batch):
        async def go():
            c = SGLangClient(url, model, concurrency=concurrency)
            try:
                outs = []
                for start in range(0, len(batch), 256):
                    part = batch[start:start + 256]
                    outs += await asyncio.gather(*[
                        c.chat([{k: v for k, v in m.items() if k != _LORA} for m in msgs],
                               lora=msgs[0].get(_LORA), max_tokens=200) for msgs in part])
                return [o["text"] for o in outs]
            finally:
                await c.aclose()
        return asyncio.run(go())
    return ask_many


def village_prompts(lora):
    """prompt_for(case, villager, question) for one village: P2's villager prompt on `lora`, the Hard killer on the
    base model with P2's liar prompt."""
    from archive.tasks.prompt import build_liar_messages, build_messages

    def prompt_for(case, vid, q, heard=()):
        if case.difficulty == "hard" and vid == case.killer:
            m = build_liar_messages(case, vid, q)
            m[0] = {**m[0], _LORA: None}
        else:
            m = build_messages(case, vid, q, heard)
            m[0] = {**m[0], _LORA: lora}
        return m
    return prompt_for


def rumour_ask_many(ask_many, lora):
    """P2's rumour/gossip code builds villager prompts itself; tag them all for this village's adapter."""
    def tagged(batch):
        return ask_many([[{**msgs[0], _LORA: lora}, *msgs[1:]] for msgs in batch])
    return tagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grounded", default="r3")
    ap.add_argument("--bot-cases", type=int, default=30)
    ap.add_argument("--rumour-runs", type=int, default=20)
    ap.add_argument("--split", default="test_game")
    ap.add_argument("--data-dir", default="data_prepared")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--out", default="artifacts/results")
    a = ap.parse_args()
    I.require("p2")
    from archive.npc import detective_bot as bot
    from archive.npc import rumour

    cases = list(I.load_cases(Path(a.data_dir) / f"cases_{a.split}.jsonl").values())
    ask_many = make_ask_many(a.url, a.model, a.concurrency)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    villages = {"base": None, "grounded": a.grounded}
    summary = {"grounded_adapter": a.grounded, "split": a.split}

    bot_res = {}
    for name, lora in villages.items():
        res = [bot.play(c, ask_many, prompt_for=village_prompts(lora)) for c in cases[: a.bot_cases]]
        bot_res[name] = res
        summary[f"bot_{name}"] = bot.solve_rate(res)
        print("bot", name, json.dumps(summary[f"bot_{name}"]), flush=True)
    (out / "bot_runs.json").write_text(json.dumps(bot_res, indent=1, default=str))

    rng = random.Random(0)
    rum = {name: [] for name in villages}
    for i, c in enumerate(cases[: a.rumour_runs]):
        innocent = rng.choice([v for v in c.villagers if v.id != c.killer])
        start = rng.choice([v for v in c.villagers if v.id != innocent.id])
        text = f"{innocent.name} was at the {c.scene} on the night of the murder."
        for name, lora in villages.items():
            rum[name].append(rumour.run(c, rumour_ask_many(ask_many, lora), text, start.id, seed=i))
    for name in villages:
        summary[f"rumour_{name}"] = rumour.spread(rum[name])
        print("rumour", name, json.dumps(summary[f"rumour_{name}"]), flush=True)
    (out / "rumour_runs.json").write_text(json.dumps(rum, indent=1, default=str))
    (out / "final_runs.json").write_text(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
