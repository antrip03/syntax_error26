"""The checker (brief section 9): colours every claim in a villager reply. Deterministic, no models, no network.

It is the reward signal for GRPO, the data filter, the eval metric and the game's badges, so a lie marked green
teaches the model to lie. When in doubt it marks red: gold replies are written by our own code and always pass.

Each claim runs these tests in order; the first failure makes it red with that reason:
1. bad_cite         every cited id is visible to the villager (own non-withheld sentences + heard H ids)
2. vacuous          the claim names something checkable besides the speaker and whoever told them
3. entity_mismatch  every name, place, item, sound, door state, day, time and number is in the cited lines,
                    and no crime action or judgement ("stabbed", "fled", "guilty") is added
4. fact_mismatch    the claim states ONE cited fact (a fact over a time span counts as one), with its key people
                    and places named (no pronouns), each cited line holds that fact, who-did-what is the right
                    way round for `saw` and `owes`, and every negation word is also in the cited lines
5. no_attribution   a hearsay claim (cites an H id) says who told them: "<name> told me" / "<name> said" / ...
Flavour words (agreed with the team): a word in the cited line that is in NO fact anywhere in the case ("grinding
flour", "her oven door") may be repeated, so quoting your own line works. Words that are in some fact must still
match the line's fact: Gus's line mentions the guildhall, but "I saw Tom at the guildhall" stays red.
A supported claim carries the facts behind it, which is what contradiction checking uses. A heard item that was
itself unsupported has no facts: repeating it with attribution is green but carries no facts (brief 4.4, 4.7).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from archive.schemas import RELATIONS, Case, CheckResult, ClaimResult, Fact, HeardItem
from archive.verifiers.parse import ParsedClaim, parse
from archive.world.lexicon import Entity, Vocab, actions, negations, vocab_for

# Entity kind for each argument role of RELATIONS; "amount" is read as text ("40 silver" -> 40 and silver).
ARG_KIND = {"person": "person", "observer": "person", "debtor": "person", "creditor": "person", "other": "person",
            "place": "place", "item": "item", "sound": "sound", "state": "state"}
# Roles a claim must name for each relation; the others (observer, a debt's amount, ...) may be left out.
CORE = {"at": ("person", "place"), "saw": ("person", "place"), "heard": ("sound",), "carried": ("person", "item"),
        "owns": ("person", "item"), "owes": ("debtor", "creditor"), "argued": ("person", "other"),
        "door": ("place", "state"), "empty": ("place",)}
# Relations with a direction: (subject role, object role, verb, passive form).
DIRECTED = {
    "saw": ("observer", "person", re.compile(r"\b(saw|seen|sees|see|spotted|watched|noticed)\b", re.I),
            re.compile(r"\b(?:am|was|were|been|being|is|are)\s+(?:\w+\s+)?(?:seen|spotted|watched|noticed)\b"
                       r"|\b(?:seen|spotted|watched|noticed)\s+by\b", re.I)),
    "owes": ("debtor", "creditor", re.compile(r"\b(owes|owed|owe|owing|debt|debts)\b", re.I),
             re.compile(r"\b(?:am|is|was|were|been|are)\s+owed\b|\bowed\s+by\b", re.I)),
}
_REPORT_VERBS = r"told|tells|said|says|mentioned|claimed|claims|reported"
_QUOTE_RE = re.compile(r'"([^"]*)"|“([^”]*)”')


@dataclass
class VillagerContext:
    """What one villager may cite: id -> text, who wrote or said it, and the facts behind it."""
    case: Case
    villager: str
    vocab: Vocab
    texts: dict[str, str]
    speakers: dict[str, str]
    facts: dict[str, list[str]]
    heard_ids: set[str]
    fact_entities: set[Entity]  # every entity that is in some fact of the case; the rest of a line is flavour

    @property
    def visible_ids(self) -> set[str]:
        return set(self.texts)

    def text(self, cite: str) -> str:
        return self.texts[cite]


_CACHE: dict[int, tuple[Case, Vocab, set[Entity]]] = {}


def _per_case(case: Case) -> tuple[Vocab, set[Entity]]:
    """Vocab and fact entities, cached per case object: GRPO checks thousands of replies against a few cases."""
    hit = _CACHE.get(id(case))
    if hit is None or hit[0] is not case:
        if len(_CACHE) > 512:
            _CACHE.clear()
        vocab = vocab_for(case)
        hit = _CACHE[id(case)] = (case, vocab, set().union(*(_fact_entities(f, vocab) for f in case.facts)))
    return hit[1], hit[2]


def context_for(case: Case, villager_id: str, heard=()) -> VillagerContext:
    """Everything `villager_id` can see: own documents minus withheld ones, plus heard items (HeardItem or dict)."""
    if villager_id not in {v.id for v in case.villagers}:
        raise KeyError(f"unknown villager {villager_id!r} in {case.case_id}")
    texts, speakers, facts = {}, {}, {}
    for did in case.villager(villager_id).docs:
        d = case.doc(did)
        if d.withheld:
            continue
        for s in d.sentences:
            texts[s.id], speakers[s.id], facts[s.id] = s.text, d.owner, list(s.facts)
    heard_ids = set()
    for h in heard or []:
        h = h if isinstance(h, HeardItem) else HeardItem.model_validate(h)
        texts[h.id], speakers[h.id], facts[h.id] = h.text, h.from_, list(h.facts)
        heard_ids.add(h.id)
    vocab, fact_entities = _per_case(case)
    return VillagerContext(case, villager_id, vocab, texts, speakers, facts, heard_ids, fact_entities)


def check(reply: str, ctx: VillagerContext) -> CheckResult:
    p = parse(reply)
    if not p.ok:
        return CheckResult(parsed=False)
    if p.abstain:
        return CheckResult(parsed=True, abstained=True)
    claims = [_check_claim(c, ctx) for c in p.claims]
    n_ok = sum(c.status == "supported" for c in claims)
    return CheckResult(parsed=True, claims=claims, support_rate=n_ok / len(claims))


# ---------------------------------------------------------------------------------------------------------------

def _check_claim(c: ParsedClaim, ctx: VillagerContext) -> ClaimResult:
    def red(reason: str) -> ClaimResult:
        return ClaimResult(text=c.text, cites=c.cites, status="unsupported", reason=reason)

    # 1. Every cited id is one this villager can see.
    if not c.cites or any(i not in ctx.texts for i in c.cites):
        return red("bad_cite")
    reporters = {ctx.speakers[i] for i in c.cites if i in ctx.heard_ids}
    text, attributed = _strip_reports(c.text, reporters, ctx)
    ents, people = _read(text, ctx, reporters)

    # 2. Says something checkable besides "I" and whoever told me.
    if not ents - {("person", r) for r in reporters} - {("person", ctx.villager)}:
        return red("vacuous")

    # 3. Every entity, and every crime action, is in the cited lines. A line's writer or speaker counts as present
    #    (Tom's diary says "Shut the mill at sunset" with no "I"), and so does what the line's own facts say but
    #    its words leave to context: "Mara here" in Ivy's ledger is the smithy; "Stayed at the mill all night"
    #    sits under the diary's "Day 2." heading.
    known = {f.id: f for f in ctx.case.facts}
    src: set[Entity] = set()
    src_actions: set[str] = set()
    src_neg: set[str] = set()
    flavour: set[Entity] = set()
    for i in c.cites:
        written = ctx.vocab.extract(ctx.texts[i], ctx.speakers[i])
        flavour |= written - ctx.fact_entities
        src |= written | {("person", ctx.speakers[i])}
        src |= set().union(*(_fact_entities(known[f], ctx.vocab) for f in ctx.facts[i] if f in known))
        src_actions |= actions(ctx.texts[i])
        src_neg |= negations(ctx.texts[i])
    if not ents <= src or not actions(text) <= src_actions:
        return red("entity_mismatch")

    # 4. The claim states one cited fact, the right way round, without added negation.
    if not negations(text) <= src_neg:
        return red("fact_mismatch")
    if not any(ctx.facts[i] for i in c.cites):
        if not all(i in ctx.heard_ids for i in c.cites):
            return red("fact_mismatch")  # a line with no fact behind it cannot be checked
        facts: list[str] = []  # repeating a heard item that was itself unsupported: green, but no facts
    else:
        facts = _match_fact(c.cites, ents, people, text, reporters, flavour, ctx)
        if facts is None:
            return red("fact_mismatch")

    # 5. Hearsay names who said it, with a reporting phrase.
    if not reporters <= attributed:
        return red("no_attribution")
    return ClaimResult(text=c.text, cites=c.cites, status="supported", reason="ok", facts=facts)


def _names(pid: str, ctx: VillagerContext) -> list[str]:
    """How a speaker may be named: their names in the case, else the id itself ("a traveller")."""
    return ctx.case.lexicon.people.get(pid) or [pid, pid.capitalize()]


def _strip_reports(text: str, reporters: set[str], ctx: VillagerContext) -> tuple[str, set[str]]:
    """Find "<name> told me (that)", "<name> said", "according to <name>", "I heard from <name>" for each reporter.
    The phrase is reduced to the bare name, so the "me" of "told me" is not read as a claim about the listener."""
    attributed = set()
    for pid in reporters:
        name = "|".join(re.escape(n) for n in sorted(_names(pid, ctx), key=len, reverse=True))
        art = r"(?:(?:a|an|the)\s+)?"
        pattern = re.compile(
            rf"\b(?i:according\s+to|(?:I\s+)?heard\s+(?:it\s+)?from)\s+{art}(?P<a>{name})\b"
            rf"|\b{art}(?P<b>{name})\s+(?:{_REPORT_VERBS})(?:\s+(?:to\s+)?me)?(?:\s+that)?\b")
        text, n = pattern.subn(lambda m: " " + (m.group("a") or m.group("b")) + " ", text)
        if n:
            attributed.add(pid)
    return text, attributed


def _read(text: str, ctx: VillagerContext, reporters: set[str]) -> tuple[set[Entity], list[tuple[int, str]]]:
    """Entities and people (in order) of a claim. "I"/"me" is the villager, except inside quotes in a hearsay claim
    with one source, where it is whoever is being quoted: Tom said "I stayed at the mill"."""
    quoted_speaker = next(iter(reporters)) if len(reporters) == 1 else None
    segments, last = [], 0
    if quoted_speaker:
        for m in _QUOTE_RE.finditer(text):
            segments.append((last, text[last:m.start()], ctx.villager))
            segments.append((m.start() + 1, m.group(1) if m.group(1) is not None else m.group(2), quoted_speaker))
            last = m.end()
    segments.append((last, text[last:], ctx.villager))
    ents: set[Entity] = set()
    people: list[tuple[int, str]] = []
    for offset, segment, speaker in segments:
        ents |= ctx.vocab.extract(segment, speaker)
        people += [(offset + pos, pid) for pos, pid in ctx.vocab.people_in_order(segment, speaker)]
    return ents, sorted(people)


def _fact_entities(f: Fact, vocab: Vocab) -> set[Entity]:
    out: set[Entity] = set()
    for role, arg in zip(RELATIONS[f.rel], f.args):
        if role == "amount":
            out |= vocab.extract(arg)
        else:
            out.add((ARG_KIND[role], arg))
    if f.t:
        out |= {("day", f.t.day), ("slot", f.t.slot)}
    return out


def _arg(f: Fact, role: str) -> str:
    return f.args[RELATIONS[f.rel].index(role)]


def _core(f: Fact) -> set[Entity]:
    return {(ARG_KIND[role], _arg(f, role)) for role in CORE[f.rel]}


def _match_fact(cites, ents, people, text, reporters, flavour, ctx) -> list[str] | None:
    """Fact ids the claim states, or None. Facts that differ only in time slot form one group, so "Mara was at
    the smithy from evening to midnight" matches at(mara, smithy) at dusk and at night together."""
    known = {f.id: f for f in ctx.case.facts}
    cited = dict.fromkeys(fid for i in cites for fid in ctx.facts[i] if fid in known)  # keeps order, drops repeats
    groups: dict[tuple, list[Fact]] = {}
    for f in map(known.get, cited):
        groups.setdefault((f.rel, tuple(f.args), f.t.day if f.t else None), []).append(f)
    for group in groups.values():
        head = group[0]
        # The speaker is allowed only as part of the fact: Nell's "I was inside the mill [D3.S1]" is red even
        # though she wrote the line, because the fact is only that the mill was empty.
        allowed = set().union(*(_fact_entities(f, ctx.vocab) for f in group)) | {("person", r) for r in reporters}
        allowed |= flavour
        if not ents <= allowed or not _core(head) <= ents:
            continue
        if not _direction_ok(head, text, people):
            continue
        slots = {v for k, v in ents - flavour if k == "slot"}
        stated = [f.id for f in group if not slots or f.t is None or f.t.slot in slots]
        if all(set(ctx.facts[i]) & set(stated) for i in cites):  # every cited line holds a fact the claim states
            return stated
    return None


def _direction_ok(f: Fact, text: str, people: list[tuple[int, str]]) -> bool:
    """For `saw` and `owes`: the person before the verb must be the subject, the one after it the object
    (swapped for the passive: "Tom was seen by me"). If the claim has no such verb, there is nothing to check."""
    if f.rel not in DIRECTED:
        return True
    subj_role, obj_role, verb, passive = DIRECTED[f.rel]
    m = verb.search(text)
    if not m:
        return True
    before = [pid for pos, pid in people if pos < m.start()]
    after = [pid for pos, pid in people if pos >= m.end()]
    subj, obj = (before[-1] if before else None), (after[0] if after else None)
    if passive.search(text):
        subj, obj = obj, subj
    return subj in (None, _arg(f, subj_role)) and obj in (None, _arg(f, obj_role))
