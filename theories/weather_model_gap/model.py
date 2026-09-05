"""Pure WG-1 forecast-error model.

The model consumes retained source envelopes only.  It has no network, ledger,
or market-price dependency, which keeps historical replay point-in-time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping, Sequence


PROTOCOL = "WG-1"
LOOKBACK_DAYS = 90
MIN_TRAINING = 30
UTC = timezone.utc


class InsufficientHistory(ValueError):
    """The station has fewer than WG-1's 30 usable prior observations."""


@dataclass(frozen=True, slots=True)
class MarketProbability:
    ticker: str
    q_yes: float
    q_no: float


@dataclass(frozen=True, slots=True)
class EventPrediction:
    event_ticker: str
    series_ticker: str
    station: str
    target_date: date
    forecast_run: datetime
    forecast_proxy: int
    training_n: int
    errors: tuple[int, ...]
    source_digest: str
    forecast_source_digest: str
    markets: tuple[MarketProbability, ...]


def _field(value, name: str):
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid target_date {value!r}") from exc
    raise ValueError(f"invalid target_date {value!r}")


def _aware_utc(value, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid {label} {value!r}") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{label} must be an aware timestamp")
    return value.astimezone(UTC)


def _response_time(value, raw_response: Mapping) -> datetime:
    """Parse an Open-Meteo hour without inventing a local timezone."""
    if not isinstance(value, str):
        raise ValueError("forecast timestamps must be ISO strings")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid forecast timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        zone = str(raw_response.get("timezone") or "").upper()
        offset = raw_response.get("utc_offset_seconds")
        if zone not in {"UTC", "GMT"} or offset not in {0, 0.0, "0"}:
            raise ValueError("naive forecast timestamps require a UTC response")
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _finite_decimal(value, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label} must be finite")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def forecast_proxy(raw_response, station, target_date, run) -> int:
    """Return WG-1's rounded max-hourly forecast for one station day.

    The required run is exactly 12Z on D-1.  The response must contain each
    of the fixed-standard-day's 24 UTC hours exactly once and temperatures in
    Fahrenheit.  Extra hours outside that window are harmless.
    """
    target = _date(target_date)
    forecast_run = _aware_utc(run, "forecast run")
    expected_run = datetime.combine(target - timedelta(days=1), time(12), UTC)
    if forecast_run != expected_run:
        raise ValueError("forecast run must be 12:00 UTC on D-1")

    offset = _field(station, "standard_utc_offset_hours")
    if isinstance(offset, bool) or not isinstance(offset, (int, float)):
        raise ValueError("station standard_utc_offset_hours is required")
    if not math.isfinite(float(offset)):
        raise ValueError("station standard_utc_offset_hours must be finite")

    if not isinstance(raw_response, Mapping):
        raise ValueError("forecast response must be a mapping")
    expected_lat = _field(station, "latitude")
    expected_lon = _field(station, "longitude")
    expected_elevation = _field(station, "elevation")
    if all(value is not None for value in
           (expected_lat, expected_lon, expected_elevation)):
        actual = (
            _finite_decimal(raw_response.get("latitude"), "forecast latitude"),
            _finite_decimal(raw_response.get("longitude"), "forecast longitude"),
            _finite_decimal(raw_response.get("elevation"), "forecast elevation"),
        )
        expected = (
            _finite_decimal(expected_lat, "station latitude"),
            _finite_decimal(expected_lon, "station longitude"),
            _finite_decimal(expected_elevation, "station elevation"),
        )
        # Open-Meteo reports its snapped model-grid coordinates, so exact
        # equality is wrong.  A quarter degree still rejects any cross-city
        # response in WG-1's three predeclared stations; supplied elevation
        # should remain the station value.
        if (abs(actual[0] - expected[0]) > Decimal("0.25")
                or abs(actual[1] - expected[1]) > Decimal("0.25")
                or abs(actual[2] - expected[2]) > Decimal("1")):
            raise ValueError("forecast response does not match station coordinates")
    units = raw_response.get("hourly_units")
    unit = units.get("temperature_2m") if isinstance(units, Mapping) else None
    normalized_unit = str(unit or "").strip().lower().replace("°", "")
    if normalized_unit not in {"f", "fahrenheit"}:
        raise ValueError("forecast temperature_2m units must be Fahrenheit")
    hourly = raw_response.get("hourly")
    if not isinstance(hourly, Mapping):
        raise ValueError("forecast response has no hourly payload")
    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    if (not isinstance(times, Sequence) or isinstance(times, (str, bytes))
            or not isinstance(temperatures, Sequence)
            or isinstance(temperatures, (str, bytes))
            or len(times) != len(temperatures)):
        raise ValueError("forecast hourly time/temperature arrays must align")

    start = datetime.combine(target, time.min, UTC) - timedelta(hours=float(offset))
    required = {start + timedelta(hours=i) for i in range(24)}
    found: dict[datetime, Decimal] = {}
    parsed_times: list[datetime] = []
    for raw_time, raw_temperature in zip(times, temperatures):
        stamp = _response_time(raw_time, raw_response)
        parsed_times.append(stamp)
        if stamp not in required:
            continue
        if stamp in found:
            raise ValueError("forecast must contain 24 complete unique timestamps")
        found[stamp] = _finite_decimal(raw_temperature, "forecast temperature")
    if set(found) != required:
        raise ValueError("forecast must contain 24 complete unique timestamps")
    if not parsed_times or parsed_times[0] != expected_run:
        raise ValueError("forecast response does not identify the requested 12Z run")

    maximum = max(found.values())
    return int(maximum.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _integer_strike(value, label: str) -> int:
    number = _finite_decimal(value, label)
    if number != number.to_integral_value():
        raise ValueError(f"{label} must be a published integer strike")
    return int(number)


def strike_satisfied(raw_market: Mapping, temperature: int) -> bool:
    """Apply a Kalshi integer strike to a whole-degree payout value."""
    if isinstance(temperature, bool) or not isinstance(temperature, int):
        raise ValueError("temperature must be a whole-degree integer")
    if not isinstance(raw_market, Mapping):
        raise ValueError("market must be a mapping")
    strike_type = raw_market.get("strike_type")
    if strike_type == "between":
        floor = _integer_strike(raw_market.get("floor_strike"), "floor_strike")
        cap = _integer_strike(raw_market.get("cap_strike"), "cap_strike")
        if floor > cap:
            raise ValueError("between strike bounds are inverted")
        return floor <= temperature <= cap
    if strike_type in {"greater", "greater_or_equal"}:
        floor = _integer_strike(raw_market.get("floor_strike"), "floor_strike")
        if raw_market.get("cap_strike") not in {None, ""}:
            raise ValueError("one-sided greater strike carries a cap")
        return temperature > floor if strike_type == "greater" else temperature >= floor
    if strike_type in {"less", "less_or_equal"}:
        cap = _integer_strike(raw_market.get("cap_strike"), "cap_strike")
        if raw_market.get("floor_strike") not in {None, ""}:
            raise ValueError("one-sided less strike carries a floor")
        return temperature < cap if strike_type == "less" else temperature <= cap
    raise ValueError(f"unsupported strike_type {strike_type!r}")


def _station_identity(station) -> str:
    value = _field(station, "station") or _field(station, "station_identifier")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("station_identifier is required")
    return value.strip()


def _label_value(label) -> int | None:
    if not isinstance(label, Mapping):
        return None
    value = label.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or float(value) != int(value):
        return None
    return int(value)


def _pinned_model(forecast: Mapping) -> bool:
    request = forecast.get("request")
    params = request.get("params") if isinstance(request, Mapping) else None
    return isinstance(params, Mapping) and params.get("models") == "ecmwf_ifs"


def predict(dataset, event, now, *, stations=None) -> EventPrediction:
    """Price one event from same-station errors known strictly before now."""
    if not isinstance(dataset, Mapping) or not isinstance(dataset.get("events"), list):
        raise ValueError("dataset must contain an events list")
    if not isinstance(event, Mapping):
        raise ValueError("event must be a mapping")
    decision_time = _aware_utc(now, "decision time")
    series = event.get("series_ticker")
    if not isinstance(series, str) or not series:
        raise ValueError("event series_ticker is required")
    if stations is None or series not in stations:
        raise ValueError(f"unsupported weather series {series!r}")
    station = stations[series]
    station_id = _station_identity(station)
    if event.get("station") != station_id:
        raise ValueError("event station does not match its series station")

    target = _date(event.get("target_date"))
    forecast = event.get("forecast")
    if not isinstance(forecast, Mapping):
        raise ValueError("event forecast is required")
    if not _pinned_model(forecast):
        raise ValueError("forecast request must pin models=ecmwf_ifs")
    target_run = _aware_utc(forecast.get("run"), "forecast run")
    target_proxy = forecast_proxy(
        forecast.get("raw_response"), station, target, target_run
    )
    forecast_source_digest = forecast.get("source_digest")
    if not isinstance(forecast_source_digest, str) or not forecast_source_digest:
        raise ValueError("forecast source_digest is required")
    source_digest = dataset.get("source_digest")
    if not isinstance(source_digest, str) or not source_digest:
        raise ValueError("dataset source_digest is required")

    lower = target - timedelta(days=LOOKBACK_DAYS)
    errors_by_date: dict[date, int] = {}
    for past in dataset["events"]:
        if not isinstance(past, Mapping):
            continue
        if past.get("series_ticker") != series or past.get("station") != station_id:
            continue
        try:
            past_date = _date(past.get("target_date"))
        except ValueError:
            continue
        if not lower <= past_date < target:
            continue
        label = past.get("label")
        value = _label_value(label)
        if value is None or not isinstance(label, Mapping):
            continue
        if label.get("reason") not in {None, ""}:
            continue
        try:
            resolved_at = _aware_utc(label.get("resolved_at"), "settlement timestamp")
        except ValueError:
            continue
        if resolved_at >= decision_time:
            continue
        past_forecast = past.get("forecast")
        if (not isinstance(past_forecast, Mapping)
                or not _pinned_model(past_forecast)):
            continue
        try:
            past_proxy = forecast_proxy(
                past_forecast.get("raw_response"), station, past_date,
                past_forecast.get("run"),
            )
        except ValueError:
            continue
        error = value - past_proxy
        prior = errors_by_date.get(past_date)
        if prior is not None and prior != error:
            raise ValueError(f"conflicting station-day training rows for {past_date}")
        errors_by_date[past_date] = error

    errors = [errors_by_date[day] for day in sorted(errors_by_date)]

    if len(errors) < MIN_TRAINING:
        raise InsufficientHistory(
            f"station {series} has {len(errors)} usable rows; {MIN_TRAINING} required"
        )

    raw_markets = event.get("markets")
    if not isinstance(raw_markets, list):
        raise ValueError("event markets must be a list")
    modeled = tuple(target_proxy + error for error in errors)
    probabilities: list[MarketProbability] = []
    for raw_market in raw_markets:
        if not isinstance(raw_market, Mapping):
            raise ValueError("event markets must contain mappings")
        ticker = raw_market.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("market ticker is required")
        hits = sum(strike_satisfied(raw_market, value) for value in modeled)
        q_yes = (hits + 0.5) / (len(errors) + 1.0)
        probabilities.append(MarketProbability(
            ticker=ticker, q_yes=q_yes, q_no=1.0 - q_yes
        ))

    return EventPrediction(
        event_ticker=str(event.get("event_ticker") or ""),
        series_ticker=series,
        station=station_id,
        target_date=target,
        forecast_run=target_run,
        forecast_proxy=target_proxy,
        training_n=len(errors),
        errors=tuple(errors),
        source_digest=source_digest,
        forecast_source_digest=forecast_source_digest,
        markets=tuple(probabilities),
    )
