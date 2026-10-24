"""Question wording and persona voice lines (archive/tasks/phrasing.py)."""
import json
import random
import re
from pathlib import Path

from archive.schemas import Case
from archive.tasks.phrasing import DAY, FORMAT_ATTACK, GENERIC_VOICE, MURDER, PRESSURE, SLOT, VOICE, style, time_phrase
from archive.tasks.personas import PERSONAS
from archive.world.lexicon import TIME_WORDS, actions, negations, pronouns, vocab_for

CASE = Case.model_validate(json.loads((Path(__file__).parent / "fixtures" / "case_elsie.json").read_text()))


def test_families_never_share_a_wording():
    for table in (DAY, MURDER, PRESSURE, FORMAT_ATTACK):
        assert not set(table["A"]) & set(table["B"])
    for slot in SLOT["A"]:
        assert not set(SLOT["A"][slot]) & set(SLOT["B"][slot])


def test_every_slot_and_day_has_wordings():
    rng = random.Random(0)
    for fam in ("A", "B"):
        for slot in SLOT[fam]:
            for day in (1, 2, 3):
                assert time_phrase(day, slot, rng, fam)


def test_voice_lines_hold_no_checkable_word():
    vocab = vocab_for(CASE)
    lines = [*GENERIC_VOICE, *(x for v in VOICE.values() for x in v)]
    for line in lines:
        assert vocab.extract(line) == set(), line
        assert not actions(line) and not pronouns(line) and not negations(line), line
        assert not any(re.search(rf"\\b{w}\\b", line.lower()) for w in TIME_WORDS), line
        assert not re.search(r"\\d", line), line


def test_every_persona_has_a_voice():
    keys = {p.split(",")[0].split(" ")[0].lower() for p in PERSONAS}
    assert keys <= set(VOICE)


def test_style_keeps_names_capitalised():
    rng = random.Random(1)
    for _ in range(200):
        assert "Tom" in style("Did you see Tom at night on day 2?", rng, "A", "Elsie")
        assert "Gus" in style("Gus says you were lying. What do you say?", rng, "B")
