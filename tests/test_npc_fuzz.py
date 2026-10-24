"""Bot, rumour and gossip under random replies: never crash, never report something impossible."""
import random

import pytest

from archive.npc.detective_bot import play
from archive.npc.gossip import MAX_HEARD, run_evening
from archive.npc.rumour import run
from archive.verifiers.parse import ABSTAIN
from archive.world.casegen import generate_case

PIECES = ["<answer>", "</answer>", "\nCLAIM: ", "# hm", "[D1.S1]", "[D2.S3]", "[H1]", "[H2]", "I saw", " Tom", " Mara",
          " poisoned", " the well", " at midnight on day 2", " told me", " said:", '"', "?", "<think>", "not",
          ABSTAIN, "\n", " ", ".", "they", "stabbed", "What do you know about", "💀"]


def noisy(seed):
    rng = random.Random(seed)

    def ask_many(batch):
        return ["".join(rng.choice(PIECES) for _ in range(rng.randint(0, 20))) for _ in batch]
    return ask_many


@pytest.mark.parametrize("seed", range(40))
def test_bot_on_noise(seed):
    case = generate_case(seed, "easy" if seed % 2 else "hard")
    r = play(case, noisy(seed))
    assert r.accused in {v.id for v in case.villagers} | {None}
    assert (not r.solved) or r.caught
    assert r.killer_red_share is None or 0 <= r.killer_red_share <= 1
    for c in r.confirmed:                                  # anything confirmed really clashes, between 2 villagers
        assert len(c["by"]) == 2 and c["suspect"] in {v.id for v in case.villagers}


@pytest.mark.parametrize("seed", range(25))
def test_rumour_on_noise(seed):
    case = generate_case(seed, "easy")
    target = case.villagers[1]
    out = run(case, noisy(seed), f"{target.name} poisoned the well.", case.villagers[0].id, seed=seed)
    for r in out["rounds"]:
        assert set(r["spread"].values()) <= {"red", "amber", "plain"}
    assert 0 <= out["repeated_as_fact"] <= out["n_villagers"]
    assert all(len(items) <= MAX_HEARD for items in out["heard"].values())


@pytest.mark.parametrize("seed", range(25))
def test_gossip_on_noise(seed):
    case = generate_case(seed, "hard")
    out = run_evening(case, noisy(seed), seed=seed)
    assert all(e["question"].endswith("?") for e in out["events"])
    for items in out["heard"].values():
        assert len(items) <= MAX_HEARD and all("<" not in h["text"] for h in items)
