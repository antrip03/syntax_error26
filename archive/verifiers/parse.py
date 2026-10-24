"""Parse a villager reply into claims (brief section 7.1). Never raises, whatever the model wrote.

Accepted shapes (after stripping surrounding whitespace):
    <answer>
    # optional in-character lines (ignored)
    CLAIM: <statement> [D3.S2]
    CLAIM: <statement> [D1.S4][H1]
    </answer>
or exactly  <abstain reason="not_in_records"/>

Strict on purpose (agreed with the team): any other non-empty line inside <answer> (free prose, a lowercase
"claim:", a <think> block) makes the whole reply unparsed, so nothing uncheckable can hide outside CLAIM lines.
An answer with no CLAIM line, or text outside the tags, is unparsed too. A CLAIM line without citations still
parses; the checker marks it bad_cite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ABSTAIN = '<abstain reason="not_in_records"/>'
_ID = r"[A-Z]\d+(?:\.S\d+)?"  # D3.S2, E1.S1, H2
_CITE_RE = re.compile(r"\[\s*(" + _ID + r"(?:\s*[,;]?\s*" + _ID + r")*)\s*\]")


@dataclass
class ParsedClaim:
    text: str
    cites: list[str]


@dataclass
class Parsed:
    ok: bool
    abstain: bool = False
    claims: list[ParsedClaim] = field(default_factory=list)
    error: str | None = None  # why parsing failed, for logs


def _claim(body: str) -> ParsedClaim:
    cites = [i for group in _CITE_RE.findall(body) for i in re.findall(_ID, group)]
    text = re.sub(r"\s+", " ", _CITE_RE.sub(" ", body)).strip()
    return ParsedClaim(text=text, cites=cites)


def parse(reply: str) -> Parsed:
    if not isinstance(reply, str):
        return Parsed(ok=False, error="not_text")
    t = reply.strip()
    if t == ABSTAIN:
        return Parsed(ok=True, abstain=True)
    if not (t.startswith("<answer>") and t.endswith("</answer>")):
        return Parsed(ok=False, error="no_answer_tags")
    inner = t[len("<answer>"): -len("</answer>")]
    if "<answer>" in inner or "</answer>" in inner:
        return Parsed(ok=False, error="nested_tags")
    claims = []
    for line in inner.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("CLAIM:"):
            return Parsed(ok=False, error="stray_text")
        claims.append(_claim(line[len("CLAIM:"):]))
    if not claims:
        return Parsed(ok=False, error="no_claims")
    return Parsed(ok=True, claims=claims)
