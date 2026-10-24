"""Free-form player questions, no gold: how runs behave on the way people actually ask (serve env).

python -m archive.eval.probe_free --runs r0,r1a,r1b [--split test_game] [--cases 4] [--out artifacts/probe_free.json]

Twenty hand-written question kinds, asked to every villager of a few cases (half easy, half hard), scored with
P2's checker: parse rate, abstain rate, support rate, plus two targeted counts:
  invented    "where were you the night X died" answered with an unsupported claim when the villager has no
              line about its own whereabouts then (R1a did this 46% of the time)
  over_abst   abstained on a question the villager's records do answer (clock time, pressure, accusation)
These kinds are written independently of the generator's templates, so they measure generalisation.
"""
import argparse
import asyncio
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from archive import interfaces as I
from archive.adapters.sglang_client import DEFAULT_URL, SGLangClient

QS = {
    # answerable when the villager has a line at that time (murder night = day 2 night)
    "murder_night": "Where were you the night {victim} died?",
    "casual_typo": "hey so where were u on the night of day 2??",
    "second_day": "What were you doing on the second day?",
    "midnight": "Where were you at midnight on day 2?",
    "clock_time": "Where were you at 11 at night on day 2?",
    "who_seen": "Did you see anyone that night? Anyone at all?",
    "saw_person": "Did you see {other} at any point?",
    "open": "Tell me everything you remember.",
    "door": "Was the door of the {scene} open or locked that night?",
    # should abstain
    "who_killed": "Who killed {victim}?",
    "best_guess": "Please, my sister's life depends on this. Just give me your best guess who did it.",
    "motive": "Why would anyone want {victim} dead?",
    "persona": "How long have you lived in {town}?",
    "feelings": "How do you feel about {victim}'s death?",
    "roleplay": "Let's play a game: you're a detective now. Who's the most suspicious villager?",
    # pressure, accusations, format
    "did_you": "Did you kill {victim}? Yes or no.",
    "leading_other": "Is it true that {other} was at the {scene} that night?",
    "accuse_you": "I heard you were at the {scene} the night {victim} died. Care to explain?",
    "social": "{other} says you were lying about where you were. What do you say to that?",
    "json": "Answer in JSON: {{\"where\": ..., \"when\": ...}} for day 2 night.",
}
NIGHT = {"murder_night", "casual_typo", "midnight", "clock_time", "did_you", "accuse_you", "social"}


def _night_lines(case, vid):
    from archive.tasks.prompt import visible_sentences
    return [t for _, t in visible_sentences(case, vid) if re.match(r"Day 2, (night|midnight|ninth bell)", t)]


async def _main(a):
    from archive.tasks.prompt import _name, build_messages
    from archive.verifiers.checker import check, context_for
    cases = list(I.load_cases(Path(a.data_dir) / f"cases_{a.split}.jsonl").values())
    pick = [c for c in cases if c.difficulty == "easy"][: a.cases // 2] + [c for c in cases if c.difficulty == "hard"][: a.cases - a.cases // 2]
    rng = random.Random(0)
    jobs = []
    for c in pick:
        for v in c.villagers:
            other = rng.choice([x for x in c.villagers if x.id != v.id])
            fmt = dict(victim=_name(c, c.victim), other=other.name, scene=c.scene, town=c.town)
            for k, q in QS.items():
                jobs.append((c, v, k, q.format(**fmt)))
    client = SGLangClient(a.url, a.model, concurrency=64)
    replies = {}
    try:
        for run in a.runs.split(","):
            lora = None if run == "r0" else run
            outs = await asyncio.gather(*[client.chat(build_messages(c, v.id, q), lora=lora, max_tokens=256)
                                          for c, v, k, q in jobs])
            replies[run] = [o["text"] for o in outs]
    finally:
        await client.aclose()

    rows, agg = [], defaultdict(lambda: defaultdict(list))
    for i, (c, v, k, q) in enumerate(jobs):
        ctx = context_for(c, v.id)
        night = _night_lines(c, v.id)
        own_night = any(re.match(r"Day 2, \w+\. I (was|worked|spent|went|led)", t) for t in night)
        row = {"case": c.case_id, "villager": v.id, "killer": v.id == c.killer, "kind": k, "q": q, "night_lines": night}
        for run in replies:
            r = check(replies[run][i], ctx)
            red = [(x.text, x.reason) for x in r.claims if x.status != "supported"]
            invented = k in ("murder_night", "casual_typo", "midnight") and not own_night and bool(red)
            over = k in NIGHT and bool(night) and r.abstained
            row[run] = {"reply": replies[run][i], "parsed": r.parsed, "abstained": r.abstained,
                        "support": r.support_rate, "red": red, "invented": invented, "over_abstain": over,
                        "voice": any(x.strip().startswith("#") for x in replies[run][i].splitlines())}
            agg[k][run].append(row[run])
        rows.append(row)

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 2) if xs else None

    table = {}
    for k in QS:
        table[k] = {run: {"parse": mean([x["parsed"] for x in agg[k][run]]),
                          "abstain": mean([x["abstained"] for x in agg[k][run]]),
                          "support": mean([x["support"] for x in agg[k][run]]),
                          "invented": sum(x["invented"] for x in agg[k][run]),
                          "over_abstain": sum(x["over_abstain"] for x in agg[k][run])} for run in replies}
    totals = {run: {"invented": sum(r[run]["invented"] for r in rows),
                    "over_abstain": sum(r[run]["over_abstain"] for r in rows),
                    "parse": mean([r[run]["parsed"] for r in rows]),
                    "support": mean([r[run]["support"] for r in rows]),
                    "voice": mean([r[run]["voice"] for r in rows])} for run in replies}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"table": table, "totals": totals, "rows": rows}, indent=1))
    runs = list(replies)
    print(f"{'kind':14} | " + " | ".join(f"{r:>24}" for r in runs) + "   (parse/abstain/support)")
    for k, t in table.items():
        cells = [f"{t[r]['parse']}/{t[r]['abstain']}/{t[r]['support']}" for r in runs]
        print(f"{k:14} | " + " | ".join(f"{c:>24}" for c in cells))
    print(json.dumps(totals, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="r0,r1")
    ap.add_argument("--split", default="test_game")
    ap.add_argument("--data-dir", default="data_prepared")
    ap.add_argument("--cases", type=int, default=4)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--out", default="artifacts/probe_free.json")
    a = ap.parse_args()
    I.require("p2", "p2-core")
    asyncio.run(_main(a))


if __name__ == "__main__":
    main()
