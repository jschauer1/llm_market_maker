"""insider_bias v3 — the mechanical MENTION-family sub-path.

find_candidates and rank are pure/no-network and tested directly.
measured_rate/record touch the database and are tested against a temp
sqlite connection via tools.db, following this repo's existing convention
for ledger-touching tests (see tests/test_ledger.py).
"""

from datetime import datetime, timezone

import pytest

from theories.insider_bias import mention_bucket
from tools import db, theories

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _market(ticker, series_ticker, **overrides):
    base = {
        "platform": "kalshi",
        "ticker": ticker,
        "series_ticker": series_ticker,
        "event_ticker": series_ticker,
        "title": f"title for {ticker}",
        "yes_bid": 0.78, "yes_ask": 0.80, "no_bid": 0.20, "no_ask": 0.22,
        "mid": 0.79, "spread": 0.02, "volume": 5000.0,
        "close_time": "2026-08-30T00:00:00Z", "is_open": True,
        "rules_primary": "rules text",
    }
    base.update(overrides)
    return base


# --- find_candidates ----------------------------------------------------


def test_find_candidates_keeps_only_mention_family_screen_hits():
    board = [
        _market("KXTRUMPMENTION-1", "KXTRUMPMENTION"),
        _market("KXTRAITORS-1", "KXTRAITORS"),  # screen-eligible, not mention
    ]
    result = mention_bucket.find_candidates(board, now=NOW)
    assert [c["ticker"] for c in result] == ["KXTRUMPMENTION-1"]


def test_find_candidates_still_applies_the_full_screen():
    # Thin volume -- would pass is_mention_family but not screen.screen().
    board = [_market("KXTRUMPMENTION-1", "KXTRUMPMENTION", volume=10.0)]
    assert mention_bucket.find_candidates(board, now=NOW) == []


def test_find_candidates_empty_board():
    assert mention_bucket.find_candidates([], now=NOW) == []


# --- rank -----------------------------------------------------------------


def _candidate(ticker, entry_price, fav_side="yes"):
    return {
        "ticker": ticker, "fav_side": fav_side, "entry_price": entry_price,
        "spread": 0.02, "volume": 5000.0,
    }


MEASURED_RATES = {"mention_family": {"n": 116, "win_rate": 0.871, "mean_entry_price": 0.806}}


def test_rank_orders_by_edge_not_input_order():
    candidates = [_candidate("A", 0.95), _candidate("B", 0.70), _candidate("C", 0.85)]
    ranked = mention_bucket.rank(candidates, MEASURED_RATES, top_n=20)
    # Cheaper favorites have more room under the flat 0.871 rate -> more edge.
    assert [c["ticker"] for c in ranked] == ["B", "C", "A"]


def test_rank_attaches_measured_edge_basis():
    ranked = mention_bucket.rank([_candidate("A", 0.80)], MEASURED_RATES, top_n=20)
    assert ranked[0]["edge_basis"] == "measured"
    assert ranked[0]["edge_pts_net"] == pytest.approx((0.871 - 0.80) * 100 - _fee(0.80))


def _fee(price):
    from tools.sizing import fee_pts
    return fee_pts(price)


def test_rank_respects_top_n():
    candidates = [_candidate(str(i), 0.70 + i * 0.01) for i in range(30)]
    ranked = mention_bucket.rank(candidates, MEASURED_RATES, top_n=20)
    assert len(ranked) == 20


def test_rank_falls_back_to_prior_below_min_bucket_n():
    thin_rates = {"mention_family": {"n": 3, "win_rate": 1.0, "mean_entry_price": 0.9}}
    ranked = mention_bucket.rank([_candidate("A", 0.80)], thin_rates, top_n=20)
    assert ranked[0]["edge_basis"] == "prior"
    assert ranked[0]["edge_pts_net"] == pytest.approx(0.0)


def test_rank_handles_no_candidates():
    assert mention_bucket.rank([], MEASURED_RATES, top_n=20) == []


# --- record (touches the database) -----------------------------------


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "insider_bias", "Insider Bias", "theories/insider_bias")
    theories.set_uses_llm_judgment(c, "insider_bias", True)
    for _ in range(2):
        theories.bump_version(c, "insider_bias")  # v1 -> v2 -> v3
    yield c
    c.close()


def test_record_writes_opportunities_with_measured_edge(conn):
    ranked = mention_bucket.rank(
        [_candidate("KXTRUMPMENTION-1", 0.80)], MEASURED_RATES, top_n=20
    )
    ids = mention_bucket.record(conn, ranked, run_id="live-test-mention")
    assert len(ids) == 1
    row = conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (ids[0],)
    ).fetchone()
    assert row["kalshi_ticker"] == "KXTRUMPMENTION-1"
    assert row["edge_basis"] == "measured"
    assert row["confidence"] == "mention_family"
    assert row["disposition"] == "screened"
    assert row["theory_version"] == 3


def test_record_writes_provenance_so_the_run_is_reproducible(conn):
    ranked = mention_bucket.rank(
        [_candidate("KXTRUMPMENTION-1", 0.80)], MEASURED_RATES, top_n=20
    )
    mention_bucket.record(conn, ranked, run_id="live-test-mention")
    runs = conn.execute(
        "SELECT * FROM judgment_runs WHERE run_id = 'live-test-mention'"
    ).fetchall()
    assert len(runs) == 1
    assert runs[0]["model"] == "none (deterministic)"


def test_record_handles_no_candidates(conn):
    assert mention_bucket.record(conn, [], run_id="live-test-empty") == []
