"""Entity extraction (archive/world/lexicon.py) on the Elsie fixture."""
import json
from pathlib import Path

import pytest

from archive.schemas import Case
from archive.world.lexicon import THEMES, TIME_WORDS, actions, has_negation, negations, vocab_for

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"

@pytest.fixture(scope="module")
def case():
    return Case.model_validate(json.loads(FIXTURE.read_text()))

@pytest.fixture(scope="module")
def vocab(case):
    return vocab_for(case)

def test_source_sentences(case, vocab):
    got = {s.id: vocab.extract(s.text, d.owner) for d in case.documents for s in d.sentences}
    assert got["D1.S1"] == {("day", 2), ("place", "mill"), ("slot", "dusk")}
    assert got["D2.S1"] == {("day", 2), ("slot", "night"), ("person", "tom"), ("place", "chapel"),
                            ("place", "guildhall"), ("item", "lantern")}
    assert got["D5.S1"] >= {("slot", "dusk"), ("slot", "night"), ("person", "mara")}
    assert got["E1.S1"] == {("person", "tom"), ("person", "elsie"), ("num", 40), ("item", "silver")}

@pytest.mark.parametrize("text, speaker, expected", [
    ("I shut the mill at dusk on day 2.", "tom", {("person", "tom"), ("place", "mill"), ("slot", "dusk"), ("day", 2)}),
    ("At the ninth bell on the second day.", "gus", {("slot", "night"), ("day", 2)}),
    ("Father Bram and Bram.", None, {("person", "bram")}),
    ("I saw the miller.", "gus", {("person", "gus"), ("person", "tom")}),
    ("I saw the weaver.", "gus", {("person", "gus"), ("unknown", "weaver")}),
    ("He owes forty-two silver coins.", None, {("num", 42), ("item", "silver"), ("item", "coin")}),
    ("Carrying two lanterns.", None, {("num", 2), ("item", "lantern")}),
    ("No one was there.", None, set()),
    ("My ledger and my notebook say so, as well.", "ivy", set()),
    ("Mara was at my smithy.", "ivy", {("person", "mara"), ("place", "smithy")}),
    ("Tom still owes me.", "elsie", {("person", "tom"), ("person", "elsie")}),
    ("The guildhall door was open, not locked.", None, {("place", "guildhall"), ("state", "open"),
                                                        ("state", "locked")}),
    ("The door was unlocked.", None, {("state", "unlocked")}),
    ("The ivy grew on the chapel.", None, {("person", "ivy"), ("place", "chapel")}),
    ("mara and tom at the mill.", None, {("person", "mara"), ("person", "tom"), ("place", "mill")}),
    ("father bram prayed.", None, {("person", "bram")}),
    ("MARA AND TOM AT THE MILL.", None, {("person", "mara"), ("person", "tom"), ("place", "mill")}),
    ("FATHER BRAM prayed.", None, {("person", "bram")}),
    ("I saw WREN.", "gus", {("person", "gus"), ("person", "wren")}),
    ("Mara and mara and MARA.", None, {("person", "mara")}),
])
def test_extract(vocab, text, speaker, expected):
    assert vocab.extract(text, speaker) == expected

@pytest.mark.parametrize("text, invented", [
    ("I saw Wren by the chapel.", ("person", "wren")),
    ("I saw Bob by the chapel.", ("unknown", "bob")),
    ("I was at the tavern.", ("place", "tavern")),
    ("Tom had a dagger.", ("item", "dagger")),
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
    assert negations("Nobody was inside; I didn't look, I never do.") == {"no one", "not", "never"}
    assert negations("It was dark and silent, no one inside.") == {"no one"}
    assert negations("I shut the mill at dusk.") == set()

def test_actions():
    assert actions("I saw Tom stab someone and he fled.") == {"stab", "flee"}
    assert actions("Tom ran away from the body.") == {"run away", "body"}
    assert actions("Nobody was inside. I shut the mill and stayed.") == set()
    assert actions("Day 2, noon. Had a loud argument with Elsie about the price of flour.") == set()

def test_people_in_order(vocab):
    assert [p for _, p in vocab.people_in_order("I saw Tom by the chapel.", "gus")] == ["gus", "tom"]
    assert [p for _, p in vocab.people_in_order("Tom saw me by the chapel.", "gus")] == ["tom", "gus"]
    assert [p for _, p in vocab.people_in_order("The miller saw Father Bram, my friend.", "gus")] == ["tom", "bram"]

def test_pools_cover_every_slot_and_have_enough_names():
    assert set(TIME_WORDS.values()) == {"dawn", "morning", "noon", "afternoon", "dusk", "night"}
    pool = THEMES["village"]
    assert len(set(pool["names"])) >= 40 and len(pool["places"]) == 8

@pytest.mark.parametrize("name", ["Elsie", "ELSIE", "elsie", "Tom", "TOM", "tom", "Father Bram", "FATHER BRAM",
                                  "father bram", "Bram", "BRAM", "bram"])
def test_every_name_in_any_case(vocab, name):
    pid = "bram" if "ram" in name.lower() else name.lower()
    assert ("person", pid) in vocab.extract(f"I saw {name} at the inn.", "gus")

@pytest.mark.parametrize("text, expected", [
    ("At Dawn on Day 2 at the Mill.", {("slot", "dawn"), ("day", 2), ("place", "mill")}),
    ("AT DAWN ON DAY 2 AT THE MILL.", {("slot", "dawn"), ("day", 2), ("place", "mill")}),
    ("at dawn on day 2 at the mill.", {("slot", "dawn"), ("day", 2), ("place", "mill")}),
    ("At MIDNIGHT, the Ninth Bell, near the River Path.", {("slot", "night"), ("place", "river path")}),
    ("A LANTERN and a Scream; the door was LOCKED.", {("item", "lantern"), ("sound", "scream"), ("state", "locked")}),
    ("On the Second Day at Sunset, FORTY silver.", {("day", 2), ("slot", "dusk"), ("num", 40), ("item", "silver")}),
])
def test_times_places_items_in_any_case(vocab, text, expected):
    assert vocab.extract(text) == expected
