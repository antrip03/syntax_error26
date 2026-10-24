"""Reward bundles. Every call returns each component separately so training can log them."""
from .consistency import consistency_reward
from .format import format_reward
from .length import length_reward
from .outcome import outcome_reward
from .process import process_reward

BUNDLES = {
    "outcome_only": {"outcome": 0.90, "format": 0.10},
    "outcome_process": {"outcome": 0.50, "process": 0.25, "format": 0.10, "consistency": 0.15},
}


def compute(scaffold, task, completion, n_tokens=None, bundle="outcome_process", token_budget=512):
    pt = scaffold.parse(completion)
    comp = {"outcome": outcome_reward(task, pt), "format": format_reward(scaffold, pt)}
    if bundle == "outcome_process":
        comp["process"] = process_reward(scaffold, task, pt)
        comp["consistency"] = consistency_reward(scaffold, task, pt)
        comp["length"] = length_reward(pt, n_tokens, token_budget)
    total = sum(w * comp[k] for k, w in BUNDLES[bundle].items()) + comp.get("length", 0.0)
    comp["total"] = total
    comp["parsed"] = float(pt.has_think and pt.has_answer)
    return comp
