"""Schema for position identity: the lane column and the two child tables."""

import pytest

from tools import db, ledger


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_opportunities_has_a_lane_column(conn):
    assert "lane" in _columns(conn, "opportunities")


def test_the_unique_key_no_longer_contains_run_id(conn):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'opportunities'"
    ).fetchone()[0]
    assert "UNIQUE (theory_id, theory_version, run_mode, lane, " \
           "kalshi_ticker, outcome)" in " ".join(sql.split())


def test_the_attempt_table_exists_with_its_key(conn):
    # Full parity (attempt-fidelity spec section 4): every non-identity
    # argument record_opportunity accepts has a column here, not just the
    # nine the position-identity plan started with. See
    # tests/test_conventions.py::test_every_record_opportunity_param_has_an_attempt_column
    # for the enforcement that keeps this set from drifting away from the
    # ledger's real signature.
    assert _columns(conn, "opportunity_attempts") == {
        "opportunity_id", "decision_date", "run_id", "recorded_at",
        "scan_id", "entry_price", "spread_at_call", "volume_at_call",
        "model_prob", "edge_pts_gross", "fee_pts", "edge_pts_net",
        "edge_basis", "disposition", "confidence", "judged_blind",
        "rationale", "suggested_size", "evidence_source",
        "evidence_market_id", "extra_json",
    }


def test_the_fill_table_exists_with_its_key(conn):
    assert _columns(conn, "opportunity_fills") == {
        "id", "opportunity_id", "filled_on", "size", "price", "reason",
        "recorded_at",
    }


def test_a_live_run_is_the_main_lane(conn):
    assert ledger.lane_for("live-2026-08-26") == "main"
    assert ledger.lane_for(None) == "main"


def test_an_experiment_run_is_its_own_lane(conn):
    assert ledger.lane_for("exp/variant-a") == "exp/variant-a"
