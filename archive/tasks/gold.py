"""Gold replies (brief section 8): the exact text we want the model to write. SFT trains on these strings, CuratorKIT
drops any task whose gold fails the checker, and the GRPO "correct" reward compares against the gold facts.

Every gold claim follows the villager prompt's rules (archive/tasks/prompt.py), because the model learns the rules
by copying gold:
- one fact per CLAIM line, one short sentence, no "and", no commas (rule 14)
- names, never "he", "she" or "they" (rule 5); Hard sightings keep the line's "the scribe" (rule 7)
- names, places, days, times, items and amounts as written: "Day 2, midnight." -> "at midnight on day 2" (rule 7)
- no added actions, judgements or negations (rules 8, 9); "I" only for the writer's own facts (rule 10)
- the ID of the one sentence that states the fact (rule 16)
- hearsay names the speaker with "<name> said" or "<name> told me" (rule 17), quoting when the speaker talks about
  themselves: Gus said: "I saw Tom by the chapel at midnight on day 2." [H1]
- an optional persona '#' line (`Gold.voice`, from archive/tasks/phrasing.py) first; it holds no checkable word
tests/test_generate.py checks every gold reply against the checker and these rules.
"""
from __future__ import annotations

import re

from archive.schemas import Case, Fact, Gold, GoldClaim, HeardItem
from archive.verifiers.parse import ABSTAIN
from archive.world.lexicon import TIME_WORDS

# Time phrase as written in a line -> how a claim says it.
_AT_TIME = {"dawn": "at dawn", "first light": "at first light", "daybreak": "at daybreak", "sunrise": "at sunrise",
            "cockcrow": "at cockcrow", "morning": "in the morning", "noon": "at noon", "midday": "at midday",
            "afternoon": "in the afternoon", "dusk": "at dusk", "sunset": "at sunset", "sundown": "at sundown",
            "evening": "in the evening", "twilight": "at twilight", "nightfall": "at nightfall", "night": "at night",
            "midnight": "at midnight", "ninth bell": "at the ninth bell", "all night": "all night"}
_HEADER = re.compile(r"^Day (\d+), ([a-z ]+)\.")
_PHRASES = sorted(TIME_WORDS, key=len, reverse=True)
_NO_ARTICLE = {"footsteps", "barking"}


def gold_reply(task) -> str:
    """The reply text for a task (Task or task row dict): the abstain line, or an <answer> block of CLAIM lines."""
    gold = task.gold if hasattr(task, "gold") else Gold.model_validate(task["gold"])
    if gold.abstain:
        return ABSTAIN
    lines = [f"CLAIM: {c.text} " + "".join(f"[{i}]" for i in c.cites) for c in gold.claims]
    if gold.voice:
        lines.insert(0, f"# {gold.voice}")
    return "<answer>\n" + "\n".join(lines) + "\n</answer>"


def when(fact: Fact, line: str) -> str:
    """The fact's time as the line writes it: "at midnight on day 2". Empty for timeless facts."""
    if fact.t is None:
        return ""
    m = _HEADER.match(line)
    phrase = m.group(2) if m and m.group(2) in _AT_TIME else None
    if phrase is None:  # hand-written lines without a "Day N, time." header: use the first time word that fits
        low = line.lower()
        phrase = next((p for p in _PHRASES if re.search(rf"\b{p}\b", low) and TIME_WORDS[p] == fact.t.slot
                       and p in _AT_TIME), fact.t.slot)
    return f" {_AT_TIME[phrase]} on day {fact.t.day}"


def _name(case: Case, pid: str) -> str:
    names = case.lexicon.people.get(pid)
    return names[0] if names else pid


def _who(case: Case, pid: str, speaker: str, line: str) -> str:
    """"I" for the speaker, "the scribe" if the line names the person by role only, else their name."""
    if pid == speaker:
        return "I"
    v = next((x for x in case.villagers if x.id == pid), None)
    if v and f"the {v.role}" in line and _name(case, pid) not in line:
        return f"the {v.role}"
    return _name(case, pid)


def _prep(line: str, place: str, options=("by", "near", "from")) -> str:
    return next((p for p in options if f" {p} the {place}" in line), "at")


def statement(case: Case, fact: Fact, speaker: str, line: str) -> str:
    """One fact as a claim sentence from `speaker`'s point of view, using the cited line's wording for times and
    sightings. No pronouns, no "and", no commas."""
    a, t = fact.args, when(fact, line)

    def who(pid):
        return _who(case, pid, speaker, line)

    if fact.rel == "at":
        s = f"{who(a[0])} was at the {a[1]}{t}." if a[0] != speaker else f"I was at the {a[1]}{t}."
        if a[0] != speaker and "all night" in t:  # "Mara stayed at the smithy all night on day 2."
            s = f"{who(a[0])} stayed at the {a[1]}{t}."
        elif a[0] == speaker and "all night" in t:
            s = f"I stayed at the {a[1]}{t}."
    elif fact.rel == "saw":
        seer = "I saw" if a[0] == speaker else f"{who(a[0])} saw"
        s = f"{seer} {who(a[1])} {_prep(line, a[2], ('by', 'near'))} the {a[2]}{t}."
    elif fact.rel == "empty":
        s = f"The {a[0]} was empty{t}."
    elif fact.rel == "heard":
        sound = a[1] if a[1] in _NO_ARTICLE else f"a {a[1]}"
        s = f"{'I' if a[0] == speaker else who(a[0])} heard {sound} {_prep(line, a[2], ('from', 'near'))} the {a[2]}{t}."
    elif fact.rel == "argued":
        if speaker in a[:2]:
            s = f"I argued with {who(a[1] if a[0] == speaker else a[0])}{t}."
        else:
            s = f"{who(a[0])} argued with {who(a[1])}{t}."
    elif fact.rel == "owes":
        if a[0] == speaker:
            s = f"I owe {who(a[1])} {a[2]}."
        elif a[1] == speaker:
            s = f"{who(a[0])} owes me {a[2]}."
        else:
            s = f"{who(a[0])} owes {who(a[1])} {a[2]}."
    elif fact.rel == "carried":
        s = f"{'I' if a[0] == speaker else who(a[0])} carried a {a[1]}{t}."
    elif fact.rel == "owns":
        s = f"{'I own' if a[0] == speaker else who(a[0]) + ' owns'} a {a[1]}."
    elif fact.rel == "door":
        s = f"The {a[0]} door was {a[1]}{t}."
    else:
        raise ValueError(f"no gold sentence for {fact.rel}")
    return s[0].upper() + s[1:]


def own_claim(case: Case, speaker: str, sentence_id: str, fact: Fact, line: str) -> GoldClaim:
    """A claim about one of the speaker's own lines."""
    return GoldClaim(text=statement(case, fact, speaker, line), cites=[sentence_id], facts=[fact.id])


def heard_claim(case: Case, item: HeardItem, fact: Fact) -> GoldClaim:
    """A hearsay claim: quote the teller when they speak about themselves, else "<name> told me ...".
    The fact is stated from the teller's point of view, so their "I" stays theirs inside the quotes."""
    said = statement(case, fact, item.from_, item.text)
    teller = _name(case, item.from_)
    if said.startswith("I "):
        text = f'{teller} said: "{said}"'
    else:
        text = f"{teller} told me {said[0].lower() + said[1:] if said.startswith('The ') else said}"
    return GoldClaim(text=text, cites=[item.id], facts=[fact.id])
