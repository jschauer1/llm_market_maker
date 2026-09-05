from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

from collect_quotes import (
    build_blind_rule,
    depth_curves,
    select_historical_entry,
)


SCRIPT = Path(__file__).with_name("collect_quotes.py")


def _ts(hour: int, minute: int) -> int:
    return int(datetime(2026, 5, 15, hour, minute, tzinfo=timezone.utc).timestamp())


def test_historical_entry_skips_untradeable_candles_and_uses_first_valid_close():
    """A missing side or wide spread must not become the selected entry."""
    candles = [
        {
            "end_period_ts": _ts(12, 14),
            "yes_bid": {"close_dollars": "0.40"},
            "yes_ask": {"close_dollars": "0.44"},
        },
        {
            "end_period_ts": _ts(12, 15),
            "yes_bid": {"close_dollars": "0.40"},
            "yes_ask": {"close_dollars": None},
        },
        {
            "end_period_ts": _ts(12, 16),
            "yes_bid": {"close_dollars": "0.40"},
            "yes_ask": {"close_dollars": "0.48"},
        },
        {
            "end_period_ts": _ts(12, 17),
            "yes_bid": {"close_dollars": "0.41"},
            "yes_ask": {"close_dollars": "0.47"},
        },
    ]

    result = select_historical_entry(candles, _ts(12, 0))

    assert result["selected"] == {
        "candle_end_utc": "2026-05-15T12:17:00Z",
        "yes_bid": 0.41,
        "yes_ask": 0.47,
        "no_ask": 0.59,
        "spread": 0.06,
    }
    assert [row["reason"] for row in result["excluded_candles"]] == [
        "before_entry_window",
        "missing_bid_or_ask",
        "spread_above_0.07",
    ]


def test_historical_entry_accepts_archived_price_keys_and_closes_window_at_75_minutes():
    """Archived candles omit the dollars suffix and the 60-minute search is inclusive."""
    candles = [
        {
            "end_period_ts": _ts(13, 15),
            "yes_bid": {"close": "0.22"},
            "yes_ask": {"close": "0.25"},
        },
        {
            "end_period_ts": _ts(13, 16),
            "yes_bid": {"close": "0.30"},
            "yes_ask": {"close": "0.31"},
        },
    ]

    result = select_historical_entry(candles, _ts(12, 0))

    assert result["selected"]["candle_end_utc"] == "2026-05-15T13:15:00Z"
    assert result["selected"]["no_ask"] == 0.78
    assert result["excluded_candles"][-1]["reason"] == "after_entry_window"


def test_depth_curves_invert_opposite_side_bids_and_keep_fractional_quantity():
    """Buying YES crosses NO bids; buying NO crosses YES bids at one minus bid."""
    orderbook = {
        "yes_dollars": [["0.70", "25.5"], ["0.65", "100"]],
        "no_dollars": [["0.60", "40.5"], ["0.55", "100"]],
    }

    curves = depth_curves(orderbook, targets=(100, 500, 1000))

    yes_100 = curves["buy_yes"]["100"]
    assert yes_100 == {
        "target_contracts": 100.0,
        "filled_contracts": 100.0,
        "available_contracts": 140.5,
        "fill_complete": True,
        "best_ask": 0.4,
        "worst_ask": 0.45,
        "vwap_ask": pytest.approx(0.42975),
        "adverse_price_movement": 0.05,
    }
    no_100 = curves["buy_no"]["100"]
    assert no_100["best_ask"] == pytest.approx(0.30)
    assert no_100["worst_ask"] == pytest.approx(0.35)
    assert no_100["vwap_ask"] == pytest.approx(0.33725)
    assert curves["buy_yes"]["500"]["fill_complete"] is False
    assert curves["buy_yes"]["500"]["filled_contracts"] == 140.5
    assert curves["buy_yes"]["500"]["available_contracts"] == 140.5


def test_blind_rule_output_has_exact_rules_without_market_economics_or_result():
    """Adding a market field must not leak prices, status, or outcome to judges."""
    market = {
        "ticker": "KXFDAAPPROVE-CAG-26OCT01",
        "title": "Will the FDA approve CagriSema before Oct 1, 2026?",
        "rules_primary": "Primary text.",
        "rules_secondary": "Secondary text.",
        "custom_strike": {"Before": "Oct 1, 2026"},
        "yes_bid_dollars": "0.42",
        "yes_ask_dollars": "0.47",
        "result": "yes",
        "status": "finalized",
    }

    rule = build_blind_rule(
        market,
        deadline="2026-10-01",
        rules_vintage="Captured after the study freeze; historical vintage unproved.",
    )

    assert rule == {
        "ticker": "KXFDAAPPROVE-CAG-26OCT01",
        "title": "Will the FDA approve CagriSema before Oct 1, 2026?",
        "rules_primary": "Primary text.",
        "rules_secondary": "Secondary text.",
        "deadline": "2026-10-01",
        "rules_vintage": "Captured after the study freeze; historical vintage unproved.",
    }


def test_direct_cli_startup_finds_repository_tools_from_any_working_directory(tmp_path):
    """Running the assigned command directly must not depend on cwd imports."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "capture rule metadata" in result.stdout
