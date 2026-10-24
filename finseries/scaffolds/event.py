"""Abstraction B: first a <segments> block from the segmentation rule, then ops per segment, then agg."""
from .base import Scaffold


class Event(Scaffold):
    id = "event"
    declares = "segments"
    summary_mdd = True

    def header(self, task, series):
        out = ["<segments>"] + [f"{i}:{g.text()}" for i, g in enumerate(series.segs)] + ["</segments>"]
        return out

    def cover(self, series, a, b, seg_idx):
        pieces = []
        for i, g in enumerate(series.segs):
            if g.end < a or g.start > b:
                continue
            pa, pb = max(a, g.start), min(b, g.end)
            pieces.append((pa, pb, i if (pa == g.start and pb == g.end) else -1))
        return pieces

    def extra_prompt(self, task):
        return ("Method: first write the `<segments>` block (one `i:(start,end,trend,vol)` line per segment, from the rule), "
                "then use seg_stat(i,op) per segment, then agg.")

    def header_ok(self, parsed):
        return parsed.has_segments_block
