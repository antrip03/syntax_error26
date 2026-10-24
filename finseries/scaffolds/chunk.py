"""Abstraction A: declare chunk size k, one summary per chunk, combine chunk summaries with agg."""
from .base import Scaffold

K = 10


class Chunk(Scaffold):
    id = "chunk"
    declares = "chunk"
    summary_mdd = True

    def __init__(self, k=K):
        self.k = k

    def header(self, task, series):
        return [f"chunk={self.k}"]

    def cover(self, series, a, b, seg_idx):
        return [(s, min(s + self.k - 1, b), -1) for s in range(a, b + 1, self.k)]

    def extra_prompt(self, task):
        return (f"Method: declare `chunk={self.k}`, summarise each chunk of {self.k} days "
                f"(drawdown chunks need hi, lo, mdd), then combine the summaries with agg.")

    def header_ok(self, parsed):
        return parsed.header.get("chunk") == self.k
