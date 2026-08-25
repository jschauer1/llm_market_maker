"""mention_family — a fully mechanical theory, split out of insider_bias
2026-08-24.

is_mention_family, find_candidates, bucket_for_price, rank, and
rank_preview are pure/no-network and tested directly. measured_rate/record
touch the database and are tested against a temp sqlite connection via
tools.db, following this repo's existing convention (see tests/test_ledger.py).
"""

from datetime import datetime, timezone

import pytest

from theories.insider_bias.mention_family import mention_bucket
from tools import db, score, theories
from tools.domain import Candidate, Leg, Market
from tools.sizing import fee_pts

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _market(ticker, series_ticker, **overrides):
    # screen.screen() (which find_candidates below reuses unmodified) reads
    # domain.Market objects natively since the OOP migration's Task 12 --
    # see theories/insider_bias/screen.py.
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
    return Market.from_mapping(base)


def _candidate(ticker, entry_price, fav_side="yes", volume=5000.0) -> Candidate:
    # rank/rank_preview/record all read the typed carrier since the OOP
    # migration's Task 13 -- see mention_bucket.py.
    market = Market(platform="kalshi", ticker=ticker, spread=0.02,
                    volume=volume)
    return Candidate(
        legs=(Leg(market=market, side=fav_side, price=entry_price),),
        days_to_close=5.0,
    )


#: Mirrors the real 2026-08-24 backtest's three price bins.
RATES = {
    "mention_family_lt75": {"n": 37, "win_rate": 0.730, "mean_entry_price": 0.696},
    "mention_family_75_85": {"n": 38, "win_rate": 0.868, "mean_entry_price": 0.793},
    "mention_family_85plus": {"n": 41, "win_rate": 1.000, "mean_entry_price": 0.916},
}


# --- is_mention_family ---------------------------------------------------


def test_is_mention_family_matches_mention_suffix_series():
    assert mention_bucket.is_mention_family("KXTRUMPMENTION") is True
    assert mention_bucket.is_mention_family("KXWCMENTION") is True
    assert mention_bucket.is_mention_family("KXFIGHTMENTION") is True


def test_is_mention_family_matches_say_and_act_suffixes():
    assert mention_bucket.is_mention_family("KXTRUMPSAY") is True
    assert mention_bucket.is_mention_family("KXTRUMPSAYMONTH") is False  # doesn't end in SAY
    assert mention_bucket.is_mention_family("KXTRUMPACT") is True


def test_is_mention_family_accepts_a_full_market_ticker():
    assert mention_bucket.is_mention_family("KXTRUMPMENTION-26JUL01-MAKE") is True
    assert mention_bucket.is_mention_family("KXTRAITORS-26-WINNER") is False


def test_is_mention_family_rejects_unrelated_tickers():
    assert mention_bucket.is_mention_family("KXBIGBROTHERELIMINATION") is False
    assert mention_bucket.is_mention_family("KXRT-GIR-45") is False


# --- find_candidates ----------------------------------------------------


def test_find_candidates_keeps_only_mention_family_screen_hits():
    board = [
        _market("KXTRUMPMENTION-1", "KXTRUMPMENTION"),
        _market("KXTRAITORS-1", "KXTRAITORS"),  # screen-eligible, not mention
    ]
    result = mention_bucket.find_candidates(board, now=NOW)
    assert [c.ticker for c in result] == ["KXTRUMPMENTION-1"]


def test_find_candidates_still_applies_the_full_screen():
    # Thin volume -- would pass is_mention_family but not screen.screen().
    board = [_market("KXTRUMPMENTION-1", "KXTRUMPMENTION", volume=10.0)]
    assert mention_bucket.find_candidates(board, now=NOW) == []


def test_find_candidates_empty_board():
    assert mention_bucket.find_candidates([], now=NOW) == []


def test_find_candidates_respects_default_14_day_window():
    # 20 days out -- past the default screen.MAX_DAYS_AHEAD=14.
    board = [_market("KXTRUMPMENTION-1", "KXTRUMPMENTION", close_time="2026-09-13T00:00:00Z")]
    assert mention_bucket.find_candidates(board, now=NOW) == []


def test_find_candidates_max_days_ahead_widens_the_window():
    board = [_market("KXTRUMPMENTION-1", "KXTRUMPMENTION", close_time="2026-09-13T00:00:00Z")]
    result = mention_bucket.find_candidates(board, now=NOW, max_days_ahead=30)
    assert [c.ticker for c in result] == ["KXTRUMPMENTION-1"]


# --- bucket_for_price ---------------------------------------------------


def test_bucket_for_price_matches_the_three_backtest_bins():
    assert mention_bucket.bucket_for_price(0.65) == "mention_family_lt75"
    assert mention_bucket.bucket_for_price(0.74) == "mention_family_lt75"
    assert mention_bucket.bucket_for_price(0.75) == "mention_family_75_85"
    assert mention_bucket.bucket_for_price(0.84) == "mention_family_75_85"
    assert mention_bucket.bucket_for_price(0.85) == "mention_family_85plus"
    assert mention_bucket.bucket_for_price(0.97) == "mention_family_85plus"


def test_bucket_for_price_clamps_out_of_range_rather_than_raising():
    assert mention_bucket.bucket_for_price(0.50) == "mention_family_lt75"
    assert mention_bucket.bucket_for_price(0.99) == "mention_family_85plus"


# --- rank -----------------------------------------------------------------


def test_rank_uses_each_candidates_own_price_bin():
    # A cheap ($0.68) and a strong ($0.90) favorite must NOT share one rate.
    candidates = [_candidate("cheap", 0.68), _candidate("strong", 0.90)]
    ranked = mention_bucket.rank(candidates, RATES, top_n=20)
    by_ticker = {c.candidate.ticker: c for c in ranked}
    assert by_ticker["cheap"].confidence == "mention_family_lt75"
    assert by_ticker["strong"].confidence == "mention_family_85plus"
    # The strong favorite's bin has both a higher win rate AND less edge
    # headroom lost to fees than the naive flat-rate model would have given
    # the cheap one -- this is the fix: the cheap end no longer looks best.
    assert by_ticker["strong"].edge.pts_net > by_ticker["cheap"].edge.pts_net


def test_rank_attaches_measured_edge_basis():
    ranked = mention_bucket.rank([_candidate("A", 0.80)], RATES, top_n=20)
    assert ranked[0].edge.basis == "measured"
    assert ranked[0].edge.pts_net == pytest.approx(
        (0.868 - 0.80) * 100 - fee_pts(0.80)
    )


def test_rank_respects_top_n():
    candidates = [_candidate(str(i), 0.70 + i * 0.005) for i in range(30)]
    ranked = mention_bucket.rank(candidates, RATES, top_n=20)
    assert len(ranked) == 20


def test_rank_falls_back_to_prior_below_min_bucket_n():
    thin_rates = {"mention_family_75_85": {"n": 3, "win_rate": 1.0, "mean_entry_price": 0.9}}
    ranked = mention_bucket.rank([_candidate("A", 0.80)], thin_rates, top_n=20)
    assert ranked[0].edge.basis == "prior"
    assert ranked[0].edge.pts_net == pytest.approx(0.0)


def test_rank_handles_no_candidates():
    assert mention_bucket.rank([], RATES, top_n=20) == []


def test_rank_breaks_edge_ties_by_volume():
    # Same price -> same bucket -> same edge; higher volume should sort first.
    candidates = [
        _candidate("thin", 0.80, volume=600.0),
        _candidate("liquid", 0.80, volume=9000.0),
    ]
    ranked = mention_bucket.rank(candidates, RATES, top_n=20)
    assert [c.candidate.ticker for c in ranked] == ["liquid", "thin"]


# --- rank_preview -----------------------------------------------------


def test_rank_preview_always_returns_model_basis_never_measured():
    ranked = mention_bucket.rank_preview([_candidate("A", 0.80)], RATES, top_n=20)
    assert ranked[0].edge.basis == "model"


def test_rank_preview_uses_the_bin_rate_as_a_point_estimate():
    ranked = mention_bucket.rank_preview([_candidate("A", 0.80)], RATES, top_n=20)
    assert ranked[0].edge.pts_net == pytest.approx(
        (0.868 - 0.80) * 100 - fee_pts(0.80)
    )


def test_rank_preview_orders_by_each_candidates_own_bin_edge():
    # A: 0.95 -> mention_family_85plus (win_rate 1.0) -> edge ~4.67pts.
    # B: 0.70 -> mention_family_lt75 (win_rate 0.730) -> edge ~1.53pts.
    # Real per-bin lookup, not a flat rate -- computed, not assumed.
    candidates = [_candidate("A", 0.95), _candidate("B", 0.70)]
    ranked = mention_bucket.rank_preview(candidates, RATES, top_n=20)
    assert [c.candidate.ticker for c in ranked] == ["A", "B"]


def test_rank_preview_zero_edge_when_validated_bucket_has_no_history():
    ranked = mention_bucket.rank_preview([_candidate("A", 0.80)], {}, top_n=20)
    assert ranked[0].edge.basis == "model"
    assert ranked[0].edge.pts_net == pytest.approx(0.0)


# --- record (touches the database) -----------------------------------


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    theories.register(c, "mention_family", "Mention Family", "theories/insider_bias/mention_family")
    # Deliberately NOT calling set_uses_llm_judgment -- this theory has no
    # LLM anywhere, so it stays at the default False, and record_provenance
    # is still called (see its docstring) even though nothing requires it.
    yield c
    c.close()


def test_record_writes_opportunities_with_the_candidates_own_bin(conn):
    ranked = mention_bucket.rank(
        [_candidate("KXTRUMPMENTION-1", 0.80)], RATES, top_n=20
    )
    ids = mention_bucket.record(conn, ranked, run_id="live-test-mention")
    assert len(ids) == 1
    row = conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (ids[0],)
    ).fetchone()
    assert row["kalshi_ticker"] == "KXTRUMPMENTION-1"
    assert row["theory_id"] == "mention_family"
    assert row["edge_basis"] == "measured"
    assert row["confidence"] == "mention_family_75_85"
    assert row["disposition"] == "screened"
    assert row["theory_version"] == 1


def test_record_works_without_uses_llm_judgment_declared(conn):
    # No set_uses_llm_judgment call in the fixture -- proves this theory
    # does not need it, unlike insider_bias.
    row = theories.get(conn, "mention_family")
    assert row["uses_llm_judgment"] == 0
    ranked = mention_bucket.rank([_candidate("KXTRUMPMENTION-1", 0.80)], RATES, top_n=20)
    ids = mention_bucket.record(conn, ranked, run_id="live-test-mention")
    assert len(ids) == 1


def test_record_writes_provenance_anyway_for_reproducibility(conn):
    ranked = mention_bucket.rank(
        [_candidate("KXTRUMPMENTION-1", 0.80)], RATES, top_n=20
    )
    mention_bucket.record(conn, ranked, run_id="live-test-mention")
    runs = conn.execute(
        "SELECT * FROM judgment_runs WHERE run_id = 'live-test-mention'"
    ).fetchall()
    assert len(runs) == 1
    assert runs[0]["model"] == "none (deterministic)"
    assert runs[0]["theory_id"] == "mention_family"


def test_record_handles_no_candidates(conn):
    assert mention_bucket.record(conn, [], run_id="live-test-empty") == []


def test_record_preview_uses_a_suffixed_confidence_bucket(conn):
    ranked = mention_bucket.rank_preview(
        [_candidate("KXTRUMPMENTION-1", 0.80)], RATES, top_n=20
    )
    ids = mention_bucket.record(
        conn, ranked, run_id="live-test-preview",
        confidence_suffix="_preview_30d",
    )
    row = conn.execute(
        "SELECT * FROM opportunities WHERE id = ?", (ids[0],)
    ).fetchone()
    assert row["confidence"] == "mention_family_75_85_preview_30d"
    assert row["edge_basis"] == "model"
    assert "EXTRAPOLATION" in row["rationale"]


def test_record_preview_never_pools_into_the_validated_bucket(conn):
    # A suffixed confidence label means score.bucket_rates() for the
    # validated bin names is unaffected by a preview run. bucket_rates()
    # only counts settled opportunities, so settle this one to observe it.
    ranked = mention_bucket.rank_preview(
        [_candidate("KXTRUMPMENTION-1", 0.80)], RATES, top_n=20
    )
    mention_bucket.record(
        conn, ranked, run_id="live-test-preview",
        confidence_suffix="_preview_30d",
    )
    score.record_settlement(conn, "KXTRUMPMENTION-1", result="yes")
    rates = score.bucket_rates(conn, "mention_family", 1, run_mode="live")
    assert "mention_family_75_85" not in rates
    assert "mention_family_75_85_preview_30d" in rates
