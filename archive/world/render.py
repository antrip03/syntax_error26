"""Facts -> document sentences (brief 5.3). Fixed templates per relation and genre; no paraphrase.

Agreed rules for every sentence:
- ONE fact per sentence, starting with its day and time ("Day 2, midnight. I saw Tom by the chapel."). Timeless facts
  (owes, owns) have no time.
- Explicit subjects ("I", a name, or "the miller" in Hard sightings), never pronouns, so a villager quoting its own
  line word for word makes a green claim. tests/test_casegen.py checks that for every line of generated cases,
  except Easy "near" sightings, whose "next to the guildhall" names a fact place (see the note in casegen).
- Only words the checker knows for times ("sunset" -> dusk, "ninth bell" -> night), and no crime words.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from archive.schemas import SLOTS, Document, Fact, Sentence

TIME_PHRASES = {"dawn": ["dawn", "first light"], "morning": ["morning"], "noon": ["noon", "midday"],
                "afternoon": ["afternoon"], "dusk": ["dusk", "sunset", "evening"], "night": ["night", "midnight"]}
PATROL_NIGHT = ["midnight", "ninth bell"]

GENRE_TITLE = {"diary": "diary", "patrol_log": "patrol log", "ledger": "ledger", "letter": "letter",
               "notebook": "notebook", "prayer_book": "prayer book", "receipt": "receipt"}

_AT_SELF = {
    "default": ["I was at the {place}.", "I went to the {place}.", "I spent the time at the {place}."],
    "patrol_log": ["I kept watch at the {place}.", "I was on patrol at the {place}."],
}
_AT_WORK = {
    "default": ["I worked at the {place}.", "I was at work at the {place}."],
    "patrol_log": ["I kept watch at the {place}.", "I was on patrol at the {place}."],
    "ledger": ["I worked at the {place}.", "I was at the {place} with the accounts."],
    "prayer_book": ["I prayed at the {place}.", "I led prayers at the {place}."],
}
_AT_OTHER = {
    "default": ["{P} was at the {place}.", "{P} came to the {place}."],
    "patrol_log": ["{P} at the {place}.", "{P} was at the {place}."],
    "ledger": ["{P} was here at the {place}.", "{P} waited at the {place}."],
}
_SAW = {
    "plain": ["I saw {P} at the {place}.", "I saw {P} by the {place}."],
    "near": ["I saw {P} by the {place}, next to the {scene}."],
    "role": ["I saw the {role} by the {place}."],
}
_EMPTY = ["The {place} was dark. No one was inside.", "The {place} was empty and silent."]
_HEARD = ["I heard {a_sound} from the {place}.", "I heard {a_sound} near the {place}."]
_ARGUED_SELF = ["I argued with {Q}.", "I had a loud argument with {Q}."]
_ARGUED_OTHER = ["{P} argued with {Q}."]
_OWES_CREDITOR = ["{P} still owes me {amount}.", "{P} owes me {amount}."]
_OWES_DEBTOR = ["I owe {Q} {amount}.", "I still owe {Q} {amount}."]
_OWNS = ["I own a {item}."]
_CARRIED_SELF = ["I carried a {item}."]
_CARRIED_OTHER = ["{P} was carrying a {item}."]
_DOOR = ["The {place} door was {state}."]
_NO_ARTICLE = {"footsteps", "barking"}

@dataclass
class Line:
    """A fact to write. style: for sightings "plain", "near" (names the scene) or "role"; for the writer's own
    whereabouts "work" when the place is their workplace."""
    fact: Fact
    style: str = "plain"
    scene: str | None = None

def when(rng: random.Random, fact: Fact, genre: str) -> str:
    if fact.t is None:
        return ""
    phrases = PATROL_NIGHT if genre == "patrol_log" and fact.t.slot == "night" else TIME_PHRASES[fact.t.slot]
    return f"Day {fact.t.day}, {rng.choice(phrases)}. "

def sentence_text(rng: random.Random, line: Line, owner: str, genre: str, names: dict[str, str],
                  roles: dict[str, str]) -> str:
    f, a = line.fact, line.fact.args

    def pick(table):
        return rng.choice(table.get(genre, table["default"]) if isinstance(table, dict) else table)

    if f.rel == "at":
        table = (_AT_WORK if line.style == "work" else _AT_SELF) if a[0] == owner else _AT_OTHER
        body = pick(table).format(P=names[a[0]], place=a[1])
    elif f.rel == "saw":
        body = rng.choice(_SAW[line.style]).format(P=names[a[1]], role=roles[a[1]], place=a[2], scene=line.scene)
    elif f.rel == "empty":
        body = rng.choice(_EMPTY).format(place=a[0])
    elif f.rel == "heard":
        sound = a[1] if a[1] in _NO_ARTICLE else f"a {a[1]}"
        body = rng.choice(_HEARD).format(a_sound=sound, place=a[2])
    elif f.rel == "argued":
        if owner in a:
            body = rng.choice(_ARGUED_SELF).format(Q=names[a[1] if a[0] == owner else a[0]])
        else:
            body = rng.choice(_ARGUED_OTHER).format(P=names[a[0]], Q=names[a[1]])
    elif f.rel == "owes":
        if owner == a[1]:
            body = rng.choice(_OWES_CREDITOR).format(P=names[a[0]], amount=a[2])
        else:
            body = rng.choice(_OWES_DEBTOR).format(Q=names[a[1]], amount=a[2])
    elif f.rel == "owns":
        body = rng.choice(_OWNS).format(item=a[1])
    elif f.rel == "carried":
        body = pick(_CARRIED_SELF if a[0] == owner else _CARRIED_OTHER).format(P=names[a[0]], item=a[1])
    elif f.rel == "door":
        body = rng.choice(_DOOR).format(place=a[0], state=a[1])
    else:
        raise ValueError(f"no template for {f.rel}")
    return when(rng, f, genre) + body

def _order(line: Line) -> tuple:
    t = line.fact.t
    return (0, t.day, SLOTS.index(t.slot)) if t else (1, 0, 0)

def render_document(rng: random.Random, doc_id: str, owner: str, owner_name: str, genre: str, lines: list[Line],
                    names: dict[str, str], roles: dict[str, str], withheld: bool = False) -> Document:
    """One document: lines in time order (timeless last), ids D{n}.S{k}, each sentence linked to its fact."""
    sentences = [Sentence(id=f"{doc_id}.S{k}", facts=[ln.fact.id],
                          text=sentence_text(rng, ln, owner, genre, names, roles))
                 for k, ln in enumerate(sorted(lines, key=_order), start=1)]
    return Document(id=doc_id, owner=owner, genre=genre, title=f"{owner_name}'s {GENRE_TITLE[genre]}",
                    forged=any(not ln.fact.truth for ln in lines), withheld=withheld, sentences=sentences)
