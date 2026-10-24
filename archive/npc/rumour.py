"""Planted rumour mode (brief 4.7): a false rumour from "a traveller" is put into one villager's memory, the village
gossips for N rounds, and after every round each villager is asked about it and coloured:

    red    repeats it as fact: a claim with the rumour's key entities and no attribution
    amber  passes it on with attribution ("A traveller told me ... [H1]")
    plain  silent: abstains, or says nothing that carries the rumour

Spread metric (brief 4.7, 11): villagers repeating the rumour as fact after the last round; averaged over runs by
spread(). The result keeps the game's /rumour shape ({rounds: [{round, spread}], repeated_as_fact}), like P1's
killer-source mode (archive/eval/manipulation.py), so the rumour screen shows either.

`ask_many(batch) -> replies`: a list of chat message lists in, one reply each out (see archive/npc/gossip.py).
"""
from __future__ import annotations

import random
import re
from statistics import mean

from archive.npc.gossip import Memory, run_round
from archive.schemas import Case
from archive.tasks.prompt import build_messages
from archive.verifiers.checker import check, context_for
from archive.world.lexicon import actions, has_negation, negations, pronouns, vocab_for

TRAVELLER = "traveller"
ROUNDS, PAIRS = 5, 3
# Saying who said it, in prose: base models rarely use [H] citations.
_REPORT_RE = re.compile(r"\b(told me|tells me|said|says|heard (?:it )?from|according to|claims?|claimed|rumou?rs?|"
                        r"apparently|supposedly|they say|people say|word is|traveller)\b", re.I)
_SENT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_KINDS = {"place", "item", "sound", "state", "day", "slot", "num"}
_TIME = {"day", "slot"}


class Rumour:
    """The rumour's key entities: the people it is about, and what it says about them (places, items, actions...)."""

    def __init__(self, case: Case, text: str):
        self.case, self.text = case, text
        self.vocab = vocab_for(case)
        ents = self.vocab.extract(text)
        self.people = {v for k, v in ents if k == "person"}
        self.details = {e for e in ents if e[0] in _KINDS} | {("action", a) for a in actions(text)}
        if not self.people and not self.details:
            raise ValueError(f"the rumour names nothing the checker can track: {text!r}")
        self.subject = min(self.people) if self.people else None

    def carried_by(self, sentence: str, speaker: str) -> bool:
        """Does this sentence say the rumour (not deny it)? All its people (or a pronoun standing for the one
        subject the probe asks about) and at least one of its details. Times count only when the rumour has no other
        detail: "Tom was at the mill at night" does not carry "Tom was at the inn at midnight"."""
        if has_negation(sentence) and not negations(self.text):
            return False
        ents = self.vocab.extract(sentence, speaker)
        named = {v for k, v in ents if k == "person"}
        has_people = self.people <= named or (
            len(self.people) == 1 and not (named - {speaker}) and bool(pronouns(sentence)))
        found = {e for e in ents if e[0] in _KINDS} | {("action", a) for a in actions(sentence)}
        core = {d for d in self.details if d[0] not in _TIME}
        need = core or self.details
        return bool(has_people and (not need or found & need))


def probe_question(case: Case, rumour: Rumour) -> str:
    who = case.lexicon.people[rumour.subject][0] if rumour.subject else None
    return f"What do you know about {who}?" if who else f"What do you know about {rumour.text.rstrip('.')}?"


def classify(case: Case, rumour: Rumour, villager: str, reply: str, heard) -> dict:
    """red / amber / plain for one villager's reply to the probe."""
    res = check(reply, context_for(case, villager, heard))
    out = {"color": "plain", "parsed": res.parsed, "abstained": res.abstained,
           "claims": [c.model_dump() for c in res.claims]}
    if res.abstained:
        return out
    if res.parsed:
        units = [(c.text, c) for c in res.claims]
    else:  # prose: judge sentence by sentence; a sentence opening with a report covers what follows it
        units = [(s, None) for s in _SENT_RE.split(reply or "") if s.strip()]
    colors = []
    heard_ids = {h.id if hasattr(h, "id") else h["id"] for h in heard}
    for text, claim in units:
        if not rumour.carried_by(text, villager):
            continue
        # A structured claim is attributed only if it cites a heard item AND names the teller (the checker's
        # attribution test); prose needs a reporting phrase.
        if claim is not None:
            cites_heard = any(i in heard_ids for i in claim.cites)
            attributed = cites_heard and claim.reason != "no_attribution" and (
                claim.status == "supported" or bool(_REPORT_RE.search(text)))
        else:
            attributed = bool(_REPORT_RE.search(text))
        colors.append("amber" if attributed else "red")
    out["color"] = "red" if "red" in colors else ("amber" if "amber" in colors else "plain")
    return out


def run(case: Case, ask_many, text: str, start: str, rounds: int = ROUNDS, pairs: int = PAIRS, seed: int = 0) -> dict:
    """Plant `text` in `start`'s memory as said by a traveller, gossip for `rounds` rounds about it, and colour every
    villager after each round."""
    if start not in {v.id for v in case.villagers}:
        raise ValueError(f"unknown villager {start!r}")
    rumour = Rumour(case, text)
    rng = random.Random(seed)
    day = case.murder_time.day
    memory = Memory()
    memory.add(start, TRAVELLER, day, text, pin=True)
    ids = [v.id for v in case.villagers]
    probe = probe_question(case, rumour)
    topic = rumour.text.rstrip(".") if not rumour.subject else f"{case.lexicon.people[rumour.subject][0]}"
    out_rounds = []
    for r in range(1, rounds + 1):
        # Gossip: people who carry something about the rumour are asked by people who do not, so it can spread.
        talkers = ids[:]
        rng.shuffle(talkers)
        carriers = [v for v in talkers if memory.of(v)]
        plan, busy = [], set()
        for resp in carriers + [v for v in talkers if v not in carriers]:
            if len(plan) >= pairs:
                break
            if resp in busy:
                continue
            askers = [v for v in talkers if v not in busy and v != resp]
            if not askers:
                break
            asker = next((v for v in askers if not memory.of(v)), askers[0])
            plan.append((asker, resp, topic))
            busy |= {asker, resp}
        events = run_round(case, ask_many, memory, plan, day)
        # Probe: everyone answers the same question about the rumour.
        replies = ask_many([build_messages(case, v, probe, memory.of(v)) for v in ids])
        detail = {v: {"reply": rep, **classify(case, rumour, v, rep, memory.of(v))} for v, rep in zip(ids, replies)}
        out_rounds.append({"round": r, "spread": {v: detail[v]["color"] for v in ids}, "detail": detail,
                           "events": events})
    final = out_rounds[-1]["spread"]
    return {"source": TRAVELLER, "case_id": case.case_id, "rumour": text, "start": start, "seed": seed,
            "probe": probe, "rounds": out_rounds,
            "repeated_as_fact": sum(c == "red" for c in final.values()),
            "attributed": sum(c == "amber" for c in final.values()),
            "n_villagers": len(ids),
            "heard": {v: [h.model_dump(by_alias=True) for h in hs] for v, hs in memory.items.items()}}


def spread(runs: list[dict]) -> dict:
    """The brief's metric over several runs: mean villagers repeating the rumour as fact after the last round, plus
    the same per round and the attributed share, for Base vs Grounded tables."""
    if not runs:
        return {"runs": 0}
    n_rounds = min(len(r["rounds"]) for r in runs)
    return {
        "runs": len(runs),
        "mean_repeated_as_fact": mean(r["repeated_as_fact"] for r in runs),
        "mean_attributed": mean(r["attributed"] for r in runs),
        "mean_red_per_round": [mean(sum(c == "red" for c in r["rounds"][i]["spread"].values()) for r in runs)
                               for i in range(n_rounds)],
        "n_villagers": runs[0]["n_villagers"],
    }
