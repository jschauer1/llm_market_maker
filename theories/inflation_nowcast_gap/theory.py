"""Theory-contract adapter for the frozen ING-1 inflation nowcast model."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import Mapping

from tools.domain import Candidate, Edge, Leg, Market, ScoredCandidate, ScreenResult
from tools.sizing import fee_pts
from tools.theory import Theory, TheoryContext

from .data import SCHEMA_VERSION, SERIES_MEASURE, parse_contract
from .model import (
    PROTOCOL,
    PROTOCOL_DIGEST,
    InsufficientHistory,
    InvalidModelInput,
    estimate,
)


UTC = timezone.utc
MIN_EDGE_PTS = 8.0
MAX_SPREAD = 0.10
MIN_OPEN_INTEREST = 100.0


def _bump(counts: dict[str, int], key: str, amount: int = 1) -> None:
    counts[key] = counts.get(key, 0) + amount


def _time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(UTC)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _days_to_close(market: Market, now: datetime) -> float:
    close = _time(market.close_time)
    return max(0.0, (close - now).total_seconds() / 86400.0) if close else 0.0


def _event_index(dataset: Mapping) -> tuple[dict[tuple[str, str], Mapping], str | None]:
    if dataset.get("schema_version") != SCHEMA_VERSION:
        return {}, "dataset_schema"
    if dataset.get("protocol_digest") != PROTOCOL_DIGEST:
        return {}, "protocol_digest"
    source_digest = dataset.get("source_digest")
    if not isinstance(source_digest, str) or not source_digest:
        return {}, "source_digest"
    events = dataset.get("events")
    if not isinstance(events, list):
        return {}, "events_missing"
    index: dict[tuple[str, str], Mapping] = {}
    for event in events:
        if not isinstance(event, Mapping):
            return {}, "event_invalid"
        key = (event.get("series_ticker"), event.get("event_ticker"))
        if not all(isinstance(value, str) and value for value in key):
            return {}, "event_invalid"
        if key in index:
            return {}, "event_duplicate"
        index[key] = event
    return index, None


class InflationNowcastGapTheory(Theory):
    id = "inflation_nowcast_gap"
    name = "Inflation Nowcast Gap"
    version = 1
    uses_llm_judgment = False
    prompts = {"other": "theories/inflation_nowcast_gap/model.py"}
    protocol = PROTOCOL

    def __init__(self, dataset=None, fetch=None):
        self._dataset = dataset
        self._fetch = fetch

    def screen(self, ctx: TheoryContext) -> ScreenResult:
        funnel = {
            "board": len(ctx.board),
            "population": 0,
            "model_ready": 0,
            "executable": 0,
            "above_edge_floor": 0,
            "candidates": 0,
        }
        removed: dict[str, int] = {}
        if ctx.now.tzinfo is None or ctx.now.utcoffset() is None:
            return ScreenResult((), funnel, {"naive_decision_time": 1})
        now = ctx.now.astimezone(UTC)
        if ctx.run_mode not in {"live", "backtest"}:
            return ScreenResult((), funnel, {"unsupported_run_mode": 1})
        if not isinstance(self._dataset, Mapping):
            return ScreenResult((), funnel, {"dataset_unavailable": 1})
        events, dataset_reason = _event_index(self._dataset)
        if dataset_reason:
            return ScreenResult((), funnel, {dataset_reason: 1})
        training_rows = self._dataset.get("training_rows")
        if not isinstance(training_rows, list):
            return ScreenResult((), funnel, {"training_rows_missing": 1})

        event_entries = [_time(event.get("entry_ts")) for event in events.values()]
        if ctx.run_mode == "live" and not any(
            entry is not None and entry <= now < entry + timedelta(hours=1)
            for entry in event_entries
        ):
            return ScreenResult((), funnel, {"outside_entry_window": 1})

        eligible: list[tuple[float, str, str, str, Candidate]] = []
        for market in sorted(ctx.board, key=lambda value: value.ticker):
            raw = dict(market.raw) if isinstance(market.raw, Mapping) else {}
            contract_input = dict(raw)
            contract_input.setdefault("event_ticker", market.event_ticker)
            contract_input.setdefault("series_ticker", market.series_ticker)
            contract_input.setdefault("rules_primary", market.rules_primary)
            parsed, reason = parse_contract(contract_input)
            if parsed is None:
                _bump(removed, reason or "contract_invalid")
                continue
            key = (parsed["series_ticker"], parsed["event_ticker"])
            event = events.get(key)
            if event is None:
                _bump(removed, "event_not_in_dataset")
                continue
            if parsed["target_month"] != event.get("target_month"):
                _bump(removed, "event_target_mismatch")
                continue
            entry = _time(event.get("entry_ts"))
            release = _time(event.get("release_ts"))
            if entry is None or release is None or entry >= release:
                _bump(removed, "event_time_invalid")
                continue
            if ctx.run_mode == "backtest" and now != entry:
                _bump(removed, "decision_time_mismatch")
                continue
            if ctx.run_mode == "live" and not entry <= now < entry + timedelta(hours=1):
                _bump(removed, "not_current_release")
                continue
            funnel["population"] += 1

            forecast = event.get("forecast")
            if not isinstance(forecast, Mapping):
                _bump(removed, "forecast_missing")
                continue
            forecast_cutoff = _time(forecast.get("cutoff_ts"))
            expected_measure = SERIES_MEASURE.get(parsed["series_ticker"])
            if (
                forecast_cutoff != entry
                or forecast.get("measure") != expected_measure
                or not isinstance(forecast.get("source_digest"), str)
                or not forecast.get("source_digest")
            ):
                _bump(removed, "forecast_identity")
                continue

            activity_by_ticker = event.get("entry_activity")
            activity = (
                activity_by_ticker.get(market.ticker)
                if isinstance(activity_by_ticker, Mapping)
                else None
            )
            if not isinstance(activity, Mapping):
                _bump(removed, "entry_hour_activity")
                continue
            volume = activity.get("volume")
            try:
                volume_number = float(volume)
            except (TypeError, ValueError):
                volume_number = 0.0
            if (
                not math.isfinite(volume_number)
                or volume_number <= 0
                or _time(activity.get("bar_end_ts")) != entry
            ):
                _bump(removed, "entry_hour_activity")
                continue
            if not market.is_open:
                _bump(removed, "not_open")
                continue
            yes_bid, yes_ask = _number(market.yes_bid), _number(market.yes_ask)
            no_ask = _number(market.no_ask)
            if (
                yes_bid is None
                or yes_ask is None
                or no_ask is None
                or not 0 <= yes_bid <= yes_ask <= 1
                or not 0 <= no_ask <= 1
            ):
                _bump(removed, "invalid_quote")
                continue
            spread = yes_ask - yes_bid
            if spread > MAX_SPREAD + 1e-12:
                _bump(removed, "spread")
                continue
            oi = _number(market.open_interest)
            if oi is None or oi < MIN_OPEN_INTEREST:
                _bump(removed, "open_interest")
                continue
            try:
                prediction = estimate(
                    training_rows,
                    series_ticker=parsed["series_ticker"],
                    target_month=parsed["target_month"],
                    decision_time=now,
                    forecast_value=forecast.get("value"),
                    strike=parsed["strike"],
                )
            except InsufficientHistory:
                _bump(removed, "insufficient_history")
                continue
            except InvalidModelInput:
                _bump(removed, "invalid_model_input")
                continue
            funnel["model_ready"] += 1

            for side, model_prob, ask in (
                ("yes", prediction.q_yes, yes_ask),
                ("no", prediction.q_no, no_ask),
            ):
                if not 0.05 <= ask <= 0.95:
                    _bump(removed, "ask_range")
                    continue
                funnel["executable"] += 1
                fee = fee_pts(ask)
                gross = (model_prob - ask) * 100.0
                net = gross - fee
                if net + 1e-12 < MIN_EDGE_PTS:
                    _bump(removed, "edge_below_floor")
                    continue
                funnel["above_edge_floor"] += 1
                details = {
                    "protocol": PROTOCOL,
                    "protocol_digest": self._dataset["protocol_digest"],
                    "source_digest": self._dataset["source_digest"],
                    "forecast_source_digest": forecast["source_digest"],
                    "series_ticker": parsed["series_ticker"],
                    "event_ticker": parsed["event_ticker"],
                    "target_month": parsed["target_month"],
                    "release_ts": release.isoformat(),
                    "entry_ts": entry.isoformat(),
                    "decision_time": now.isoformat(),
                    "forecast_observation_date": forecast.get("observation_date"),
                    "forecast_value": str(forecast.get("value")),
                    "strike": str(parsed["strike"]),
                    "hits": prediction.hits,
                    "training_n": prediction.training_n,
                    "model_prob": model_prob,
                    "edge_pts_gross": gross,
                    "fee_pts": fee,
                    "edge_pts_net": net,
                    "entry_hour_volume": volume_number,
                }
                priced_raw = dict(raw)
                priced_raw["_inflation_nowcast_gap"] = details
                priced_market = replace(market, raw=priced_raw, spread=spread)
                candidate = Candidate(
                    legs=(Leg(priced_market, side, ask),),
                    days_to_close=_days_to_close(market, now),
                )
                release_key = release.date().isoformat()
                eligible.append((net, market.ticker, side, release_key, candidate))

        by_release: dict[str, tuple[float, str, str, str, Candidate]] = {}
        for row in eligible:
            current = by_release.get(row[3])
            if current is None or (-row[0], row[1], row[2]) < (
                -current[0], current[1], current[2]
            ):
                if current is not None:
                    _bump(removed, "lower_ranked_same_release")
                by_release[row[3]] = row
            else:
                _bump(removed, "lower_ranked_same_release")
        candidates = tuple(by_release[key][4] for key in sorted(by_release))
        funnel["candidates"] = len(candidates)
        return ScreenResult(candidates, funnel, removed)

    def price(self, ctx: TheoryContext, cands: list[Candidate], verdicts=None):
        scored = []
        for candidate in cands:
            details = dict(
                candidate.legs[0].market.raw["_inflation_nowcast_gap"]
            )
            scored.append(ScoredCandidate(
                candidate=candidate,
                edge=Edge(
                    pts_net=details["edge_pts_net"],
                    basis="model",
                    pts_gross=details["edge_pts_gross"],
                    fee_pts=details["fee_pts"],
                    model_prob=details["model_prob"],
                ),
                rationale=(
                    "ING-1 official-nowcast residual CDF clears the frozen "
                    "executable edge floor."
                ),
                disposition="screened",
                evidence_source="cleveland_fed",
                extra=details,
            ))
        return scored


__all__ = ["InflationNowcastGapTheory"]
