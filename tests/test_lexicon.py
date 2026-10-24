"""Entity extraction (archive/world/lexicon.py) on the Elsie fixture."""
import json
from pathlib import Path

import pytest

from archive.schemas import Case
from archive.world.lexicon import THEMES, TIME_WORDS, has_negation, vocab_for

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"


@pytest.fixture(scope="module")
def case():
    return Case.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture(scope="module")
def vocab(case):
    return vocab_for(case)


def test_source_sentences(case, vocab):
    got = {s.id: vocab.extract(s.text, d.owner) for d in case.documents for s in d.sentences}
    assert got["D1.S1"] == {("day", 2), ("place", "mill"), ("slot", "dusk")}  # "sunset" -> dusk
    assert got["D2.S1"] == {("day", 2), ("slot", "night"), ("person", "tom"), ("place", "chapel"),
                            ("place", "guildhall"), ("item", "lantern")}
    assert got["D5.S1"] >= {("slot", "dusk"), ("slot", "night"), ("person", "mara")}  # "evening to midnight"
    assert got["E1.S1"] == {("person", "tom"), ("person", "elsie"), ("num", 40), ("item", "silver")}  # me -> owner


@pytest.mark.parametrize("text, speaker, expected", [
    ("I shut the mill at dusk on day 2.", "tom", {("person", "tom"), ("place", "mill"), ("slot", "dusk"), ("day", 2)}),
    ("At the ninth bell on the second day.", "gus", {("slot", "night"), ("day", 2)}),     # not the sound "bell"
    ("Father Bram and Bram.", None, {("person", "bram")}),
    ("I saw the miller.", "gus", {("person", "gus"), ("person", "tom")}),               # unique role -> person
    ("I saw the weaver.", "gus", {("person", "gus"), ("unknown", "weaver")}),           # role nobody in the case has
    ("He owes forty-two silver coins.", None, {("num", 42), ("item", "silver"), ("item", "coin")}),
    ("Carrying two lanterns.", None, {("num", 2), ("item", "lantern")}),
    ("No one was there.", None, set()),                                                 # "one" is not a number
    ("My ledger and my notebook say so, as well.", "ivy", {("person", "ivy")}),          # own records, "well"
    ("The ivy grew on the chapel.", None, {("place", "chapel")}),                       # plant, not the person Ivy
])
def test_extract(vocab, text, speaker, expected):
    assert vocab.extract(text, speaker) == expected


@pytest.mark.parametrize("text, invented", [
    ("I saw Wren by the chapel.", ("person", "wren")),        # pool name not in this case
    ("I saw Bob by the chapel.", ("unknown", "bob")),         # unknown capitalised name
    ("I was at the tavern.", ("place", "tavern")),            # decoy place
    ("Tom had a dagger.", ("item", "dagger")),                # decoy item
])
def test_invented_things_are_recognised(vocab, text, invented):
    assert invented in vocab.extract(text, "gus")


def test_sentence_start_capital_is_not_a_name(vocab):
    assert vocab.extract("Then I went home. Later I slept.", "tom") == {("person", "tom")}


def test_town_name_is_ignored(vocab):
    assert vocab.extract("I live in Hollowmere.", "tom") == {("person", "tom")}


def test_negation():
    assert has_negation("I was not at the mill.") and has_negation("I didn't see him.")
    assert has_negation("No one was inside.") and not has_negation("I shut the mill at dusk.")


def test_pools_cover_every_slot_and_have_enough_names():
    assert set(TIME_WORDS.values()) == {"dawn", "morning", "noon", "afternoon", "dusk", "night"}
    pool = THEMES["village"]
    assert len(set(pool["names"])) >= 40 and len(pool["places"]) == 8
