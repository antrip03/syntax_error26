"""R_process: fraction of VALID steps (junk lines count as invalid), gated by coverage.

Anti-hacking: duplicate steps are invalid (verifiers/steps.py), and credit is scaled by
min(1, n_valid / (0.5 * n_gold_steps)) so a single trivially-true step cannot earn the full reward.
"""


def n_gold_steps(scaffold, task):
    pt = scaffold.parse(scaffold.gold_trace(task))
    return sum(1 for s in pt.steps if s.kind == "step")


def process_reward(scaffold, task, parsed):
    sc = scaffold
    sc.check_steps(parsed, task)
    real = parsed.steps  # segment lines, junk lines and op steps all count
    ops_steps = [s for s in real if s.kind == "step"]
    if not ops_steps:
        return 0.0
    frac = sum(s.valid for s in real) / len(real)
    n_valid = sum(s.valid for s in ops_steps)
    cover = min(1.0, n_valid / max(1.0, 0.5 * n_gold_steps(sc, task)))
    return frac * cover
