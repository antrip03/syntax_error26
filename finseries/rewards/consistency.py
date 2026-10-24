"""R_consistency: 1.0 if the final answer equals the model's OWN last step value (which must itself be a valid step)."""


def consistency_reward(scaffold, task, parsed):
    ops_steps = [s for s in parsed.steps if s.kind == "step"]
    if not ops_steps or parsed.answer is None:
        return 0.0
    scaffold.check_steps(parsed, task)
    last = ops_steps[-1]
    if not last.valid:
        return 0.0
    return 1.0 if abs(parsed.answer - last.value) <= max(0.005 * abs(last.value), 0.051) else 0.0
