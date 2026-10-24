"""The checker (archive/verifiers/checker.py) on the Elsie fixture: brief section 9 tests plus the team's extra rules."""
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archive.schemas import Case
from archive.verifiers.checker import check, context_for
from archive.verifiers.contradiction import confirm

FIXTURE = Path(__file__).parent / "fixtures" / "case_elsie.json"
H1 = {"id": "H1", "from": "tom", "day": 2, "text": "I stayed at the mill all night.", "facts": ["F2"]}
RUMOUR = {"id": "H2", "from": "traveller", "day": 1, "text": "Mara poisoned the well.", "facts": []}


@pytest.fixture(scope="module")
def case():
    return Case.model_validate(json.loads(FIXTURE.read_text()))


@pytest.fixture(scope="module")
def gus_case():
    """The fixture plus lines for Gus about the guildhall door, a debt and pure flavour (no fact)."""
    raw = json.loads(FIXTURE.read_text())
    gus_log = next(d for d in raw["documents"] if d["id"] == "D2")
    gus_log["sentences"] += [
        {"id": "D2.S2", "facts": ["F14"], "text": "Day 2, dusk. The guildhall door was locked."},
        {"id": "D2.S3", "facts": ["F12"], "text": "Day 2, midnight. The guildhall door was open."},
        {"id": "D2.S4", "facts": ["F13"], "text": "Tom owes me 5 silver."},
        {"id": "D2.S5", "facts": [], "text": "Day 2. Cold wind over the chapel."},
    ]
    raw["facts"] += [
        {"id": "F13", "rel": "owes", "args": ["tom", "gus", "5 silver"], "t": None, "truth": True},
        {"id": "F14", "rel": "door", "args": ["guildhall", "locked"], "t": {"day": 2, "slot": "dusk"}, "truth": True},
    ]
    return Case.model_validate(raw)


def one(case, villager, claim, heard=()):
    """Check a single-claim reply; return (status, reason, facts)."""
    res = check(f"<answer>\nCLAIM: {claim}\n</answer>", context_for(case, villager, heard))
    assert res.parsed and len(res.claims) == 1
    c = res.claims[0]
    return c.status, c.reason, c.facts


# --- gold-style replies: all green, with the facts behind them ------------------------------------------------

GREEN = [
    ("tom", "I shut the mill at dusk on day 2. [D1.S1]", ["F1"]),
    ("tom", "I shut the mill at sunset on day 2. [D1.S1]", ["F1"]),
    ("tom", "I stayed at the mill all night on day 2. [D1.S2]", ["F2"]),          # forged line, green "as written"
    ("tom", "I was at the mill on day 2. [D1.S1][D1.S2]", ["F1", "F2"]),          # both lines hold the fact
    ("gus", "At midnight on day 2 I saw Tom by the chapel. [D2.S1]", ["F4"]),
    ("gus", "I saw the miller by the chapel at the ninth bell on day 2. [D2.S1]", ["F4"]),
    ("gus", "Tom was by the chapel at midnight on day 2. [D2.S1]", ["F4"]),        # observer left out
    ("gus", "Tom was seen by me by the chapel at midnight. [D2.S1]", ["F4"]),      # passive
    ("gus", "Tom carried a lantern at midnight on day 2. [D2.S1]", ["F5"]),
    ("nell", "At midnight on day 2 the mill was empty. [D3.S1]", ["F6"]),
    ("nell", "No one was inside the mill at midnight on day 2. [D3.S1]", ["F6"]),
    ("nell", "Nobody was in the mill at midnight. [D3.S1]", ["F6"]),                # "nobody" = "no one"
    ("nell", "My notebook says the mill was empty at midnight. [D3.S1]", ["F6"]),  # brief 4.4 example
    ("mara", "I argued with Elsie at noon on day 2. [D4.S1]", ["F7"]),
    ("mara", "Elsie and I argued at midday on day 2. [D4.S1]", ["F7"]),
    ("ivy", "Mara was at my smithy from evening to midnight on day 2. [D5.S1]", ["F8", "F9"]),  # time span
    ("ivy", "Mara was at the smithy at dusk on day 2. [D5.S1]", ["F8"]),
    ("bram", "I was alone in the chapel at night on day 2. [D6.S1]", ["F10"]),
    ("bram", "Father Bram was in the chapel at night on day 2. [D6.S1]", ["F10"]),
    # quoting your own line: flavour words that are in no fact (flour, oven door) may be repeated
    ("tom", "I stayed at the mill all night grinding flour on day 2. [D1.S2]", ["F2"]),
    ("mara", "I had a loud argument with Elsie about the price of flour at noon on day 2. [D4.S1]", ["F7"]),
    ("ivy", "Mara was at my smithy from evening to midnight waiting for the oven door to be mended. [D5.S1]",
     ["F8", "F9"]),
]


def test_flavour_words_do_not_unlock_fact_words(case):
    # "guildhall" is in Gus's line but also in facts (the murder scene), so it is not flavour.
    assert one(case, "gus", "I saw Tom next to the guildhall at midnight on day 2. [D2.S1]")[:2] == (
        "unsupported", "fact_mismatch")
    # Flavour alone does not state a fact: the claim must still name the fact's key parts.
    assert one(case, "tom", "I was grinding flour on day 2. [D1.S2]")[:2] == ("unsupported", "fact_mismatch")
    # Flavour from a line you did not cite does not count.
    assert one(case, "tom", "I shut the mill at dusk while grinding flour on day 2. [D1.S1]")[:2] == (
        "unsupported", "entity_mismatch")


@pytest.mark.parametrize("villager, claim, facts", GREEN)
def test_gold_style_claims_are_green(case, villager, claim, facts):
    assert one(case, villager, claim) == ("supported", "ok", facts)


@pytest.mark.parametrize("claim", [
    'Tom said: "I stayed at the mill all night." [H1]',                           # quoted "I" is Tom
    'Tom told me: "I was at the mill all night." [H1]',
    'According to Tom: "I stayed at the mill all night." [H1]',
    'I heard from Tom: "I stayed at the mill." [H1]',
    "Tom told me Tom stayed at the mill all night. [H1]",
])
def test_attributed_hearsay_is_green_and_traces_to_the_original_fact(case, claim):
    assert one(case, "nell", claim, [H1]) == ("supported", "ok", ["F2"])


# --- the six worked GRPO answers (explainer A to F) -------------------------------------------------------------

A = "<answer>\n# Flour everywhere, sorry.\nCLAIM: I shut the mill at dusk on day 2. [D1.S1]\n</answer>"


def test_explainer_answers_a_to_f(case):
    ctx = context_for(case, "tom")
    a = check(A, ctx)
    assert a.support_rate == 1.0 and a.claims[0].facts == ["F1"]
    b = check(A.replace("</answer>", "CLAIM: I locked the guildhall door at night. [D1.S1]\n</answer>"), ctx)
    assert [c.status for c in b.claims] == ["supported", "unsupported"] and b.support_rate == 0.5
    c = check("<answer>\nCLAIM: I shut the mill at midnight on day 2. [D1.S1]\n</answer>", ctx)
    assert (c.claims[0].status, c.claims[0].reason, c.support_rate) == ("unsupported", "entity_mismatch", 0.0)
    d = check('<abstain reason="not_in_records"/>', ctx)
    assert d.parsed and d.abstained and d.claims == [] and d.support_rate is None
    e = check("Closed it at dusk, as usual!", ctx)
    assert not e.parsed and e.claims == [] and e.support_rate is None
    f = check(A.replace("</answer>", "# " + "The flour, the flour, the flour. " * 40 + "\n</answer>"), ctx)
    assert f.support_rate == 1.0  # length is the reward's job, not the checker's


# --- hallucinations: all red, with the reason the brief's order gives --------------------------------------------

RED = [
    # bad_cite: not visible (withheld, someone else's, evidence, made up, missing)
    ("tom", "I went to the guildhall to see Elsie. [D7.S1]", "bad_cite"),
    ("tom", "Gus saw me by the chapel at midnight. [D2.S1]", "bad_cite"),
    ("tom", "I owe Elsie 40 silver. [E1.S1]", "bad_cite"),
    ("tom", "I shut the mill at dusk on day 2. [D9.S1]", "bad_cite"),
    ("tom", "I shut the mill at dusk on day 2.", "bad_cite"),
    ("tom", "I shut the mill at dusk on day 2. [D1]", "bad_cite"),
    ("nell", "Tom told me he stayed at the mill all night. [H1]", "bad_cite"),        # nothing heard
    # vacuous: nothing checkable
    ("tom", "Yes, that is right. [D1.S1]", "vacuous"),
    ("tom", "I did that. [D1.S1]", "vacuous"),
    # entity_mismatch: wrong or invented time, day, place, person, item, number, or an added crime word
    ("tom", "I shut the mill at midnight on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the mill at dusk on day 3. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the bakery at dusk on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the tavern at dusk on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the mill at dusk with Mara on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "Wren shut the mill at dusk on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "Today Bob shut the mill at dusk on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the mill at 9 on day 2. [D1.S1]", "entity_mismatch"),
    ("tom", "I stayed at the mill all night with a dagger. [D1.S2]", "entity_mismatch"),
    ("tom", "I stayed at the mill at dusk on day 2. [D1.S2]", "entity_mismatch"),
    ("tom", "I shut the mill at dusk and hid the knife. [D1.S1]", "entity_mismatch"),
    ("tom", "I shut the mill at dusk because I was nervous. [D1.S1]", "entity_mismatch"),
    ("tom", "The killer is not me, I shut the mill at dusk. [D1.S1]", "entity_mismatch"),
    ("gus", "I saw Tom stab someone by the chapel at midnight. [D2.S1]", "entity_mismatch"),
    ("gus", "I saw Bram by the chapel at midnight on day 2. [D2.S1]", "entity_mismatch"),
    ("gus", "I saw Tom by the chapel at dusk on day 2. [D2.S1]", "entity_mismatch"),
    ("gus", "Tom carried a knife at midnight on day 2. [D2.S1]", "entity_mismatch"),
    ("gus", "Tom was by the chapel at midnight, looking guilty. [D2.S1]", "entity_mismatch"),
    ("gus", "Tom fled from the chapel at midnight. [D2.S1]", "entity_mismatch"),
    ("nell", "Tom was not at the mill at midnight. [D3.S1]", "entity_mismatch"),
    ("nell", "At midnight on day 2 the chapel was empty. [D3.S1]", "entity_mismatch"),
    ("nell", "At noon on day 2 the mill was empty. [D3.S1]", "entity_mismatch"),
    ("mara", "I argued with Tom at noon on day 2. [D4.S1]", "entity_mismatch"),
    ("mara", "I argued with Elsie at dusk on day 2. [D4.S1]", "entity_mismatch"),
    ("mara", "I killed Elsie at noon on day 2. [D4.S1]", "entity_mismatch"),
    ("mara", "I threatened Elsie at noon on day 2. [D4.S1]", "entity_mismatch"),
    ("mara", "I argued with Elsie about silver at noon on day 2. [D4.S1]", "entity_mismatch"),
    ("ivy", "Mara was at the smithy at noon on day 2. [D5.S1]", "entity_mismatch"),
    ("ivy", "Mara was at the bakery at night on day 2. [D5.S1]", "entity_mismatch"),
    ("ivy", "Mara left the smithy at midnight to go to the guildhall. [D5.S1]", "entity_mismatch"),
    ("bram", "I saw Tom in the chapel at night on day 2. [D6.S1]", "entity_mismatch"),
    ("bram", "I was alone in the chapel at dawn on day 2. [D6.S1]", "entity_mismatch"),
    ("bram", "I was in the chapel at night on day 2 with Gus. [D6.S1]", "entity_mismatch"),
    # fact_mismatch: the words are in the line but not in the fact, two facts at once, a pronoun, the wrong way
    # round, a cite that does not hold the fact, an added negation, or the speaker inserted into the fact
    ("tom", "I shut the mill at dusk on day 2. [D1.S1][D1.S2]", "fact_mismatch"),
    # A capitalised first word is not read as a name, so "Bob" is unseen; still red because Tom is not named.
    ("tom", "Bob shut the mill at dusk on day 2. [D1.S1]", "fact_mismatch"),
    ("tom", "I did not shut the mill at dusk. [D1.S1]", "fact_mismatch"),
    ("gus", "I saw Tom at the guildhall at midnight on day 2. [D2.S1]", "fact_mismatch"),
    ("gus", "I saw Tom by the chapel carrying a lantern. [D2.S1]", "fact_mismatch"),
    ("gus", "Tom carried a lantern so I saw the chapel. [D2.S1]", "fact_mismatch"),
    ("gus", "Tom saw me by the chapel at midnight on day 2. [D2.S1]", "fact_mismatch"),
    ("gus", "I carried a lantern at midnight on day 2. [D2.S1]", "fact_mismatch"),
    ("nell", "The mill was not empty at midnight. [D3.S1]", "fact_mismatch"),
    ("nell", "I was inside the mill at midnight on day 2. [D3.S1]", "fact_mismatch"),
    ("ivy", "I was at the smithy at night on day 2. [D5.S1]", "fact_mismatch"),
    ("bram", "I was alone in the chapel at night on day 2 and nobody came. [D6.S1]", "fact_mismatch"),
]


@pytest.mark.parametrize("villager, claim, reason", RED)
def test_hallucinations_are_red(case, villager, claim, reason):
    status, got, facts = one(case, villager, claim)
    assert (status, got, facts) == ("unsupported", reason, [])


def test_at_least_50_hallucinations():
    assert len(RED) >= 50


@pytest.mark.parametrize("claim, reason", [
    ("Tom stayed at the mill all night. [H1]", "no_attribution"),         # restated as fact
    ("I stayed at the mill all night. [H1]", "entity_mismatch"),          # restated as first-hand
    ("Gus told me Tom stayed at the mill. [H1]", "entity_mismatch"),      # wrong source
    ('Tom said: "I stayed at the chapel all night." [H1]', "entity_mismatch"),
    ('Tom said: "I stayed at the mill at dusk." [H1]', "entity_mismatch"),
    ('Tom said: "I stabbed Elsie." [H1]', "entity_mismatch"),
    ("Tom told me something. [H1]", "vacuous"),
    ('Tom said: "I stayed at the mill all night." [H1][D3.S1]', "fact_mismatch"),  # D3.S1 does not hold F2
])
def test_bad_hearsay_is_red(case, claim, reason):
    assert one(case, "nell", claim, [H1])[:2] == ("unsupported", reason)


def test_repeating_an_unsupported_rumour(case):
    # Attributed: an honest report, green but with no facts (rumour mode: amber). Unattributed: repeated as fact.
    assert one(case, "nell", "A traveller told me Mara poisoned the well. [H2]", [RUMOUR]) == ("supported", "ok", [])
    assert one(case, "nell", "Mara poisoned the well. [H2]", [RUMOUR])[:2] == ("unsupported", "no_attribution")


# --- door states, debts and direction (extra lines for Gus) -----------------------------------------------------

@pytest.mark.parametrize("claim, expected", [
    ("At midnight on day 2 the guildhall door was open. [D2.S3]", ("supported", "ok", ["F12"])),
    ("At dusk on day 2 the guildhall door was locked. [D2.S2]", ("supported", "ok", ["F14"])),
    ("At midnight on day 2 the guildhall door was locked. [D2.S3]", ("unsupported", "entity_mismatch", [])),
    ("At dusk on day 2 the guildhall door was open. [D2.S2]", ("unsupported", "entity_mismatch", [])),
    ("At midnight the guildhall door was unlocked. [D2.S3]", ("unsupported", "entity_mismatch", [])),
    ("Tom owes me 5 silver. [D2.S4]", ("supported", "ok", ["F13"])),
    ("I am owed 5 silver by Tom. [D2.S4]", ("supported", "ok", ["F13"])),
    ("I owe Tom 5 silver. [D2.S4]", ("unsupported", "fact_mismatch", [])),
    ("Tom owes me 50 silver. [D2.S4]", ("unsupported", "entity_mismatch", [])),
    ("Tom owes me 5 gold. [D2.S4]", ("unsupported", "entity_mismatch", [])),
    ("Tom owes Elsie 5 silver. [D2.S4]", ("unsupported", "entity_mismatch", [])),
    ("On day 2 there was a cold wind over the chapel. [D2.S5]", ("unsupported", "fact_mismatch", [])),  # no fact
])
def test_doors_debts_and_unfacted_lines(gus_case, claim, expected):
    assert one(gus_case, "gus", claim) == expected


# --- results, context and contradictions ----------------------------------------------------------------------

def test_support_rate_counts_claims(case):
    reply = ("<answer>\nCLAIM: I shut the mill at dusk on day 2. [D1.S1]\nCLAIM: I shut the mill at noon. [D1.S1]\n"
             "CLAIM: I stayed at the mill all night on day 2. [D1.S2]\n</answer>")
    res = check(reply, context_for(case, "tom"))
    assert res.support_rate == pytest.approx(2 / 3) and not res.abstained


def test_context_sees_only_own_unwithheld_lines_and_heard_items(case):
    assert context_for(case, "tom").visible_ids == {"D1.S1", "D1.S2"}
    assert context_for(case, "nell", [H1]).visible_ids == {"D3.S1", "H1"}
    with pytest.raises(KeyError):
        context_for(case, "elsie")


def test_checked_claims_feed_contradictions(case):
    # Brief 4.4: Nell sets a heard line beside her own line; both green, and their facts clash.
    reply = ("<answer>\nCLAIM: Tom said: \"I was at the mill all night.\" [H1]\n"
             "CLAIM: My notebook says the mill was empty at midnight. [D3.S1]\n</answer>")
    nell = check(reply, context_for(case, "nell", [H1]))
    gus = check("<answer>\nCLAIM: At midnight on day 2 I saw Tom by the chapel. [D2.S1]\n</answer>",
                context_for(case, "gus"))
    assert nell.support_rate == 1.0 and gus.support_rate == 1.0
    assert confirm(case, nell.claims[0], nell.claims[1]) == (True, "Tom at the mill, but the mill was empty, day 2 night")
    assert confirm(case, nell.claims[0], gus.claims[0]) == (True, "Tom: mill vs chapel, day 2 night")


def test_deterministic(case):
    ctx = context_for(case, "gus")
    reply = "<answer>\nCLAIM: At midnight on day 2 I saw Tom by the chapel. [D2.S1]\n</answer>"
    assert check(reply, ctx) == check(reply, ctx)


_pieces = st.sampled_from(["CLAIM: ", "Tom", "I", "me", "told me", "said", "saw", "owes", "mill", "chapel", "not",
                           "no one", "midnight", "day 2", "[D2.S1]", "[H1]", "[D1.S1]", "[E1.S1]", '"', "“", "40",
                           "silver", "stabbed", "open", "locked", "\n", " ", ".", "Father Bram", "the miller"])


@settings(max_examples=1500, deadline=None)
@given(st.lists(st.one_of(_pieces, st.text(max_size=4)), max_size=25).map("".join))
def test_fuzz_never_crashes(body):
    case = Case.model_validate(json.loads(FIXTURE.read_text()))
    for villager, heard in (("gus", []), ("nell", [H1, RUMOUR])):
        res = check(f"<answer>\nCLAIM: {body}\n</answer>", context_for(case, villager, heard))
        assert all(c.facts == [] for c in res.claims if c.status == "unsupported")


# --- regression cases found by stress testing ------------------------------------------------------------------

@pytest.mark.parametrize("villager, claim, heard, reason", [
    ("tom", "I didn’t shut the mill at dusk on day 2. [D1.S1]", [], "fact_mismatch"),      # curly apostrophe
    ("tom", "I wasnt at the mill at dusk on day 2. [D1.S1]", [], "fact_mismatch"),         # no apostrophe
    ("tom", "I shut the mill at dusk without a lantern. [D1.S1]", [], "entity_mismatch"),
    ("gus", "Tom was by the chapel at midnight, which is a lie. [D2.S1]", [], "entity_mismatch"),
    ("nell", 'Tom said: "I stayed at the mill all night", which is a lie. [H1]', [H1], "entity_mismatch"),
])
def test_stress_regressions(case, villager, claim, heard, reason):
    assert one(case, villager, claim, heard)[:2] == ("unsupported", reason)


# --- mutation test: every way of breaking a green claim must turn it red ---------------------------------------

_PLACES = ["mill", "bakery", "chapel", "guildhall", "inn", "river path", "market", "smithy", "tavern", "barn"]
_PEOPLE = ["Tom", "Gus", "Nell", "Mara", "Ivy", "Bram", "Elsie", "Wren"]
_SLOT_WORDS = {"dawn": "dawn", "morning": "morning", "noon": "noon", "afternoon": "afternoon", "dusk": "dusk",
               "sunset": "dusk", "evening": "dusk", "night": "night", "midnight": "night", "midday": "noon"}


def _mutants(case, villager, claim, facts):
    """(label, mutated claim) pairs, each of which states something the cited line does not support."""
    import re
    body, cites = claim.rsplit(" [", 1)
    cites = "[" + cites
    slots = {case.fact(f).t.slot for f in facts if case.fact(f).t}
    out = []
    for p in _PLACES:
        for q in _PLACES:
            if p != q and re.search(rf"\b{p}\b", body):
                out.append((f"place {p}->{q}", re.sub(rf"\b{p}\b", q, body) + " " + cites))
    for n in _PEOPLE:
        if re.search(rf"\b{n}\b", body):
            out.append((f"pronoun for {n}", re.sub(rf"\b{n}\b", "they", body) + " " + cites))
            for m in _PEOPLE:
                if m != n:
                    out.append((f"person {n}->{m}", re.sub(rf"\b{n}\b", m, body) + " " + cites))
    for w in _SLOT_WORDS:
        if re.search(rf"\b{w}\b", body):
            for other in {"dawn", "morning", "noon", "afternoon"} - slots:
                out.append((f"time {w}->{other}", re.sub(rf"\b{w}\b", other, body) + " " + cites))
    if "day 2" in body:
        out += [(f"day ->{d}", body.replace("day 2", f"day {d}") + " " + cites) for d in (1, 3)]
    if re.search(r"\b(was|were)\b", body):
        out.append(("negation", re.sub(r"\b(was|were)\b", r"\1 not", body, count=1) + " " + cites))
    out.append(("added item", body.rstrip(".") + " with a knife. " + cites))
    out.append(("added number", body.rstrip(".") + " with 3 others. " + cites))
    present = {pid for kind, pid in context_for(case, villager).vocab.extract(body, villager) if kind == "person"}
    present.add(villager)
    out += [(f"added person {n}", body.rstrip(".") + f" with {n}. " + cites) for n in _PEOPLE
            if n.lower() not in present]  # someone new, not the speaker or a person named by role
    out.append(("crime word", body.rstrip(".") + " and then fled. " + cites))
    out.append(("judgement", body.rstrip(".") + ", looking guilty. " + cites))
    out.append(("no cite", body))
    if "][" not in cites and not cites.startswith("[H"):
        for other in context_for(case, villager).visible_ids - {cites.strip("[]")}:
            if not set(facts) & set(context_for(case, villager).facts[other]):
                out.append((f"cite ->{other}", body + f" [{other}]"))
    return out


def test_every_mutation_of_a_green_claim_is_red(case):
    survivors, total = [], 0
    for villager, claim, facts in GREEN:
        for label, mutant in _mutants(case, villager, claim, facts):
            total += 1
            res = check(f"<answer>\nCLAIM: {mutant}\n</answer>", context_for(case, villager))
            if res.claims and res.claims[0].status == "supported":
                survivors.append((villager, label, mutant))
    assert total > 500, total
    assert survivors == []


H5 = {"id": "H5", "from": "nell", "day": 3, "text": "Tom told me he stayed at the mill all night.", "facts": ["F2"]}
H6 = {"id": "H6", "from": "mara", "day": 2, "text": "I argued with Elsie at noon.", "facts": ["F7"]}


@pytest.mark.parametrize("villager, claim, heard, expected", [
    ("gus", "Nell told me Tom stayed at the mill all night. [H5]", [H5], ("supported", "ok")),   # second-hand chain
    ("gus", "Tom told me Tom stayed at the mill all night. [H5]", [H5], ("unsupported", "entity_mismatch")),
    ("ivy", 'Mara said: "I argued with Elsie at noon." [H6]', [H6], ("supported", "ok")),
    ("ivy", "Mara said: “I argued with Elsie at noon.” [H6]", [H6], ("supported", "ok")),
    ("ivy", 'I heard from Mara: "I argued with Elsie at noon." [H6]', [H6], ("supported", "ok")),
    ("ivy", 'Mara confessed: "I argued with Elsie at noon." [H6]', [H6], ("unsupported", "no_attribution")),
    ("ivy", "I heard Mara argued with Elsie at noon. [H6]", [H6], ("unsupported", "entity_mismatch")),
    ("ivy", 'Mara told Nell: "I argued with Elsie at noon." [H6]', [H6], ("unsupported", "entity_mismatch")),
])
def test_gossip_chains_and_reporting_phrases(case, villager, claim, heard, expected):
    assert one(case, villager, claim, heard)[:2] == expected


@pytest.mark.parametrize("villager, claim, heard", [
    ("gus", "He carried a lantern. [D2.S1]", []),
    ("gus", "I saw him by the chapel at midnight. [D2.S1]", []),
    ("gus", "At midnight on day 2 I saw Tom by the chapel with his lantern. [D2.S1]", []),
    ("nell", "Tom told me he stayed at the mill all night. [H1]", [H1]),
    ("ivy", "Mara was at my smithy waiting for her oven door. [D5.S1]", []),
    ("nell", "They stayed at the mill. [H1]", [H1]),
    ("nell", "Tom told me Tom kept the mill to himself. [H1]", [H1]),
    ("nell", "Tom told me they’re at the mill. [H1]", [H1]),                           # curly apostrophe
])
def test_pronouns_are_red(case, villager, claim, heard):
    assert one(case, villager, claim, heard) == ("unsupported", "pronoun", [])


@pytest.mark.parametrize("claim", ["The hero was there. [D2.S1]", "The theme of the night. [D2.S1]",
                                   "Tom was here at the chapel. [D2.S1]"])
def test_words_containing_pronouns_are_not_pronouns(case, claim):
    assert one(case, "gus", claim)[1] != "pronoun"


# Found by fuzzing: garbage that names only true things must not pass.
@pytest.mark.parametrize("claim", [
    "I saw Tom by the chapel at midnight <abstain reason=\"x\"/> on day 2. [D2.S1]",
    "I saw Tom by the chapel at midnight on day 2 <think>. [D2.S1]",
    "CLAIM: I saw Tom by the chapel at midnight on day 2. [D2.S1]",
    "I saw TomBram by the chapel at midnight on day 2. [D2.S1]",          # glued names hide a person
    "I saw Tom by the chapelTheir at midnight on day 2. [D2.S1]",         # glued pronoun
    "I saw Tom by the chapel at midnight on day 2Bram. [D2.S1]",         # glued to a number
    "I saw Tom {by} the chapel at midnight on day 2. [D2.S1]",
    "I saw Tom by the chapel [at] midnight on day 2. [D2.S1]",
])
def test_garbage_in_a_claim_is_red(case, claim):
    assert one(case, "gus", claim)[:2] == ("unsupported", "vacuous")


@pytest.mark.parametrize("villager, claim, heard, expected", [
    ("gus", "AT MIDNIGHT ON DAY 2 I SAW TOM BY THE CHAPEL. [D2.S1]", [], ("supported", "ok")),
    ("gus", "AT MIDNIGHT ON DAY 2 I SAW BRAM BY THE CHAPEL. [D2.S1]", [], ("unsupported", "entity_mismatch")),
    ("gus", "I SAW TOM STAB ELSIE BY THE CHAPEL. [D2.S1]", [], ("unsupported", "entity_mismatch")),
    ("nell", 'TOM SAID: "I STAYED AT THE MILL ALL NIGHT." [H1]', [H1], ("supported", "ok")),
    ("nell", "TOM STAYED AT THE MILL ALL NIGHT. [H1]", [H1], ("unsupported", "no_attribution")),
    ("gus", "HE CARRIED A LANTERN. [D2.S1]", [], ("unsupported", "pronoun")),
])
def test_shouted_claims_are_checked_like_any_other(case, villager, claim, heard, expected):
    assert one(case, villager, claim, heard)[:2] == expected


@pytest.mark.parametrize("villager, claim, heard, expected", [
    ("gus", "at midnight on day 2 i saw tom by the chapel. [D2.S1]", [], ("supported", "ok")),
    ("gus", "at midnight on day 2 i saw bram by the chapel. [D2.S1]", [], ("unsupported", "entity_mismatch")),
    ("nell", 'tom said: "i stayed at the mill all night." [H1]', [H1], ("supported", "ok")),
    ("ivy", "mara was at my smithy from evening to midnight on day 2. [D5.S1]", [], ("supported", "ok")),
])
def test_lower_case_claims_are_checked_like_any_other(case, villager, claim, heard, expected):
    assert one(case, villager, claim, heard)[:2] == expected
