"""Real game API: the section 12.3 contract (game/HANDOFF.md) served by our models (serve env).

    source scripts/env.sh serve && python -m uvicorn archive.serve.game_api:app --host 0.0.0.0 --port 8000

Same routes and response shapes as the stub (archive/serve/api.py), so the game needs no change. Behind them:
  /case       P2's case generator (generate_case), evidence documents, the motive line as a pinnable claim
  /ask        the villager prompt on SGLang (adapter by mode), P2's checker -> claims with statuses and quotes;
              on Hard the killer is the untrained model with P2's liar prompt (brief 4.6), its sentences wrapped
              as uncited claims, so Verify shows them red
  /day/end    P2's gossip engine (npc/gossip.run_evening) with the game's memory, clash hints on Easy
  /link       P2's contradiction check (verifiers/contradiction.confirm)
  /accuse     killer + 2 confirmed contradictions + the motive line, as the brief scores it
  /rumour     source "traveller" (P2's npc/rumour.run) or "killer" (P1's eval/manipulation.run_mode)
Modes (the title screen's village toggle): "grounded" = ARCHIVE_GROUNDED (default r3), "sft" = ARCHIVE_SFT (default
r1b), "base" = the untrained model. SGLang must serve those adapters (scripts/serve_game.sh).
"""
from __future__ import annotations

import asyncio
import itertools
import os
import pickle
import random
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from archive.adapters.sglang_client import SGLangClient
from archive.npc import gossip, rumour as rumour_mod
from archive.schemas import Case, ClaimResult
from archive.tasks.prompt import build_liar_messages, build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.contradiction import confirm, facts_clash
from archive.world.casegen import generate_case

SGLANG_URL = os.environ.get("SGLANG_URL", "http://127.0.0.1:30000")
MODEL = os.environ.get("ARCHIVE_MODEL", "Qwen/Qwen3-1.7B")
MODES = {"grounded": os.environ.get("ARCHIVE_GROUNDED", "r3"), "sft": os.environ.get("ARCHIVE_SFT", "r1b"),
         "base": None}
TEMPERATURE = float(os.environ.get("ARCHIVE_TEMPERATURE", "0.7"))  # villagers sample, like a real game would
DIFFICULTY = {
    "easy": {"questions_per_day": 8, "days": 3, "strikes": 3, "verifies_per_day": 0, "badges": True},
    "hard": {"questions_per_day": 5, "days": 2, "strikes": 1, "verifies_per_day": 3, "badges": False},
}
SCENE_KEYS = {"mill": "mill", "river path": "river", "guildhall": "guildhall", "chapel": "chapel", "inn": "inn",
              "bakery": "bakery", "smithy": "smithy"}  # game/js/map.js ROOMS keys

app = FastAPI(title="The Archive")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def _persist(request, call_next):
    response = await call_next(request)
    if request.method == "POST" and response.status_code < 400:
        _save()
    return response

GAMES: dict[str, dict] = {}
CLAIMS: dict[str, dict] = {}
_ids = itertools.count(1)
# Games survive an API restart: everything is pickled to STATE_FILE after each change and loaded on start.
STATE_FILE = Path(os.environ.get("ARCHIVE_STATE", "/tmp/archive_p1/game_state.pkl"))


def _save() -> None:
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"games": GAMES, "claims": CLAIMS, "next_id": next(_ids)}, f)
        tmp.replace(STATE_FILE)
    except Exception as e:  # never break a request over persistence
        print(f"[game_api] could not save state: {e}", flush=True)


def _load() -> None:
    global _ids
    try:
        with open(STATE_FILE, "rb") as f:
            st = pickle.load(f)
        GAMES.update(st["games"]); CLAIMS.update(st["claims"]); _ids = itertools.count(st["next_id"] + 1)
        print(f"[game_api] restored {len(GAMES)} games, {len(CLAIMS)} claims", flush=True)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[game_api] could not load state: {e}", flush=True)


_load()
_SENT = re.compile(r"(?<=[.!?])\s+")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*\[[^\]]*\]|</?answer>", "", text)).strip()


# ---------- models ----------------------------------------------------------------------------------------------

def chat_many(batch: list[tuple[list[dict], str | None]], max_tokens: int = 200) -> list[str]:
    """[(messages, lora)] -> replies, in one concurrent batch. Called from FastAPI's threadpool."""
    async def go():
        c = SGLangClient(SGLANG_URL, MODEL, concurrency=16)
        try:
            outs = await asyncio.gather(*[c.chat(m, lora=l, max_tokens=max_tokens, temperature=TEMPERATURE)
                                          for m, l in batch])
            return [o["text"] for o in outs]
        finally:
            await c.aclose()
    return asyncio.run(go())


def ask_many_for(lora):
    """P2's npc code calls ask_many(list of message lists); route them all to one village's adapter."""
    return lambda batch: chat_many([(m, lora) for m in batch])


# ---------- helpers ---------------------------------------------------------------------------------------------

def _game(case_id: str) -> dict:
    if case_id not in GAMES:
        raise HTTPException(404, "This case is no longer on the server. Start a new case from the menu.")
    return GAMES[case_id]


def _name(case: Case, pid: str) -> str:
    names = case.lexicon.people.get(pid)
    return names[0] if names else pid


def _victim(case: Case) -> dict:
    m = re.match(r"^(.+?) the ([a-z ]+?) was found", case.briefing)
    return {"id": case.victim, "name": _name(case, case.victim), "role": m.group(2) if m else "villager"}


def _key_facts(case: Case) -> set[str]:
    """Facts behind the Easy-mode star: both sides of each contradiction, and every motive in the evidence
    (the killer's and the red herrings', so the star does not say which motive is the real one)."""
    evidence = {f for d in case.evidence_docs for s in case.doc(d).sentences for f in s.facts}
    motives = {f.id for f in case.facts if f.id in evidence and f.rel in ("owes", "argued")}
    return {f for pair in case.solution.contradictions for f in pair} | {case.solution.motive} | motives


def _store(g: dict, villager_id: str, c: ClaimResult | dict, quote: str | None, source: str | None,
           hearsay_from: str | None = None) -> dict:
    c = c if isinstance(c, ClaimResult) else ClaimResult.model_validate(c)
    cid = f"k{next(_ids)}"
    rec = {"claim_id": cid, "case_id": g["case_id"], "villager_id": villager_id, "text": c.text,
           "status": c.status, "reason": c.reason, "cites": c.cites, "facts": c.facts, "quote": quote,
           "source_title": source, "hearsay_from": hearsay_from,
           # Easy-mode hint: part of the solution, and never the killer's own lines (that would point at them)
           "highlight": g["difficulty"] == "easy" and villager_id != g["case"].killer
                        and bool(set(c.facts) & _key_facts(g["case"])), "verified": False}
    CLAIMS[cid] = rec
    return rec


def _public(rec: dict, badges: bool) -> dict:
    out = {k: rec[k] for k in ("claim_id", "villager_id", "text", "quote", "source_title", "cites", "hearsay_from",
                               "highlight")}
    out["status"] = rec["status"] if badges or rec.get("verified") else "unchecked"
    if out["status"] == "unsupported":
        out["reason"] = rec["reason"]
    return out


def _state(g: dict) -> dict:
    return {k: g[k] for k in ("day", "questions_left", "questions_used", "strikes_left", "verifies_left", "seed",
                              "over", "mode", "difficulty")}


def _sources(case: Case, vid: str, heard, cites: list[str]) -> tuple[str | None, str | None, str | None]:
    """(quote, source title, hearsay teller) for a claim's cited lines."""
    ctx = context_for(case, vid, heard)
    quote = " ".join(ctx.texts[i] for i in cites if i in ctx.texts) or None
    teller = next((ctx.speakers[i] for i in cites if i in ctx.heard_ids), None)
    if teller:
        return quote, f"Heard from {_name(case, teller)}", teller
    doc = next((d for d in case.documents for s in d.sentences if cites and s.id == cites[0]), None)
    return quote, doc.title if doc else None, None


# ---------- routes ----------------------------------------------------------------------------------------------

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
    villager_id: str | None = None
    text: str = ""
    mode: str = "grounded"
    rounds: int = 5
    source: str = "traveller"
    seed: int = 0


@app.get("/health")
def health():
    return {"ok": True, "stub": False, "model": MODEL, "modes": MODES}


@app.post("/case")
def new_case(req: NewCase):
    if req.difficulty not in DIFFICULTY:
        raise HTTPException(400, "difficulty must be easy|hard")
    if req.mode not in MODES:
        raise HTTPException(400, f"mode must be one of {'|'.join(MODES)}")
    seed = req.seed if req.seed is not None else random.randint(10_000, 99_999)
    case = generate_case(seed, req.difficulty)
    limits = DIFFICULTY[req.difficulty]
    case_id = f"c_{uuid.uuid4().hex[:8]}"
    g = {"case_id": case_id, "case": case, "seed": seed, "difficulty": req.difficulty, "mode": req.mode,
         "day": 1, "questions_left": limits["questions_per_day"], "strikes_left": limits["strikes"],
         "verifies_left": limits["verifies_per_day"], "questions_used": 0, "pinned": [], "over": False,
         "memory": gossip.Memory()}
    GAMES[case_id] = g
    evidence, evidence_claims = [], []
    for did in case.evidence_docs:
        d = case.doc(did)
        evidence.append({"id": d.id, "title": d.title, "sentences": [{"id": s.id, "text": s.text} for s in d.sentences]})
        for s in d.sentences:
            rec = _store(g, "evidence", {"text": s.text, "cites": [s.id], "status": "supported", "reason": "ok",
                                         "facts": s.facts}, s.text, d.title)
            rec["verified"] = True
            evidence_claims.append(_public(rec, True))
    out = {"case_id": case_id, "briefing": case.briefing, "victim": _victim(case),
           "villagers": [{"id": v.id, "name": v.name, "role": v.role, "persona": v.persona} for v in case.villagers],
           "evidence": evidence, "evidence_claims": evidence_claims, "limits": limits, "state": _state(g),
           "mode": req.mode, "difficulty": req.difficulty}
    out["scene"] = SCENE_KEYS.get(case.scene, case.scene)  # a room key, or an outdoor place ("market")
    out["scene_place"] = case.scene
    return out


def _liar(g: dict, vid: str) -> bool:
    return g["difficulty"] == "hard" and vid == g["case"].killer


def _answer(g: dict, vid: str, question: str) -> dict:
    """One villager reply: speech lines and stored claims (not yet public)."""
    case, heard = g["case"], g["memory"].of(vid)
    if _liar(g, vid):
        msgs, lora = build_liar_messages(case, vid, question), None
    else:
        msgs, lora = build_messages(case, vid, question, heard), MODES[g["mode"]]
    reply = chat_many([(msgs, lora)])[0]
    res = check(reply, context_for(case, vid, heard))
    speech = [_clean(ln.strip()[1:]) for ln in reply.splitlines() if ln.strip().startswith("#")]
    speech = [x for x in speech if x]
    claims = []
    if res.parsed and not res.abstained:
        for c in res.claims:
            q, src, teller = _sources(case, vid, heard, c.cites)
            claims.append(_store(g, vid, c, q, src, teller))
    elif not res.parsed:
        # free prose (the untrained model, or the liar): every sentence becomes an uncited claim, which is red
        prose = re.sub(r"<[^>]+>|\[[^\]]*\]", " ", reply)
        prose = re.sub(r"(?m)^\s*(CLAIM:|#)\s*", "", prose)
        sents = [s.strip() for s in _SENT.split(re.sub(r"\s+", " ", prose)) if len(s.strip()) > 3][:4]
        for s in sents:
            claims.append(_store(g, vid, {"text": s, "cites": [], "status": "unsupported", "reason": "bad_cite"},
                                 None, None))
    return {"reply": reply, "speech": speech, "abstained": res.abstained, "claims": claims}


@app.post("/ask")
def ask(req: Ask):
    g = _game(req.case_id)
    if req.villager_id not in {v.id for v in g["case"].villagers}:
        raise HTTPException(404, "unknown villager")
    if g["questions_left"] <= 0:
        raise HTTPException(409, "no questions left today")
    question = req.question.strip()[:300]
    if not question:
        raise HTTPException(400, "empty question")
    g["questions_left"] -= 1
    g["questions_used"] += 1
    a = _answer(g, req.villager_id, question)
    badges = DIFFICULTY[g["difficulty"]]["badges"]
    return {"villager_id": req.villager_id, "speech": a["speech"], "abstained": a["abstained"],
            "claims": [_public(c, badges) for c in a["claims"]], "questions_left": g["questions_left"],
            "raw": a["reply"]}


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
    return {"claim_id": req.claim_id, "status": c["status"], "verifies_left": g["verifies_left"],
            "reason": c["reason"] if c["status"] != "supported" else None}


@app.post("/pin")
def pin(req: ClaimRef):
    c = CLAIMS.get(req.claim_id)
    if c is None:
        raise HTTPException(404, "unknown claim")
    g = _game(c["case_id"])
    if c["status"] != "supported" or (not DIFFICULTY[g["difficulty"]]["badges"] and not c["verified"]
                                       and c["villager_id"] != "evidence"):
        return {"ok": False, "pinned": g["pinned"], "reason": "only green claims can go in your notebook"}
    if req.claim_id not in g["pinned"]:
        g["pinned"].append(req.claim_id)
    return {"ok": True, "pinned": g["pinned"], "reason": None}


def _as_result(rec: dict) -> dict:
    return {"text": rec["text"], "cites": rec["cites"], "status": rec["status"], "reason": rec["reason"],
            "facts": rec["facts"]}


@app.post("/link")
def link(req: Link):
    a, b = CLAIMS.get(req.claim_a), CLAIMS.get(req.claim_b)
    if a is None or b is None:
        raise HTTPException(404, "unknown claim")
    ok, reason = confirm(_game(a["case_id"])["case"], _as_result(a), _as_result(b))
    return {"confirmed": ok, "reason": reason}


@app.post("/day/end")
def day_end(req: DayEnd):
    g = _game(req.case_id)
    case, limits = g["case"], DIFFICULTY[g["difficulty"]]
    ev = _evening(g, rounds=2, pairs=3)
    events = []
    for e in ev["events"]:
        res = check(e["reply"], context_for(case, e["responder"], g["memory"].of(e["responder"])))
        status = "abstained" if res.abstained else "supported" if res.parsed and res.support_rate == 1.0 else "unsupported"
        reply = "I'm not sure." if res.abstained else (
            _clean(re.sub(r"(?m)^\s*(CLAIM:\s*|#[^\n]*\n?)", " ", e["reply"])) or _clean(e["reply"]) or "...")
        events.append({"round": e["round"], "asker": e["asker"], "responder": e["responder"], "question": e["question"],
                       "reply": reply, "status": status,
                       "heard_id": (e["heard_ids"] or [None])[0], "clash": bool(e["hints"])})
    hints = [h["text"] for h in ev["hints"]] if g["difficulty"] == "easy" else []
    g["day"] += 1
    g["questions_left"] = limits["questions_per_day"]
    g["verifies_left"] = limits["verifies_per_day"]
    if g["day"] > limits["days"]:
        g["over"] = True
    return {"events": events, "hints": hints, "day": g["day"], "game_over": g["over"], "state": _state(g)}


def _question(case: Case, topic) -> str:
    if topic.kind == "night":
        return "Where were you on the night of the murder?"
    if topic.kind == "person":
        return f"Did you see {topic.text} at any point?"
    if topic.kind == "victim":
        return f"What do you know about {topic.text}?"
    return f"What did you see at {topic.text}?"


def _evening(g: dict, rounds: int, pairs: int) -> dict:
    """Evening gossip with P2's scheduler, memory and clash hints. Questions come from the topic (the asker prompt
    makes the small model ask for things nobody wrote down), and each topic is one the responder has a line on
    when possible, so gossip actually moves information around."""
    case, memory, lora = g["case"], g["memory"], MODES[g["mode"]]
    rng = random.Random(g["seed"] * 10 + g["day"])
    events = []
    for rnd, plan in enumerate(gossip.schedule(case, rng, memory, rounds, pairs), start=1):
        plan2 = []
        for a, r, t in plan:
            if not gossip.knows(case, r, t, memory.of(r)):
                known = [x for x in gossip.topics(case) if x.value not in (a, r) and gossip.knows(case, r, x, memory.of(r))]
                night = [x for x in known if x.kind == "night"]
                t = (night or known or [t])[0] if rng.random() < 0.5 or not known else rng.choice(known)
            plan2.append((a, r, t, _question(case, t)))
        batch = [(build_liar_messages(case, r, q, speaker=_name(case, a)), None) if _liar(g, r)
                 else (build_messages(case, r, q, memory.of(r), speaker=_name(case, a)), lora) for a, r, t, q in plan2]
        replies = chat_many(batch)
        for (a, r, t, q), reply in zip(plan2, replies):
            stored = gossip.remember_reply(case, memory, a, r, reply, g["day"])
            events.append({"round": rnd, "asker": a, "responder": r, "question": q, "reply": reply,
                           "heard_ids": [h.id for h in stored], "hints": gossip.clash_hints(case, a, stored)})
    return {"events": events, "hints": [h for e in events for h in e["hints"]]}


def _reveal(case: Case) -> dict:
    motive = next((s.text for d in case.documents for s in d.sentences if case.solution.motive in s.facts), "")
    reasons = [facts_clash(case, case.fact(a), case.fact(b)) or f"{a} vs {b}" for a, b in case.solution.contradictions]
    return {"killer": case.killer, "killer_name": _name(case, case.killer), "motive": motive, "contradictions": reasons}


@app.post("/accuse")
def accuse(req: Accuse):
    g = _game(req.case_id)
    case = g["case"]
    confirmed = 0
    for pair in req.links:
        if len(pair) == 2 and all(p in CLAIMS for p in pair):
            ok, _ = confirm(case, _as_result(CLAIMS[pair[0]]), _as_result(CLAIMS[pair[1]]))
            confirmed += ok
    # A motive is any evidence line about a quarrel or a debt with the victim; it "holds" when it names the accused.
    mfacts = [case.fact(f) for f in CLAIMS.get(req.motive_claim, {}).get("facts", []) if req.motive_claim]
    has_motive = any(f.rel in ("owes", "argued") and case.victim in f.args[:2] for f in mfacts)
    motive_ok = any(f.rel in ("owes", "argued") and req.villager_id in f.args[:2] and case.victim in f.args[:2]
                    for f in mfacts)
    # Not enough evidence yet: no strike, and no hint whether the suspect is right (that would give it away).
    if confirmed < 2 or not has_motive:
        missing = []
        if confirmed < 2:
            missing.append(f"2 confirmed contradictions (you have {confirmed})")
        if not has_motive:
            missing.append("a motive from the evidence")
        return {"correct": False, "insufficient": True, "score": None, "confirmed_links": confirmed, "motive_ok": motive_ok,
                "strikes_left": g["strikes_left"], "reveal": None,
                "reason": "Not enough evidence to charge anyone yet: you need " + " and ".join(missing) + "."}
    correct = req.villager_id == case.killer
    if not correct:
        g["strikes_left"] -= 1
    limits = DIFFICULTY[g["difficulty"]]
    score = max(0, 1000 - 40 * g["questions_used"] - 300 * (limits["strikes"] - g["strikes_left"])
                - (0 if motive_ok else 200))  # the right killer with someone else's motive scores less
    g["over"] = correct or g["strikes_left"] <= 0
    return {"correct": correct, "score": score if correct else None, "confirmed_links": confirmed,
            "motive_ok": motive_ok, "strikes_left": g["strikes_left"], "reveal": _reveal(case) if g["over"] else None}


@app.post("/rumour")
def rumour(req: Rumour):
    g = _game(req.case_id)
    case = g["case"]
    mode = req.mode if req.mode in MODES or req.mode == "plain" else "grounded"
    if req.source == "killer":
        from archive.eval.manipulation import run_mode
        game_mode = {"sft": "grounded", "grounded": "grounded"}.get(mode, mode)
        lora = MODES.get(mode) if mode in ("sft", "grounded") else None
        res = asyncio.run(run_mode(case, game_mode, url=SGLANG_URL, model=MODEL, grounded_lora=lora or MODES["grounded"],
                                   seed=req.seed, rounds=req.rounds))
        return {**res, "mode": req.mode}
    if not req.villager_id or not req.text.strip():
        raise HTTPException(400, "villager_id and text are needed for a traveller rumour")
    try:
        res = rumour_mod.run(case, ask_many_for(MODES.get(mode)), req.text.strip(), req.villager_id, rounds=req.rounds,
                             seed=req.seed)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {**res, "mode": req.mode}


@app.get("/state/{case_id}")
def state(case_id: str):
    g = _game(case_id)
    return {"state": _state(g), "claims": [_public(c, True) for c in CLAIMS.values() if c["case_id"] == case_id]}
