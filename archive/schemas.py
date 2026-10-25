"""Data shapes shared by every part of The Archive (brief section 6). Pydantic v2; JSONL on disk.

P1 (training/eval) and P3 (game) code against these names, so keep them stable.

Deviations from the brief's section 6 sketch, agreed with the team:
- `Sentence.facts` is a list: one line can carry several facts (a sighting plus a carried lantern;
  "evening to midnight" covering two slots). A line with no fact (pure flavour) has an empty list.
- New relation `empty(place)`: "the mill was dark, no one inside". It contradicts anyone being `at` that place
  at the same day and slot.
- `Document.forged` means the document contains at least one false fact (the killer's alibi); its other
  sentences may be true. Truth lives on each `Fact`.
- `Case` also carries `town`, `scene`, `murder_time` and `briefing` for the game, and `Task` keeps extra
  keys (`messages`, `gold_reply`, curation samples) that P1's pipeline adds to task rows.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SLOTS = ("dawn", "morning", "noon", "afternoon", "dusk", "night")
Slot = Literal["dawn", "morning", "noon", "afternoon", "dusk", "night"]
Difficulty = Literal["easy", "hard"]
Genre = Literal["diary", "ledger", "letter", "patrol_log", "notebook", "prayer_book", "receipt"]
Split = Literal["train", "val", "test_id", "test_world", "test_adv", "test_game", "test_free"]
TaskType = Literal["answerable_1hop", "answerable_multihop", "unanswerable", "false_premise", "other_npc",
                   "injection", "hearsay", "hearsay_plus_own", "unreliable_doc",
                   "pressure", "format_attack", "hearsay_conflict"]
ClaimStatus = Literal["supported", "unsupported"]
ClaimReason = Literal["ok", "bad_cite", "pronoun", "vacuous", "entity_mismatch", "fact_mismatch", "no_attribution"]

RELATIONS: dict[str, tuple[str, ...]] = {
    "at": ("person", "place"),
    "saw": ("observer", "person", "place"),
    "heard": ("person", "sound", "place"),
    "carried": ("person", "item"),
    "owns": ("person", "item"),
    "owes": ("debtor", "creditor", "amount"),
    "argued": ("person", "other"),
    "door": ("place", "state"),
    "empty": ("place",),
}
TIMELESS = {"owns", "owes"}
Relation = Literal["at", "saw", "heard", "carried", "owns", "owes", "argued", "door", "empty"]

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class TimePoint(_Strict):
    day: int = Field(ge=1, le=3)
    slot: Slot

class Fact(_Strict):
    id: str
    rel: Relation
    args: list[str]
    t: TimePoint | None = None
    truth: bool = True

    @model_validator(mode="after")
    def _check_shape(self):
        if len(self.args) != len(RELATIONS[self.rel]):
            raise ValueError(f"{self.id}: {self.rel} takes {RELATIONS[self.rel]}, got {self.args}")
        if (self.t is None) != (self.rel in TIMELESS):
            raise ValueError(f"{self.id}: {self.rel} {'must not' if self.rel in TIMELESS else 'must'} have a time")
        return self

class Sentence(_Strict):
    id: str
    facts: list[str] = []
    text: str

class Document(_Strict):
    id: str
    owner: str
    genre: Genre
    title: str
    forged: bool = False
    withheld: bool = False
    sentences: list[Sentence]

class Villager(_Strict):
    id: str
    name: str
    role: str
    persona: str
    docs: list[str]
    secret_topic: str | None = None
    model: Literal["grounded", "base"] = "grounded"

class Lexicon(_Strict):
    """Per-case vocabulary. Time words and number words are global (archive/world/lexicon.py)."""
    people: dict[str, list[str]]
    places: list[str]
    items: list[str] = []
    sounds: list[str] = []

class Solution(_Strict):
    killer: str
    contradictions: list[tuple[str, str]]
    motive: str

class Case(_Strict):
    case_id: str
    seed: int
    theme: str = "village"
    town: str = "Hollowmere"
    difficulty: Difficulty
    victim: str
    killer: str
    scene: str
    murder_time: TimePoint
    briefing: str
    villagers: list[Villager]
    documents: list[Document]
    evidence_docs: list[str]
    facts: list[Fact]
    lexicon: Lexicon
    solution: Solution

    def villager(self, vid: str) -> Villager:
        return next(v for v in self.villagers if v.id == vid)

    def doc(self, did: str) -> Document:
        return next(d for d in self.documents if d.id == did)

    def fact(self, fid: str) -> Fact:
        return next(f for f in self.facts if f.id == fid)

    @model_validator(mode="after")
    def _check_refs(self):
        """Cheap consistency checks so a broken case fails at load time, not deep inside training."""
        fact_ids = [f.id for f in self.facts]
        doc_ids = [d.id for d in self.documents]
        vids = [v.id for v in self.villagers]
        for name, ids in (("fact", fact_ids), ("document", doc_ids), ("villager", vids)):
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {name} ids")
        facts = {f.id: f for f in self.facts}
        sent_ids = set()
        for d in self.documents:
            for s in d.sentences:
                if not s.id.startswith(d.id + ".S") or s.id in sent_ids:
                    raise ValueError(f"bad or duplicate sentence id {s.id} in {d.id}")
                sent_ids.add(s.id)
                if missing := [f for f in s.facts if f not in facts]:
                    raise ValueError(f"{s.id} links unknown facts {missing}")
            has_false = any(not facts[f].truth for s in d.sentences for f in s.facts)
            if d.forged != has_false:
                raise ValueError(f"{d.id}: forged={d.forged} but contains false facts={has_false}")
        for v in self.villagers:
            if missing := [x for x in v.docs if x not in doc_ids]:
                raise ValueError(f"villager {v.id} has unknown docs {missing}")
        if missing := [x for x in self.evidence_docs if x not in doc_ids]:
            raise ValueError(f"unknown evidence docs {missing}")
        if self.killer not in vids or self.killer != self.solution.killer:
            raise ValueError("killer must be a villager and match the solution")
        if self.victim in vids:
            raise ValueError("the victim is not a villager")
        for pid in [self.victim, *vids]:
            if pid not in self.lexicon.people:
                raise ValueError(f"{pid} has no names in the lexicon")
        for fid in [self.solution.motive, *(f for pair in self.solution.contradictions for f in pair)]:
            if fid not in facts:
                raise ValueError(f"solution references unknown fact {fid}")
        return self

class HeardItem(BaseModel):
    """Something a villager was told. `from` is a Python keyword, so the field is `from_` with alias "from"."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    id: str
    from_: str = Field(alias="from")
    day: int
    text: str
    facts: list[str] = []

class GoldClaim(_Strict):
    text: str
    cites: list[str]
    facts: list[str] = []

class Gold(_Strict):
    abstain: bool
    claims: list[GoldClaim] = []
    voice: str | None = None

class Task(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    case_id: str
    villager: str
    type: TaskType
    split: Split
    question: str
    gold: Gold
    heard: list[HeardItem] = []
    pass_rate: float | None = None

class ClaimResult(_Strict):
    text: str
    cites: list[str]
    status: ClaimStatus
    reason: ClaimReason
    facts: list[str] = []

class CheckResult(_Strict):
    parsed: bool
    abstained: bool = False
    support_rate: float | None = None
    claims: list[ClaimResult] = []
