"""Live ND-1 collection stays bulk, resumable, and explicit about gaps."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from tools.domain import Market


DAY = 86_400
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
AS_OF = int(NOW.timestamp())


def _market(ticker: str, **updates) -> Market:
    base = dict(
        platform="kalshi",
        ticker=ticker,
        title=f"Question {ticker}?",
        yes_bid=0.54,
        yes_ask=0.56,
        no_bid=0.44,
        no_ask=0.46,
        mid=0.55,
        spread=0.02,
        volume=1_000.0,
        volume_24h=25.0,
        open_interest=200.0,
        status="active",
        is_open=True,
        event_ticker=f"E-{ticker}",
        series_ticker=f"S-{ticker}",
        event={"category": "Politics", "custom": f"envelope-{ticker}"},
    )
    base.update(updates)
    return Market(**base)


def _raw_candles(*, signal: bool = True) -> list[dict]:
    mids = (0.20, 0.22, 0.30, 0.50, 0.55) if signal else (
        0.40, 0.41, 0.42, 0.43, 0.44
    )
    volumes = (10.0, 20.0, 30.0, 40.0, 5.0)
    start = AS_OF - 4 * DAY
    return [
        {
            "end_period_ts": start + i * DAY,
            "yes_bid": {
                "open_dollars": f"{mid - .01:.4f}",
                "low_dollars": f"{mid - .01:.4f}",
                "high_dollars": f"{mid - .01:.4f}",
                "close_dollars": f"{mid - .01:.4f}",
            },
            "yes_ask": {
                "open_dollars": f"{mid + .01:.4f}",
                "low_dollars": f"{mid + .01:.4f}",
                "high_dollars": f"{mid + .01:.4f}",
                "close_dollars": f"{mid + .01:.4f}",
            },
            "price": {
                "open_dollars": f"{mid:.4f}",
                "low_dollars": f"{mid:.4f}",
                "high_dollars": f"{mid:.4f}",
                "close_dollars": f"{mid:.4f}",
                "mean_dollars": f"{mid:.4f}",
                "previous_dollars": f"{mid:.4f}",
                "min_dollars": f"{mid:.4f}",
                "max_dollars": f"{mid:.4f}",
            },
            "volume_fp": f"{volumes[i]:.2f}",
            "open_interest_fp": "200.00",
        }
        for i, mid in enumerate(mids)
    ]


def _block(ticker: str, *, signal: bool = True) -> dict:
    return {"market_ticker": ticker, "candlesticks": _raw_candles(signal=signal)}


def test_normalization_excludes_future_and_null_rows_and_deduplicates_periods():
    """A future, synthetic-null, or duplicate API row cannot become history."""
    from theories.news_drift.live import normalize_batch_payload

    first = _raw_candles()[0]
    replacement = {
        **first,
        "yes_ask": {**first["yes_ask"], "close_dollars": "0.2500"},
    }
    synthetic = {
        **first,
        "end_period_ts": first["end_period_ts"] + DAY,
        "yes_bid": {**first["yes_bid"], "close_dollars": None},
    }
    future = {**first, "end_period_ts": AS_OF + 1}
    payload = {
        "markets": [
            {"market_ticker": "A", "candlesticks": [first, replacement,
                                                        synthetic, future]},
            {"market_ticker": "UNREQUESTED", "candlesticks": [first]},
        ]
    }

    histories, missing = normalize_batch_payload(
        payload, requested_tickers=["A", "B"], as_of_ts=AS_OF
    )

    assert missing == ["B"]
    assert list(histories) == ["A"]
    assert histories["A"] == [{
        "end_ts": first["end_period_ts"],
        "yes_bid_close": 0.19,
        "yes_ask_close": 0.25,
        "volume": 10.0,
        "open_interest": 200.0,
    }]


def test_collection_batches_at_100_checkpoints_raw_and_resumes(tmp_path):
    """Removing chunking, gap reporting, or checkpoint reuse breaks this."""
    from theories.news_drift.live import collect_live

    unique = [_market(f"T{i:03d}") for i in range(101)]
    board = unique + [unique[0]]
    calls = []

    def board_loader(*, force):
        assert force is False
        return board

    def batch_fetch(url, params=None, **kwargs):
        assert url.endswith("/markets/candlesticks")
        asked = params["market_tickers"].split(",")
        calls.append((asked, dict(params)))
        returned = [ticker for ticker in asked if ticker != "T100"]
        return {"markets": [_block(ticker) for ticker in returned]}

    result = collect_live(
        now=NOW,
        board_loader=board_loader,
        batch_fetch=batch_fetch,
        quote_loader=lambda tickers: {},
        data_dir=tmp_path / "raw",
        out_path=tmp_path / "result.json",
    )

    assert [len(asked) for asked, _ in calls] == [100, 1]
    assert all(call[1] == {
        "market_tickers": ",".join(call[0]),
        "start_ts": AS_OF - 10 * DAY,
        "end_ts": AS_OF,
        "period_interval": 1440,
        "include_latest_before_start": False,
    } for call in calls)
    assert result["funnel"]["board"] == 102
    assert result["funnel"]["prefiltered_unique"] == 101
    assert result["funnel"]["history_returned"] == 100
    assert result["history"]["missing_tickers"] == ["T100"]
    assert result["quotes"]["missing_tickers"] == [f"T{i:03d}" for i in range(100)]

    checkpoints = sorted((tmp_path / "raw").glob("batch-*.json"))
    assert len(checkpoints) == 2
    saved = json.loads(checkpoints[0].read_text(encoding="utf-8"))
    assert saved["requested_tickers"] == [f"T{i:03d}" for i in range(100)]
    assert saved["response"]["markets"][0]["market_ticker"] == "T000"
    assert json.loads((tmp_path / "result.json").read_text()) == result

    collect_live(
        now=NOW,
        board_loader=board_loader,
        batch_fetch=batch_fetch,
        quote_loader=lambda tickers: {},
        data_dir=tmp_path / "raw",
    )
    assert len(calls) == 2, "a resumed run must reuse both raw checkpoints"


def test_only_signal_survivors_are_requoted_and_event_envelope_is_preserved(tmp_path):
    """Bulk history gates quote calls, and refresh cannot erase category data."""
    from theories.news_drift.live import collect_live

    moving = _market("MOVE")
    quiet = _market("QUIET")

    def batch_fetch(url, params=None, **kwargs):
        return {"markets": [_block("MOVE"), _block("QUIET", signal=False)]}

    quote_requests = []

    def quote_loader(tickers):
        quote_requests.append(list(tickers))
        return {
            "MOVE": _market(
                "MOVE",
                yes_bid=0.56,
                yes_ask=0.58,
                no_bid=0.42,
                no_ask=0.44,
                mid=0.57,
                spread=0.02,
                event={},
                event_ticker=None,
                series_ticker=None,
            )
        }

    quote_started = NOW + timedelta(seconds=30)
    quote_completed = NOW + timedelta(seconds=31)
    quote_clock = iter([quote_started, quote_completed])
    result = collect_live(
        now=NOW,
        board_loader=lambda *, force: (
            [moving, quiet], {"captured_at": "2026-09-05T11:59:00Z"}
        ),
        batch_fetch=batch_fetch,
        quote_loader=quote_loader,
        clock=lambda: next(quote_clock),
        data_dir=tmp_path / "raw",
    )

    assert result["history_as_of"] == NOW.isoformat()
    assert result["board"]["captured_at"] == "2026-09-05T11:59:00Z"
    assert result["quotes"]["fetch_started_at"] == quote_started.isoformat()
    assert result["quotes"]["fetch_completed_at"] == quote_completed.isoformat()
    assert quote_requests == [["MOVE"]]
    assert result["quotes"]["requested_tickers"] == ["MOVE"]
    assert result["quotes"]["missing_tickers"] == []
    assert len(result["signals"]) == 1
    row = result["signals"][0]
    assert row["ticker"] == "MOVE"
    assert row["event_ticker"] == moving.event_ticker
    assert row["series_ticker"] == moving.series_ticker
    assert row["category"] == "Politics"
    assert row["event"] == moving.event
    assert row["side"] == "yes"
    assert row["quote"]["yes_ask"] == pytest.approx(0.58)
    assert "edge" not in json.dumps(result).lower()


def test_live_cli_rejects_a_history_cutoff_more_than_one_hour_old():
    """An old resume token cannot be emitted as a current live artifact."""
    from theories.news_drift.live import main

    with pytest.raises(SystemExit) as error:
        main(["--collect", "--as-of", "1970-01-01T00:00:00Z"])
    assert error.value.code == 2
