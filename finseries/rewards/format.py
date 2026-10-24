"""R_format: 1.0 if <think>..</think><answer>..</answer> parse (one answer, after the think block) AND the
scaffold's declared header (window / chunk / <segments>) is present; 0.5 for structure without header; else 0."""


def format_reward(scaffold, parsed):
    structure = parsed.has_think and parsed.has_answer and not parsed.multi_answer and not parsed.truncated \
        and parsed.answer_raw is not None
    if not structure:
        return 0.0
    return 1.0 if scaffold.header_ok(parsed) else 0.5
