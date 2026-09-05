from datetime import date, datetime, timedelta, timezone

import pytest

from tools.domain import Market
from tools.theory import TheoryContext


UTC = timezone.utc
WEEK_END = date(2026, 9, 6)


def _counts(*, high_weeks=52):
    counts = {}
    for index in range(1, 53):
        sunday = WEEK_END - timedelta(days=7 * index)
        for offset in range(7):
            counts[(sunday - timedelta(days=6 - offset)).isoformat()] = 100
        # S4=400.  A 200/day strike gives t=2.5; make the requested number
        # of prior Fri-Sun totals strictly greater than 1000.
        counts[(sunday - timedelta(days=2)).isoformat()] = (
            801 if index <= high_weeks else 800
        )
    for offset in range(6, 2, -1):
        counts[(WEEK_END - timedelta(days=offset)).isoformat()] = 100
    return counts


def _market(ticker="KXTSAW-26SEP06-A", *, ask=.20, bid=.15, oi=200):
    entry = datetime(2026, 9, 4, 15, tzinfo=UTC)
    event = "KXTSAW-26SEP06"
    rules = (
        "This market resolves to Yes if the weekly average TSA airport "
        "screenings are above 200 for the week ending September 6, 2026, "
        "according to the TSA."
    )
    raw = {
        "ticker": ticker,
        "event_ticker": event,
        "series_ticker": "KXTSAW",
        "rules_primary": rules,
        "rules_secondary": "TSA checkpoint travel numbers.",
        "open_time": "2026-08-01T00:00:00Z",
        "strike_type": "greater",
        "floor_strike": 200,
        "week_end": WEEK_END.isoformat(),
        "strike": 200,
        "entry_time": entry.isoformat(),
        "source_digest": "source-abc",
    }
    return Market(
        platform="kalshi", ticker=ticker, event_ticker=event,
        series_ticker="KXTSAW", title="TSA", yes_bid=bid, yes_ask=ask,
        no_bid=1 - ask, no_ask=1 - bid, mid=(ask + bid) / 2,
        spread=ask - bid, open_interest=oi, status="open", is_open=True,
        open_time=raw["open_time"], close_time="2026-09-07T13:00:00Z",
        rules_primary=rules, raw=raw,
    )


def test_forecast_is_decimal_probability_and_uses_strict_integer_boundary():
    from theories.tsa_remainder_gap.model import forecast

    counts = _counts(high_weeks=26)
    result = forecast(counts, WEEK_END, 200)

    # The 26 lower weeks land exactly on the threshold (1000/400=2.5)
    # and therefore count NO. Jeffreys add-half: (26 + .5) / 53.
    assert result.s4 == 400
    assert result.ratio_count == 26
    assert result.q_yes == pytest.approx(26.5 / 53)
    assert result.q_no == pytest.approx(26.5 / 53)
    assert 0 <= result.q_yes <= 1


def test_forecast_requires_every_day_in_all_52_prior_calendar_weeks():
    from theories.tsa_remainder_gap.model import InsufficientCounts, forecast

    counts = _counts()
    del counts[(WEEK_END - timedelta(days=7 + 3)).isoformat()]

    with pytest.raises(InsufficientCounts, match="52 complete prior weeks"):
        forecast(counts, WEEK_END, 200)


def test_forecast_does_not_read_target_friday_through_sunday():
    from theories.tsa_remainder_gap.model import forecast

    counts = _counts(high_weeks=40)
    before = forecast(counts, WEEK_END, 200)
    for offset in range(3):
        counts[(WEEK_END - timedelta(days=offset)).isoformat()] = 999_999_999

    assert forecast(counts, WEEK_END, 200) == before


def test_theory_keeps_one_stable_best_candidate_per_week_and_prices_model_q():
    from theories.tsa_remainder_gap.theory import TsaRemainderGapTheory

    now = datetime(2026, 9, 4, 15, tzinfo=UTC)
    board = [_market("KXTSAW-26SEP06-B"), _market("KXTSAW-26SEP06-A")]
    ctx = TheoryContext(
        conn=None, board=board, now=now,
        run_id="exp/trg1-20260905/holdout", run_mode="backtest",
    )
    result = TsaRemainderGapTheory(_counts()).start(ctx).finish(dry_run=True)

    assert [row.candidate.ticker for row in result.scored] == ["KXTSAW-26SEP06-A"]
    scored = result.scored[0]
    assert scored.candidate.fav_side == "yes"
    assert scored.edge.basis == "model"
    assert scored.edge.model_prob == pytest.approx(52.5 / 53)
    assert scored.extra["week_end"] == "2026-09-06"
    assert scored.extra["S4"] == 400
    assert scored.extra["ratio_count"] == 52


def test_historical_source_reconstruction_is_rejected_outside_exp_runs():
    from theories.tsa_remainder_gap.theory import TsaRemainderGapTheory

    ctx = TheoryContext(
        conn=None, board=[_market()],
        now=datetime(2026, 9, 4, 15, tzinfo=UTC),
        run_id="trg1-production-looking", run_mode="backtest",
    )
    result = TsaRemainderGapTheory(_counts()).screen(ctx)

    assert result.candidates == ()
    assert result.gate_removed == {"experimental_source_requires_exp_run": 1}


def test_package_exports_default_theory_for_registry_discovery():
    from theories.tsa_remainder_gap import THEORY, TsaRemainderGapTheory

    assert isinstance(THEORY, TsaRemainderGapTheory)
    assert THEORY.id == "tsa_remainder_gap"
    assert THEORY.prompts == {"other": "theories/tsa_remainder_gap/model.py"}
