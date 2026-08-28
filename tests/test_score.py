import math
import sqlite3

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "t1", "Theory One", "theories/t1", now=TS)
    yield c
    c.close()


def _bet(conn, ticker, entry_price, edge, outcome="yes",
         disposition="screened"):
    opp_id, _ = ledger.record_opportunity(
        conn,
        theory_id="t1",
        theory_version=1,
        kalshi_ticker=ticker,
        outcome=outcome,
        entry_price=entry_price,
        edge_pts_net=edge,
        now=TS,
    )
    if disposition != "screened":
        ledger.interpret(conn, opp_id, disposition, "test", now=TS)
    return opp_id


def test_unsettled_opportunities_score_as_empty(conn):
    _bet(conn, "A", 0.50, 6.0)
    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 0
    assert result["win_rate"] is None


def test_win_rate_counts_matching_outcomes(conn):
    _bet(conn, "A", 0.50, 6.0, outcome="yes")
    _bet(conn, "B", 0.50, 6.0, outcome="yes")
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["n"] == 2
    assert result["win_rate"] == pytest.approx(0.5)


def test_no_side_bets_win_when_market_resolves_no(conn):
    _bet(conn, "A", 0.30, 5.0, outcome="no")
    score.record_settlement(conn, "A", "no")
    result = score.compute_score(conn, "t1", 1)
    assert result["win_rate"] == pytest.approx(1.0)


def test_calibration_edge_is_in_points(conn):
    # Two bets at 0.50, one wins -> win_rate 0.50, implied 0.50, edge 0 points
    _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["price_implied_rate"] == pytest.approx(0.50)
    assert result["calibration_edge"] == pytest.approx(0.0)


def test_positive_calibration_edge(conn):
    # Four bets at 0.50, three win -> 75% vs 50% implied = 25 points
    for ticker in "ABCD":
        _bet(conn, ticker, 0.50, 6.0)
    for ticker in "ABC":
        score.record_settlement(conn, ticker, "yes")
    score.record_settlement(conn, "D", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["calibration_edge"] == pytest.approx(25.0)


def test_realization_compares_delivered_to_claimed(conn):
    # 25 points delivered GROSS against a 25 point claim that is already net
    # of fees. The comparison must be net-to-net: at 0.50 the fee is 1.75
    # points, so 23.25 net points were delivered against the 25 claimed.
    for ticker in "ABCD":
        _bet(conn, ticker, 0.50, 25.0)
    for ticker in "ABC":
        score.record_settlement(conn, ticker, "yes")
    score.record_settlement(conn, "D", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["mean_claimed_edge"] == pytest.approx(25.0)
    assert result["mean_fee_pts"] == pytest.approx(1.75)
    assert result["calibration_edge"] == pytest.approx(25.0)
    assert result["calibration_edge_net"] == pytest.approx(23.25)
    assert result["realization"] == pytest.approx(23.25 / 25.0)


def test_break_even_after_fees_scores_zero_net_edge(conn):
    # A theory whose bets exactly cover their fees has delivered nothing.
    # Gross calibration edge is positive and says so honestly; the net figure
    # — the one realization and the lifecycle thresholds read — must be zero,
    # or a zero-profit theory survives the "pause if edge <= 0" rule.
    #
    # P is the price at which a 50% win rate breaks even after fees:
    #   0.50 - P == fee_pts(P)/100 == 0.07*P*(1-P)
    #   =>  0.07 P^2 - 1.07 P + 0.5 == 0
    p = (1.07 - math.sqrt(1.07**2 - 4 * 0.07 * 0.5)) / (2 * 0.07)
    _bet(conn, "A", p, 6.0)
    _bet(conn, "B", p, 6.0)
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["calibration_edge"] > 0, "the market really was mispriced"
    assert result["calibration_edge_net"] == pytest.approx(0.0, abs=0.01)
    assert result["roi_all"] == pytest.approx(0.0, abs=0.001)


def test_scoring_uses_the_revised_claim_not_the_screen_claim(conn):
    # The whole point of stage-2 revision is that the revised number is the
    # one the theory is held to. Scoring against the frozen screen claim
    # would make interpretation unmeasurable.
    opp_id = _bet(conn, "A", 0.50, 6.0)
    ledger.interpret(
        conn, opp_id, "endorsed", "stronger than the screen thought",
        revised_edge_pts_net=9.0, now=TS,
    )
    score.record_settlement(conn, "A", "yes")

    result = score.compute_score(conn, "t1", 1)
    assert result["mean_claimed_edge"] == pytest.approx(9.0)


def test_scores_can_be_scoped_to_a_single_run(conn):
    # Two backtest runs proposing the same market merge into one position
    # (position-identity dedup), so re-running a backtest must not multiply
    # n -- pooled still reads 1, not 2. Each run individually still finds
    # that one position, because the position is "in" every run that
    # proposed it.
    for run in ("run-a", "run-b"):
        ledger.record_opportunity(
            conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
            outcome="yes", entry_price=0.50, edge_pts_net=6.0,
            run_mode="backtest", run_id=run, now=TS,
            decision_date=TS[:10],
        )
    score.record_settlement(conn, "A", "yes")

    pooled = score.compute_score(conn, "t1", 1, run_mode="backtest")
    assert pooled["n"] == 1, "a duplicate recording must not move n"

    for run in ("run-a", "run-b"):
        scoped = score.compute_score(
            conn, "t1", 1, run_mode="backtest", run_id=run
        )
        assert scoped["n"] == 1
        assert scoped["win_rate"] == pytest.approx(1.0)


def test_roi_is_net_of_fees(conn):
    # One bet at 0.50 that wins. Cost = 0.50 + 0.0175 fee = 0.5175.
    # Return = 1.00. ROI = (1.00 - 0.5175) / 0.5175
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    result = score.compute_score(conn, "t1", 1)
    expected = (1.0 - 0.5175) / 0.5175
    assert result["roi_all"] == pytest.approx(expected, rel=1e-3)


def test_roi_taken_only_counts_taken_bets(conn):
    winner = _bet(conn, "A", 0.50, 6.0)
    _bet(conn, "B", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")
    ledger.mark_user_action(conn, winner, "taken", size=10.0, theory_id="t1")

    result = score.compute_score(conn, "t1", 1)
    assert result["roi_all"] < result["roi_taken"]
    assert result["roi_taken"] > 0


def test_roi_taken_is_none_when_nothing_was_taken(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    assert score.compute_score(conn, "t1", 1)["roi_taken"] is None


def test_disposition_filter_segments_the_sample(conn):
    _bet(conn, "A", 0.50, 6.0, disposition="endorsed")
    _bet(conn, "B", 0.50, 6.0, disposition="rejected")
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    assert score.compute_score(conn, "t1", 1, disposition="all")["n"] == 2
    endorsed = score.compute_score(conn, "t1", 1, disposition="endorsed")
    rejected = score.compute_score(conn, "t1", 1, disposition="rejected")
    assert endorsed["n"] == 1
    assert endorsed["win_rate"] == pytest.approx(1.0)
    assert rejected["win_rate"] == pytest.approx(0.0)


def test_interpretation_value_reports_the_delta(conn):
    # Endorsed picks win, rejected ones lose: interpretation is adding edge.
    for ticker in ("A", "B"):
        _bet(conn, ticker, 0.50, 6.0, disposition="endorsed")
        score.record_settlement(conn, ticker, "yes")
    for ticker in ("C", "D"):
        _bet(conn, ticker, 0.50, 6.0, disposition="rejected")
        score.record_settlement(conn, ticker, "no")

    value = score.interpretation_value(conn, "t1", 1)
    assert value["endorsed"]["win_rate"] == pytest.approx(1.0)
    assert value["rejected"]["win_rate"] == pytest.approx(0.0)
    assert value["delta"] == pytest.approx(100.0)


def test_interpretation_value_delta_is_net_not_gross(conn):
    # Endorsed bets sit at 0.10 (fee 0.63 pts), rejected bets at 0.50 (fee
    # 1.75 pts). Both groups win every bet, so their GROSS calibration edges
    # differ only because of the different implied prices (90 vs 50 -> a
    # gross delta of 40). But the NET delta must also account for the
    # differing fees: 89.37 - 48.25 = 41.12. If interpretation_value used
    # the gross figures, delta would come out as 40.0 instead.
    for ticker in ("A", "B"):
        _bet(conn, ticker, 0.10, 6.0, disposition="endorsed")
        score.record_settlement(conn, ticker, "yes")
    for ticker in ("C", "D"):
        _bet(conn, ticker, 0.50, 6.0, disposition="rejected")
        score.record_settlement(conn, ticker, "yes")

    value = score.interpretation_value(conn, "t1", 1)
    assert value["endorsed"]["calibration_edge"] == pytest.approx(90.0)
    assert value["endorsed"]["calibration_edge_net"] == pytest.approx(89.37)
    assert value["rejected"]["calibration_edge"] == pytest.approx(50.0)
    assert value["rejected"]["calibration_edge_net"] == pytest.approx(48.25)
    assert value["delta"] == pytest.approx(41.12)


def test_interpretation_value_delta_is_none_without_a_control(conn):
    _bet(conn, "A", 0.50, 6.0, disposition="endorsed")
    score.record_settlement(conn, "A", "yes")
    assert score.interpretation_value(conn, "t1", 1)["delta"] is None


def test_scores_are_segmented_by_theory_version(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=2, kalshi_ticker="B",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0, now=TS,
    )
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "B", "no")

    assert score.compute_score(conn, "t1", 1)["win_rate"] == pytest.approx(1.0)
    assert score.compute_score(conn, "t1", 2)["win_rate"] == pytest.approx(0.0)


def test_save_score_persists_a_row(conn):
    _bet(conn, "A", 0.50, 6.0)
    score.record_settlement(conn, "A", "yes")
    result = score.compute_score(conn, "t1", 1)
    row_id = score.save_score(conn, "t1", 1, "live", "all", result, now=TS)

    saved = conn.execute(
        "SELECT * FROM scores WHERE id = ?", (row_id,)
    ).fetchone()
    assert saved["theory_id"] == "t1"
    assert saved["disposition"] == "all"
    assert saved["n"] == 1
    assert saved["computed_at"] == TS
    assert saved["calibration_edge_net"] == pytest.approx(
        result["calibration_edge_net"]
    )


def test_record_settlement_is_idempotent(conn):
    score.record_settlement(conn, "A", "yes")
    score.record_settlement(conn, "A", "no")
    row = conn.execute(
        "SELECT * FROM settlements WHERE kalshi_ticker = 'A'"
    ).fetchone()
    assert row["result"] == "no"
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM settlements"
    ).fetchone()["n"]
    assert count == 1


def test_record_backtest_run_persists_all_fields(conn):
    score.record_backtest_run(
        conn, "run-a", "t1", 1,
        as_of_start="2026-01-01T00:00:00Z",
        as_of_end="2026-06-01T00:00:00Z",
        tier="A",
        uses_llm_judgment=False,
        model_cutoff="2026-01-01",
        notes="stage-1 screen only",
        now=TS,
    )
    row = conn.execute(
        "SELECT * FROM backtest_runs WHERE run_id = 'run-a'"
    ).fetchone()
    assert row["theory_id"] == "t1"
    assert row["theory_version"] == 1
    assert row["as_of_start"] == "2026-01-01T00:00:00Z"
    assert row["as_of_end"] == "2026-06-01T00:00:00Z"
    assert row["tier"] == "A"
    assert row["uses_llm_judgment"] == 0
    assert row["model_cutoff"] == "2026-01-01"
    assert row["notes"] == "stage-1 screen only"
    assert row["created_at"] == TS


def test_record_backtest_run_stores_bool_as_int(conn):
    score.record_backtest_run(conn, "run-b", "t1", 1, uses_llm_judgment=True,
                              now=TS)
    row = conn.execute(
        "SELECT uses_llm_judgment FROM backtest_runs WHERE run_id = 'run-b'"
    ).fetchone()
    assert row["uses_llm_judgment"] == 1


def test_record_backtest_run_rejects_invalid_tier(conn):
    with pytest.raises(ValueError, match="tier"):
        score.record_backtest_run(conn, "run-c", "t1", 1, tier="Z", now=TS)


def test_record_backtest_run_leaves_no_open_transaction_on_failure(conn):
    with pytest.raises(sqlite3.IntegrityError):
        score.record_backtest_run(conn, "run-d", "no_such_theory", 1, now=TS)
    assert conn.in_transaction is False
