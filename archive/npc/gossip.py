"""Villager-to-villager gossip (brief 4.4): the evening scheduler, what the asker remembers, and clash hints.

One model plays everyone, so a conversation is two calls: the asker writes a question (asker prompt, brief 7.3), the
responder answers with the normal villager prompt. The checker colours the reply and the asker stores what was said
as HeardItems, one per claim: a supported claim keeps its facts, a red claim is stored with no facts (brief 4.4), an
unparsed reply is stored as said with no facts, an abstain stores nothing.

`ask_many(batch) -> replies` takes a list of chat message lists and returns one reply each, so callers can run a
whole round in parallel (P1: SGLang chat_many; tests: a fake).
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from archive.schemas import Case, HeardItem
from archive.tasks.prompt import build_asker_messages, build_messages
from archive.verifiers.checker import check, context_for
from archive.verifiers.contradiction import facts_clash

ROUNDS, PAIRS = 3, 3          # per evening (brief 4.4)
MAX_HEARD = 4                 # heard items a villager keeps (oldest unpinned forgotten): keeps prompts under budget
_THINK_RE = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_CITE_RE = re.compile(r"\s*\[[^\]]*\]")


@dataclass(frozen=True)
class Topic:
    kind: str     # victim | night | place | person
    value: str    # person id, place, or "" for the night
    text: str     # what the asker is asked to learn about


@dataclass
class Memory:
    """Every villager's HeardItems, with fresh ids and a size cap. Pinned items (a planted rumour) are never dropped."""
    items: dict[str, list[HeardItem]] = field(default_factory=dict)
    pinned: set[str] = field(default_factory=set)
    _n: int = 0

    def of(self, vid: str) -> list[HeardItem]:
        return self.items.setdefault(vid, [])

    def add(self, vid: str, frm: str, day: int, text: str, facts=(), pin: bool = False) -> HeardItem | None:
        text = clean(text)
        if not text:
            return None
        self._n += 1
        h = HeardItem.model_validate({"id": f"H{self._n}", "from": frm, "day": day, "text": text, "facts": list(facts)})
        mine = self.of(vid)
        mine.append(h)
        if pin:
            self.pinned.add(h.id)
        while len(mine) > MAX_HEARD:
            drop = next((x for x in mine if x.id not in self.pinned), None)
            if drop is None:
                break
            mine.remove(drop)
        return h


def clean(text: str, limit: int = 300) -> str:
    """A reply as plain words: no thinking, no tags, no CLAIM:/# prefixes, no citations."""
    t = _TAG_RE.sub(" ", _THINK_RE.sub(" ", text or ""))
    t = re.sub(r"(?m)^\s*(CLAIM:|#)\s*", "", t)
    t = _CITE_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip()[:limit]


def _name(case: Case, pid: str) -> str:
    names = case.lexicon.people.get(pid)
    return names[0] if names else pid


def topics(case: Case) -> list[Topic]:
    """What villagers may ask about (brief 4.4): the victim, the murder night, a place, a person."""
    mt = case.murder_time
    out = [Topic("victim", case.victim, _name(case, case.victim)),
           Topic("night", "", f"the night of day {mt.day}")]
    out += [Topic("place", p, f"the {p}") for p in case.lexicon.places]
    out += [Topic("person", v.id, v.name) for v in case.villagers]
    return out


def knows(case: Case, vid: str, topic: Topic, heard=()) -> bool:
    """Does the villager have any line (or heard item) about the topic?"""
    ctx = context_for(case, vid, heard)
    facts = [case.fact(f) for fs in ctx.facts.values() for f in fs]
    if topic.kind == "night":
        return any(f.t and (f.t.day, f.t.slot) == (case.murder_time.day, case.murder_time.slot) for f in facts)
    return any(topic.value in f.args for f in facts) or any(topic.text in t for t in ctx.texts.values())


def schedule(case: Case, rng: random.Random, memory: Memory | None = None, rounds: int = ROUNDS,
             pairs: int = PAIRS) -> list[list[tuple[str, str, Topic]]]:
    """For each round, up to `pairs` (asker, responder, topic): nobody talks twice in a round, nobody talks to
    themselves, and the topic is one the asker knows nothing about when there is one (brief 4.4)."""
    ids = [v.id for v in case.villagers]
    all_topics = topics(case)
    plan = []
    for _ in range(rounds):
        free = ids[:]
        rng.shuffle(free)
        rnd = []
        while len(free) >= 2 and len(rnd) < pairs:
            asker, responder = free.pop(), free.pop()
            heard = memory.of(asker) if memory else ()
            options = [t for t in all_topics if t.value not in (asker, responder) or t.kind == "night"]
            unknown = [t for t in options if not knows(case, asker, t, heard)]
            rnd.append((asker, responder, rng.choice(unknown or options)))
        plan.append(rnd)
    return plan


def question_from(text: str, fallback: str) -> str:
    """The asker's output as one question; the fallback when the model wrote nothing usable."""
    t = clean(text, 200)
    if "?" in t:
        t = t[: t.index("?") + 1]
    t = t.strip(" \"'")
    return t if len(t) >= 8 and t.endswith("?") else fallback


def remember_reply(case: Case, memory: Memory, asker: str, responder: str, reply: str, day: int) -> list[HeardItem]:
    """What the asker keeps from the responder's reply (one item per claim; see the module docstring)."""
    res = check(reply, context_for(case, responder, memory.of(responder)))
    if res.abstained:
        return []
    if not res.parsed:
        h = memory.add(asker, responder, day, reply)
        return [h] if h else []
    out = []
    for c in res.claims:
        facts = c.facts if c.status == "supported" else []
        h = memory.add(asker, responder, day, c.text, facts)
        if h:
            out.append(h)
    return out


def clash_hints(case: Case, listener: str, items: list[HeardItem]) -> list[dict]:
    """A heard item whose facts clash with the listener's own lines: the game may show "X looked puzzled"."""
    ctx = context_for(case, listener)
    own = [case.fact(f) for fs in ctx.facts.values() for f in fs]
    hints = []
    for h in items:
        for fid in h.facts:
            heard_fact = case.fact(fid)
            if any(facts_clash(case, heard_fact, f) for f in own):
                hints.append({"listener": listener, "speaker": h.from_, "heard_id": h.id,
                              "text": f"{_name(case, listener)} looked puzzled by something "
                                      f"{_name(case, h.from_)} said."})
                break
    return hints


def run_round(case: Case, ask_many, memory: Memory, pairs: list[tuple[str, str, Topic | str]], day: int) -> list[dict]:
    """One round of conversations: all questions in one batch, then all answers in one batch."""
    if not pairs:
        return []
    topic_text = [t.text if isinstance(t, Topic) else t for _, _, t in pairs]
    asks = [build_asker_messages(case, a, r, tt, memory.of(a)) for (a, r, _), tt in zip(pairs, topic_text)]
    raw_q = ask_many(asks)
    questions = [question_from(q, f"What do you know about {tt}?") for q, tt in zip(raw_q, topic_text)]
    answers = ask_many([build_messages(case, r, q, memory.of(r), speaker=_name(case, a))
                        for (a, r, _), q in zip(pairs, questions)])
    events = []
    for (a, r, _), tt, q, reply in zip(pairs, topic_text, questions, answers):
        stored = remember_reply(case, memory, a, r, reply, day)
        events.append({"type": "gossip", "asker": a, "responder": r, "topic": tt, "question": q, "reply": reply,
                       "heard_ids": [h.id for h in stored], "hints": clash_hints(case, a, stored)})
    return events


def run_evening(case: Case, ask_many, memory: Memory | None = None, seed: int = 0, day: int | None = None,
                rounds: int = ROUNDS, pairs: int = PAIRS) -> dict:
    """A whole evening for the game (P3): schedule, talk, remember. Returns the events and everyone's memory."""
    memory = memory or Memory()
    rng = random.Random(seed)
    day = day or case.murder_time.day
    events = []
    for rnd, plan in enumerate(schedule(case, rng, memory, rounds, pairs), start=1):
        for e in run_round(case, ask_many, memory, plan, day):
            events.append({**e, "round": rnd})
    return {"events": events, "heard": {v: [h.model_dump(by_alias=True) for h in hs] for v, hs in memory.items.items()},
            "hints": [h for e in events for h in e["hints"]]}
