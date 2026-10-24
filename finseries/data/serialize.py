"""Series -> compact prompt text. Rows of 10 daily returns (integer bps), each row labelled by its first index."""
ROW = 10


def serialize(r):
    r = [int(x) for x in r]
    lines = [f"{i}| " + " ".join(str(x) for x in r[i:i + ROW]) for i in range(0, len(r), ROW)]
    return f"N={len(r)} daily returns in bps (0-based indices, windows inclusive)\n" + "\n".join(lines)
