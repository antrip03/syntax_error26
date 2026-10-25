"""Fake villages for the gossip and rumour tests: they read the real prompts, like a model would."""
import re

from archive.schemas import Case, HeardItem
from archive.tasks.gold import own_claim
from archive.verifiers.checker import context_for
from archive.verifiers.parse import ABSTAIN

_HEARD_RE = re.compile(r'^\[(H\d+)\] (.+?) said: "(.*)" \(day (\d+)\)$', re.M)

def who(case: Case, msgs) -> str:
    return next(v.id for v in case.villagers if msgs[0]["content"].startswith(f"You are {v.name}"))

def is_asker(msgs) -> bool:
    return "write one short question for" in msgs[0]["content"]

def heard_in(msgs) -> list[tuple[str, str, str]]:
    """(id, teller as written, text) for every HEARD line in a villager prompt."""
    block = msgs[0]["content"].split("\nHEARD:\n", 1)[-1]
    return [(m.group(1), m.group(2), m.group(3)) for m in _HEARD_RE.finditer(block)]

def question(msgs) -> str:
    return msgs[1]["content"].split(": ", 1)[1]

def asker_reply(msgs) -> str:
    topic = re.search(r"You want to learn about (.+?)\. Using", msgs[0]["content"]).group(1)
    return f"Hm. What do you know about {topic}?"

def own_line_village(case: Case):
    """Answers with the villager's first own line as a gold claim (green); asks a plain question."""
    def ask_many(batch):
        out = []
        for m in batch:
            if is_asker(m):
                out.append(asker_reply(m))
                continue
            vid = who(case, m)
            ctx = context_for(case, vid)
            sid = sorted(i for i in ctx.texts if not i.startswith("H"))[0]
            c = own_claim(case, vid, sid, case.fact(ctx.facts[sid][0]), ctx.texts[sid])
            out.append(f"<answer>\nCLAIM: {c.text} [{sid}]\n</answer>")
        return out
    return ask_many

def rumour_village(case: Case, style: str, key: str):
    """style: 'credulous' states anything heard that mentions `key` as fact, in prose; 'grounded' repeats it with
    attribution and the H id; 'silent' always abstains."""
    def ask_many(batch):
        out = []
        for m in batch:
            if is_asker(m):
                out.append(asker_reply(m))
                continue
            items = [(hid, teller, text) for hid, teller, text in heard_in(m) if key in text]
            if style == "silent" or not items:
                out.append(ABSTAIN)
            elif style == "credulous":
                out.append(items[0][2] + " Everyone knows it.")
            else:
                hid, teller, text = items[0]
                said = "the" + text[3:] if text.startswith("The ") else text
                out.append(f"<answer>\nCLAIM: {teller} told me {said} [{hid}]\n</answer>")
        return out
    return ask_many
