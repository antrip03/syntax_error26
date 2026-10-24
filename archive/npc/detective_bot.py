"""Rule-based detective (brief section 11): measures whether a village's answers are enough to solve the case.

1. Ask every villager "Where were you at {slot} on day {d}?" for the murder slot and the slots either side of it.
2. Ask every villager "Who did you see near the {scene}?" and "What did you see or hear on the night of the murder?"
   (the second is added so that a witness whose clue is an empty place, not a sighting, is heard too).
3. Keep only supported (green) claims; their facts give a person-by-slot location table.
4. Link every pair of green claims from different villagers with the game's own contradiction check
   (contradiction.confirm). Accuse the villager contradicted by the most different witnesses; break ties by a motive
   in the evidence documents, then by the number of confirmed contradictions. When nobody is contradicted, a villager
   whose claims are red counts as evidence (brief 4.6, liar mode).
5. Solved = the accused is the killer with at least 2 confirmed contradictions (brief 11). Caught = the accused is
   the killer, however.

`ask_many(batch) -> replies` gets every question in one batch (a list of chat message lists). `prompt_for(case,
villager, question)` builds each prompt; the default is the villager prompt, and a caller swaps in the liar prompt
for a Hard killer.
"""
from __future__ import annotations

import itertools
import random

from archive.schemas import SLOTS, Case, ClaimResult
from archive.tasks.prompt import build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.contradiction import confirm, facts_clash, locations
from archive.world.solver import MOTIVE_RELATIONS, suspects

_Q_TIME = {"dawn": "at dawn", "morning": "in the morning", "noon": "at noon", "afternoon": "in the afternoon",
           "dusk": "at dusk", "night": "at night"}
NIGHT_Q = "What did you see or hear on the night of the murder?"


class BotResult(dict):
    """The bot's verdict: a plain dict (play() -> dict, JSON-ready) whose keys also read as attributes.

    case_id, killer, accused (None when the bot will not guess),
    solved            accused == killer with 2+ confirmed contradictions
    caught            accused == killer
    confirmed         [{a, b, by: [speakers], suspect, facts, reason}]
    witnesses         suspect -> villagers whose green claims contradict them
    table             person -> "day 2 night" -> places
    red               villager -> red claims in their replies
    killer_red_share  share of the killer's claims that are red (liar caught, brief 11)
    questions, transcript
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None


def plan(case: Case) -> list[tuple[str, str]]:
    """(villager, question) for every question the bot asks."""
    mt = case.murder_time
    days = sorted({f.t.day for f in case.facts if f.t})
    times = [(d, s) for d in days for s in SLOTS]
    i = times.index((mt.day, mt.slot))
    around = times[max(0, i - 1): i + 2]
    qs = [f"Where were you {_Q_TIME[s]} on day {d}?" for d, s in around]
    qs += [f"Who did you see near the {case.scene}?", NIGHT_Q]
    return [(v.id, q) for v in case.villagers for q in qs]


def _wrap(reply: str) -> str:
    """Brief 7.4: a reply that is not in the format (the liar, a base model) is wrapped sentence by sentence as
    claims with no sources, so the checker can mark it."""
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", reply or "") if p.strip()]
    parts = [re.sub(r"^(CLAIM:|#)\s*", "", p) for p in parts]
    parts = [p for p in parts if p]
    return "<answer>\n" + "\n".join(f"CLAIM: {p}" for p in parts) + "\n</answer>" if parts else ""


def judge(case: Case, replies: dict[tuple[str, str], str]) -> BotResult:
    """Everything the bot concludes from the villagers' replies."""
    green: list[tuple[str, ClaimResult]] = []
    red: dict[str, int] = {v.id: 0 for v in case.villagers}
    killer_claims = killer_red = 0
    transcript = []
    for (vid, q), reply in replies.items():
        ctx = context_for(case, vid)
        res = check(reply, ctx)
        if not res.parsed and not res.abstained and (reply or "").strip():
            res = check(_wrap(reply), ctx)  # free prose: every sentence is an unsourced, red claim
        for c in res.claims:
            if c.status == "supported":
                green.append((vid, c))
            else:
                red[vid] += 1
        if vid == case.killer:
            killer_claims += len(res.claims)
            killer_red += sum(c.status != "supported" for c in res.claims)
        transcript.append({"villager": vid, "question": q, "reply": reply,
                           "claims": [(c.text, c.status, c.reason) for c in res.claims]})

    # Location table from green facts.
    table: dict[str, dict[str, list[str]]] = {}
    for _, c in green:
        for fid in c.facts:
            for loc in locations(case.fact(fid)):
                key = f"day {loc.day} {loc.slot}"
                places = table.setdefault(loc.person or "(nobody)", {}).setdefault(key, [])
                if loc.place not in places:
                    places.append(loc.place)

    # Confirmed contradictions between green claims of different villagers, with the game's own check.
    confirmed, seen_pairs = [], set()
    witnesses: dict[str, set[str]] = {}
    for (va, a), (vb, b) in itertools.combinations(green, 2):
        if va == vb:
            continue
        ok, reason = confirm(case, a, b)
        if not ok:
            continue
        for fa in a.facts:
            for fb in b.facts:
                f1, f2 = case.fact(fa), case.fact(fb)
                if fa == fb or not facts_clash(case, f1, f2):
                    continue
                pair = frozenset((fa, fb))
                for p in suspects(f1, f2):
                    witnesses.setdefault(p, set()).update({va, vb} - {p})
                    if (pair, p) not in seen_pairs:
                        seen_pairs.add((pair, p))
                        confirmed.append({"a": a.text, "b": b.text, "by": sorted({va, vb}), "suspect": p,
                                          "facts": sorted(pair), "reason": reason})

    villagers = {v.id for v in case.villagers}
    motive = _motives(case)
    count = {p: sum(1 for c in confirmed if c["suspect"] == p) for p in villagers}
    ranked = sorted((p for p in villagers if witnesses.get(p)),
                    key=lambda p: (-len(witnesses[p]), p not in motive, -count[p], p))
    if ranked:
        accused = ranked[0]
        top = ranked[1] if len(ranked) > 1 else None
        if top and (len(witnesses[top]), top in motive, count[top]) == (len(witnesses[accused]), accused in motive,
                                                                        count[accused]):
            accused = None  # a true tie: the bot does not guess
    else:  # nobody contradicted: the villager with the most red claims (liar evidence), if there is one
        worst = max(red.values(), default=0)
        liars = [v for v, n in red.items() if n == worst]
        accused = liars[0] if worst > 0 and len(liars) == 1 else None
    n_against = count.get(accused, 0) if accused else 0
    return BotResult(
        case_id=case.case_id, killer=case.killer, accused=accused,
        solved=accused == case.killer and n_against >= 2, caught=accused == case.killer,
        confirmed=confirmed, witnesses={p: sorted(w) for p, w in witnesses.items()}, table=table, red=red,
        killer_red_share=(killer_red / killer_claims) if killer_claims else None,
        questions=len(replies), transcript=transcript)


def _motives(case: Case) -> set[str]:
    """Villagers linked to the victim by a debt or an argument in the public evidence documents."""
    out = set()
    for did in case.evidence_docs:
        for s in case.doc(did).sentences:
            for fid in s.facts:
                f = case.fact(fid)
                if f.rel in MOTIVE_RELATIONS and case.victim in f.args[:2]:
                    out |= set(f.args[:2]) - {case.victim}
    return out


def play(case: Case, ask_many, prompt_for=build_messages) -> BotResult:
    """Ask every question in one batch and judge the answers."""
    questions = plan(case)
    replies = ask_many([prompt_for(case, v, q) for v, q in questions])
    if len(replies) != len(questions):
        raise ValueError(f"ask_many returned {len(replies)} replies for {len(questions)} questions")
    return judge(case, dict(zip(questions, replies)))


def solve_rate(results: list[BotResult], n_boot: int = 1000, seed: int = 0) -> dict:
    """Solve and catch rates over cases (one result per case), with bootstrap 95% CIs."""
    n = len(results)
    if not n:
        return {"cases": 0}
    rng = random.Random(seed)
    out = {"cases": n}
    for name in ("solved", "caught"):
        hits = [int(getattr(r, name)) for r in results]
        boot = sorted(sum(rng.choices(hits, k=n)) / n for _ in range(n_boot))
        out[f"{name}_rate"] = sum(hits) / n
        out[f"{name}_ci95"] = [boot[int(0.025 * (n_boot - 1))], boot[int(0.975 * (n_boot - 1))]]
    shares = [r.killer_red_share for r in results if r.killer_red_share is not None]
    out["killer_red_share"] = sum(shares) / len(shares) if shares else None
    return out


def gold_ask(case: Case):
    """A perfect village for tests and upper bounds: every villager answers the bot's questions exactly from its own
    lines with gold-style claims, and abstains when nothing matches."""
    from archive.tasks.gold import gold_reply, own_claim
    from archive.schemas import Gold, Task
    from archive.world.casegen import NEIGHBOURS

    def answer(vid: str, q: str) -> str:
        ctx = context_for(case, vid)
        picks = []
        for sid, fids in ctx.facts.items():
            for fid in fids:
                f = case.fact(fid)
                if q == NIGHT_Q:
                    hit = f.t and (f.t.day, f.t.slot) == (case.murder_time.day, case.murder_time.slot) and \
                        not (f.rel == "at" and f.args[0] == vid)
                elif q.startswith("Who did you see near"):
                    near = {case.scene} | NEIGHBOURS.get(case.scene, set())
                    hit = f.rel == "saw" and f.args[0] == vid and f.args[2] in near
                else:
                    hit = f.rel == "at" and f.args[0] == vid and f.t and q == \
                        f"Where were you {_Q_TIME[f.t.slot]} on day {f.t.day}?"
                if hit:
                    picks.append(own_claim(case, vid, sid, f, ctx.texts[sid]))
        task = Task(task_id="bot", case_id=case.case_id, villager=vid, type="answerable_1hop", split="test_game",
                    question=q, gold=Gold(abstain=not picks, claims=picks))
        return gold_reply(task)

    def ask_many(batch):
        out = []
        for msgs in batch:
            system, user = msgs[0]["content"], msgs[1]["content"]
            vid = next(v.id for v in case.villagers if system.startswith(f"You are {v.name},"))
            out.append(answer(vid, user.split(": ", 1)[1]))
        return out
    return ask_many
