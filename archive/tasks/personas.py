"""Persona cards (brief 4.8): sampled per villager, shown as "Personality: ..." in the villager prompt.

A persona only changes '#' lines, never claims (prompt rule 18). Training on many of them teaches the model that
style never changes facts. Cards avoid every word the checker reads as an entity (names, places, items, sounds,
roles) and every crime/judgement word, so the persona can never put a checkable word into the model's mouth.
tests/test_casegen.py enforces this.
"""
from __future__ import annotations

import random

PERSONAS = [
    "gruff, very short sentences, uses watch times",
    "cheerful, chatty, laughs often",
    "dreamy, mentions plants and herbs",
    "loud and quick-tempered",
    "practical, counts everything",
    "gentle, quotes old sayings",
    "overly polite, apologises a lot",
    "shy, speaks softly and briefly",
    "proud, boasts about hard work",
    "sarcastic, dry humour",
    "formal, speaks like a clerk",
    "forgetful, wanders off topic in asides",
    "superstitious, mentions omens and luck",
    "warm, calls everyone dear",
    "blunt, no small talk",
    "curious, asks questions back",
    "tired, sighs and yawns",
    "poetic, talks about the weather and the sky",
    "grumpy, complains about the cold",
    "excitable, uses many exclamations",
    "careful, chooses each word slowly",
    "old-fashioned, uses old words like aye and nay",
    "hearty, talks about food and supper",
    "musical, hums and mentions songs",
    "fussy, cares about tidiness",
    "brave, speaks with confidence",
    "humble, says it is only a simple worker",
    "gossipy in tone, but sticks to the records",
    "stern, speaks like a teacher",
    "playful, makes little jokes",
    "solemn, very serious",
    "homesick, mentions family far away",
    "busy, always in a hurry",
    "patient, explains slowly",
    "stubborn, repeats the point",
    "kind, worries about others",
    "proper, uses full sentences",
    "rustic, talks about sheep and goats",
    "bookish, mentions reading",
    "nostalgic, recalls the old days",
]


def sample_personas(rng: random.Random, n: int) -> list[str]:
    """n different persona cards."""
    return rng.sample(PERSONAS, n)
