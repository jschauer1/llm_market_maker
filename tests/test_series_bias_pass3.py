"""Tests for pass 3's runner (`studies/.../pass3.py`).

Pass 3 changes the *population*, never the statistic: `mine.stat_for`,
`mine.holm` and the four gates are reused unchanged, and these tests
exist to pin exactly that. What is new and therefore testable here is
the pre-registered pass-3 bookkeeping committed in STUDY.md on
2026-09-01, before any per-series number on the broad sweep existed:

  * admission by COUNT alone -- no MDE filter (reversing pass 2, whose
    SE-based floor was not outcome-neutral);
  * mention_family held OUT of the Holm family and reported as control;
  * the `measured` verdict computed from its two fixed thresholds;
  * the carried candidates' signs read as pre-registered predictions,
    so an opposite-signed result reads as a FAILED test, never a find.

Written and run against a fixture universe before `pass3.py` was pointed
at `collect.db` -- the same ordering the miner itself was built under.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_STUDY = (Path(__file__).resolve().parents[1]
          / "studies/2026-08-29-series-bias-mining")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# pass3 imports `mine`, so it must resolve on sys.path first.
sys.path.insert(0, str(_STUDY))
mine = _load("mine", _STUDY / "mine.py")
pass3 = _load("_pass3", _STUDY / "pass3.py")

from tests.test_series_bias_mining import rows_for  # noqa: E402


def test_the_planted_series_is_flagged_through_the_pass3_runner():
    """Pass 3 must reproduce the miner's own headline fixture result."""
    universe = {
        "KXCALIBA": rows_for(0.80, 0.80, n_days=20, per_day=8, seed=1),
        "KXCALIBB": rows_for(0.60, 0.60, n_days=20, per_day=8, seed=2),
        "KXCALIBC": rows_for(0.40, 0.40, n_days=20, per_day=8, seed=3),
        "KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8, seed=4),
    }
    r = pass3.run(universe)
    assert {s.series for s in r["flagged"]} == {"KXPLANTED"}


def test_mention_family_is_held_out_of_the_holm_family():
    """Revisit-angle step 3: the control must not spend correction budget.

    Ten control series in the universe must not appear in `stats` (the
    Holm family) and must be reported under `control` instead.
    """
    universe = {
        "KXCALIBA": rows_for(0.80, 0.80, n_days=20, per_day=8, seed=1),
        "KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8, seed=4),
    }
    for i in range(10):
        universe[f"KXMENTION{i}"] = rows_for(
            0.70, 0.70, n_days=20, per_day=8, seed=100 + i)

    r = pass3.run(universe)
    tested = {s.series for s in r["stats"]}
    assert not any(m.startswith("KXMENTION") for m in tested), (
        "mention_family must be excluded from the Holm family")
    assert len(r["control"]) == 10
    assert r["series_admitted"] == 12, "control is still admitted+measured"
    # The family shrank to 2, so the correction is spent on real series.
    assert len(r["stats"]) == 2


def test_admission_does_not_filter_on_mde():
    """Pass 3 reverses pass 2: an underpowered series is still TESTED.

    A noisy series has a large MDE. Under pass 2's rule it was dropped
    before Holm; under pass 3 it stays in the family, because admission
    on an SE-derived quantity is not outcome-neutral.
    """
    noisy = rows_for(0.50, 0.50, n_days=10, per_day=5, seed=7)
    universe = {"KXNOISY": noisy,
                "KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8,
                                      seed=4)}
    r = pass3.run(universe)
    assert "KXNOISY" in {s.series for s in r["stats"]}, (
        "an underpowered series must remain in the pass-3 family")
    noisy_stat = next(s for s in r["stats"] if s.series == "KXNOISY")
    assert mine.mde(noisy_stat) > mine.MAX_MDE_PTS, (
        "fixture must actually be underpowered for this test to bite")


def test_measured_verdict_uses_its_two_pre_registered_thresholds():
    """`measured` needs >=30 tested AND median MDE <=8 -- both, fixed."""
    small = {"KXPLANTED": rows_for(0.80, 0.60, n_days=20, per_day=8,
                                   seed=4)}
    assert pass3.run(small)["measured"] is False, (
        "one tested series can never be 'measured'")

    # 30+ well-powered series clears both thresholds.
    big = {f"KXS{i:03d}": rows_for(0.80, 0.80, n_days=40, per_day=20,
                                   seed=i) for i in range(35)}
    r = pass3.run(big)
    assert len(r["stats"]) >= pass3.MIN_TESTED_FOR_MEASURED
    assert r["median_mde"] <= pass3.MAX_MEDIAN_MDE_FOR_MEASURED
    assert r["measured"] is True


def test_a_carried_candidate_of_the_wrong_sign_is_not_a_confirmation():
    """KXRT is pre-registered NEGATIVE; a positive result must not read
    as a find. The runner exposes the sign so the report can say
    'failed test' rather than 'bias exists in the other direction'."""
    universe = {"KXRT": rows_for(0.80, 0.60, n_days=20, per_day=8,
                                 seed=4)}          # strongly POSITIVE
    r = pass3.run(universe)
    st = r["carried"]["KXRT"]
    assert st.edge > 0
    assert pass3.PREREGISTERED_SIGNS["KXRT"] == -1, (
        "the prediction is negative, so this fixture is the wrong sign")


def test_the_loader_shapes_collect_db_rows_for_the_miner(tmp_path):
    """`load_collect` must emit exactly {series: [(day, won, ask)]}."""
    import sqlite3
    db = tmp_path / "collect.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE obs (ticker TEXT PRIMARY KEY, series_ticker TEXT, "
        "close_time TEXT, result TEXT, side TEXT, ask REAL, won INTEGER, "
        "offset_h REAL, n_candles INTEGER, ask_24h REAL, side_24h TEXT, "
        "won_24h INTEGER, early_settled INTEGER)")
    conn.executemany(
        "INSERT INTO obs (ticker, series_ticker, close_time, ask, won) "
        "VALUES (?,?,?,?,?)",
        [("KXA-1", "KXA", "2026-06-01T12:00:00Z", 0.80, 1),
         ("KXA-2", "KXA", "2026-06-01T18:00:00Z", 0.70, 0),
         ("KXA-3", "KXA", "2026-06-02T12:00:00Z", 0.90, 1),
         # dropped: no ask, and no won -- never guessed at.
         ("KXB-1", "KXB", "2026-06-01T12:00:00Z", None, 1),
         ("KXB-2", "KXB", "2026-06-01T12:00:00Z", 0.50, None)])
    conn.commit()
    conn.close()

    out = pass3.load_collect(db)
    assert set(out) == {"KXA"}, "rows missing ask or won are dropped"
    assert sorted(out["KXA"]) == [
        ("2026-06-01", 0.0, 0.70),
        ("2026-06-01", 1.0, 0.80),
        ("2026-06-02", 1.0, 0.90)]
