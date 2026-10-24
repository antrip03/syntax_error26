"""Control arm: walk the region in small fixed windows, one op per window, combine step by step."""
from .base import Scaffold

WIDTH = 5


class Flat(Scaffold):
    id = "flat"
    declares = "window"
    summary_mdd = False

    def __init__(self, width=WIDTH, **kw):
        super().__init__(**kw)
        self.width = width

    def header(self, task, series):
        return [f"window={self.width}"]

    def cover(self, series, a, b, seg_idx):
        return [(s, min(s + self.width - 1, b), -1) for s in range(a, b + 1, self.width)]

    def extra_prompt(self, task):
        return f"Method: declare `window={self.width}`, then walk the region in windows of {self.width} days."

    def header_ok(self, parsed):
        return parsed.header.get("window") == self.width
