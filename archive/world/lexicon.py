"""Vocabulary for the village theme and deterministic entity extraction (brief sections 5.1 and 9).

`casegen` picks names, roles, places, items and sounds from the pools below. The checker uses `Vocab.extract`
to turn a claim and its source sentence into comparable sets of tagged entities, e.g.
    "Day 2. Shut the mill at sunset."  ->  {("day", 2), ("place", "mill"), ("slot", "dusk")}

The pools also hold decoy words that never appear in generated cases (tavern, dagger, ...), and every name in
the pool is recognised whether or not it is in the case. That is what lets the checker see an invented person,
place or item: it gets extracted, is missing from the cited source, and the claim fails.

No models, no network: plain regular expressions.
"""
from __future__ import annotations

import re
from functools import cached_property

from archive.schemas import SLOTS, Case, Lexicon

Entity = tuple[str, object]  # (kind, value); kinds: person, place, item, sound, state, day, slot, num, unknown

THEMES: dict[str, dict[str, list[str]]] = {
    "village": {
        # Avoid names that are ordinary English words (Kit, Lark, Will, May): they would be read as people.
        "names": ["Tom", "Gus", "Nell", "Mara", "Ivy", "Bram", "Elsie", "Wren", "Hollis", "Agnes", "Edwin", "Maud",
                  "Osric", "Bess", "Cedric", "Rowan", "Tilda", "Fenn", "Hugh", "Alba", "Jory", "Morwen", "Ned",
                  "Orla", "Piers", "Silas", "Tamsin", "Ulric", "Vera", "Yara", "Ada", "Bertram", "Clem", "Dora",
                  "Ezra", "Flora", "Giles", "Hattie", "Ines", "Jasper", "Lettie", "Milo", "Nora", "Otto", "Perrin",
                  "Greta", "Aldous", "Brenna", "Corin", "Delphine"],
        "roles": ["miller", "guard", "herbalist", "baker", "blacksmith", "priest", "innkeeper", "weaver", "fisher",
                  "carpenter", "shepherd", "cooper", "tailor", "chandler", "brewer", "midwife", "scribe", "tanner"],
        "places": ["mill", "bakery", "chapel", "guildhall", "inn", "river path", "market", "smithy"],
        "items": ["lantern", "key", "knife", "seal", "flour sack", "flour", "oven door", "silver", "rope", "candle",
                  "basket", "cloak", "hammer", "axe", "bottle", "shovel"],
        "sounds": ["scream", "shout", "door slam", "bell", "crash", "footsteps", "barking"],
    },
}

# Never used in cases. Present only so invented places/items are recognised (and then fail the checker).
# Everyday words that double as nouns ("well", "ring", "bow") are left out: "as well" must not read as a place.
DECOY_PLACES = ["tavern", "forest", "barn", "church", "castle", "harbour", "farm", "bridge", "cellar",
                "graveyard", "stable", "school", "woods", "cottage", "field", "orchard"]
DECOY_ITEMS = ["sword", "dagger", "poison", "gold", "coin", "arrow", "torch", "necklace", "pistol", "crossbow",
               "vial", "satchel"]

# Words for a villager's own records ("my notebook says ..."). Removed before extraction so that naming your own
# document is not read as an item that the source line lacks.
RECORD_WORDS = ["patrol log", "prayer book", "diary", "ledger", "letter", "notebook", "log", "receipt", "records",
                "record", "papers", "notes", "journal"]

# Phrase -> slot. Longest phrases win ("ninth bell" before the sound "bell", "nightfall" is dusk).
TIME_WORDS: dict[str, str] = {
    "dawn": "dawn", "daybreak": "dawn", "sunrise": "dawn", "first light": "dawn", "cockcrow": "dawn",
    "morning": "morning",
    "noon": "noon", "midday": "noon",
    "afternoon": "afternoon",
    "dusk": "dusk", "sunset": "dusk", "sundown": "dusk", "evening": "dusk", "twilight": "dusk", "nightfall": "dusk",
    "night": "night", "midnight": "night", "ninth bell": "night", "all night": "night",
}
assert set(TIME_WORDS.values()) == set(SLOTS)

# "one" is left out on purpose: "no one", "the one who" would otherwise read as the number 1.
NUMBER_WORDS: dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
_DAY_WORDS = {"one": 1, "two": 2, "three": 3, "first": 1, "second": 2, "third": 3}

# Door states (the `door` relation). "unlocked" is recognised so that it never passes as "open" or "locked".
STATE_WORDS: dict[str, str] = {"open": "open", "opened": "open", "locked": "locked", "unlocked": "unlocked"}

# Only these mean the speaker. "my"/"mine" do not: "Mara was at my smithy" says nothing about where I was.
SELF_WORDS = ["i", "me", "myself"]
NEGATION_WORDS = ["not", "never", "no", "nobody", "nothing", "none", "no one", "didn't", "wasn't", "weren't",
                  "don't", "doesn't", "hadn't", "haven't", "isn't", "can't", "cannot", "couldn't", "won't",
                  # the same without the apostrophe, as models often write them
                  *(_NO_APOSTROPHE := ["didnt", "wasnt", "werent", "dont", "doesnt", "hadnt", "havent", "isnt", "cant",
                                       "couldnt", "wont"]),
                  "without", "neither", "nor", "nowhere", "absent"]
# Negations that mean the same, so "nobody" in a claim matches "no one" in the source; "n't" forms are "not".
_NEG_SAME = {"nobody": "no one", "none": "no one", "cannot": "not", "neither": "not", "nor": "not"}

# Crime actions and judgements a claim must not add: the brief's entity check cannot see verbs, so without this
# "I saw Tom stab someone by the chapel [D2.S1]" would pass. A claim may use a stem only if its cited line has the
# same stem. Stem -> its word forms.
_ACTION_FORMS = {
    "kill": "kill kills killed killing killer", "murder": "murder murders murdered murdering murderer",
    "stab": "stab stabs stabbed stabbing", "poison": "poison poisons poisoned poisoning",
    "strangle": "strangle strangles strangled strangling", "choke": "choke chokes choked choking",
    "hit": "hit hits hitting", "strike": "strike strikes struck striking",
    "attack": "attack attacks attacked attacking", "beat": "beat beats beaten beating",
    "push": "push pushes pushed pushing", "shoot": "shoot shoots shot shooting", "drown": "drown drowns drowned",
    "steal": "steal steals stole stolen stealing thief", "hide": "hide hides hid hidden hiding",
    "flee": "flee flees fled fleeing escape escaped escaping", "sneak": "sneak sneaks sneaked snuck sneaking",
    "threaten": "threaten threatens threatened threatening threat threats",
    "burn": "burn burns burned burnt burning", "break": "break breaks broke broken breaking",
    "lie": "lie lies lied liar lying", "fight": "fight fights fought fighting", "blood": "blood bloody bloodied",
    "dead": "dead die died dies dying death", "body": "body corpse", "weapon": "weapon weapons",
    "crime": "crime crimes culprit", "guilty": "guilty", "suspicious": "suspicious suspect suspected",
    "nervous": "nervous", "afraid": "afraid scared", "angry": "angry furious", "secret": "secret secretly",
}
ACTION_WORDS: dict[str, str] = {w: stem for stem, forms in _ACTION_FORMS.items() for w in forms.split()}
ACTION_WORDS |= {"ran away": "run away", "run away": "run away", "running away": "run away"}


def _alternation(phrases) -> str:
    """Regex alternation, longest phrase first, spaces matching any whitespace."""
    parts = sorted({p for p in phrases}, key=len, reverse=True)
    return "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in parts)


_DAY_RE = re.compile(r"\bday\s+(\d+|one|two|three)\b|\b(first|second|third)\s+day\b", re.I)
_NUM_RE = re.compile(r"\b(\d+)\b|\b(" + _alternation(NUMBER_WORDS) + r")(?:[\s-]+(two|three|four|five|six|seven|eight|nine))?\b",
                     re.I)
_SELF_RE = re.compile(r"\b(" + _alternation(SELF_WORDS) + r")\b", re.I)
_RECORD_RE = re.compile(r"\b(" + _alternation(RECORD_WORDS) + r")\b", re.I)
_NEG_RE = re.compile(r"\b(" + _alternation(NEGATION_WORDS) + r")\b|n't\b", re.I)
_ACTION_RE = re.compile(r"\b(" + _alternation(ACTION_WORDS) + r")\b", re.I)
_CAP_RE = re.compile(r"\b[A-Z][a-z]+\b")
_SENTENCE_START = set(".!?:;\"'([")


def _unknown_names(work: str) -> list[str]:
    """Capitalised words that do not start a sentence: names the vocabulary does not know."""
    out = []
    for m in _CAP_RE.finditer(work):
        before = work[: m.start()].rstrip()
        if before and before[-1] not in _SENTENCE_START:
            out.append(m.group(0))
    return out


def _straight(text: str) -> str:
    """Curly apostrophes as straight ones, so "didn’t" is read like "didn't"."""
    return text.replace("’", "'").replace("‘", "'")


def has_negation(text: str) -> bool:
    return bool(_NEG_RE.search(_straight(text)))


def negations(text: str) -> set[str]:
    """Negations in `text`, normalised: "didn't"/"wasnt" -> "not", "nobody" -> "no one"."""
    out = set()
    for m in _NEG_RE.finditer(_straight(text)):
        w = re.sub(r"\s+", " ", (m.group(1) or "n't").lower())
        out.add("not" if w.endswith("n't") or w in _NO_APOSTROPHE else _NEG_SAME.get(w, w))
    return out


def actions(text: str) -> set[str]:
    """Crime actions and judgements in `text`, as stems ("stabbed" -> "stab")."""
    return {ACTION_WORDS[re.sub(r"\s+", " ", m.group(1).lower())] for m in _ACTION_RE.finditer(text)}


class Vocab:
    """Compiled vocabulary for one case: theme pools + decoys + the case's own names and roles."""

    def __init__(self, people: dict[str, list[str]], roles: dict[str, str] | None = None, theme: str = "village",
                 extra_places=(), extra_items=(), extra_sounds=(), ignore=()):
        pools = THEMES[theme]
        # Surface name -> person id. Pool names map to their lowercase form; the case's own names override.
        self.names = {n: n.lower() for n in pools["names"]}
        for pid, surfaces in people.items():
            for s in surfaces:
                self.names[s] = pid
        # Role word -> person id when exactly one villager has that role; other roles are unknown people.
        self.roles = {r: None for r in pools["roles"]} | {r.lower(): pid for r, pid in (roles or {}).items()}
        self.terms: dict[str, Entity] = {}
        for kind, words in (("place", [*pools["places"], *DECOY_PLACES, *extra_places]),
                            ("item", [*pools["items"], *DECOY_ITEMS, *extra_items]),
                            ("sound", [*pools["sounds"], *extra_sounds])):
            for w in words:
                self.terms[w.lower()] = (kind, w.lower())
        for w, state in STATE_WORDS.items():
            self.terms[w] = ("state", state)
        for w, slot in TIME_WORDS.items():
            self.terms[w] = ("slot", slot)
        self.ignore = {w.lower() for w in ignore}

    @cached_property
    def _name_re(self):  # case-sensitive: "Ivy" the person, not "ivy" the plant
        return re.compile(r"\b(" + _alternation(self.names) + r")\b")

    @cached_property
    def _term_re(self):
        return re.compile(r"\b(" + _alternation([*self.terms, *self.roles]) + r")(?:e?s)?\b", re.I)  # plurals too

    def extract(self, text: str, speaker: str | None = None) -> set[Entity]:
        """Tagged entities in `text`. "I"/"me"/"myself" become `speaker` when given ("my" does not)."""
        out: set[Entity] = set()
        work = text

        def blank(m):  # remove a match so later passes don't read it again
            return " " * len(m.group(0))

        def day(m):
            w = (m.group(1) or m.group(2)).lower()
            out.add(("day", int(w) if w.isdigit() else _DAY_WORDS[w]))
            return blank(m)

        def name(m):
            out.add(("person", self.names[m.group(1)]))
            return blank(m)

        def term(m):
            w = re.sub(r"\s+", " ", m.group(1).lower())
            if w in self.roles:
                pid = self.roles[w]
                out.add(("person", pid) if pid else ("unknown", w))
            else:
                out.add(self.terms[w])
            return blank(m)

        def num(m):
            if m.group(1):
                out.add(("num", int(m.group(1))))
            else:
                out.add(("num", NUMBER_WORDS[m.group(2).lower()] + (NUMBER_WORDS[m.group(3).lower()] if m.group(3) else 0)))
            return blank(m)

        work = _DAY_RE.sub(day, work)
        work = _RECORD_RE.sub(blank, work)
        work = self._name_re.sub(name, work)
        work = self._term_re.sub(term, work)
        work = re.sub(r"\bno\s+one\b|\bsomeone\b|\banyone\b|\beveryone\b", blank, work, flags=re.I)
        work = _NUM_RE.sub(num, work)
        if speaker and _SELF_RE.search(work):
            out.add(("person", speaker))
        for w in _unknown_names(work):
            if w.lower() not in self.ignore:
                out.add(("unknown", w.lower()))
        return out


    def people_in_order(self, text: str, speaker: str | None = None) -> list[tuple[int, str]]:
        """(position, person id) for each person mentioned, in text order; "I"/"me" are `speaker`.
        The checker uses it to tell "I saw Tom" from "Tom saw me"."""
        hits = [(m.start(), self.names[m.group(1)]) for m in self._name_re.finditer(text)]
        for m in self._term_re.finditer(text):
            if pid := self.roles.get(re.sub(r"\s+", " ", m.group(1).lower())):
                hits.append((m.start(), pid))
        if speaker:
            hits += [(m.start(), speaker) for m in _SELF_RE.finditer(text)]
        return sorted(hits)


def vocab_for(case: Case) -> Vocab:
    """Vocab for a case: its people's names, its villagers' roles, and its own place/item/sound lists."""
    roles: dict[str, str] = {}
    counts: dict[str, int] = {}
    for v in case.villagers:
        counts[v.role] = counts.get(v.role, 0) + 1
        roles[v.role] = v.id
    roles = {r: pid for r, pid in roles.items() if counts[r] == 1}
    lex: Lexicon = case.lexicon
    return Vocab(lex.people, roles, theme=case.theme, extra_places=lex.places, extra_items=lex.items,
                 extra_sounds=lex.sounds, ignore=[case.town])
