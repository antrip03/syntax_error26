"""R_outcome: 1.0 inside the tolerance band, linear decay to 0 at the soft band (5% rel), ABSTAIN exact."""
from ..tasks.templates import SOFT_REL


def outcome_reward(task, parsed):
    if parsed.truncated or not parsed.has_answer or parsed.multi_answer:
        return 0.0
    if task.answer == "ABSTAIN":
        return 1.0 if parsed.abstain else 0.0
    if parsed.answer is None:
        return 0.0
    g, p = float(task.answer), parsed.answer
    err = abs(p - g)
    band = max(task.tolerance_rel * abs(g), task.tolerance_abs)
    soft = max(SOFT_REL * abs(g), task.soft_abs, band)
    if err <= band:
        return 1.0
    if err >= soft:
        return 0.0
    return 1.0 - (err - band) / (soft - band)


def is_correct(task, parsed):
    return outcome_reward(task, parsed) >= 1.0
