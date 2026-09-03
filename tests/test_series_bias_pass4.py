"""Tests for pass 4's runner (`tickets/study/.../pass4.py`).

Pass 4 changes the *population* again and nothing else: it is pass 3
restricted to observations that carried a tradeable book at the decision
point. So these tests pin exactly the two things that are new, and
deliberately re-pin one thing that must NOT have changed:

  * the tradeable-book WHERE clause -- `spread <= 0.07` AND
    `open_interest >= 100`, with a NULL in either field excluded rather
    than treated as passing;
  * `filter_accounting`, whose counts STUDY.md's correction requires be
    recorded with the threshold ("the chosen value is recorded here with
    the count of observations it removes"). Admitted + removed must
    reconcile against the priced total, and the by-reason breakdown must
    partition the removals;
  * **the acceptance test as a real term in `measured`** -- STUDY.md
    fixes it twice: *if mention_family still trips the gates under that
    filter, the population is still wrong and pass 4 is not measured
    either, whatever else it flags.* Pass 3 flagged nine series and was
    not measured; a pass 4 that printed the control as advice rather
    than enforcing it would repeat that failure while looking like it
    had fixed it;
  * that the statistic and gates are still pass 3's, by reusing pass 3's
    own headline fixture through pass 4's runner.

Written and run against a fixture universe before `pass4.py` was pointed
at `collect.db`, the same ordering pass 3 and the miner were built under.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

_STUDY = (Path(__file__).resolve().parents[1]
          / "tickets/study/investigation"
          / "2026-08-29-series-bias-mining")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# pass4 imports `mine` and `pass3`, so both must resolve on sys.path.
sys.path.insert(0, str(_STUDY))
mine = _load("mine", _STUDY / "mine.py")
pass3 = _load("pass3", _STUDY / "pass3.py")
pass4 = _load("_pass4", _STUDY / "pass4.py")

from tests.test_series_bias_mining import rows_for  # noqa: E402

_SCHEMA = """
CREATE TABLE obs (
  ticker TEXT PRIMARY KEY, series_ticker TEXT, close_time TEXT,
  result TEXT, side TEXT, ask REAL, won REAL, offset_h REAL,
  n_candles INTEGER, ask_24h REAL, side_24h TEXT, won_24h REAL,
  early_settled INTEGER, spread REAL, volume REAL,
  open_interest REAL, spread_24h REAL)
"""


def _db(tmp_path, universe, *, spread=0.01, oi=500.0,
        early=0, with_24h=True):
    """A collect.db-shaped fixture from {series: [(day, won, ask), ...]}.

    `spread`/`oi` may be a scalar (applied to every row) or a callable
    taking the series name, so a test can make one series untradeable.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "collect.db"
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    i = 0
    for series, rows in universe.items():
        sp = spread(series) if callable(spread) else spread
        oi_ = oi(series) if callable(oi) else oi
        for day, won, ask in rows:
            i += 1
            conn.execute(
                "INSERT INTO obs (ticker, series_ticker, close_time, "
                "ask, won, ask_24h, won_24h, early_settled, spread, "
                "open_interest, spread_24h) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (f"{series}-{i}", series, f"{day}T00:00:00Z", ask, won,
                 ask if with_24h else None, won if with_24h else None,
                 early, sp, oi_, sp))
    conn.commit()
    conn.close()
    return path


# ------------------------------------------------- the filter clause

def test_the_filter_admits_only_a_tradeable_book(tmp_path):
    """spread <= 0.07 AND open_interest >= 100, at the decision point."""
    universe = {"KXTIGHT": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=1)}
    ok = _db(tmp_path / "a", universe, spread=0.07, oi=100.0)
    assert len(pass4.load_tradeable(ok)["KXTIGHT"]) == 50

    wide = _db(tmp_path / "b", universe, spread=0.08, oi=100.0)
    assert pass4.load_tradeable(wide) == {}

    empty = _db(tmp_path / "c", universe, spread=0.07, oi=99.0)
    assert pass4.load_tradeable(empty) == {}


def test_a_null_book_field_is_excluded_not_treated_as_passing(tmp_path):
    """The 0.02% of rows the backfill never reached must not sneak in.

    SQL comparisons against NULL are neither true nor false, so a filter
    written as `NOT (spread > 0.07)` would admit them. This pins the
    positive form.
    """
    universe = {"KXNULL": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=1)}
    p = _db(tmp_path / "n", universe, spread=None, oi=500.0)
    assert pass4.load_tradeable(p) == {}
    p2 = _db(tmp_path / "n2", universe, spread=0.01, oi=None)
    assert pass4.load_tradeable(p2) == {}


def test_filter_accounting_reconciles_and_partitions(tmp_path):
    """Admitted + removed == priced, and the reasons partition removals."""
    universe = {
        "KXGOOD": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=1),
        "KXWIDE": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=2),
        "KXTHIN": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=3),
    }
    p = _db(tmp_path / "acct", universe,
            spread=lambda s: 0.20 if s == "KXWIDE" else 0.01,
            oi=lambda s: 0.0 if s == "KXTHIN" else 500.0)
    f = pass4.filter_accounting(p)
    assert f["priced_obs"] == 150
    assert f["admitted"] == 50
    assert f["removed"] == 100
    assert f["admitted"] + f["removed"] == f["priced_obs"]
    assert f["fails_spread_only"] == 50          # KXWIDE
    assert f["fails_oi_only"] == 50              # KXTHIN
    assert f["fails_both"] == 0
    assert f["no_book_fields"] == 0
    assert (f["fails_spread_only"] + f["fails_oi_only"]
            + f["fails_both"] + f["no_book_fields"]) == f["removed"]


# ------------------------------------------- the acceptance test

def test_a_tripping_control_makes_the_pass_not_measured(tmp_path):
    """STUDY.md's acceptance test, enforced rather than printed.

    The universe is built so pass 3's own criterion is comfortably met
    (well over 30 tested series at low MDE) and one control series
    carries a planted bias. `measured` must still be False, and the
    pass-3 criterion must be reported separately as met -- so a reader
    can see it was the control that decided, not power.
    """
    universe = {f"KXCAL{i:02d}": rows_for(0.80, 0.80, n_days=20,
                                          per_day=40, seed=i)
                for i in range(40)}
    universe["KXMENTIONBAD"] = rows_for(0.60, 0.80, n_days=20,
                                        per_day=40, seed=99)
    p = _db(tmp_path / "ctl", universe)
    r = pass4.run(p)
    assert [s.series for s in r["control_tripping"]] == ["KXMENTIONBAD"]
    assert r["control_clean"] is False
    assert r["measured_pass3_criterion"] is True
    assert r["measured"] is False


def test_a_clean_control_leaves_the_pass3_criterion_deciding(tmp_path):
    """With the control quiet, `measured` is pass 3's criterion again."""
    universe = {f"KXCAL{i:02d}": rows_for(0.80, 0.80, n_days=20,
                                          per_day=40, seed=i)
                for i in range(40)}
    universe["KXMENTIONOK"] = rows_for(0.80, 0.80, n_days=20,
                                       per_day=40, seed=98)
    p = _db(tmp_path / "clean", universe)
    r = pass4.run(p)
    assert r["control_tripping"] == []
    assert r["control_clean"] is True
    assert r["measured"] is r["measured_pass3_criterion"]


# ------------------------------------- the bar is still pass 3's

def test_pass3s_headline_fixture_reproduces_through_pass4(tmp_path):
    """The statistic and the four gates must be pass 3's, unchanged.

    Same universe as `test_the_planted_series_is_flagged_through_the_
    pass3_runner`, with every row given a tradeable book so the filter
    is a no-op. If pass 4 flagged anything different here, it would have
    changed the bar rather than the population.
    """
    universe = {
        "KXCALIBA": rows_for(0.80, 0.80, n_days=20, per_day=8, seed=1),
        "KXCALIBB": rows_for(0.60, 0.60, n_days=20, per_day=8, seed=2),
        "KXCALIBC": rows_for(0.40, 0.40, n_days=20, per_day=8, seed=3),
        "KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8, seed=4),
    }
    p = _db(tmp_path / "same", universe)
    r = pass4.run(p)
    assert {s.series for s in r["flagged"]} == {"KXPLANTED"}
    #: and the filter really was a no-op, so the comparison is clean
    assert pass4.load_tradeable(p) == pass3.load_collect(p)


def test_the_24h_view_filters_on_its_own_spread(tmp_path):
    """The 24h view uses `spread_24h`, not the 25%-point spread.

    It borrows open interest from the 25% point because no
    `open_interest_24h` was ever captured -- documented in `_view_clause`
    -- but the spread condition must be the one belonging to its own
    timestamp, or the view is not the robustness check it claims to be.
    """
    universe = {"KXV": rows_for(0.8, 0.8, n_days=10, per_day=5, seed=1)}
    p = _db(tmp_path / "v", universe, spread=0.01, oi=500.0)
    conn = sqlite3.connect(p)
    conn.execute("UPDATE obs SET spread_24h = 0.30")
    conn.commit()
    conn.close()
    assert pass4.load_tradeable(p, view="primary") != {}
    assert pass4.load_tradeable(p, view="at_24h") == {}
