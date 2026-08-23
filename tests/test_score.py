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
    # 25 points delivered against a 25 point claim -> realization 1.0
    for ticker in "ABCD":
        _bet(conn, ticker, 0.50, 25.0)
    for ticker in "ABC":
        score.record_settlement(conn, ticker, "yes")
    score.record_settlement(conn, "D", "no")

    result = score.compute_score(conn, "t1", 1)
    assert result["mean_claimed_edge"] == pytest.approx(25.0)
    assert result["realization"] == pytest.approx(1.0)


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
    ledger.mark_user_action(conn, winner, "taken", size=10.0)

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
