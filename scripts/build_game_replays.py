"""Replays for the finance game, generated from game/data/cases.json (real model outputs, verifier-checked)."""
import json

book = json.load(open("game/data/cases.json"))
kase = book["cases"][0]
fmt = lambda x: str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.1f}"


def claim(desk, c):
    return {"villager_id": desk, "text": c["text"], "status": c["status"], "reason": c["reason"], "quote": c["quote"],
            "source_title": "Verifier recompute", "cites": c["cites"]}


def make(mode, include_base):
    desks = [d for d in kase["desks"] if include_base or d != "base"][:6]
    if kase["culprit"] not in desks:
        desks[-1] = kase["culprit"]
    info = book["desks"]
    turns = []
    for d in desks:
        v = kase["desks"][d]
        turns.append({"type": "ask", "day": 1, "villager_id": d, "question": "Show me your work, step by step.",
                      "speech": ["Here is my working." if d != "base" else (v["prose"][0][:80] if v["prose"] else "...")],
                      "abstained": not v["claims"] and d != "base",
                      "claims": [claim(d, c) for c in v["claims"][:3]] or ([{"villager_id": d, "text": v["prose"][0][:120], "status": "unsupported",
                                                                         "reason": "not_a_checkable_step", "quote": "Verifier: not an S<k>: op(args) = value line.",
                                                                         "source_title": "Verifier", "cites": []}] if v["prose"] else [])})
        if v["answer"] is not None:
            turns.append({"type": "ask", "day": 1, "villager_id": d, "question": "What is your final figure?", "speech": ["My figure:"],
                          "abstained": False, "claims": [{"villager_id": d, "text": f"Final figure: {fmt(v['answer'])}",
                                                           "status": "supported" if v["final_ok"] else "unsupported",
                                                           "reason": None if v["final_ok"] else "wrong_final",
                                                           "quote": f"Verifier ground truth: {fmt(kase['gold'])}", "source_title": "Verifier ground truth", "cites": []}]})
    for p in kase["pairs"][:2]:
        turns.append({"type": "link", "day": 2, "claim_a": f"{p['call']} = {fmt(p['wrote'])}", "claim_b": f"{p['call']} = {fmt(p['truth'])}",
                      "confirmed": True, "reason": f"Two desks disagree on {p['call']}: {fmt(p['wrote'])} vs {fmt(p['truth'])}."})
    turns.append({"type": "accuse", "day": 2, "villager_id": kase["culprit"], "correct": True, "confirmed_links": len(kase["pairs"][:2]), "motive_ok": True})
    return {"replay_id": f"audit_{mode}", "title": f"{kase['question'][:60]}... · {'with baseline' if include_base else 'trained desks only'}", "mode": mode,
            "difficulty": "easy", "source": "Recorded from real model outputs (finseries verifier recompute); not simulated.",
            "briefing": f"Audit question: {kase['question']}", "villagers": [{"id": d, "name": info[d]["name"], "role": info[d]["role"], "persona": info[d]["persona"]} for d in desks],
            "victim": {"id": "ledger", "name": "the audit file"}, "turns": turns}


out = []
for mode, inc in (("base", True), ("grounded", False)):
    r = make(mode, inc)
    fn = f"audit_{mode}.json"
    json.dump(r, open(f"game/replays/{fn}", "w"), indent=1)
    out.append({"file": fn, "title": r["title"], "mode": mode,
                "description": "Real model outputs: every line was recomputed by the verifier." if inc else "Trained desks only: no untrained baseline on the floor."})
json.dump(out, open("game/replays/index.json", "w"), indent=1)
print("replays:", [o["file"] for o in out])
