"""Tests for the series-bias miner (spec #4, section 9).

The headline test is the fixture universe the spec asks for: one series
with a planted, persistent bias among calibrated ones, verifying that
*exactly* it is flagged. The rest pin the pre-registered guard, because
every one of those thresholds is a claim in
`theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/STUDY.md` and a silent change to
one would invalidate the pre-registration.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

_PATH = (Path(__file__).resolve().parents[1]
         / "theories/insider_bias/mention_family/studies/investigation"
         / "2026-08-29-series-bias-mining" / "mine.py")
_spec = importlib.util.spec_from_file_location("_mine", _PATH)
mine = importlib.util.module_from_spec(_spec)
# Must be in sys.modules BEFORE exec: @dataclass resolves its own module
# through sys.modules and raises AttributeError on a None entry.
sys.modules["_mine"] = mine
_spec.loader.exec_module(mine)


def rows_for(win_rate: float, ask: float, n_days: int = 12,
             per_day: int = 5, seed: int = 0):
    """Settled rows whose realized rate is `win_rate` at price `ask`."""
    rnd = random.Random(seed)
    out = []
    for d in range(n_days):
        day = f"2026-06-{d + 1:02d}"
        for _ in range(per_day):
            out.append((day, 1.0 if rnd.random() < win_rate else 0.0, ask))
    return out


def exact_rows(win_rate: float, ask: float, n_days: int = 12,
               per_day: int = 5):
    """Deterministic version: exactly `win_rate` of each day's rows win."""
    out = []
    wins = round(per_day * win_rate)
    for d in range(n_days):
        day = f"2026-06-{d + 1:02d}"
        for i in range(per_day):
            out.append((day, 1.0 if i < wins else 0.0, ask))
    return out


# ------------------------------------------------------ the spec's test

def test_a_planted_bias_series_is_flagged_and_calibrated_ones_are_not():
    """Spec section 9: one planted-bias series among calibrated ones."""
    universe = {
        # Calibrated: realized rate equals the ask, with realistic
        # day-to-day noise so the between-day SE is meaningful.
        "KXCALIBA": rows_for(0.80, 0.80, n_days=20, per_day=8, seed=1),
        "KXCALIBB": rows_for(0.60, 0.60, n_days=20, per_day=8, seed=2),
        "KXCALIBC": rows_for(0.40, 0.40, n_days=20, per_day=8, seed=3),
        # Planted: wins ~80% of the time while priced at 0.60. +20pts.
        "KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8, seed=4),
    }
    stats = [s for k, v in universe.items()
             if (s := mine.stat_for(k, v)) is not None]
    assert len(stats) == 4, "all four should clear the inclusion floors"

    survivors = mine.holm(stats)
    flagged = {s.series for s in stats
               if s.passes_split and s.passes_t and s.series in survivors}
    assert flagged == {"KXPLANTED"}, (
        f"expected exactly the planted series, got {flagged}"
    )


def test_the_planted_series_edge_is_measured_at_its_true_size():
    """Gross edge is the bias; net is reported alongside for
    bettability. See STUDY.md's 2026-08-29 amendment."""
    s = mine.stat_for("KXPLANTED", exact_rows(0.80, 0.60))
    assert s.edge == pytest.approx(20.0, abs=0.01)
    assert s.edge_net == pytest.approx(20.0 - mine.fee_pts(0.60), abs=0.01)


def test_a_perfectly_calibrated_series_shows_no_bias():
    """The amendment's whole point: scored net of fees this series would
    read as a persistent -1.12pt bias, same sign in both halves, and
    would have passed the split guard."""
    s = mine.stat_for("KXCALIB", exact_rows(0.80, 0.80))
    assert s.edge == pytest.approx(0.0, abs=0.01), "gross bias is zero"
    assert s.edge_net < -1.0, "net is negative purely from fees"
    assert not s.passes_split, "must not flag a calibrated series"


# ------------------------------------------------- the inclusion floors

def test_a_series_below_the_row_floor_is_not_read_in_either_direction():
    assert mine.stat_for("KXTHIN", exact_rows(0.9, 0.5, n_days=10, per_day=3)) is None


def test_a_series_below_the_day_floor_is_not_read():
    """30 rows but only 5 settlement days -- the clumping case the
    day-clustered statistic exists for."""
    assert mine.stat_for("KXCLUMP", exact_rows(0.9, 0.5, n_days=5, per_day=10)) is None


def test_a_series_not_alive_in_both_halves_is_excluded():
    """Survivorship (spec section 10): history truncated to one half."""
    rows = exact_rows(0.9, 0.5, n_days=12, per_day=5)
    # Collapse the second half onto two days -> fails MIN_HALF_DAYS.
    rows = [r for r in rows if r[0] <= "2026-06-06"] + \
           [("2026-06-07", w, a) for _d, w, a in rows if _d > "2026-06-06"]
    assert mine.stat_for("KXTRUNC", rows) is None


# --------------------------------------------------------- the guard

def test_a_sign_flip_between_halves_fails_the_split_guard():
    """The whole point of the split test: a series that looks biased
    overall but reverses is chance, not bias."""
    first = exact_rows(0.90, 0.60, n_days=6)                       # +30
    second = [(f"2026-07-{d + 1:02d}", w, a)
              for d, day in enumerate(range(6))
              for _dd, w, a in exact_rows(0.30, 0.60, n_days=1)]
    s = mine.stat_for("KXFLIP", first + second)
    assert s is not None
    assert (s.first_edge > 0) != (s.second_edge > 0), "fixture must reverse"
    assert not s.passes_split


def test_a_tiny_but_consistent_bias_fails_the_half_magnitude_gate():
    """Same sign in both halves is not enough; STUDY.md requires each
    half to be at least MIN_HALF_EDGE from zero."""
    # 0.805 at an ask of 0.80 = +0.5 pts gross, comfortably under the gate.
    s = mine.stat_for("KXTINY", exact_rows(0.805, 0.80, per_day=200))
    assert s is not None
    assert min(abs(s.first_edge), abs(s.second_edge)) < mine.MIN_HALF_EDGE
    assert not s.passes_split


def test_holm_is_stricter_than_uncorrected_significance():
    """With many series, a p just under 0.05 must not survive."""
    class S:
        def __init__(self, series, p):
            self.series, self.p = series, p
    family = [S(f"KX{i}", 0.04) for i in range(20)]
    assert mine.holm(family) == set(), (
        "twenty series each at p=0.04 is roughly what chance delivers; "
        "Holm must reject all of them"
    )


def test_holm_still_admits_a_genuinely_strong_result():
    class S:
        def __init__(self, series, p):
            self.series, self.p = series, p
    family = [S("KXREAL", 0.0001)] + [S(f"KX{i}", 0.6) for i in range(19)]
    assert mine.holm(family) == {"KXREAL"}


# ------------------------------------------------- the negative control

@pytest.mark.parametrize("series", ["KXTRUMPMENTION", "KXWCMENTION",
                                    "KXTRUMPSAY"])
def test_mention_family_series_are_recognised_as_the_negative_control(series):
    assert mine.is_mention_family(series)


def test_an_ordinary_series_is_not_mistaken_for_the_control():
    assert not mine.is_mention_family("KXHIGHNY")
