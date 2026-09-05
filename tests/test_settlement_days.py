"""Settlement-day clustering — the confound found on 2026-08-27.

Both live theories' first scores (insider_judgment v3 n=17 at +11.85 net,
no_side_premium cell B n=12 at +14.59 net) came from opportunities that all
settled on ONE day, and a whole-population control over that same screen
(n=215 across three days) showed the day-level favorite edge swinging
+5.00 / -6.30 / +6.14 — a range wider than any edge either theory claims.
Rows settling the same day are not independent draws, so `n` overstates the
evidence. These tests pin the reporting that makes that visible.
"""

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(registered_conn):
    return registered_conn


def _bet(conn, ticker, entry_price, outcome="yes", disposition="screened",
         edge=6.0):
    opp_id, _ = ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=entry_price, edge_pts_net=edge, now=TS,
    )
    if disposition != "screened":
        ledger.interpret(conn, opp_id, disposition, "test", now=TS)
    return opp_id


def test_no_settlements_reports_no_clusters(conn):
    _bet(conn, "A", 0.80)
    out = score.settlement_day_clusters(conn, "t1", 1)
    assert out["n"] == 0
    assert out["n_days"] == 0
    assert out["days"] == []
    assert out["day_clustered_se"] is None


def test_single_day_reports_one_cluster_and_no_se(conn):
    """The 2026-08-27 case: many rows, one day, no computable SE."""
    for i, price in enumerate([0.80, 0.85, 0.90]):
        _bet(conn, f"A{i}", price)
        score.record_settlement(conn, f"A{i}", "yes",
                                resolved_at="2026-08-27T14:00:00Z")

    out = score.settlement_day_clusters(conn, "t1", 1)
    assert out["n"] == 3
    assert out["n_days"] == 1
    # One cluster cannot produce a between-cluster standard error. Reporting
    # the naive row-level SE here is exactly the overstatement this exists
    # to prevent.
    assert out["day_clustered_se"] is None
    assert out["days"][0]["day"] == "2026-08-27"
    assert out["days"][0]["n"] == 3


def test_days_carry_their_own_edge_and_are_date_sorted(conn):
    _bet(conn, "A", 0.50, outcome="yes")
    score.record_settlement(conn, "A", "yes", resolved_at="2026-08-27T01:00:00Z")
    _bet(conn, "B", 0.50, outcome="yes")
    score.record_settlement(conn, "B", "no", resolved_at="2026-08-25T01:00:00Z")

    out = score.settlement_day_clusters(conn, "t1", 1)
    assert [d["day"] for d in out["days"]] == ["2026-08-25", "2026-08-27"]
    # 08-25 lost at an implied 0.50 -> -50 pts; 08-27 won -> +50 pts.
    assert out["days"][0]["calibration_edge"] == pytest.approx(-50.0)
    assert out["days"][1]["calibration_edge"] == pytest.approx(50.0)


def test_day_clustered_se_is_the_spread_between_days(conn):
    """SE comes from between-day variation, not from row count.

    Two days at +50 and -50 have a mean of 0 and a between-day SE of 50 --
    however many rows sit inside each day.
    """
    for i in range(5):
        _bet(conn, f"W{i}", 0.50, outcome="yes")
        score.record_settlement(conn, f"W{i}", "yes",
                                resolved_at="2026-08-27T01:00:00Z")
    for i in range(5):
        _bet(conn, f"L{i}", 0.50, outcome="yes")
        score.record_settlement(conn, f"L{i}", "no",
                                resolved_at="2026-08-25T01:00:00Z")

    out = score.settlement_day_clusters(conn, "t1", 1)
    assert out["n"] == 10
    assert out["n_days"] == 2
    assert out["calibration_edge"] == pytest.approx(0.0)
    assert out["day_clustered_se"] == pytest.approx(50.0)


def test_disposition_segments_like_compute_score(conn):
    """no_side_premium encodes its cells as dispositions, so this must split."""
    _bet(conn, "A", 0.80, disposition="rejected")
    score.record_settlement(conn, "A", "yes", resolved_at="2026-08-27T01:00:00Z")
    _bet(conn, "B", 0.80, disposition="endorsed")
    score.record_settlement(conn, "B", "yes", resolved_at="2026-08-26T01:00:00Z")

    assert score.settlement_day_clusters(
        conn, "t1", 1, disposition="rejected")["n"] == 1
    assert score.settlement_day_clusters(
        conn, "t1", 1, disposition="all")["n"] == 2


def test_run_scoped_pricing_matches_compute_score(conn):
    # Position identity freezes the position row's entry_price at first
    # sighting (0.50, run r1); a later run (r2) proposing the same market
    # records its own attempt at a different price (0.80) without moving
    # the frozen position-row price. Under --run-id this must price at
    # THAT run's own attempt, exactly as compute_score does -- not at the
    # position row's frozen entry_price -- or the two reports, printed
    # side by side by `score report`, disagree about the price behind the
    # edge they show.
    score.record_backtest_run(conn, "r1", "t1", 1, tier="A")
    score.record_backtest_run(conn, "r2", "t1", 1, tier="B")
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0,
        run_mode="backtest", run_id="r1", decision_date="2026-08-24",
        now=TS,
    )
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.80, edge_pts_net=6.0,
        run_mode="backtest", run_id="r2", decision_date="2026-08-25",
        now=TS,
    )
    score.record_settlement(conn, "A", "yes",
                            resolved_at="2026-08-27T01:00:00Z")

    scoped = score.settlement_day_clusters(
        conn, "t1", 1, run_mode="backtest", run_id="r2"
    )
    assert scoped["days"][0]["price_implied_rate"] == pytest.approx(0.80), (
        "must price at r2's own attempt, not the position row's frozen "
        "first-sighting entry_price (0.50)"
    )

    pooled_by_row = score.compute_score(
        conn, "t1", 1, run_mode="backtest", run_id="r2"
    )
    assert scoped["days"][0]["price_implied_rate"] == pytest.approx(
        pooled_by_row["price_implied_rate"]
    ), "must never silently disagree with compute_score on price"


def test_pooled_clustering_still_reads_the_position_row(conn):
    # Without run_id the derived attempt table matches nothing (SQL
    # equality against a bound NULL is never true), so pooled clustering
    # keeps reading o.entry_price unchanged -- the same fallback
    # _single_leg_observations relies on.
    score.record_backtest_run(conn, "r1", "t1", 1, tier="A")
    score.record_backtest_run(conn, "r2", "t1", 1, tier="B")
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.50, edge_pts_net=6.0,
        run_mode="backtest", run_id="r1", decision_date="2026-08-24",
        now=TS,
    )
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="A",
        outcome="yes", entry_price=0.80, edge_pts_net=6.0,
        run_mode="backtest", run_id="r2", decision_date="2026-08-25",
        now=TS,
    )
    score.record_settlement(conn, "A", "yes",
                            resolved_at="2026-08-27T01:00:00Z")

    pooled = score.settlement_day_clusters(conn, "t1", 1, run_mode="backtest")
    assert pooled["days"][0]["price_implied_rate"] == pytest.approx(0.50)


def test_experiment_runs_are_excluded_when_pooling(conn):
    ledger.record_opportunity(
        conn, theory_id="t1", theory_version=1, kalshi_ticker="X",
        outcome="yes", entry_price=0.80, edge_pts_net=6.0,
        run_id="exp/whatever", now=TS,
    )
    score.record_settlement(conn, "X", "yes", resolved_at="2026-08-27T01:00:00Z")
    assert score.settlement_day_clusters(conn, "t1", 1)["n"] == 0
    assert score.settlement_day_clusters(
        conn, "t1", 1, run_id="exp/whatever")["n"] == 1
