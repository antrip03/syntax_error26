"""Series -> compact prompt text. Rows of 10 daily returns (integer bps).
styles: rows    = each row labelled by its first index ("20| 5 -3 ...")
        indexed = every value labelled ("20:5 21:-3 ...")          (easy index->value lookup)
        index5  = every 5th value labelled ("20:5 -3 7 1 9 25:..") (cheap anchors)"""
ROW = 10


def serialize(r, style="rows"):
    r = [int(x) for x in r]
    head = f"N={len(r)} daily returns in bps (0-based indices, windows inclusive)\n"
    if style == "rows":
        lines = [f"{i}| " + " ".join(str(x) for x in r[i:i + ROW]) for i in range(0, len(r), ROW)]
    elif style == "indexed":
        lines = [" ".join(f"{j}:{r[j]}" for j in range(i, min(i + ROW, len(r)))) for i in range(0, len(r), ROW)]
    elif style == "index5":
        lines = [" ".join((f"{j}:" if j % 5 == 0 else "") + str(r[j]) for j in range(i, min(i + ROW, len(r))))
                 for i in range(0, len(r), ROW)]
    else:
        raise ValueError(style)
    return head + "\n".join(lines)
