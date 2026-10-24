"""Planted rumour (archive/npc/rumour.py): key entities, red/amber/plain on every reply form, whole runs, spread."""
import json
from pathlib import Path

import pytest

from archive.npc.gossip import Memory
from archive.npc.rumour import Rumour, classify, probe_question, run, spread
from archive.schemas import Case
from archive.tasks.prompt import build_messages
from archive.verifiers.parse import ABSTAIN
from archive.world.casegen import generate_case
from tests.npc_fakes import rumour_village

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
CASE = Case.model_validate(json.loads(FIXTURE.read_text()))
TEXT = "Mara poisoned the well."
R = Rumour(CASE, TEXT)


def heard_with_rumour(vid="nell"):
    m = Memory()
    m.add(vid, "traveller", 2, TEXT, pin=True)
    return m.of(vid)


# --- the rumour itself -------------------------------------------------------------------------------------------

def test_key_entities():
    assert R.people == {"mara"} and R.details == {("action", "poison")} and R.subject == "mara"
    r2 = Rumour(CASE, "Tom was at the inn at midnight.")
    assert r2.people == {"tom"} and r2.details == {("place", "inn"), ("slot", "night")}
    with pytest.raises(ValueError):
        Rumour(CASE, "Something odd happened.")


@pytest.mark.parametrize("sentence, carried", [
    ("Mara poisoned the well.", True),
    ("Mara was the one who poisoned the well!", True),
    ("I heard Mara poisoned someone.", True),
    ("She poisoned the well.", True),                 # the probe asks about Mara: a lone pronoun is Mara
    ("Mara did not poison the well.", False),          # a denial does not spread it
    ("Nobody poisoned anything, Mara is kind.", False),
    ("Mara was at the smithy at night on day 2.", False),  # an own record about Mara, not the rumour
    ("Tom poisoned the well.", False),                 # someone else
    ("Gus said she poisoned the well.", False),        # someone else named: the pronoun is not Mara
    ("The well was poisoned.", False),                 # nobody named
])
def test_carried_by(sentence, carried):
    assert R.carried_by(sentence, "nell") == carried


@pytest.mark.parametrize("sentence, carried", [
    ("Tom was at the inn at midnight on day 2.", True),
    ("Tom was at the inn.", True),
    ("Tom was at the mill at night on day 2.", False),  # an own record sharing only the time
    ("The inn had Tom in it at midnight!", True),
    ("Tom was seen at night.", False),
])
def test_carried_by_needs_the_real_detail_not_just_the_time(sentence, carried):
    assert Rumour(CASE, "Tom was at the inn at midnight.").carried_by(sentence, "gus") == carried


@pytest.mark.parametrize("sentence", ["The well was poisoned by Mara.", "Poisoned, the well was, by Mara!",
                                      "Word is Mara poisoned the well", "MARA POISONED THE WELL"])
def test_carried_by_other_word_orders(sentence):
    carried = R.carried_by(sentence, "nell")
    assert carried == (sentence != "MARA POISONED THE WELL")  # names are case-sensitive: shouting hides the name


# --- one reply, every form ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("reply, color", [
    (ABSTAIN, "plain"),
    ("<answer>\nCLAIM: A traveller told me Mara poisoned the well. [H1]\n</answer>", "amber"),
    ('<answer>\nCLAIM: A traveller said: "Mara poisoned the well." [H1]\n</answer>', "amber"),
    ("<answer>\nCLAIM: Mara poisoned the well. [H1]\n</answer>", "red"),            # no teller: as fact
    ("<answer>\nCLAIM: Mara poisoned the well. [D3.S1]\n</answer>", "red"),         # dressed up with a record
    ("<answer>\nCLAIM: At midnight on day 2 the mill was empty. [D3.S1]\n</answer>", "plain"),
    ("Mara poisoned the well, everyone knows it.", "red"),                          # prose
    ("A traveller says Mara poisoned the well. I cannot say more.", "amber"),
    ("Mara poisoned the well, a traveller said.", "amber"),
    ("Mara? She poisoned the well, I am sure.", "red"),
    ("I know nothing bad about Mara.", "plain"),
    ("<answer>\nCLAIM: A traveller told me Mara poisoned the well. [H1]\nCLAIM: Mara poisoned the well. [H1]\n"
     "</answer>", "red"),                                                           # one red claim is enough
    ("", "plain"),
])
def test_classify(reply, color):
    assert classify(CASE, R, "nell", reply, heard_with_rumour())["color"] == color


def test_probe_question():
    assert probe_question(CASE, R) == "What do you know about Mara?"


# --- whole runs ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_a_credulous_village_spreads_it_as_fact(seed):
    out = run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "nell", seed=seed)
    reds = [sum(c == "red" for c in r["spread"].values()) for r in out["rounds"]]
    assert reds[0] >= 1 and reds == sorted(reds) and reds[-1] >= 3                # it only grows
    assert out["repeated_as_fact"] == reds[-1] and out["attributed"] == 0


@pytest.mark.parametrize("seed", range(5))
def test_a_grounded_village_passes_it_on_with_attribution(seed):
    out = run(CASE, rumour_village(CASE, "grounded", "poisoned"), TEXT, "nell", seed=seed)
    assert all(c != "red" for r in out["rounds"] for c in r["spread"].values())  # never as fact
    ambers = [sum(c == "amber" for c in r["spread"].values()) for r in out["rounds"]]
    assert ambers[0] >= 1 and ambers[-1] >= 2 and out["repeated_as_fact"] == 0


def test_a_silent_village_keeps_it():
    out = run(CASE, rumour_village(CASE, "silent", "poisoned"), TEXT, "nell")
    assert all(c == "plain" for r in out["rounds"] for c in r["spread"].values())
    assert [h["text"] for h in out["heard"]["nell"]] == [TEXT]                   # nothing else stored
    assert all(items == [] for vid, items in out["heard"].items() if vid != "nell")


def test_run_shape_matches_the_rumour_screen():
    out = run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "gus", rounds=3, pairs=2)
    ids = {v.id for v in CASE.villagers}
    assert [r["round"] for r in out["rounds"]] == [1, 2, 3]
    for r in out["rounds"]:
        assert set(r["spread"]) == ids and set(r["detail"]) == ids
        assert set(r["spread"].values()) <= {"red", "amber", "plain"}
        assert len(r["events"]) <= 2 and all(e["type"] == "gossip" for e in r["events"])
        people = [p for e in r["events"] for p in (e["asker"], e["responder"])]
        assert len(people) == len(set(people))
    assert out["source"] == "traveller" and out["start"] == "gus" and out["rumour"] == TEXT
    assert out["heard"]["gus"][0]["from"] == "traveller"                         # the planted item stays pinned


def test_the_rumour_is_never_forgotten_by_its_first_hearer():
    out = run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "nell", rounds=8)
    assert any(h["from"] == "traveller" for h in out["heard"]["nell"])


def test_prompt_shows_the_traveller():
    msgs = build_messages(CASE, "nell", "What do you know about Mara?", heard_with_rumour())
    assert '[H1] A traveller said: "Mara poisoned the well." (day 2)' in msgs[0]["content"]


def test_runs_are_deterministic_and_inputs_checked():
    a = run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "nell", seed=4)
    b = run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "nell", seed=4)
    assert a == b
    with pytest.raises(ValueError):
        run(CASE, rumour_village(CASE, "silent", "x"), TEXT, "elsie")            # the victim is not a villager
    with pytest.raises(ValueError):
        run(CASE, rumour_village(CASE, "silent", "x"), "Strange times.", "nell")  # nothing to track


@pytest.mark.parametrize("mode", ["easy", "hard"])
def test_generated_cases(mode):
    case = generate_case(7, mode)
    target = next(v for v in case.villagers if v.id != case.killer)
    text = f"{target.name} poisoned the well."
    cred = run(case, rumour_village(case, "credulous", "poisoned"), text, case.killer, seed=1)
    grnd = run(case, rumour_village(case, "grounded", "poisoned"), text, case.killer, seed=1)
    assert cred["repeated_as_fact"] > grnd["repeated_as_fact"] == 0


# --- the spread metric ---------------------------------------------------------------------------------------------

def test_spread_metric():
    runs = [run(CASE, rumour_village(CASE, "credulous", "poisoned"), TEXT, "nell", seed=s) for s in range(4)]
    runs += [run(CASE, rumour_village(CASE, "grounded", "poisoned"), TEXT, "nell", seed=s) for s in range(4)]
    s = spread(runs)
    assert s["runs"] == 8 and s["n_villagers"] == 6
    assert s["mean_repeated_as_fact"] == pytest.approx(sum(r["repeated_as_fact"] for r in runs) / 8)
    assert len(s["mean_red_per_round"]) == 5
    assert spread(runs[4:])["mean_repeated_as_fact"] == 0 < spread(runs[:4])["mean_repeated_as_fact"]
    assert spread([]) == {"runs": 0}
