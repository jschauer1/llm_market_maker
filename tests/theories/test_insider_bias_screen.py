from datetime import datetime, timezone

import pytest

from theories.insider_bias import screen
from tools.kalshi import markets

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def _market(**overrides):
    base = {
        "platform": "kalshi",
        "ticker": "KXTRAITORS-26-WINNER",
        "title": "Will contestant X win The Traitors?",
        "yes_bid": 0.78,
        "yes_ask": 0.80,
        "no_bid": 0.20,
        "no_ask": 0.22,
        "mid": 0.79,
        "spread": 0.02,
        "volume": 5000.0,
        "close_time": "2026-08-30T00:00:00Z",
        "is_open": True,
        "rules_primary": "Resolves Yes if X is named winner.",
    }
    base.update(overrides)
    return base


def test_favorite_is_yes_when_mid_above_half():
    side, price = screen.favorite(_market(mid=0.79))
    assert side == "yes"
    assert price == pytest.approx(0.80), "must use the ask you would pay"


def test_favorite_is_no_when_mid_below_half():
    side, price = screen.favorite(_market(mid=0.21))
    assert side == "no"
    assert price == pytest.approx(0.22)


def test_favorite_returns_none_without_a_mid():
    assert screen.favorite(_market(mid=None)) is None


def test_favorite_returns_none_without_an_executable_price():
    assert screen.favorite(_market(mid=0.79, yes_ask=None)) is None


def test_days_until_computes_a_horizon():
    assert screen.days_until("2026-08-30T00:00:00Z", now=NOW) == \
        pytest.approx(7.0, abs=0.1)


def test_days_until_handles_missing_or_bad_input():
    assert screen.days_until(None, now=NOW) is None
    assert screen.days_until("not-a-date", now=NOW) is None


def test_is_excluded_matches_sports_prefixes():
    assert screen.is_excluded("KXNFLGAME-26") is True
    assert screen.is_excluded("KXMVECROSS-1") is True
    assert screen.is_excluded("KXATP-26") is True


def test_is_excluded_allows_non_sports_tickers():
    assert screen.is_excluded("KXTRAITORS-26-WINNER") is False
    assert screen.is_excluded("KXCABINET-26") is False


def test_screen_accepts_a_clean_candidate():
    result = screen.screen([_market()], now=NOW)
    assert len(result) == 1
    assert result[0]["fav_side"] == "yes"
    assert result[0]["entry_price"] == pytest.approx(0.80)
    assert result[0]["days_to_close"] == pytest.approx(7.0, abs=0.1)


def test_screen_rejects_excluded_sports_tickers():
    assert screen.screen([_market(ticker="KXNFLGAME-26")], now=NOW) == []


def test_screen_rejects_prices_below_the_favorite_band():
    assert screen.screen(
        [_market(mid=0.55, yes_ask=0.56)], now=NOW
    ) == []


def test_screen_rejects_prices_above_the_favorite_band():
    # Too little room left to be worth the fee.
    assert screen.screen(
        [_market(mid=0.99, yes_ask=0.99)], now=NOW
    ) == []


def test_screen_rejects_wide_spreads():
    assert screen.screen(
        [_market(spread=0.12, yes_bid=0.70, yes_ask=0.82)], now=NOW
    ) == []


def test_screen_rejects_thin_volume():
    assert screen.screen([_market(volume=50.0)], now=NOW) == []


def test_screen_rejects_markets_closing_too_far_out():
    assert screen.screen(
        [_market(close_time="2027-08-30T00:00:00Z")], now=NOW
    ) == []


def test_screen_rejects_already_closed_markets():
    assert screen.screen(
        [_market(close_time="2026-08-01T00:00:00Z")], now=NOW
    ) == []


def test_screen_rejects_closed_markets():
    assert screen.screen([_market(is_open=False)], now=NOW) == []


def test_screen_thresholds_are_overridable():
    thin = _market(volume=100.0)
    assert screen.screen([thin], now=NOW) == []
    assert len(screen.screen([thin], now=NOW, min_volume=50)) == 1


def test_screen_keeps_resolution_rules_for_stage_two():
    result = screen.screen([_market()], now=NOW)
    assert "named winner" in result[0]["rules_primary"]


def test_screen_accepts_a_clean_no_side_candidate():
    # 36 of the 96 imported historical rows are NO-side, but every other
    # acceptance test in this file drives a YES candidate through screen();
    # the existing NO-side test (test_favorite_is_no_when_mid_below_half)
    # uses no_ask=0.22, which the [0.65, 0.97] favorite band rejects. This
    # is the one test that proves a NO candidate can reach acceptance.
    result = screen.screen([_market(mid=0.10, no_ask=0.90)], now=NOW)
    assert len(result) == 1
    assert result[0]["fav_side"] == "no"
    assert result[0]["entry_price"] == pytest.approx(0.90)


# --- Coupling test: normalize() output must still be what screen() wants ---
#
# The tests above hand-write normalize()'s output shape as fixtures. That
# means a key rename inside tools.kalshi.markets.normalize() could leave
# every one of them green while screen() silently returns [] against a real,
# normalized board. This test runs a raw Kalshi payload through the real
# normalize() and asserts a candidate survives, so that seam is covered too.

def _raw_kalshi_market(**overrides):
    base = {
        "ticker": "KXTRAITORS-26-WINNER",
        "event_ticker": "KXTRAITORS-26",
        "title": "Will contestant X win The Traitors?",
        "status": "active",
        "yes_bid_dollars": "0.7800",
        "yes_ask_dollars": "0.8000",
        "no_bid_dollars": "0.2000",
        "no_ask_dollars": "0.2200",
        "volume_fp": "5000.00",
        "close_time": "2026-08-30T00:00:00Z",
        "rules_primary": "Resolves Yes if X is named winner.",
    }
    base.update(overrides)
    return base


def test_normalized_kalshi_payload_survives_the_screen():
    market = markets.normalize(_raw_kalshi_market())
    result = screen.screen([market], now=NOW)
    assert len(result) == 1
    assert result[0]["fav_side"] == "yes"
    assert result[0]["entry_price"] == pytest.approx(0.80)
