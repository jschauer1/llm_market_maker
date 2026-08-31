"""Scoring follows DECISIONS, not positions (ruling 2026-08-29).

`compute_score` used to group by the *position's current* disposition, so
a position re-judged by a later run had its earlier decision erased from
the record. That is the disposition-form of the silent merge the
versioning rule exists to prevent: a theory could re-see its losers, flip
them to `rejected`, and launder its endorsed pool.

The rule now: **each attempt joins the pool of its own disposition**, and
the position-level disposition is display-only, never a scoring key. A
position endorsed on Monday and rejected on Tuesday earns settlement
feedback in *both* pools, because two decisions really were made.

Fixture shape is the live case that forced the ruling -- positions 9184,
9186 and 9203, each `endorsed` 2026-08-27 then `rejected` 2026-08-28.
"""

from __future__ import annotations

import pytest

from tools import db, ledger, score, theories


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t")
    return c


def _record(c, ticker, *, disposition, price, day, run_id):
    """One attempt on one position, at a stated disposition and price."""
    res = ledger.record_opportunity(
        c, theory_id="t", theory_version=1, kalshi_ticker=ticker,
        outcome="yes", entry_price=price, edge_pts_net=5.0,
        edge_basis="model", run_id=run_id, decision_date=day,
        rationale="x",
    )
    opp_id = res[0] if isinstance(res, tuple) else res
    if disposition != "screened":
        ledger.interpret(c, opp_id, disposition, "because", now=f"{day}T00:00:00Z")
    return opp_id


def _flip(c, ticker):
    """Endorsed Monday, rejected Tuesday -- the shape that forced this."""
    opp = _record(c, ticker, disposition="endorsed", price=0.73,
                  day="2026-08-27", run_id="live-2026-08-26")
    _record(c, ticker, disposition="rejected", price=0.77,
            day="2026-08-28", run_id="live-2026-08-28")
    return opp


def test_a_reversed_decision_scores_in_BOTH_pools(conn):
    """The ruling's core: neither decision erases the other."""
    _flip(conn, "KXA-1")
    score.record_settlement(conn, "KXA-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    endorsed = score.compute_score(conn, "t", 1, disposition="endorsed")
    rejected = score.compute_score(conn, "t", 1, disposition="rejected")
    assert endorsed["n"] == 1, "the endorsement happened and must still score"
    assert rejected["n"] == 1, "the withdrawal happened and must also score"


def test_each_pool_prices_at_its_OWN_decision(conn):
    """An attempt is scored at the price of the decision it records, not
    at whatever the position row last held."""
    _flip(conn, "KXB-1")
    score.record_settlement(conn, "KXB-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    endorsed = score.compute_score(conn, "t", 1, disposition="endorsed")
    rejected = score.compute_score(conn, "t", 1, disposition="rejected")
    assert endorsed["price_implied_rate"] == pytest.approx(0.73)
    assert rejected["price_implied_rate"] == pytest.approx(0.77)


def test_a_later_run_cannot_erase_an_earlier_endorsement(conn):
    """The laundering case, stated directly: re-seeing a loser and
    flipping it to rejected must not empty the endorsed pool."""
    _flip(conn, "KXC-1")
    score.record_settlement(conn, "KXC-1", "no", resolved_at="2026-09-01T00:00:00Z")

    endorsed = score.compute_score(conn, "t", 1, disposition="endorsed")
    assert endorsed["n"] == 1
    assert endorsed["win_rate"] == 0.0, (
        "the endorsement lost, and the endorsed pool must carry that loss"
    )


def test_repeated_attempts_at_one_disposition_count_ONCE(conn):
    """No within-pool double-counting. Position 9249 on the live data was
    `screened` four times across three days at four prices; scoring it
    four times against one settlement would inflate n and over-weight
    markets merely for staying open longer."""
    _record(conn, "KXD-1", disposition="screened", price=0.91,
            day="2026-08-27", run_id="r1")
    for day, price, run in (("2026-08-28", 0.88, "r2"),
                            ("2026-08-29", 0.95, "r3"),
                            ("2026-08-29", 0.94, "r4")):
        _record(conn, "KXD-1", disposition="screened", price=price,
                day=day, run_id=run)
    score.record_settlement(conn, "KXD-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    screened = score.compute_score(conn, "t", 1, disposition="screened")
    assert screened["n"] == 1, "one market, one settlement, one row"
    assert screened["price_implied_rate"] == pytest.approx(0.91), (
        "priced at the FIRST time that verdict was reached -- the earliest "
        "price is also the least contaminated by drift toward resolution"
    )


def test_all_disposition_still_counts_each_position_once(conn):
    """`all` is the whole population, so a position that was judged twice
    must not appear twice in it."""
    _flip(conn, "KXE-1")
    score.record_settlement(conn, "KXE-1", "yes", resolved_at="2026-09-01T00:00:00Z")
    assert score.compute_score(conn, "t", 1, disposition="all")["n"] == 1


def test_a_flip_BACK_scores_both_decisions(conn):
    """endorsed -> rejected -> endorsed. The re-endorsement is a real
    changed mind at its own price, so it scores too.

    This is why the dedupe keys on disposition CHANGES rather than on
    (position, disposition) globally: global dedupe would collapse the
    second endorsement into the first and silently lose a decision.
    """
    _record(conn, "KXF-1", disposition="endorsed", price=0.70,
            day="2026-08-27", run_id="r1")
    _record(conn, "KXF-1", disposition="rejected", price=0.80,
            day="2026-08-28", run_id="r2")
    _record(conn, "KXF-1", disposition="endorsed", price=0.60,
            day="2026-08-29", run_id="r3")
    score.record_settlement(conn, "KXF-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    endorsed = score.compute_score(conn, "t", 1, disposition="endorsed")
    assert endorsed["n"] == 2, "two separate endorsements were made"
    # Both at their own prices: mean of 0.70 and 0.60.
    assert endorsed["price_implied_rate"] == pytest.approx(0.65)


def test_a_screened_row_AFTER_interpretation_is_a_non_decision(conn):
    """The scan re-seeing a market without stage 2 engaging is the
    ABSENCE of a judgment, not a judgment. Scoring it would put one
    settlement into three pools and pollute the stage-1 baseline with
    exactly the subpopulation stage 2 engaged on."""
    _record(conn, "KXG-1", disposition="endorsed", price=0.73,
            day="2026-08-27", run_id="r1")
    _record(conn, "KXG-1", disposition="rejected", price=0.77,
            day="2026-08-28", run_id="r2")
    _record(conn, "KXG-1", disposition="screened", price=0.86,
            day="2026-08-29", run_id="r3")
    score.record_settlement(conn, "KXG-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    assert score.compute_score(conn, "t", 1, disposition="endorsed")["n"] == 1
    assert score.compute_score(conn, "t", 1, disposition="rejected")["n"] == 1
    assert score.compute_score(conn, "t", 1, disposition="screened")["n"] == 0, (
        "the 08-29 row is retained in the ledger but is not a decision"
    )
    # ...and it really is still on disk.
    kept = conn.execute(
        "SELECT COUNT(*) FROM opportunity_attempts WHERE disposition='screened'"
    ).fetchone()[0]
    assert kept == 1, "unscored is not the same as deleted"


def test_a_screened_row_BEFORE_interpretation_still_scores(conn):
    """Stage 1 really did select this market before stage 2 looked at it.
    Dropping that row would bias the screened pool toward positions
    nobody ever interpreted -- a cherry-picked baseline."""
    _record(conn, "KXH-1", disposition="screened", price=0.60,
            day="2026-08-26", run_id="r0")
    _record(conn, "KXH-1", disposition="endorsed", price=0.73,
            day="2026-08-27", run_id="r1")
    score.record_settlement(conn, "KXH-1", "yes", resolved_at="2026-09-01T00:00:00Z")

    assert score.compute_score(conn, "t", 1, disposition="screened")["n"] == 1
    assert score.compute_score(conn, "t", 1, disposition="endorsed")["n"] == 1


# --------------------------------------------------- event clustering

def test_siblings_of_one_event_are_ONE_cluster(conn):
    """Fifty siblings of one event share an outcome driver. Pooling them
    as independent draws manufactures precision -- session 78's hazard
    estimate ran z~9 naive against 1.34 clustered, on 2,805 rows that
    were only 48 clusters."""
    for i in range(12):
        _record(conn, f"KXEV-26SEP01-{i}", disposition="screened",
                price=0.80, day="2026-08-27", run_id="r1")
        score.record_settlement(conn, f"KXEV-26SEP01-{i}", "yes",
                                resolved_at="2026-09-01T00:00:00Z")
    r = score.compute_score(conn, "t", 1, disposition="screened")
    assert r["n"] == 12, "twelve rows really were recorded"
    assert r["n_clusters"] == 1, (
        "but they are one event, so one draw -- this is what credibility "
        "must key on, or fifty siblings rank as n=50"
    )


def test_clustered_se_is_wider_than_the_naive_row_se(conn):
    """The whole point: correlated siblings must not buy precision."""
    import statistics
    # Two events, siblings within each disagreeing sharply between events.
    for i in range(8):
        _record(conn, f"KXA-26SEP01-{i}", disposition="screened",
                price=0.50, day="2026-08-27", run_id="r1")
        score.record_settlement(conn, f"KXA-26SEP01-{i}", "yes",
                                resolved_at="2026-09-01T00:00:00Z")
        _record(conn, f"KXB-26SEP01-{i}", disposition="screened",
                price=0.50, day="2026-08-27", run_id="r1")
        score.record_settlement(conn, f"KXB-26SEP01-{i}", "no",
                                resolved_at="2026-09-01T00:00:00Z")
    r = score.compute_score(conn, "t", 1, disposition="screened")
    assert r["n"] == 16
    assert r["n_clusters"] == 2

    rows = [50.0] * 8 + [-50.0] * 8          # per-row net edges, roughly
    naive_se = statistics.stdev(rows) / len(rows) ** 0.5
    assert r["clustered_se"] > naive_se, (
        "two clusters that disagree completely must report MORE "
        "uncertainty than sixteen rows pretending to be independent"
    )


def test_a_single_cluster_reports_no_se_rather_than_a_narrow_one(conn):
    """One cluster carries no information about spread. Returning the
    row-level SE there is exactly the overstatement this corrects."""
    for i in range(5):
        _record(conn, f"KXONE-26SEP01-{i}", disposition="screened",
                price=0.80, day="2026-08-27", run_id="r1")
        score.record_settlement(conn, f"KXONE-26SEP01-{i}", "yes",
                                resolved_at="2026-09-01T00:00:00Z")
    r = score.compute_score(conn, "t", 1, disposition="screened")
    assert r["n_clusters"] == 1
    assert r["clustered_se"] is None


def test_an_unrecoverable_event_is_counted_not_hidden(conn):
    """A ticker with no dash cannot yield an event. It clusters alone --
    conservative, since it never merges two events -- but that must be
    reported rather than silently shrinking nothing."""
    _record(conn, "NODASHTICKER", disposition="screened", price=0.80,
            day="2026-08-27", run_id="r1")
    score.record_settlement(conn, "NODASHTICKER", "yes",
                            resolved_at="2026-09-01T00:00:00Z")
    r = score.compute_score(conn, "t", 1, disposition="screened")
    assert r["unclustered_rows"] == 1
