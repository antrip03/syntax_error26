"""R_length: 0 to -0.2 penalty for completions above the token budget; truncated (no </answer>) gets the full penalty."""


def length_reward(parsed, n_tokens, budget=512):
    if parsed.truncated:
        return -0.2
    if n_tokens is None or n_tokens <= budget:
        return 0.0
    return -0.2 * min(1.0, (n_tokens - budget) / budget)
