"""Reply parser (archive/verifiers/parse.py): strict format, never crashes."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archive.verifiers.parse import ABSTAIN, parse


def test_answer_with_persona_line_and_claims():
    p = parse("<answer>\n# Ninth bell.\nCLAIM: At midnight on day 2 I saw Tom by the chapel. [D2.S1]\n"
              "CLAIM: He carried a lantern. [D2.S1]\n</answer>")
    assert p.ok and not p.abstain
    assert [(c.text, c.cites) for c in p.claims] == [
        ("At midnight on day 2 I saw Tom by the chapel.", ["D2.S1"]), ("He carried a lantern.", ["D2.S1"])]


@pytest.mark.parametrize("line, text, cites", [
    ("CLAIM: Two sources. [D1.S4][D3.S1]", "Two sources.", ["D1.S4", "D3.S1"]),
    ("CLAIM: Comma list. [D1.S4, D3.S1]", "Comma list.", ["D1.S4", "D3.S1"]),
    ("CLAIM: Tom told me so [H1] and I agree.", "Tom told me so and I agree.", ["H1"]),
    ("CLAIM: Evidence. [E1.S1]", "Evidence.", ["E1.S1"]),
    ("CLAIM: No citation at all.", "No citation at all.", []),                # parses; checker marks bad_cite
    ("CLAIM: Not an id [see above].", "Not an id [see above].", []),
])
def test_citations(line, text, cites):
    p = parse(f"<answer>\n{line}\n</answer>")
    assert p.ok and (p.claims[0].text, p.claims[0].cites) == (text, cites)


def test_one_line_answer_and_surrounding_whitespace():
    p = parse("  <answer>CLAIM: I shut the mill at dusk on day 2. [D1.S1]</answer>\n")
    assert p.ok and p.claims[0].cites == ["D1.S1"]


def test_abstain_exact():
    p = parse(f"\n{ABSTAIN}\n")
    assert p.ok and p.abstain and p.claims == []


@pytest.mark.parametrize("reply, error", [
    ("Closed it at dusk, as usual!", "no_answer_tags"),                                        # answer E
    ("<answer>\nCLAIM: I saw Tom. [D2.S1]\nI think he was up to no good.\n</answer>", "stray_text"),
    ("<answer>\nclaim: lowercase. [D1.S1]\n</answer>", "stray_text"),
    ("<answer>\n# only a persona line\n</answer>", "no_claims"),
    ("<answer>\n</answer>", "no_claims"),
    ("<answer>\nCLAIM: cut off mid", "no_answer_tags"),                                       # truncated
    ("<think>hmm</think>\n<answer>\nCLAIM: x [D1.S1]\n</answer>", "no_answer_tags"),
    ("<answer>\nCLAIM: x [D1.S1]\n</answer>\nAnything else?", "no_answer_tags"),              # text after tags
    ("<answer><answer>CLAIM: x [D1.S1]</answer></answer>", "nested_tags"),
    ("<abstain/>", "no_answer_tags"),                                                         # not the exact form
    ('<abstain reason="not_in_records"/> Sorry!', "no_answer_tags"),
    ("", "no_answer_tags"),
])
def test_unparsed(reply, error):
    p = parse(reply)
    assert not p.ok and p.error == error and p.claims == []


def test_non_string_input():
    assert not parse(None).ok and not parse(42).ok


_pieces = st.sampled_from(["<answer>", "</answer>", "CLAIM:", "# ", "[D1.S1]", "[H1]", "[", "]", "\n", " ", ABSTAIN,
                           "Tom", "mill", "\x00", "[D1.S1, ", "<abstain", "💀"])


@settings(max_examples=2000, deadline=None)
@given(st.one_of(st.text(), st.lists(st.one_of(_pieces, st.text(max_size=5)), max_size=30).map("".join)))
def test_fuzz_never_crashes(reply):
    p = parse(reply)
    assert isinstance(p.ok, bool)
    if p.ok and not p.abstain:
        assert p.claims and all(isinstance(c.text, str) and isinstance(c.cites, list) for c in p.claims)
