"""Paraphrased questions for GRPO round 2 (serve env; SGLang must serve the base model).

python -m archive.train.paraphrase --split train --n-tasks 2500 --per-task 2 --out data_prepared/paraphrase/tasks_train.jsonl

The base model rewrites each question the way a player might type it. The gold answer does not depend on wording,
so a rewrite keeps the task's gold as long as it asks the same thing. A rewrite is kept only if P2's lexicon reads
the same people, places, items, sounds, days and time slots in it as in the original, and it contains none of the
held-out family-B phrases (archive/tasks/phrasing.py), so test_free stays unseen. GRPO then trains on these with
the checker as the reward: free player wording that SFT's templates never covered.
"""
import argparse
import asyncio
import json
import random
import re
from collections import Counter
from pathlib import Path

from archive import interfaces as I
from archive.adapters.sglang_client import DEFAULT_URL, SGLangClient

SYSTEM = """You rewrite questions for a village murder-mystery game. Rewrite the player's question the way a real
player might type it: casual or blunt or chatty, different words and word order. Keep every name, place and day
number exactly. Keep the same time of day, but you may say it another way. Do not add or drop anything asked.
Output only the rewritten question, on one line."""
STYLES = ["Make it very casual, like a text message, with lowercase and slang.",
          "Make it blunt and impatient, like a tired detective.",
          "Make it chatty: add a short friendly remark before the question.",
          "Say the time of day as a clock time instead (for example 'around 8 in the morning' or '10 at night').",
          "Reorder it: put the time first, then the question.",
          "Make it polite and a little formal, like a visiting magistrate."]
_CLOCK = re.compile(r"\b(\d{1,2})(?::\d\d)?\s*(am|pm|o'?clock in the morning|o'?clock at night|in the morning|in the "
                    r"afternoon|in the evening|at night)\b", re.I)
SKIP_TYPES = {"format_attack", "injection"}  # their wording is the point; keep them as written


def entities(vocab, text: str) -> set:
    return {e for e in vocab.extract(text) if e[0] in ("person", "place", "item", "sound", "day", "slot", "state")}


def clock_slot(text: str) -> str | None:
    """'8 in the morning' -> morning, '10 at night' -> night, '7pm' -> dusk; None when there is no clock time."""
    m = _CLOCK.search(text)
    if not m:
        return None
    h, part = int(m.group(1)) % 12, m.group(2).lower()
    if "am" == part or "morning" in part:
        return "dawn" if h <= 6 else "morning" if h <= 11 else None
    if "afternoon" in part:
        return "noon" if h == 0 else "afternoon"
    if "pm" == part:
        return "noon" if h == 0 else "afternoon" if h <= 4 else "dusk" if h <= 8 else "night"
    if "evening" in part:
        return "dusk" if h <= 8 else "night"
    return "night" if h >= 9 or h <= 2 else "dusk"


def same_question(vocab, orig: str, q: str) -> bool:
    """Same people, places, items, sounds, days; the same time slot, said with a time word or a clock time."""
    want, got = entities(vocab, orig), entities(vocab, q)
    slot = lambda es: {e for e in es if e[0] == "slot"}
    if want - slot(want) != got - slot(got):
        return False
    if slot(got) == slot(want):
        return True
    c = clock_slot(q)
    return not slot(got) and c is not None and {("slot", c)} == slot(want)


def held_out_phrases() -> list[str]:
    from archive.tasks.phrasing import DAY, MURDER, SLOT
    out = [p for ps in SLOT["B"].values() for p in ps] + MURDER["B"]
    out += [d.split("{")[0].strip() for d in DAY["B"]]
    return [p.lower() for p in out if len(p) > 6]


async def _main(a):
    from archive.world.lexicon import vocab_for
    data = Path(a.data_dir)
    cases = I.load_cases(data / f"cases_{a.split}.jsonl")
    rows = [r for r in I.read_jsonl(data / f"tasks_{a.split}.jsonl") if r["type"] not in SKIP_TYPES]
    rng = random.Random(a.seed)
    rows = rng.sample(rows, min(a.n_tasks, len(rows)))
    banned = held_out_phrases()
    client = SGLangClient(a.url, a.model, concurrency=64)
    try:
        outs = await asyncio.gather(*[
            client.chat([{"role": "system", "content": SYSTEM + "\n" + STYLES[(i + k) % len(STYLES)]},
                         {"role": "user", "content": r["question"]}],
                        lora=None, max_tokens=60, temperature=1.1, seed=a.seed * 100000 + i * 10 + k)
            for i, r in enumerate(rows) for k in range(a.per_task)])
    finally:
        await client.aclose()
    vocabs, kept, why = {}, [], Counter()
    for i, r in enumerate(rows):
        vocab = vocabs.setdefault(r["case_id"], vocab_for(cases[r["case_id"]]))
        seen = set()
        for k in range(a.per_task):
            q = outs[i * a.per_task + k]["text"].strip().strip('"').strip()
            q = re.sub(r"^(rewritten( question)?|question)\s*:\s*", "", q, flags=re.I).strip()
            if not q or "\n" in q or len(q) > 220:
                why["shape"] += 1
            elif q.lower() == r["question"].lower() or q.lower() in seen:
                why["duplicate"] += 1
            elif r["question"].rstrip().endswith("?") and "?" not in q:
                why["not_a_question"] += 1
            elif not same_question(vocab, r["question"], q):
                why["meaning_changed"] += 1
            elif any(b in q.lower() for b in banned):
                why["held_out_phrase"] += 1
            else:
                seen.add(q.lower())
                meta = dict(r.get("meta") or {}, paraphrase_of=r["task_id"])
                kept.append({**{x: y for x, y in r.items() if x not in ("messages", "gold_reply")},
                             "task_id": f"{r['task_id']}_p{k}", "question": q, "meta": meta})
                why["kept"] += 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    I.write_jsonl(a.out, kept)
    for s in ("cases",):
        src = data / f"{s}_{a.split}.jsonl"
        (Path(a.out).parent / src.name).write_text(src.read_text())
    report = {"tasks": len(rows), "samples": len(outs), **why, "by_type": Counter(x["type"] for x in kept)}
    (Path(a.out).parent / "paraphrase_manifest.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=1, default=str))
    for x in rng.sample(kept, min(8, len(kept))):
        orig = next(r["question"] for r in rows if r["task_id"] == x["meta"]["paraphrase_of"])
        print(f"  {orig!r}\n   -> {x['question']!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--data-dir", default="data_prepared")
    ap.add_argument("--n-tasks", type=int, default=2500)
    ap.add_argument("--per-task", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--out", default="data_prepared/paraphrase/tasks_train.jsonl")
    a = ap.parse_args()
    I.require("p2")
    asyncio.run(_main(a))


if __name__ == "__main__":
    main()
