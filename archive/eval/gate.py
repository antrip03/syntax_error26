"""Quick checker-only gate on a split (serve env; MODE p2 or p2-core). Needs no rewards or metrics code.

python -m archive.eval.gate --split val [--lora r1] [--limit 300] [--url http://127.0.0.1:30000]
python -m archive.eval.gate --split test_free --lora r3 --samples 4 --temperature 0.8   # reliability

Greedy replies through SGLang, scored with P2's checker against each task's gold:
  parse        reply parses (answer block or abstain)
  support      supported / claims, over non-abstain parsed replies
  abstain_acc  abstained == gold.abstain
  fact_recall  gold facts covered by supported claims (answerable tasks)
  exact        parsed, right abstain decision, and (if answering) every claim supported and every gold fact covered
  hash_leak    a '#' persona line names something checkable (person, place, item, time, number, crime word):
               the checker ignores '#' lines, so a fact hidden there would dodge it; counts as not exact
With --samples N (N > 1) every task is answered N times at --temperature, and the summary adds
  reliable     share of tasks answered exactly right in all N samples (what GRPO optimises; the game samples too)
  exact_mean   share of all samples exactly right
Brief 10.2 gate before GRPO: parse >= 0.95, support >= 0.90, and answers actually right (fact_recall), not
just abstaining (the dry run collapsed to always-abstain).
"""
import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from archive import interfaces as I
from archive.adapters.sglang_client import DEFAULT_URL, SGLangClient

_VOCAB: dict = {}


def hash_leak(reply: str, case) -> bool:
    """True if a '#' line holds a checkable word (P2's lexicon): facts must live in CLAIM lines only."""
    from archive.world.lexicon import actions, vocab_for
    vocab = _VOCAB.setdefault(case.case_id, vocab_for(case))
    for line in reply.splitlines():
        line = line.strip()
        if line.startswith("#"):
            ents = {e for e in vocab.extract(line[1:]) if e[0] != "unknown"}
            if ents or actions(line):
                return True
    return False


def score(row: dict, reply: str, cases: dict) -> dict:
    c = I.check(reply, row, cases)
    gold = row["gold"]
    gold_facts = {f for g in gold["claims"] for f in g.get("facts", [])}
    sup = {f for x in c["claims"] if x["status"] == "supported" for f in x["facts"]}
    n_claims = len(c["claims"])
    all_sup = n_claims > 0 and all(x["status"] == "supported" for x in c["claims"])
    recall = len(gold_facts & sup) / len(gold_facts) if gold_facts else None
    right_abstain = c["parsed"] and c["abstained"] == gold["abstain"]
    leak = hash_leak(reply, cases[row["case_id"]]) if I.MODE != "devstub" else False
    exact = right_abstain and not leak and (gold["abstain"] or (all_sup and (recall is None or recall == 1.0)))
    return {"parse": c["parsed"], "abstained": c["abstained"], "gold_abstain": gold["abstain"],
            "support": c["support_rate"], "fact_recall": recall, "abstain_acc": right_abstain, "exact": exact,
            "hash_leak": leak, "voice": any(x.strip().startswith("#") for x in reply.splitlines()),
            "reasons": [x["reason"] for x in c["claims"] if x["status"] != "supported"]}


def summarize(scored: list[dict]) -> dict:
    def mean(xs):
        xs = [float(x) for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None
    reasons = defaultdict(int)
    for s in scored:
        for r in s["reasons"]:
            reasons[r] += 1
    return {"n": len(scored), "parse": mean(s["parse"] for s in scored),
            "support": mean(s["support"] for s in scored),
            "abstain_acc": mean(s["abstain_acc"] for s in scored),
            "abstain_rate": mean(s["abstained"] for s in scored),
            "gold_abstain_rate": mean(s["gold_abstain"] for s in scored),
            "fact_recall": mean(s["fact_recall"] for s in scored if not s["gold_abstain"]),
            "exact": mean(s["exact"] for s in scored), "hash_leak": mean(s["hash_leak"] for s in scored),
            "voice": mean(s["voice"] for s in scored), "red_reasons": dict(reasons)}


async def _main(a):
    data = Path(a.data_dir)
    cases = I.load_cases(data / f"cases_{a.split}.jsonl")
    rows = I.read_jsonl(data / f"tasks_{a.split}.jsonl")[: a.limit or None]
    client = SGLangClient(a.url, a.model, concurrency=64)
    try:
        n = max(1, a.samples)
        kw = {"temperature": a.temperature} if n > 1 else {}
        flat = await asyncio.gather(*[client.chat(I.messages(r, cases), lora=a.lora, max_tokens=a.max_tokens,
                                                  seed=(1000 * k + i if n > 1 else None), **kw)
                                      for i, r in enumerate(rows) for k in range(n)])
        groups = [flat[i * n:(i + 1) * n] for i in range(len(rows))]
        outs = [g[0] for g in groups]
    finally:
        await client.aclose()
    scored = [{**score(r, o["text"], cases), "type": r["type"],
               "key": f"{r['type']}:{r['variant']}" if r.get("variant") else r["type"]} for r, o in zip(rows, outs)]
    by_type = defaultdict(list)
    for s in scored:
        by_type[s["key"]].append(s)
    res = {"split": a.split, "lora": a.lora, "interfaces_mode": I.MODE, "all": summarize(scored),
           "by_type": {t: summarize(v) for t, v in sorted(by_type.items())}}
    if n > 1:
        every = [[score(r, o["text"], cases)["exact"] for o in g] for r, g in zip(rows, groups)]
        rel = defaultdict(list)
        for s, e in zip(scored, every):
            rel[s["key"]].append(all(e))
        res["all"]["reliable"] = round(sum(all(e) for e in every) / len(every), 3)
        res["all"]["exact_mean"] = round(sum(map(sum, every)) / (n * len(every)), 3)
        res["samples"], res["temperature"] = n, a.temperature
        for k, v in rel.items():
            res["by_type"][k]["reliable"] = round(sum(v) / len(v), 3)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=2))
        I.write_jsonl(Path(a.out).with_suffix(".samples.jsonl"),
                      [{"task_id": r["task_id"], "type": r["type"], "question": r["question"], "gold": r.get("gold"),
                        "reply": o["text"], **s} for r, o, s in zip(rows, outs, scored)])
    print(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--data-dir", default="data_prepared")
    ap.add_argument("--lora", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--out", default=None)
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.8)
    a = ap.parse_args()
    if I.MODE == "devstub":
        I.require("p2", "p2-core")
    asyncio.run(_main(a))


if __name__ == "__main__":
    main()
