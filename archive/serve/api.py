"""Stub game API (brief section 12.3) with canned responses from the Elsie case (section 4.3).

P3 builds the UI against this. Routes and response shapes are the contract; the canned
logic gets replaced by the real NPC engine and checker.
"""
from __future__ import annotations

import copy
import itertools
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="The Archive (stub)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DIFFICULTY = {
    "easy": {"questions_per_day": 8, "days": 3, "strikes": 3, "verifies_per_day": 0, "badges": True},
    "hard": {"questions_per_day": 5, "days": 2, "strikes": 1, "verifies_per_day": 3, "badges": False},
}

VILLAGERS = [
    {"id": "tom", "name": "Tom", "role": "miller", "persona": "nervous, overly polite, talks about flour"},
    {"id": "gus", "name": "Gus", "role": "guard", "persona": "gruff, very short sentences, uses watch times"},
    {"id": "nell", "name": "Nell", "role": "herbalist", "persona": "dreamy, mentions plants"},
    {"id": "mara", "name": "Mara", "role": "baker", "persona": "loud, quick-tempered"},
    {"id": "ivy", "name": "Ivy", "role": "blacksmith", "persona": "practical, counts everything"},
    {"id": "bram", "name": "Father Bram", "role": "priest", "persona": "gentle, quotes scripture"},
]

EVIDENCE = [
    {"id": "E1", "title": "Elsie's diary",
     "sentences": [{"id": "E1.S1", "text": "Tom still owes me 40 silver. I told him I'd go to the guild tomorrow."}]},
]

CANNED = {
    "tom": {"speech": ["Oh! Good day, good day. Flour everywhere, sorry."],
            "claims": [{"text": "I stayed at the mill all night on day 2.", "status": "supported",
                        "quote": "Day 2. Shut the mill at sunset. Stayed at the mill all night grinding flour.",
                        "source_title": "Tom's diary", "cites": ["D1.S1"], "fact": "F_tom_mill"}]},
    "gus": {"speech": ["Ninth bell. I keep watch."],
            "claims": [{"text": "At midnight on day 2 I saw Tom by the chapel wall, next to the guildhall.",
                        "status": "supported",
                        "quote": "Day 2, midnight. Saw Tom by the chapel wall, next to the guildhall, carrying a lantern.",
                        "source_title": "Gus's patrol log", "cites": ["D2.S1"], "fact": "F_gus_saw_tom"}]},
    "nell": {"speech": ["The night air smelled of yarrow..."],
             "claims": [{"text": "At midnight on day 2 the mill was dark and empty.", "status": "supported",
                         "quote": "Day 2, midnight. Walked past the mill. It was dark and silent, no one inside.",
                         "source_title": "Nell's notebook", "cites": ["D3.S1"], "fact": "F_nell_mill_empty"}]},
    "mara": {"speech": ["Don't look at me like that!"],
             "claims": [{"text": "I argued with Elsie about the price of flour at noon on day 2.", "status": "supported",
                         "quote": "Day 2, noon. Had a loud argument with Elsie about the price of flour.",
                         "source_title": "Mara's letter", "cites": ["D4.S1"], "fact": "F_mara_argued"},
                        {"text": "Elsie deserved it.", "status": "unsupported", "quote": None,
                         "source_title": None, "cites": [], "fact": None, "reason": "bad_cite"}]},
    "ivy": {"speech": ["Two hinges, one oven door. Long evening."],
            "claims": [{"text": "Mara was at my smithy from evening to midnight on day 2.", "status": "supported",
                        "quote": "Day 2, evening to midnight. Mara here, waiting for her oven door to be mended.",
                        "source_title": "Ivy's ledger", "cites": ["D5.S1"], "fact": "F_ivy_mara"}]},
    "bram": {"speech": ["Peace be with you, child."], "abstain": True, "claims": []},
}

CONTRADICTIONS = {
    frozenset({"F_tom_mill", "F_gus_saw_tom"}): "Tom: mill vs chapel wall, day 2 night",
    frozenset({"F_tom_mill", "F_nell_mill_empty"}): "Tom: at mill vs mill empty, day 2 night",
}
KILLER, MOTIVE_FACT = "tom", "F_elsie_debt"

GAMES: dict[str, dict] = {}
CLAIMS: dict[str, dict] = {}
_claim_ids = itertools.count(1)

class NewCase(BaseModel):
    seed: int | None = None
    difficulty: str = "easy"
    mode: str = "grounded"

class Ask(BaseModel):
    case_id: str
    villager_id: str
    question: str

class ClaimRef(BaseModel):
    claim_id: str

class Link(BaseModel):
    claim_a: str
    claim_b: str

class DayEnd(BaseModel):
    case_id: str

class Accuse(BaseModel):
    case_id: str
    villager_id: str
    links: list[list[str]] = []
    motive_claim: str | None = None

class Rumour(BaseModel):
    case_id: str
    villager_id: str
    text: str
    mode: str = "grounded"
    rounds: int = 5

def _game(case_id: str) -> dict:
    if case_id not in GAMES:
        raise HTTPException(404, "unknown case_id")
    return GAMES[case_id]

def _public_claim(c: dict, badges: bool) -> dict:
    out = {k: c[k] for k in ("claim_id", "villager_id", "text", "quote", "source_title", "cites")}
    out["status"] = c["status"] if badges or c.get("verified") else "unchecked"
    return out

@app.get("/health")
def health():
    return {"ok": True, "stub": True}

@app.post("/case")
def new_case(req: NewCase):
    if req.difficulty not in DIFFICULTY:
        raise HTTPException(400, "difficulty must be easy|hard")
    limits = DIFFICULTY[req.difficulty]
    case_id = f"c_{uuid.uuid4().hex[:8]}"
    motive_id = f"k{next(_claim_ids)}"
    CLAIMS[motive_id] = {"claim_id": motive_id, "villager_id": "evidence", "text": EVIDENCE[0]["sentences"][0]["text"],
                         "status": "supported", "quote": EVIDENCE[0]["sentences"][0]["text"],
                         "source_title": "Elsie's diary", "cites": ["E1.S1"], "fact": MOTIVE_FACT,
                         "case_id": case_id, "verified": True}
    GAMES[case_id] = {
        "case_id": case_id, "seed": req.seed or 0, "difficulty": req.difficulty, "mode": req.mode,
        "day": 1, "questions_left": limits["questions_per_day"], "strikes_left": limits["strikes"],
        "verifies_left": limits["verifies_per_day"], "questions_used": 0, "pinned": [], "log": [],
        "over": False,
    }
    return {
        "case_id": case_id,
        "briefing": "Elsie the innkeeper was found dead in the guildhall on the night of day 2. The side door was open.",
        "victim": {"id": "elsie", "name": "Elsie", "role": "innkeeper"},
        "scene": "guildhall",
        "villagers": VILLAGERS,
        "evidence": EVIDENCE,
        "evidence_claims": [_public_claim(CLAIMS[motive_id], True)],
        "limits": limits,
        "state": GAMES[case_id],
    }

@app.post("/ask")
def ask(req: Ask):
    g = _game(req.case_id)
    if req.villager_id not in CANNED:
        raise HTTPException(404, "unknown villager")
    if g["questions_left"] <= 0:
        raise HTTPException(409, "no questions left today")
    g["questions_left"] -= 1
    g["questions_used"] += 1
    canned = CANNED[req.villager_id]
    badges = DIFFICULTY[g["difficulty"]]["badges"]
    claims = []
    for c in canned["claims"]:
        cid = f"k{next(_claim_ids)}"
        rec = copy.deepcopy(c) | {"claim_id": cid, "villager_id": req.villager_id, "case_id": req.case_id}
        CLAIMS[cid] = rec
        claims.append(_public_claim(rec, badges))
    g["log"].append({"day": g["day"], "villager": req.villager_id, "question": req.question,
                     "claim_ids": [c["claim_id"] for c in claims]})
    return {
        "villager_id": req.villager_id,
        "speech": canned["speech"],
        "abstained": bool(canned.get("abstain")),
        "claims": claims,
        "questions_left": g["questions_left"],
    }

@app.post("/verify")
def verify(req: ClaimRef):
    c = CLAIMS.get(req.claim_id)
    if c is None:
        raise HTTPException(404, "unknown claim")
    g = _game(c["case_id"])
    if g["verifies_left"] <= 0:
        raise HTTPException(409, "no verify checks left today")
    g["verifies_left"] -= 1
    c["verified"] = True
    return {"claim_id": req.claim_id, "status": c["status"], "verifies_left": g["verifies_left"]}

@app.post("/pin")
def pin(req: ClaimRef):
    c = CLAIMS.get(req.claim_id)
    if c is None:
        raise HTTPException(404, "unknown claim")
    if c["status"] != "supported":
        return {"ok": False, "reason": "only supported (green) claims can be pinned"}
    g = _game(c["case_id"])
    if req.claim_id not in g["pinned"]:
        g["pinned"].append(req.claim_id)
    return {"ok": True, "pinned": g["pinned"]}

@app.post("/link")
def link(req: Link):
    a, b = CLAIMS.get(req.claim_a), CLAIMS.get(req.claim_b)
    if a is None or b is None:
        raise HTTPException(404, "unknown claim")
    reason = CONTRADICTIONS.get(frozenset({a.get("fact"), b.get("fact")}))
    return {"confirmed": reason is not None, "reason": reason or "no contradiction between these facts"}

@app.post("/day/end")
def day_end(req: DayEnd):
    g = _game(req.case_id)
    limits = DIFFICULTY[g["difficulty"]]
    events = [
        {"asker": "nell", "responder": "tom", "question": "Where were you on the night of day 2?",
         "reply": "I stayed at the mill all night. [D1.S1]", "status": "supported",
         "heard_id": "H1"},
        {"asker": "mara", "responder": "ivy", "question": "Do you remember when I left the smithy?",
         "reply": "You were here until midnight on day 2. [D5.S1]", "status": "supported", "heard_id": "H2"},
    ]
    hints = ["Nell looked puzzled by something Tom said."] if g["difficulty"] == "easy" else []
    g["day"] += 1
    g["questions_left"] = limits["questions_per_day"]
    g["verifies_left"] = limits["verifies_per_day"]
    if g["day"] > limits["days"]:
        g["over"] = True
    return {"events": events, "hints": hints, "day": g["day"], "game_over": g["over"], "state": g}

@app.post("/accuse")
def accuse(req: Accuse):
    g = _game(req.case_id)
    confirmed = 0
    for pair in req.links:
        if len(pair) == 2:
            a, b = CLAIMS.get(pair[0]), CLAIMS.get(pair[1])
            if a and b and frozenset({a.get("fact"), b.get("fact")}) in CONTRADICTIONS:
                confirmed += 1
    motive_ok = bool(req.motive_claim and CLAIMS.get(req.motive_claim, {}).get("fact") == MOTIVE_FACT)
    correct = req.villager_id == KILLER and confirmed >= 2 and motive_ok
    if not correct:
        g["strikes_left"] -= 1
    score = max(0, 1000 - 40 * g["questions_used"] - 300 * (DIFFICULTY[g["difficulty"]]["strikes"] - g["strikes_left"]))
    g["over"] = correct or g["strikes_left"] <= 0
    return {
        "correct": correct,
        "score": score if correct else None,
        "confirmed_links": confirmed,
        "motive_ok": motive_ok,
        "strikes_left": g["strikes_left"],
        "reveal": {"killer": "tom", "motive": "Tom owed Elsie 40 silver.",
                   "contradictions": list(CONTRADICTIONS.values())} if g["over"] else None,
    }

@app.post("/rumour")
def rumour(req: Rumour):
    _game(req.case_id)
    ids = [v["id"] for v in VILLAGERS]
    rounds = []
    for r in range(1, req.rounds + 1):
        spread = {}
        for i, vid in enumerate(ids):
            if vid == req.villager_id:
                spread[vid] = "amber" if req.mode == "grounded" else "red"
            elif req.mode == "base" and i < r + 1:
                spread[vid] = "red"
            elif req.mode == "grounded" and i < r // 2 + 1:
                spread[vid] = "amber"
            else:
                spread[vid] = "plain"
        rounds.append({"round": r, "spread": spread})
    return {"rumour": req.text, "mode": req.mode, "rounds": rounds,
            "repeated_as_fact": sum(s == "red" for s in rounds[-1]["spread"].values())}

@app.get("/state/{case_id}")
def state(case_id: str):
    g = _game(case_id)
    return {"state": g, "claims": [_public_claim(c, True) for c in CLAIMS.values() if c["case_id"] == case_id]}

@app.get("/replay/{replay_id}")
def replay(replay_id: str):
    return {"replay_id": replay_id, "stub": True,
            "turns": [{"villager_id": v, **CANNED[v]} for v in CANNED]}
