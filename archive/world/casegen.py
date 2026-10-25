"""Case generator (brief 5.2), seeded: the same (seed, difficulty) always gives the same case.

First the TRUE world, then who knows what:
1. cast: villagers + victim, distinct names and roles, a persona each
2. routine: every person gets one true place per day and slot
3. murder: killer and victim at the scene at the murder time (day 2, night)
4. forged alibi: at(killer, alibi place), false, in the killer's own document
5. witnesses: each holds ONE fact contradicting the alibi: a sighting of the killer, or the alibi place empty
6. motive: a debt or an argument between killer and victim, in the victim's diary (evidence document)
7. red herrings: an argument or debt with the victim in their own document, and a true alibi in another villager's
   document (their "clearer"); Hard also gives 2 villagers a secret (a withheld, unrelated debt)
8. withhold the killer's true whereabouts
9. render (render.py), 4 to 8 visible lines per villager
10. the solver (brief 5.4) re-checks the case; on failure generate_case retries with the next attempt.

Agreed with the team: two modes (easy, hard); every job is a different person; contradictions come only from
sightings and empty places; Hard's "heard a noise" line is an extra clue, not a contradiction.

Because each person has exactly one true place per slot, two true facts never clash: the only false fact is the
alibi, so every contradiction points at the killer (solver rule e). One exception is deliberate: an Easy "near"
sighting puts the killer by a neighbouring place while his withheld true fact puts him at the scene; the slot is
several hours, and the withheld fact is never visible, so no visible facts clash.
"""
from __future__ import annotations

import logging
import os
import random

from archive.schemas import SLOTS, Case, Fact, TimePoint, Villager
from archive.tasks.personas import sample_personas
from archive.world.lexicon import THEMES
from archive.world.render import Line, render_document
from archive.world.solver import solve

PRESETS = {
    "easy": {"villagers": 6, "witnesses": ["saw", "empty", "saw"], "sighting": ["plain", "near"],
             "noise_clue": False, "red_herrings": 1, "secrets": 0, "days": 3, "killer_model": "grounded",
             "gossip_noise": "none"},
    "hard": {"villagers": 8, "witnesses": ["saw", "empty"], "sighting": ["role"],
             "noise_clue": True, "red_herrings": 2, "secrets": 2, "days": 2, "killer_model": "base",
             "gossip_noise": "alibi"},
}
MURDER_TIME = TimePoint(day=2, slot="night")
DIARY_SUSPECTS = os.environ.get("ARCHIVE_DIARY_SUSPECTS") == "1"
LINES_PER_VILLAGER = (4, 8)

NEIGHBOURS: dict[str, set[str]] = {}
for _a, _b in [("guildhall", "chapel"), ("guildhall", "market"), ("market", "bakery"), ("market", "smithy"),
               ("market", "inn"), ("inn", "river path"), ("river path", "mill"), ("mill", "bakery"),
               ("chapel", "inn")]:
    NEIGHBOURS.setdefault(_a, set()).add(_b)
    NEIGHBOURS.setdefault(_b, set()).add(_a)

WORKPLACE = {"miller": "mill", "baker": "bakery", "priest": "chapel", "innkeeper": "inn", "brewer": "inn",
             "blacksmith": "smithy", "fisher": "river path", "shepherd": "river path", "scribe": "guildhall",
             "guard": "guildhall", "chandler": "market", "tailor": "market", "cooper": "market",
             "weaver": "market", "tanner": "market", "carpenter": "market", "herbalist": "market",
             "midwife": "inn"}
GENRE = {"guard": "patrol_log", "priest": "prayer_book", "blacksmith": "ledger", "chandler": "ledger",
         "cooper": "ledger", "tanner": "ledger", "innkeeper": "ledger", "brewer": "ledger", "tailor": "ledger",
         "weaver": "ledger", "herbalist": "notebook", "scribe": "notebook", "midwife": "notebook",
         "miller": "diary", "baker": "letter", "fisher": "diary", "carpenter": "diary", "shepherd": "diary"}
NOISES = ["scream", "shout", "crash"]

class _World:
    """Facts and routine while a case is being built."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.facts: list[Fact] = []
        self.routine: dict[str, dict[tuple[int, str], str]] = {}

    def fact(self, rel: str, args: list[str], t: TimePoint | None = None, truth: bool = True) -> Fact:
        f = Fact(id=f"F{len(self.facts) + 1}", rel=rel, args=args, t=t, truth=truth)
        self.facts.append(f)
        return f

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 20

def generate_case(seed: int, difficulty: str = "easy", theme: str = "village") -> Case:
    """Build a case and run the solver; on failure try again (same seed, next attempt), up to MAX_ATTEMPTS."""
    if difficulty not in PRESETS:
        raise ValueError(f"difficulty must be one of {sorted(PRESETS)}")
    failures = []
    for attempt in range(MAX_ATTEMPTS):
        case = _build_case(seed, difficulty, theme, attempt)
        result = solve(case)
        if result.passed:
            return case
        failures.append(result.failures)
        log.warning("case %s attempt %d failed the solver: %s", case.case_id, attempt, result.failures)
    raise RuntimeError(f"no solvable case for seed {seed} ({difficulty}) in {MAX_ATTEMPTS} attempts: {failures[-1]}")

def _build_case(seed: int, difficulty: str, theme: str, attempt: int) -> Case:
    preset = PRESETS[difficulty]
    rng = random.Random(f"{theme}:{difficulty}:{seed}" + (f":{attempt}" if attempt else ""))
    pool = THEMES[theme]
    places = list(pool["places"])
    w = _World(rng)

    n = preset["villagers"]
    names = rng.sample(pool["names"], n + 1)
    roles = rng.sample(pool["roles"], n + 1)
    ids = [x.lower() for x in names]
    name_of, role_of = dict(zip(ids, names)), dict(zip(ids, roles))
    victim, cast = ids[0], ids[1:]
    queue = list(cast)
    killer = queue.pop(0)
    witnesses = [queue.pop(0) for _ in preset["witnesses"]]
    noise = queue.pop(0) if preset["noise_clue"] else None
    herrings = [queue.pop(0) for _ in range(preset["red_herrings"])]
    clearers = [queue.pop(0) for _ in range(preset["red_herrings"])]
    others = queue
    days = range(1, preset["days"] + 1)
    mt = MURDER_TIME
    murder_key = (mt.day, mt.slot)

    scene = rng.choice(places)
    alibi = rng.choice([p for p in places if p != scene and p not in NEIGHBOURS[scene]])
    style = rng.choice(preset["sighting"])
    sight_place = scene if style == "plain" else rng.choice(sorted(NEIGHBOURS[scene]))

    workplace = {pid: WORKPLACE.get(role_of[pid], rng.choice(places)) for pid in ids}
    for pid in ids:
        w.routine[pid] = {(d, s): (workplace[pid] if rng.random() < 0.6 else rng.choice(places))
                          for d in days for s in SLOTS}
    free = [p for p in places if p not in (scene, alibi)]
    for pid in ids:
        if w.routine[pid][murder_key] in (scene, alibi):
            w.routine[pid][murder_key] = rng.choice(free)
    w.routine[killer][murder_key] = w.routine[victim][murder_key] = scene

    lines: dict[str, list[Line]] = {pid: [] for pid in cast}
    withheld: dict[str, list[Line]] = {}
    busy: dict[str, set[tuple[int, str]]] = {pid: set() for pid in cast}

    def add(owner: str, f: Fact, **kw):
        lines[owner].append(Line(f, **kw))
        if f.t:
            busy[owner].add((f.t.day, f.t.slot))

    alibi_fact = w.fact("at", [killer, alibi], mt, truth=False)
    add(killer, alibi_fact, style="work" if alibi == workplace[killer] else "plain")
    withheld[killer] = [Line(w.fact("at", [killer, scene], mt))]

    contradictions = []
    for wid, kind in zip(witnesses, preset["witnesses"]):
        if kind == "saw":
            w.routine[wid][murder_key] = sight_place if sight_place != scene else rng.choice(
                sorted(NEIGHBOURS[scene] - {alibi}))
            f = w.fact("saw", [wid, killer, sight_place], mt)
            add(wid, f, style=style, scene=scene)
        else:
            w.routine[wid][murder_key] = rng.choice(sorted(NEIGHBOURS[alibi] - {scene}))
            f = w.fact("empty", [alibi], mt)
            add(wid, f)
        contradictions.append((alibi_fact.id, f.id))
    if noise:
        w.routine[noise][murder_key] = rng.choice(sorted(NEIGHBOURS[scene] - {alibi}))
        add(noise, w.fact("heard", [noise, rng.choice(NOISES), scene], mt))

    if rng.random() < 0.5:
        motive = w.fact("owes", [killer, victim, f"{rng.randint(2, 9) * 10} silver"])
    else:
        motive = w.fact("argued", [killer, victim], _meet(w, killer, victim, days, mt))
    evidence = [Line(motive)]

    for rh, cl in zip(herrings, clearers):
        if rng.random() < 0.5:
            rh_motive = w.fact("argued", [rh, victim], _meet(w, rh, victim, days, mt))
        else:
            rh_motive = w.fact("owes", [rh, victim, f"{rng.randint(1, 9) * 5} silver"])
        add(rh, rh_motive)
        if DIARY_SUSPECTS:
            evidence.append(Line(rh_motive))
        q = w.routine[cl][murder_key]
        w.routine[rh][murder_key] = q
        add(cl, w.fact("at", [rh, q], mt))
    for holder in herrings[: preset["secrets"]]:
        creditor = rng.choice([p for p in cast if p not in (killer, holder)])
        withheld[holder] = [Line(w.fact("owes", [holder, creditor, f"{rng.randint(1, 9) * 5} silver"]))]

    for pid in cast:
        target = rng.randint(*LINES_PER_VILLAGER)
        times = [(d, s) for d in days for s in SLOTS if (d, s) != murder_key and (d, s) not in busy[pid]]
        rng.shuffle(times)
        for d, s in times[: max(0, target - len(lines[pid]))]:
            t = TimePoint(day=d, slot=s)
            here = w.routine[pid][(d, s)]
            alive = [o for o in ids if not (o == victim and _after(t, mt))]
            company = [o for o in alive if o != pid and w.routine[o][(d, s)] == here]
            if company and rng.random() < 0.3:
                add(pid, w.fact("saw", [pid, rng.choice(company), here], t))
            else:
                add(pid, w.fact("at", [pid, here], t), style="work" if here == workplace[pid] else "plain")

    docs, villagers = [], []
    personas = sample_personas(rng, n)
    for k, pid in enumerate(cast):
        genre = GENRE.get(role_of[pid], "diary")
        my_docs = [f"D{len(docs) + 1}"]
        docs.append(render_document(rng, my_docs[0], pid, name_of[pid], genre, lines[pid], name_of, role_of))
        villagers.append((pid, k, my_docs))
    for pid, held in withheld.items():
        did = f"D{len(docs) + 1}"
        docs.append(render_document(rng, did, pid, name_of[pid], "notebook", held, name_of, role_of, withheld=True))
        next(v for v in villagers if v[0] == pid)[2].append(did)
    if DIARY_SUSPECTS:
        random.Random(f"evidence:{seed}:{attempt}").shuffle(evidence)
    docs.append(render_document(rng, "E1", victim, name_of[victim], "diary", evidence, name_of, role_of))

    slot_words = "the night" if mt.slot == "night" else mt.slot
    case = Case(
        case_id=f"c_{difficulty}_{seed:05d}", seed=seed, theme=theme, difficulty=difficulty,
        victim=victim, killer=killer, scene=scene, murder_time=mt,
        briefing=f"{name_of[victim]} the {role_of[victim]} was found dead in the {scene} "
                 f"on {slot_words} of day {mt.day}.",
        villagers=[Villager(id=pid, name=name_of[pid], role=role_of[pid], persona=personas[k], docs=my_docs,
                            secret_topic="debt" if pid in withheld and pid != killer else None,
                            model=preset["killer_model"] if pid == killer else "grounded")
                   for pid, k, my_docs in villagers],
        documents=docs, evidence_docs=["E1"], facts=w.facts,
        lexicon={"people": {pid: [name_of[pid]] for pid in ids}, "places": places,
                 "items": list(pool["items"]), "sounds": list(pool["sounds"])},
        solution={"killer": killer, "contradictions": contradictions, "motive": motive.id},
    )
    assert not others, "presets leave no unassigned villagers"
    return case

def _after(t: TimePoint, mt: TimePoint) -> bool:
    return (t.day, SLOTS.index(t.slot)) > (mt.day, SLOTS.index(mt.slot))

def _meet(w: _World, a: str, b: str, days, mt: TimePoint) -> TimePoint:
    """A time before the murder when a and b are together (for an argument); their routines are set to match."""
    times = [(d, s) for d in days for s in SLOTS if (d, SLOTS.index(s)) < (mt.day, SLOTS.index(mt.slot))]
    d, s = w.rng.choice(times)
    w.routine[b][(d, s)] = w.routine[a][(d, s)]
    return TimePoint(day=d, slot=s)
