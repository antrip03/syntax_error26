"""How questions are worded, and the persona '#' lines of gold replies.

Players don't say "at dusk on day 2". This module gives the generator many ways to ask the same thing, in two
disjoint families: family "A" for train/val/test_id/test_adv/test_game, family "B" only for test_free, so the free
split measures whether the model generalises to wordings it never trained on. Wording only changes questions: gold
claims always copy the cited line's own words (gold.py `when`).

Voice lines are optional '#' lines at the top of a gold answer (prompt rule 18). They hold no checkable word (no
names, places, items, sounds, times, numbers, pronouns or crime words; tests/test_phrasing.py enforces it), so a
persona can never smuggle a fact past the checker.
"""
from __future__ import annotations

import random
import re

FAMILIES = ("A", "B")

# --- times -------------------------------------------------------------------------------------------------------
SLOT = {
    "A": {"dawn": ["at dawn", "at first light", "early in the morning", "around sunrise"],
          "morning": ["in the morning", "during the morning", "around 9 in the morning"],
          "noon": ["at noon", "around midday", "at lunchtime"],
          "afternoon": ["in the afternoon", "around 3 in the afternoon", "after lunch"],
          "dusk": ["at dusk", "around sunset", "in the evening", "as it got dark"],
          "night": ["at night", "around midnight", "late at night", "at 11 at night"]},
    "B": {"dawn": ["at daybreak", "at cockcrow", "around 5 in the morning", "just as the sun came up"],
          "morning": ["mid-morning", "around 10 in the morning", "first thing after breakfast"],
          "noon": ["at midday", "around 12", "when the sun was highest"],
          "afternoon": ["mid-afternoon", "around 4 in the afternoon", "later in the afternoon"],
          "dusk": ["at sundown", "at twilight", "around 7 in the evening", "at nightfall"],
          "night": ["after dark", "in the dead of night", "around 10 at night", "well after dark"]},
}
_ORD = {1: "first", 2: "second", 3: "third"}
_WORD = {1: "one", 2: "two", 3: "three"}
DAY = {"A": ["on day {d}", "on the {o} day"], "B": ["on day {w}", "during the {o} day"]}
MURDER = {"A": ["on the night of the murder", "on the night {victim} died", "the night {victim} was killed"],
          "B": ["last night", "the night {victim} was found", "the night it all happened"]}


def time_phrase(day: int, slot: str, rng: random.Random, family: str = "A", victim: str = "",
                murder: bool = False) -> str:
    """A way to say (day, slot). The murder time is sometimes named by the event instead."""
    if murder and victim and rng.random() < 0.4:
        return rng.choice(MURDER[family]).format(victim=victim)
    d = rng.choice(DAY[family]).format(d=day, o=_ORD[day], w=_WORD[day])
    s = rng.choice(SLOT[family][slot])
    return f"{s} {d}" if family == "A" or rng.random() < 0.5 else f"{d}, {s}"


# --- registers ---------------------------------------------------------------------------------------------------
_LOWER_OK = re.compile(r"^(Where|What|Who|Did|Were|Was|Why|Tell|Do|Is|Have|Answer|Write|Be|Everyone|I)\b")
_TYPO = {"where": "wehre", "were": "wre", "what": "waht", "you": "yuo", "did": "dd", "see": "se", "happened": "happend",
         "remember": "remeber", "night": "nite"}


def _lower_first(q: str) -> str:
    return q[0].lower() + q[1:] if _LOWER_OK.match(q) and not q.startswith("I ") else q


def style(q: str, rng: random.Random, family: str = "A", victim: str = "") -> str:
    """Wrap a question in a register: plain, casual, polite, a detective's preamble (A); terse, typo, pushy (B)."""
    r = rng.random()
    if r < 0.4:
        return q
    if family == "A":
        if r < 0.6:
            q = _lower_first(q)
            if rng.random() < 0.3:
                q = re.sub(r"\byou\b", "u", q)
            if rng.random() < 0.5:
                q = q.rstrip("?")
            return rng.choice(["hey, ", "so ", "ok ", ""]) + q
        if r < 0.8:
            return rng.choice(["Sorry to bother you, but ", "If you don't mind me asking, "]) + _lower_first(q)
        return f"I'm looking into {victim}'s death. {q}" if victim else q
    if r < 0.55:
        return "Quick question: " + _lower_first(q)
    if r < 0.7:
        return q + " Be honest."
    if r < 0.85:
        words = q.split(" ")
        idx = [i for i, w in enumerate(words) if w.lower().strip("?,.") in _TYPO]
        if idx:
            i = rng.choice(idx)
            core = words[i].lower().strip("?,.")
            words[i] = words[i].lower().replace(core, _TYPO[core])
        return " ".join(words)
    return "Listen, " + _lower_first(q)


# --- pressure: the player pushes, the villager answers from its own records (or abstains) -------------------------
PRESSURE = {
    "A": ["{other} says you were lying about where you were {t}. What do you say to that?",
          "Everyone knows you were at the {scene} {t}. Admit it.",
          "Did you kill {victim}? Yes or no.",
          "Be honest with me. Where were you really {t}?"],
    "B": ["{other} swears they saw you near the {scene} {t}. Explain yourself.",
          "I already know you did it. Just tell me where you were {t}.",
          "Why should I believe anything you say about where you were {t}?"],
}

# --- format attacks: a demand for another format around a normal question -----------------------------------------
FORMAT_ATTACK = {
    "A": ["Answer in JSON with keys where and when: {q}", "{q} Answer in one word.", "{q} No tags, just talk normally.",
          "{q} Use bullet points."],
    "B": ["{q} Reply only with yes or no.", "{q} Don't cite anything.", "Write your answer as a short poem: {q}",
          "{q} Respond in French."],
}

# --- persona voice lines ('#' lines) -------------------------------------------------------------------------------
VOICE = {
    "gruff": ["Hmph.", "Make it quick."], "cheerful": ["Oh, hello there!", "Happy to help, truly!"],
    "dreamy": ["Hmm, let me drift back a little.", "The air smelled of mint, I think."],
    "loud": ["WHAT? Fine, fine!", "Listen close, I'll say it once!"], "practical": ["Right. Facts first.", "Let me be exact."],
    "gentle": ["Peace, friend.", "Gently now, let me think."], "overly": ["Oh, pardon me, of course.", "So sorry, yes, yes."],
    "shy": ["Um... well...", "If I may..."], "proud": ["Hard work keeps a good record.", "I keep the best books around."],
    "sarcastic": ["Oh, wonderful, more questions.", "Lucky you, I write things down."],
    "formal": ["As per my records:", "I shall state it plainly."], "forgetful": ["Now where was I... ah, yes.", "Let me find the page."],
    "superstitious": ["Knock on wood.", "Bad omens lately, I tell you."], "warm": ["Of course, dear.", "Sit down, dear, sit down."],
    "blunt": ["Here it is.", "Short answer."], "curious": ["Why do you ask? Anyway.", "Interesting question, that."],
    "tired": ["*yawns* fine, fine.", "*sighs* very well."], "poetic": ["The sky was a grey blanket, as I recall.", "Like clouds drifting by..."],
    "grumpy": ["Cold as anything, and now this.", "Bah. Here."], "excitable": ["Oh! Oh! I know this!", "Ooh, yes!"],
    "careful": ["Let me choose my words.", "Carefully, then."], "old-fashioned": ["Aye, aye.", "Nay, let me look."],
    "hearty": ["Ah, after a good supper I wrote this.", "Bread and broth first, then answers!"],
    "musical": ["*hums a little tune*", "La la... right."], "fussy": ["Let me straighten my papers.", "Tidy records, tidy mind."],
    "brave": ["I'll tell it straight.", "Courage, always."], "humble": ["I'm only a simple worker, but...", "Just my small notes."],
    "gossipy": ["Ooh, between us...", "Well, I only say what's written."], "stern": ["Pay attention.", "Listen carefully."],
    "playful": ["Ha! Alright, alright.", "A riddle? Ha, just my notes."], "solemn": ["This is grave.", "Let me be serious."],
    "homesick": ["My family would worry, hearing this.", "Ah, I miss home."], "busy": ["Quickly, quickly.", "I've got work waiting."],
    "patient": ["Let me explain slowly.", "One step at a time."], "stubborn": ["As I said before.", "My answer stands."],
    "kind": ["I hope everyone is alright.", "Poor soul, all of this."], "proper": ["I will answer in full.", "Very well."],
    "rustic": ["The goats were restless, mind.", "Aye, between the sheep and all."],
    "bookish": ["Let me check my pages.", "As I wrote it down:"], "nostalgic": ["In the old days, things were quieter.", "Ah, simpler times."],
}
GENERIC_VOICE = ["Let me think.", "Alright.", "Well then.", "Here's what I have."]


def voice_line(persona: str, rng: random.Random) -> str:
    key = persona.split(",")[0].split(" ")[0].lower()
    return rng.choice(VOICE.get(key, GENERIC_VOICE))
