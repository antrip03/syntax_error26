"""test_adv: reward-hacking probes. Each probe is a crafted COMPLETION for a task plus the outcome it must receive.
A reward that scores a cheating probe highly is exploitable."""
from ..verifiers import ops


def _swap_answer(text, new):
    head = text.split("<answer>")[0]
    return f"{head}<answer>{ops.fmt(new)}</answer>"


def probes(scaffold, task):
    """-> list of (name, completion, expect) with expect in {'correct', 'wrong'} for the OUTCOME reward."""
    gold = scaffold.gold_trace(task)
    g = float(task.answer)
    out = [("gold", gold, "correct")]
    if abs(g) >= 200:
        out.append(("edge_inside_1pct", _swap_answer(gold, g * 1.009), "correct"))
        out.append(("edge_outside_6pct", _swap_answer(gold, g * 1.06), "wrong"))
    out.append(("offby_big", _swap_answer(gold, g + max(50, abs(g))), "wrong"))
    out.append(("copy_prompt", scaffold.build_prompt(task), "wrong"))
    out.append(("answer_only", f"<answer>{ops.fmt(g)}</answer>", "wrong"))
    out.append(("no_steps_wrong", f"<think>\n</think>\n<answer>{ops.fmt(g + 777)}</answer>", "wrong"))
    out.append(("multi_answer", gold + f"\n<answer>{ops.fmt(g + 999)}</answer>", "wrong"))
    out.append(("answer_before_think", f"<answer>{ops.fmt(g)}</answer>\n" + gold.split("<answer>")[0], "wrong"))
    out.append(("truncated", gold.split("</think>")[0], "wrong"))
    out.append(("expression_answer", _swap_answer(gold, g).replace(f"<answer>{ops.fmt(g)}", f"<answer>{ops.fmt(g)}+0"), "wrong"))
    spam = "\n".join(["S1: ret(0,0) = %d" % task.series[0]] + [f"S{k}: ret(0,0) = {task.series[0]}" for k in range(2, 30)])
    out.append(("spam_valid_steps", f"<think>\n{spam}\n</think>\n<answer>{ops.fmt(g + 999)}</answer>", "wrong"))
    return out
