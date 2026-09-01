"""Sub-theory scoring — a slice's record persists under its own name.

A sub-theory is a theory run over a SUBSET of another theory's data. Its
evidence is its own: it accrues separately, clears its own gates, and can
be strong while the parent it lives inside is flat. `insider_judgment` is
the worked example — a breakeven screen whose strong/moderate-NO subset
is the best-evidenced result in the repo.

Until this module's mechanism existed, `scores` had no column for a
segment, so `score report --save` persisted only the parent aggregate:
sub-theory evidence was recomputed live and thrown away, and `state` —
the surface every session orients on — could not show it at all. A
sub-theory whose record was strong stayed invisible to the session that
should have bet it.
"""

from __future__ import annotations

import pytest

from tools import db, ledger, score, slices, theories


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t", status="testing")
    return c


def _settled(c, ticker, *, outcome="no", confidence="strong", price=0.85,
             result=None, resolved="2026-09-01T00:00:00Z"):
    ledger.record_opportunity(
        c, theory_id="t", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=price, edge_pts_net=4.0,
        edge_basis="model", run_mode="live", run_id="live",
        decision_date="2026-08-27", confidence=confidence, rationale="x",
    )
    score.record_settlement(
        c, ticker, result if result is not None else outcome,
        resolved_at=resolved,
    )


def _sub_theory(c):
    """A strong/moderate-NO subset inside a theory that also holds
    weak/YES rows — the insider_judgment shape in miniature."""
    slices.register_slice(
        c, "t", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="the NO subset carries the edge the aggregate hides",
        origin="test fixture",
        registered_at="2026-08-26T00:00:00Z",
    )


def test_a_saved_score_defaults_to_the_theory_aggregate(conn):
    """Every score written before segments existed was the parent's, so
    the default must keep meaning exactly that."""
    result = score.compute_score(conn, "t", 1, "live", "all")
    score.save_score(conn, "t", 1, "live", "all", result)

    row = conn.execute("SELECT segment FROM scores").fetchone()
    assert row["segment"] == "aggregate"


def test_a_sub_theorys_score_persists_under_its_own_segment(conn):
    _sub_theory(conn)
    for i in range(12):
        _settled(conn, f"SUB{i}", resolved=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")

    saved = score.save_segment_scores(conn, "t", 1)

    segments = {
        r["segment"] for r in conn.execute("SELECT segment FROM scores")
    }
    assert "aggregate" in segments
    assert "slice:strong-moderate-no" in segments
    assert saved["slice:strong-moderate-no"] is not None


def test_a_sub_theory_can_be_strong_while_its_parent_is_flat(conn):
    """The case the user named: evidence for the sub-theory and none for
    the theory. Both records persist, separately, and neither is allowed
    to average the other away."""
    _sub_theory(conn)
    # The subset wins.
    for i in range(12):
        _settled(conn, f"WIN{i}",
                 resolved=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")
    # Rows outside the subset lose, dragging the aggregate down.
    for i in range(12):
        _settled(conn, f"LOSE{i}", outcome="yes", confidence="weak",
                 result="no", resolved=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")

    score.save_segment_scores(conn, "t", 1)

    def net(segment):
        return conn.execute(
            "SELECT calibration_edge_net FROM scores WHERE segment = ?"
            " ORDER BY computed_at DESC LIMIT 1", (segment,),
        ).fetchone()["calibration_edge_net"]

    assert net("slice:strong-moderate-no") > 0
    assert net("aggregate") < net("slice:strong-moderate-no")


def test_the_complement_persists_so_the_remainder_never_borrows(conn):
    """A ready sub-theory partitions the parent. The leftover rows get
    their own row too, or the remainder would silently rank on a record
    the subset earned."""
    _sub_theory(conn)
    for i in range(12):
        _settled(conn, f"WIN{i}",
                 resolved=f"2026-09-{(i % 6) + 1:02d}T00:00:00Z")
    for i in range(4):
        _settled(conn, f"OTHER{i}", outcome="yes", confidence="weak",
                 resolved=f"2026-09-{i + 1:02d}T00:00:00Z")

    score.save_segment_scores(conn, "t", 1)

    segments = {
        r["segment"] for r in conn.execute("SELECT segment FROM scores")
    }
    assert "complement" in segments


def test_an_unready_sub_theory_still_records_its_accruing_evidence(conn):
    """Below its gates a sub-theory changes no ranking — but its record
    must still be visible, or nobody can see it approaching readiness."""
    _sub_theory(conn)
    _settled(conn, "ONE")

    score.save_segment_scores(conn, "t", 1)

    row = conn.execute(
        "SELECT n FROM scores WHERE segment = 'slice:strong-moderate-no'"
    ).fetchone()
    assert row is not None and row["n"] == 1


def _backtest_settled(c, ticker, run_id, *, outcome="no", confidence="strong",
                      resolved="2026-06-05T00:00:00Z"):
    ledger.record_opportunity(
        c, theory_id="t", theory_version=1, kalshi_ticker=ticker,
        outcome=outcome, entry_price=0.85, edge_pts_net=4.0,
        edge_basis="model", run_mode="backtest", run_id=run_id,
        decision_date="2026-06-01", confidence=confidence, rationale="x",
    )
    score.record_settlement(c, ticker, outcome, resolved_at=resolved)


def test_a_theory_and_its_sub_theories_share_one_evidence_pool(conn):
    """A parent scored over live rows while its sub-theory is scored over
    live+backtest is two different questions answered side by side. The
    numbers would not be comparable, and the sub-theory would look like
    it had evidence the parent somehow lacked."""
    _sub_theory(conn)
    score.record_backtest_run(conn, "bt-1", "t", 1, tier="B")
    _settled(conn, "LIVE1")
    for i in range(8):
        _backtest_settled(conn, f"BT{i}", "bt-1",
                          resolved=f"2026-06-{i + 1:02d}T00:00:00Z")

    score.save_segment_scores(conn, "t", 1)

    rows = {
        r["segment"]: r for r in conn.execute(
            "SELECT segment, n, run_mode FROM scores")
    }
    assert rows["aggregate"]["n"] == 9, (
        "the parent must see the backtest rows its sub-theory sees"
    )
    assert rows["slice:strong-moderate-no"]["n"] == 9


def test_a_pooled_score_is_labelled_pooled_not_live(conn):
    """A row spanning live and backtest evidence must not claim to be a
    live-only measurement -- that is the row-mixing this repo keeps
    getting bitten by."""
    _sub_theory(conn)
    _settled(conn, "LIVE1")

    score.save_segment_scores(conn, "t", 1)

    modes = {r["run_mode"] for r in conn.execute(
        "SELECT run_mode FROM scores")}
    assert modes == {"pooled"}


def test_scoring_can_still_be_scoped_to_one_run_mode(conn):
    _sub_theory(conn)
    score.record_backtest_run(conn, "bt-1", "t", 1, tier="B")
    _settled(conn, "LIVE1")
    _backtest_settled(conn, "BT0", "bt-1")

    score.save_segment_scores(conn, "t", 1, run_modes=("live",))

    row = conn.execute(
        "SELECT n, run_mode FROM scores WHERE segment = 'aggregate'"
    ).fetchone()
    assert row["n"] == 1 and row["run_mode"] == "live"
