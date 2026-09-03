"""A basket seen by two runs is one position, and keeps its legs."""

import pytest

from tools import db, ledger, score, theories

TS = "2026-08-26T12:00:00Z"
TS2 = "2026-08-27T12:00:00Z"

LEGS = [
    {"kalshi_ticker": "KXA-T1", "outcome": "yes", "entry_price": 0.40},
    {"kalshi_ticker": "KXA-T2", "outcome": "no", "entry_price": 0.50},
]


@pytest.fixture
def conn(registered_conn):
    return registered_conn


def _basket(conn, run_id, now=TS, decision_date=None):
    return ledger.record_basket(
        conn, theory_id="t1", theory_version=1, legs=LEGS,
        edge_pts_net=5.0, run_id=run_id, now=now,
        decision_date=decision_date,
    )


def test_two_runs_seeing_one_basket_make_one_position(conn):
    a, made_a = _basket(conn, "live-2026-08-26")
    b, made_b = _basket(conn, "live-2026-08-26-eve")
    assert a == b
    assert made_a is True and made_b is False
    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    assert len(rows) == 1


def test_the_merged_basket_keeps_exactly_one_set_of_legs(conn):
    opp, _ = _basket(conn, "live-2026-08-26")
    _basket(conn, "live-2026-08-26-eve")
    legs = ledger.get_legs(conn, opp)
    assert [leg["kalshi_ticker"] for leg in legs] == ["KXA-T1", "KXA-T2"]
    orphans = conn.execute(
        """
        SELECT COUNT(*) FROM opportunity_legs
        WHERE opportunity_id NOT IN (SELECT id FROM opportunities)
        """
    ).fetchone()[0]
    assert orphans == 0


def test_a_basket_records_an_attempt_per_decision_day(conn):
    opp, _ = _basket(conn, "r1", now=TS, decision_date="2026-08-26")
    _basket(conn, "r2", now=TS2, decision_date="2026-08-27")
    assert ledger.attempt_dates(conn, opp) == ["2026-08-26", "2026-08-27"]


def test_resighting_a_basket_with_a_judgment_carries_both_fields(conn):
    # Mirrors record_opportunity's rule: a screen run records neither
    # confidence nor judged_blind, a later judging run records both, and
    # the rollup must carry both together rather than ending up with
    # confidence='strong' and a NULL blind flag (attempt-fidelity spec
    # section 8c).
    opp, _ = _basket(conn, "r1", now=TS)
    ledger.record_basket(
        conn, theory_id="t1", theory_version=1, legs=LEGS,
        edge_pts_net=5.0, run_id="r2", now=TS2,
        confidence="strong", judged_blind=True,
    )
    row = conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (opp,)
    ).fetchone()
    assert row["confidence"] == "strong"
    assert row["judged_blind"] == 1


def _settle(conn, pairs):
    for ticker, result in pairs:
        score.record_settlement(conn, ticker, result, resolved_at=TS)


def test_run_scoped_n_attempts_does_not_count_other_runs(conn):
    # Pooled n_attempts is the basket's lifetime attempt count across every
    # run that ever proposed it -- score.compute_score's collapse reveal --
    # and that reading must not change. A run-scoped count must not fold in
    # attempts made by OTHER runs that happened to see the same basket: the
    # correlated subquery had no run filter at all, so `--run-id
    # backtest-...-s200` reported n_attempts as if every run that ever
    # touched the position belonged to it.
    _basket(conn, "r1")
    _basket(conn, "r2")
    # KXA-T1 (outcome 'yes') wins, KXA-T2 (outcome 'no') loses against a
    # 'yes' settlement -- payout 1.0, exactly the default max_payout, so
    # this is a valid at-risk observation rather than a raised mismatch.
    _settle(conn, [("KXA-T1", "yes"), ("KXA-T2", "yes")])

    pooled = score.compute_score(conn, "t1", 1)
    assert pooled["n"] == 1
    assert pooled["n_attempts"] == 2, "pooled reads the position's lifetime attempts"

    scoped = score.compute_score(conn, "t1", 1, run_id="r1")
    assert scoped["n"] == 1
    assert scoped["n_attempts"] == 1, "must not count r2's attempt too"


def test_backtest_basket_without_decision_date_is_rejected(conn):
    # Mirrors record_opportunity's rule (attempt-fidelity spec section 5):
    # without a real decision_date, a backtest replaying many days would
    # collapse every day's attempt into one row under the shared wall-clock
    # fallback.
    with pytest.raises(ValueError, match="decision_date"):
        ledger.record_basket(
            conn, theory_id="t1", theory_version=1, legs=LEGS,
            edge_pts_net=5.0, run_mode="backtest", run_id="bt-nodate",
            now=TS,
        )
