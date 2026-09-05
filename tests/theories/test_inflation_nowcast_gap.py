from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tools.domain import Market
from tools.theory import TheoryContext


UTC = timezone.utc
DECISION = datetime(2026, 9, 10, 16, tzinfo=UTC)


def _row(index, *, series="KXCPI", residual="0.0", published_at=None):
    month = 1 + index % 12
    year = 2023 + index // 12
    forecast = Decimal("0.25")
    return {
        "series_ticker": series,
        "measure": "CPI Inflation" if series == "KXCPI" else "Core CPI Inflation",
        "target_month": f"{year:04d}-{month:02d}",
        "cutoff_ts": f"{year:04d}-{month:02d}-10T16:00:00+00:00",
        "forecast_observation_date": f"{year:04d}-{month:02d}-10",
        "forecast_value": str(forecast),
        "actual_value": str(forecast + Decimal(residual)),
        "actual_published_at": (
            published_at
            or f"{year:04d}-{month:02d}-11T12:30:00+00:00"
        ),
        "forecast_source_digest": "f" * 64,
        "label_source_digest": "l" * 64,
    }


def test_empirical_cdf_uses_half_up_rounding_and_strict_above_boundary():
    from theories.inflation_nowcast_gap.model import estimate

    rows = [
        _row(i, residual="0.05" if i < 10 else "0.00")
        for i in range(30)
    ]
    result = estimate(
        rows,
        series_ticker="KXCPI",
        target_month="2026-08",
        decision_time=DECISION,
        forecast_value="0.30",
        strike="0.3",
    )

    # 0.30 equals the strike and is NO. 0.35 rounds HALF_UP to 0.4 and is YES.
    assert result.hits == 10
    assert result.training_n == 30
    assert result.q_yes == pytest.approx(10.5 / 31)
    assert result.q_no == pytest.approx(20.5 / 31)


def test_estimate_ignores_other_series_and_rows_unavailable_at_decision():
    from theories.inflation_nowcast_gap.model import estimate

    rows = [_row(i, residual="0.0") for i in range(30)]
    rows.extend(_row(i, series="KXCPICORE", residual="9.0") for i in range(30))
    rows.append(_row(30, residual="9.0", published_at="2026-09-11T12:30:00Z"))

    result = estimate(
        rows,
        series_ticker="KXCPI",
        target_month="2026-08",
        decision_time=DECISION,
        forecast_value="0.3",
        strike="0.3",
    )

    assert result.training_n == 30
    assert result.hits == 0


def test_estimate_requires_30_distinct_prior_target_months():
    from theories.inflation_nowcast_gap.model import InsufficientHistory, estimate

    rows = [_row(i) for i in range(29)]

    with pytest.raises(InsufficientHistory, match="30"):
        estimate(
            rows,
            series_ticker="KXCPI",
            target_month="2026-08",
            decision_time=DECISION,
            forecast_value="0.3",
            strike="0.3",
        )


def test_estimate_rejects_duplicate_training_months():
    from theories.inflation_nowcast_gap.model import InvalidModelInput, estimate

    rows = [_row(i) for i in range(30)]
    rows.append(dict(rows[0]))

    with pytest.raises(InvalidModelInput, match="duplicate"):
        estimate(
            rows,
            series_ticker="KXCPI",
            target_month="2026-08",
            decision_time=DECISION,
            forecast_value="0.3",
            strike="0.3",
        )


def test_estimate_rejects_naive_decision_time():
    from theories.inflation_nowcast_gap.model import InvalidModelInput, estimate

    with pytest.raises(InvalidModelInput, match="timezone-aware"):
        estimate(
            [_row(i) for i in range(30)],
            series_ticker="KXCPI",
            target_month="2026-08",
            decision_time=DECISION.replace(tzinfo=None),
            forecast_value="0.3",
            strike="0.3",
        )


def _dataset(*, activity=5.0, second_event=False):
    rows = [_row(i, residual="0.10") for i in range(30)]
    event = {
        "series_ticker": "KXCPI",
        "event_ticker": "KXCPI-26AUG",
        "target_month": "2026-08",
        "release_ts": "2026-09-11T12:30:00Z",
        "entry_ts": DECISION.isoformat(),
        "forecast": {
            "measure": "CPI Inflation",
            "observation_date": "2026-09-10",
            "cutoff_ts": DECISION.isoformat(),
            "value": "0.30",
            "source_digest": "f" * 64,
        },
        "markets": [],
        "candles": {},
        "candle_reasons": {},
        "entry_activity": {
            "KXCPI-26AUG-T0.3": {
                "volume": activity,
                "bar_end_ts": DECISION.isoformat(),
            },
            "KXCPI-26AUG-T0.2": {
                "volume": activity,
                "bar_end_ts": DECISION.isoformat(),
            },
        },
        "market_sources": {},
    }
    events = [event]
    if second_event:
        core = dict(event)
        core.update({
            "series_ticker": "KXCPICORE",
            "event_ticker": "KXCPICORE-26AUG",
            "forecast": dict(event["forecast"], measure="Core CPI Inflation"),
        })
        events.append(core)
        rows.extend(_row(i, series="KXCPICORE", residual="0.10") for i in range(30))
    return {
        "schema_version": "inflation-nowcast-gap/v1",
        "campaign": "fixture",
        "collected_at": "2026-09-05T00:00:00Z",
        "protocol_digest": "c4791bccb7979a23c35479aac65669433c27954410fe349d422e2bda16fc7171",
        "source_digest": "s" * 64,
        "sources": {},
        "training_rows": rows,
        "events": events,
        "coverage": {},
    }


def _market(ticker="KXCPI-26AUG-T0.3", *, ask=.40, bid=.35, oi=200):
    event_ticker = ticker.rsplit("-", 1)[0]
    series = "KXCPICORE" if ticker.startswith("KXCPICORE") else "KXCPI"
    target = (
        "Consumer Price Index for All Urban Consumers: All Items less Food and Energy"
        if series == "KXCPICORE"
        else "Consumer Price Index (CPI)"
    )
    rules = (
        f"If the seasonally adjusted {target} month-over-month increase for "
        "August 2026 is above 0.3%, according to the Bureau of Labor "
        "Statistics, then the market resolves to Yes."
    )
    raw = {
        "ticker": ticker,
        "event_ticker": event_ticker,
        "series_ticker": series,
        "strike_type": "greater",
        "floor_strike": 0.3,
        "rules_primary": rules,
        "rules_secondary": "The first published single-decimal value is used.",
        "open_time": "2026-08-15T00:00:00Z",
    }
    return Market(
        platform="kalshi",
        ticker=ticker,
        event_ticker=event_ticker,
        series_ticker=series,
        title=f"Will {target} rise more than 0.3% in August 2026?",
        yes_bid=bid,
        yes_ask=ask,
        no_bid=1 - ask,
        no_ask=1 - bid,
        mid=(ask + bid) / 2,
        spread=ask - bid,
        open_interest=oi,
        status="open",
        is_open=True,
        open_time=raw["open_time"],
        close_time="2026-09-11T12:25:00Z",
        rules_primary=rules,
        raw=raw,
    )


def _context(board, *, now=DECISION, run_mode="backtest"):
    return TheoryContext(
        conn=None,
        board=board,
        now=now,
        run_id="ing1-20260905/holdout",
        run_mode=run_mode,
    )


def test_theory_prices_empirical_probability_and_records_source_metadata():
    from theories.inflation_nowcast_gap.theory import InflationNowcastGapTheory

    result = InflationNowcastGapTheory(_dataset()).start(
        _context([_market()])
    ).finish(dry_run=True)

    assert len(result.scored) == 1
    scored = result.scored[0]
    assert scored.candidate.ticker == "KXCPI-26AUG-T0.3"
    assert scored.candidate.fav_side == "yes"
    assert scored.edge.basis == "model"
    assert scored.edge.model_prob == pytest.approx(30.5 / 31)
    assert scored.extra["training_n"] == 30
    assert scored.extra["forecast_value"] == "0.30"
    assert scored.extra["source_digest"] == "s" * 64
    assert scored.extra["protocol_digest"] == (
        "c4791bccb7979a23c35479aac65669433c27954410fe349d422e2bda16fc7171"
    )


def test_theory_requires_positive_exact_entry_hour_activity():
    from theories.inflation_nowcast_gap.theory import InflationNowcastGapTheory

    result = InflationNowcastGapTheory(_dataset(activity=0)).screen(
        _context([_market()])
    )

    assert result.candidates == ()
    assert result.gate_removed == {"entry_hour_activity": 1}


def test_theory_keeps_one_highest_gap_across_series_on_same_release():
    from theories.inflation_nowcast_gap.theory import InflationNowcastGapTheory

    dataset = _dataset(second_event=True)
    headline = _market(ask=.45, bid=.40)
    core = _market("KXCPICORE-26AUG-T0.3", ask=.35, bid=.30)
    dataset["events"][1]["entry_activity"] = {
        core.ticker: {"volume": 2, "bar_end_ts": DECISION.isoformat()}
    }

    result = InflationNowcastGapTheory(dataset).screen(
        _context([headline, core])
    )

    assert [candidate.ticker for candidate in result.candidates] == [core.ticker]
    assert result.gate_removed["lower_ranked_same_release"] == 1


def test_theory_rejects_wrong_replay_time_and_live_outside_window():
    from theories.inflation_nowcast_gap.theory import InflationNowcastGapTheory

    theory = InflationNowcastGapTheory(_dataset())
    replay = theory.screen(_context([_market()], now=DECISION + timedelta(minutes=1)))
    live = theory.screen(_context(
        [_market()], now=DECISION - timedelta(minutes=1), run_mode="live"
    ))

    assert replay.candidates == ()
    assert replay.gate_removed == {"decision_time_mismatch": 1}
    assert live.candidates == ()
    assert live.gate_removed == {"outside_entry_window": 1}


def test_theory_rejects_missing_dataset_without_silent_empty_scan():
    from theories.inflation_nowcast_gap.theory import InflationNowcastGapTheory

    result = InflationNowcastGapTheory().screen(_context([_market()]))

    assert result.candidates == ()
    assert result.gate_removed == {"dataset_unavailable": 1}


def test_package_exports_default_theory_for_registry_discovery():
    from theories.inflation_nowcast_gap import THEORY, InflationNowcastGapTheory

    assert isinstance(THEORY, InflationNowcastGapTheory)
    assert THEORY.id == "inflation_nowcast_gap"
    assert THEORY.prompts == {
        "other": "theories/inflation_nowcast_gap/model.py"
    }
