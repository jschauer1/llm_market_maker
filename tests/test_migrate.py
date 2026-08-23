import json

import pytest

import migrate_kalshi_trader as mig
from tools import db, ledger, score, theories

TS = "2026-08-23T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


def _row(ticker="KXA", side="yes", price="0.80", q="0.90",
         ts="2026-06-01T12:00:00Z", rationale="insider story"):
    return {
        "ticker": ticker,
        "bet_side": side,
        "price": price,
        "q": q,
        "timestamp": ts,
        "rationale": rationale,
    }


def test_parse_extracts_the_core_fields():
    parsed = mig.parse_ledger_row(_row())
    assert parsed["kalshi_ticker"] == "KXA"
    assert parsed["outcome"] == "yes"
    assert parsed["entry_price"] == pytest.approx(0.80)
    assert parsed["model_prob"] == pytest.approx(0.90)


def test_parse_computes_net_edge_from_q_and_price():
    # q 0.90 vs price 0.80 = 10 points gross, minus the fee at 0.80
    parsed = mig.parse_ledger_row(_row(price="0.80", q="0.90"))
    assert parsed["edge_pts_net"] == pytest.approx(10.0 - 1.12, abs=0.01)


def test_parse_returns_none_without_a_ticker():
    assert mig.parse_ledger_row(_row(ticker="")) is None


def test_parse_returns_none_on_unparseable_price():
    assert mig.parse_ledger_row(_row(price="n/a")) is None


def test_parse_handles_integer_cent_prices():
    # The old schema stored cents; anything above 1 is cents, not dollars.
    parsed = mig.parse_ledger_row(_row(price="80", q="90"))
    assert parsed["entry_price"] == pytest.approx(0.80)
    assert parsed["model_prob"] == pytest.approx(0.90)


def test_migrate_imports_rows(conn):
    result = mig.migrate(conn, [_row("KXA"), _row("KXB")], now=TS)
    assert result["imported"] == 2
    assert len(ledger.list_opportunities(conn)) == 2


def test_migrate_registers_the_theory(conn):
    mig.migrate(conn, [_row()], now=TS)
    theory = theories.get(conn, "insider_bias")
    assert theory is not None
    assert theory["version"] == 1


def test_migrate_dedupes_repeat_recommendations(conn):
    # The source ledger appends the same bet on every run. One real bet.
    rows = [
        _row("KXA", ts="2026-06-01T12:00:00Z", price="0.80"),
        _row("KXA", ts="2026-06-02T12:00:00Z", price="0.85"),
        _row("KXA", ts="2026-06-03T12:00:00Z", price="0.88"),
    ]
    result = mig.migrate(conn, rows, now=TS)
    assert result["imported"] == 1
    assert result["deduped"] == 2

    rows_out = ledger.list_opportunities(conn)
    assert len(rows_out) == 1
    assert rows_out[0]["times_seen"] == 3


def test_migrate_keeps_the_earliest_entry_price(conn):
    rows = [
        _row("KXA", ts="2026-06-03T12:00:00Z", price="0.88"),
        _row("KXA", ts="2026-06-01T12:00:00Z", price="0.80"),
    ]
    mig.migrate(conn, rows, now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["entry_price"] == pytest.approx(0.80), \
        "earliest sighting is the entry that was actually available"
    assert row["first_seen_at"] == "2026-06-01T12:00:00Z"


def test_migrate_treats_opposite_sides_as_distinct(conn):
    result = mig.migrate(
        conn, [_row("KXA", side="yes"), _row("KXA", side="no")], now=TS
    )
    assert result["imported"] == 2


def test_migrate_marks_rows_as_untouched_and_screened(conn):
    # The historical ledger records what was SUGGESTED. The user has said
    # they did not bet it as given, so nothing may be marked taken.
    mig.migrate(conn, [_row()], now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["user_action"] == "untouched"
    assert row["disposition"] == "screened"


def test_migrate_preserves_original_timestamps(conn):
    mig.migrate(conn, [_row(ts="2026-06-01T12:00:00Z")], now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["first_seen_at"] == "2026-06-01T12:00:00Z"


def test_migrate_imports_settlements(conn):
    mig.migrate(
        conn,
        [_row("KXA")],
        scored_rows=[{"ticker": "KXA", "result": "yes",
                      "resolved_at": "2026-06-15T00:00:00Z"}],
        now=TS,
    )
    result = score.compute_score(conn, "insider_bias", 1)
    assert result["n"] == 1
    assert result["win_rate"] == pytest.approx(1.0)


def test_migrate_skips_unparseable_rows(conn):
    result = mig.migrate(conn, [_row(), _row(ticker="")], now=TS)
    assert result["imported"] == 1
    assert result["skipped"] == 1


def test_migrate_is_rerunnable_without_duplicating(conn):
    mig.migrate(conn, [_row("KXA")], now=TS)
    mig.migrate(conn, [_row("KXA")], now=TS)
    assert len(ledger.list_opportunities(conn)) == 1


# --- Corrections: real kalshi_trader column names ---------------------
#
# The real source CSV header is:
#   run_ts,config_name,ticker,event_ticker,bet_side,price,q_model,q_blend,
#   stake_usd,contracts,est_cost_usd,close_time,summary,rank,rationale,status
#
# The brief's _first(...) key lists were written before anyone looked at
# this file and don't match it: the probability column is q_blend/q_model,
# not q/model_q/blended_q, and the timestamp column is run_ts, not
# timestamp/created_at/ts. These tests pin the corrected behavior.

def _real_row(ticker="KXLIU", side="NO", price="0.7400", q_model="0.84",
              q_blend="0.787", run_ts="2026-06-10T01:33:10Z",
              stake_usd="5.18", rationale="insider story"):
    return {
        "run_ts": run_ts,
        "config_name": "insider_bias",
        "ticker": ticker,
        "event_ticker": "KXLIUSAELIMINATIONW-26JUN12",
        "bet_side": side,
        "price": price,
        "q_model": q_model,
        "q_blend": q_blend,
        "stake_usd": stake_usd,
        "contracts": "7",
        "est_cost_usd": "5.28",
        "close_time": "2026-06-13T03:59:00Z",
        "summary": "Beatriz",
        "rank": "1",
        "rationale": rationale,
        "status": "BET",
    }


def test_parse_real_columns_run_ts_q_blend_stake_usd():
    parsed = mig.parse_ledger_row(_real_row())
    assert parsed["kalshi_ticker"] == "KXLIU"
    assert parsed["outcome"] == "no"
    assert parsed["entry_price"] == pytest.approx(0.74)
    # q_blend preferred: model_prob and edge derive from it, not q_model
    assert parsed["model_prob"] == pytest.approx(0.787)
    assert parsed["timestamp"] == "2026-06-10T01:33:10Z"
    assert parsed["q_model"] == pytest.approx(0.84)
    assert parsed["q_blend"] == pytest.approx(0.787)
    assert parsed["stake_usd"] == pytest.approx(5.18)


def test_parse_prefers_q_blend_over_q_model():
    row = _real_row(q_model="0.99", q_blend="0.60")
    parsed = mig.parse_ledger_row(row)
    assert parsed["model_prob"] == pytest.approx(0.60)


def test_migrate_extra_json_round_trips_provenance(conn):
    mig.migrate(conn, [_real_row("KXLIU")], now=TS)
    row = ledger.list_opportunities(conn)[0]
    assert row["edge_basis"] == "prior"
    assert row["suggested_size"] == pytest.approx(5.18)
    extra = json.loads(row["extra_json"])
    assert extra["model_prob_source"] == \
        "kalshi_trader gpt-5 (LLM-introspected)"
    assert extra["q_model"] == pytest.approx(0.84)
    assert extra["q_blend"] == pytest.approx(0.787)


# --- Fix round 1: `result` (market resolution) vs `outcome` (bet W/L) --
#
# The real scored CSV has BOTH a `result` column (the market's resolution:
# "yes"/"no", empty while unresolved) and an `outcome` column (whether the
# BET won: "WIN"/"LOSS"/"pending"). These are categorically different and
# must not be used as fallbacks for each other. Before this fix, the
# settlement loop's `_first(row, "result", "settlement_result", "outcome")`
# would, for an unresolved row (`result=""`, `outcome="pending"`), fall
# through to writing a settlement with result="pending" — which never
# matches a bet's "yes"/"no" outcome in `compute_score`, silently scoring
# every such row as a loss.

# --- Fix round 2: `status` (BET vs LIMIT-no-edge) must survive the import --
#
# The source ledger's `status` column distinguishes rows kalshi_trader
# actually BET from rows it declined ("LIMIT: bid <= Xc (ask Y% has no
# edge)", stake_usd=0.00) where the recorded price is the ask the system
# said had NO edge. Dropping status entirely made every imported row look
# like a real recommendation. config_name is free to keep alongside it.

def test_migrate_extra_json_round_trips_limit_status(conn):
    row = _real_row("KXKAY")
    row["status"] = "LIMIT: bid <= 95c (ask 97% has no edge)"
    mig.migrate(conn, [row], now=TS)
    opp = ledger.list_opportunities(conn)[0]
    extra = json.loads(opp["extra_json"])
    assert extra["status"] == "LIMIT: bid <= 95c (ask 97% has no edge)"
    assert extra["config_name"] == "insider_bias"


def test_migrate_extra_json_round_trips_bet_status(conn):
    mig.migrate(conn, [_real_row("KXLIU")], now=TS)
    opp = ledger.list_opportunities(conn)[0]
    extra = json.loads(opp["extra_json"])
    assert extra["status"] == "BET"


def test_migrate_skips_unresolved_scored_rows(conn):
    result = mig.migrate(
        conn,
        [_row("KXA")],
        scored_rows=[{"ticker": "KXA", "result": "", "outcome": "pending",
                      "market_status": "active"}],
        now=TS,
    )
    assert result["settlements"] == 0

    score_result = score.compute_score(conn, "insider_bias", 1)
    assert score_result["n"] == 0, \
        "an unresolved market must not be scored as a settled loss"
