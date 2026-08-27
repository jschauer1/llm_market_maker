"""Position identity: one position per theory version, however many runs saw it.

The defect these pin: `opportunities` used to carry `run_id` in its UNIQUE
key, so "one row per market per RUN" was enforced where "one position per
market per THEORY VERSION" was meant. Two consequences, one cause --
pooled scoring counted a re-recorded bet twice, and `times_seen` (the
counter that exists to record re-proposal) read 1 on all 9,153 rows in the
live database because every repetition inserted a new row instead of
incrementing the existing one.

See docs/DEDUP_PLAN.md.
"""

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-27T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    theories.register(c, "t2", "Theory Two", "theories/t2", now=TS)
    yield c
    c.close()


def _rec(conn, *, ticker="A", outcome="yes", price=0.60, edge=6.0,
         theory="t1", version=1, run_mode="live", run_id=None, now=TS,
         decision_date=None):
    return ledger.record_opportunity(
        conn, theory_id=theory, theory_version=version, kalshi_ticker=ticker,
        outcome=outcome, entry_price=price, edge_pts_net=edge,
        run_mode=run_mode, run_id=run_id, now=now, decision_date=decision_date,
    )


def _rows(conn):
    return conn.execute("SELECT * FROM opportunities ORDER BY id").fetchall()


# --- identity -------------------------------------------------------------

def test_two_runs_recording_one_bet_make_one_position(conn):
    a, made_a = _rec(conn, run_id="live-2026-08-26-a")
    b, made_b = _rec(conn, run_id="live-2026-08-26-b")
    assert a == b, "same bet in two runs must land on one position"
    assert made_a is True and made_b is False
    assert len(_rows(conn)) == 1


def test_a_re_proposal_increments_the_persistence_counter(conn):
    _rec(conn, run_id="r1", now=TS)
    _rec(conn, run_id="r2", now=TS2)
    assert _rows(conn)[0]["times_seen"] == 2


def test_experiment_runs_stay_in_their_own_lane(conn):
    main_id, _ = _rec(conn, run_id="live-2026-08-26")
    exp_id, _ = _rec(conn, run_id="exp/variant-a")
    assert main_id != exp_id, (
        "an experiment must not merge into the record it is measured against"
    )


def test_two_experiments_do_not_merge_into_each_other(conn):
    a, _ = _rec(conn, run_id="exp/variant-a")
    b, _ = _rec(conn, run_id="exp/variant-b")
    assert a != b


def test_versions_theories_sides_and_modes_stay_separate(conn):
    base, _ = _rec(conn)
    assert _rec(conn, version=2)[0] != base
    assert _rec(conn, theory="t2")[0] != base
    assert _rec(conn, outcome="no")[0] != base
    assert _rec(conn, ticker="B")[0] != base
    assert _rec(conn, run_mode="backtest", run_id="bt-1")[0] != base


# --- the attempt list -----------------------------------------------------

def test_each_proposal_date_is_recorded_once(conn):
    opp, _ = _rec(conn, run_id="r1", decision_date="2026-08-26")
    _rec(conn, run_id="r2", decision_date="2026-08-27")
    assert ledger.attempt_dates(conn, opp) == ["2026-08-26", "2026-08-27"]


def test_the_same_decision_recorded_twice_is_one_date(conn):
    opp, _ = _rec(conn, run_id="r1", decision_date="2026-08-26")
    _rec(conn, run_id="r2", decision_date="2026-08-26")
    assert ledger.attempt_dates(conn, opp) == ["2026-08-26"]


def test_attempts_keep_the_run_and_price_of_each_proposal(conn):
    opp, _ = _rec(conn, run_id="r1", price=0.60, decision_date="2026-08-26")
    _rec(conn, run_id="r2", price=0.80, decision_date="2026-08-27")
    got = [(a["decision_date"], a["run_id"], a["entry_price"])
           for a in ledger.attempts(conn, opp)]
    assert got == [("2026-08-26", "r1", 0.60), ("2026-08-27", "r2", 0.80)]


def test_first_sighting_still_owns_entry_price(conn):
    opp, _ = _rec(conn, run_id="r1", price=0.60, decision_date="2026-08-26")
    _rec(conn, run_id="r2", price=0.80, decision_date="2026-08-27")
    assert _rows(conn)[0]["entry_price"] == 0.60


# --- what this is all for: duplicates must not move the score -------------

def _settle(conn, ticker, result):
    score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_a_duplicate_recording_does_not_change_the_score(conn):
    _rec(conn, ticker="A", price=0.60, run_id="r1")
    _rec(conn, ticker="B", price=0.60, run_id="r1")
    _settle(conn, "A", "yes")
    _settle(conn, "B", "no")
    clean = score.compute_score(conn, "t1", 1)

    # The same two bets, re-recorded by a second run. Nothing new was
    # decided, so nothing about the measured record may move.
    _rec(conn, ticker="A", price=0.60, run_id="r2")
    _rec(conn, ticker="B", price=0.60, run_id="r2")
    after = score.compute_score(conn, "t1", 1)

    assert after["n"] == clean["n"] == 2
    assert after["calibration_edge"] == clean["calibration_edge"]
    assert after["roi_all"] == clean["roi_all"]


def test_a_repeated_winner_cannot_book_two_wins(conn):
    _rec(conn, ticker="A", price=0.50, run_id="r1")
    _rec(conn, ticker="B", price=0.50, run_id="r1")
    _settle(conn, "A", "yes")
    _settle(conn, "B", "no")
    # Re-propose only the winner, three more times, across three runs.
    for r in ("r2", "r3", "r4"):
        _rec(conn, ticker="A", price=0.50, run_id=r)
    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 2
    assert result["win_rate"] == 0.5, "one settlement is one draw"


def test_score_reports_how_many_attempts_backed_it(conn):
    _rec(conn, ticker="A", run_id="r1")
    _rec(conn, ticker="A", run_id="r2")
    _settle(conn, "A", "yes")
    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 1
    assert result["n_attempts"] == 2, "the collapse must be visible, not silent"


def test_a_single_run_can_still_be_scored_alone(conn):
    _rec(conn, ticker="A", price=0.50, run_mode="backtest", run_id="bt-1")
    _rec(conn, ticker="B", price=0.50, run_mode="backtest", run_id="bt-2")
    _settle(conn, "A", "yes")
    _settle(conn, "B", "yes")
    one = score.compute_score(conn, "t1", 1, "backtest", run_id="bt-1")
    assert one["n"] == 1


def test_a_position_is_in_every_run_that_proposed_it(conn):
    _rec(conn, ticker="A", price=0.50, run_mode="backtest", run_id="bt-1")
    _rec(conn, ticker="A", price=0.50, run_mode="backtest", run_id="bt-2")
    _settle(conn, "A", "yes")
    for run in ("bt-1", "bt-2"):
        assert score.compute_score(
            conn, "t1", 1, "backtest", run_id=run
        )["n"] == 1


def test_pooled_scoring_still_excludes_experiments(conn):
    _rec(conn, ticker="A", price=0.50, run_id="live-1")
    _rec(conn, ticker="B", price=0.50, run_id="exp/variant")
    _settle(conn, "A", "yes")
    _settle(conn, "B", "yes")
    assert score.compute_score(conn, "t1", 1)["n"] == 1
