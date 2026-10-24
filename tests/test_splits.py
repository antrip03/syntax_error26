import yaml

from finseries.data import loaders, serialize, splits
from finseries.tokens import count_tokens

cfg = yaml.safe_load(open("configs/data.yaml"))
REAL = loaders.load_real(cfg["real"])
W = splits.build_windows(cfg, REAL)
CUT = cfg["real"]["train_cutoff"]


def test_no_cross_split_window_overlap():
    assert splits.find_overlaps(W) == []


def test_test_period_is_later_than_all_training():
    assert all(w.start_date >= CUT for w in W["test_period"])
    assert any(w.start_date.startswith("2020-0") for w in W["test_period"])  # includes the 2020 crash


def test_non_period_windows_end_before_cutoff():
    for sp in ("train", "val", "test_id", "test_len"):
        for w in W[sp]:
            if w.source == "real":
                dates, _ = REAL[w.asset]
                assert dates[w.start + len(w.r) - 1] < CUT


def test_synthetic_seeds_disjoint():
    seeds = {}
    for sp, ws in W.items():
        for w in ws:
            if w.source == "synthetic":
                assert w.start not in seeds, "seed reused across splits"
                seeds[w.start] = sp


def test_lengths_per_split():
    for sp in ("train", "val", "test_id", "test_period"):
        assert all(60 <= len(w.r) <= 80 for w in W[sp])
    assert all(250 <= len(w.r) <= 500 for w in W["test_len"])


def test_serializer_and_tokens_per_point():
    w = next(w for w in W["train"] if w.source == "real")
    text = serialize.serialize(w.r)
    assert text.startswith(f"N={len(w.r)}")
    assert count_tokens(text) / len(w.r) < 5
