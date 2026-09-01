"""calibration_harvest -- the forward cell corpus and what it refuses to read.

These tests encode one incident, in three parts.

Between 2026-08-29 and 2026-09-01 the live screen ran **twice per floor**,
once with a weather category map and once with a politics one, on the belief
(stated in the RUNBOOK) that each run covered "one complete population".
`screen()` has no population filter -- `categories` is only a label map --
so both runs screened the whole board. Measured on the 2026-09-01 board:
9,247 attempts per run, 100% overlap, 6,944 of them carrying an identical
cell key.

The damage was not only the duplicate. `domain_for` returned `"other"` both
for a series the grid deliberately does not map (Commodities, Social,
Transportation, Exotics, Education) and for a series **this run's map simply
did not cover** -- which on the weather run was 99.4% of the board. So
`other|*` silently changed meaning between runs, which is the one thing
CLAUDE.md's vocabulary rule forbids: every row already written was recorded
under the old meaning.

The fix splits the two meanings (`other` vs `unmapped`, see
`tests/theories/test_calibration_harvest_cells.py`) and quarantines the rows
written under the old one.
"""

import pytest

from tools import db, ledger, score, theories
from theories.calibration_harvest import forward_cells
from theories.calibration_harvest.theory import CalibrationHarvestTheory

TS = "2026-08-27T00:00:00Z"
V = CalibrationHarvestTheory.version


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "calibration_harvest", "Calibration Harvest",
                      "theories/calibration_harvest", now=TS)
    yield c
    c.close()


def _row(conn, ticker, cell, run_id, *, version=V, ask=0.90,
         outcome="yes", result="yes", day="2026-08-28"):
    """One live observation row in the shape forward_cells reads."""
    ledger.record_opportunity(
        conn, theory_id="calibration_harvest", theory_version=version,
        kalshi_ticker=ticker, outcome=outcome, entry_price=ask,
        edge_pts_net=0.0, run_mode="live", run_id=run_id,
        edge_basis="model",
        rationale=f"cell {cell}: no measured rows yet. Recorded so the "
                  f"cell accrues settlements; not a recommendation.",
    )
    score.record_settlement(conn, ticker, result,
                            resolved_at=f"{day}T00:00:00Z")


# ---- the meaning of `other` changed, so the old rows cannot be read ------

def test_other_cells_written_under_the_old_meaning_are_quarantined(conn):
    """`other|*` before the complete-map fix pooled every domain.

    The weather run labelled 2,244 politics markets `other`; the politics
    run labelled 59 weather markets `other`. A cell that mixes domains is
    measuring exactly what this theory claims cancels -- politics is
    compressed toward 50%, weather has the OPPOSITE sign inside 12h -- so
    the pooled cell cannot bear on the hypothesis at all.
    """
    _row(conn, "KX-A", "other|<=2d|0.85-0.92", "live-2026-08-31-calharvest",
         version=2)
    rows = forward_cells.load(conn)
    assert [r["cell"] for r in rows] == []


def test_a_correctly_labelled_cell_from_the_same_run_survives(conn):
    """Quarantine is per CELL, not per run.

    `weather|*` on the weather run and `politics|*` on the politics run
    were always correct: each was populated by exactly one run, from a map
    that did cover it. Excluding the whole run would throw those away to
    punish the `other` cells beside them.
    """
    _row(conn, "KX-W", "weather|<=2d|0.85-0.92",
         "live-2026-08-31-calharvest", version=2)
    _row(conn, "KX-O", "other|<=2d|0.85-0.92",
         "live-2026-08-31-calharvest", version=2)
    cells = {r["cell"] for r in forward_cells.load(conn)}
    assert cells == {"weather|<=2d|0.85-0.92"}


def test_other_cells_at_the_current_version_are_read_normally(conn):
    """After the fix `other` means "a category the grid does not map".

    That is a real, small residual (102 of 9,220 survivors on the
    2026-09-01 board) and a legitimate cell. The quarantine must not
    outlive the defect it was written for.
    """
    _row(conn, "KX-C", "other|<=2d|0.85-0.92", "live-2026-09-02-calharvest")
    cells = {r["cell"] for r in forward_cells.load(conn)}
    assert cells == {"other|<=2d|0.85-0.92"}


# ---- the duplicate pair --------------------------------------------------

def test_the_duplicated_2026_08_29_run_is_excluded_by_id(conn):
    """`-v2` re-ran the SAME board with the SAME map: 10,269 rows, 100%
    identical cell keys. Both copies counted into every cell.

    Run-level exclusion is right here and cell-level is not: nothing about
    the run is mislabelled, it is simply the second copy.
    """
    _row(conn, "KX-D", "weather|<=2d|0.85-0.92",
         "live-2026-08-29-calharvest", version=2)
    _row(conn, "KX-D", "weather|<=2d|0.85-0.92",
         "live-2026-08-29-calharvest-v2", version=2)
    rows = forward_cells.load(conn)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "live-2026-08-29-calharvest"


# ---- versions ------------------------------------------------------------

def test_load_reads_every_version_not_a_hardcoded_two(conn):
    """The bump to v3 is `continues`, so the corpus pools across it.

    `load` defaulted to `version=2`, which would have made every row the
    fix records invisible to the measurement the fix exists to protect.
    """
    _row(conn, "KX-V2", "weather|<=2d|0.85-0.92",
         "live-2026-08-31-calharvest", version=2)
    _row(conn, "KX-V3", "weather|<=2d|0.85-0.92",
         "live-2026-09-02-calharvest", version=3)
    tickers = {r["ticker"] for r in forward_cells.load(conn)}
    assert tickers == {"KX-V2", "KX-V3"}


def test_one_market_one_row_per_day_after_quarantine(conn):
    """The whole point, end to end.

    A politics market on 2026-09-01 was recorded twice: `other|*` by the
    weather run and `politics|*` by the politics run. After the quarantine
    exactly one row survives, and it is the correctly labelled one.
    """
    _row(conn, "KX-P", "other|<=2d|0.85-0.92",
         "live-2026-08-31-calharvest", version=2)
    _row(conn, "KX-P", "politics|<=2d|0.85-0.92",
         "live-2026-08-31-calharvest-politics", version=2)
    rows = forward_cells.load(conn)
    assert len(rows) == 1
    assert rows[0]["cell"] == "politics|<=2d|0.85-0.92"
