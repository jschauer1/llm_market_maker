"""Pure ING-1 empirical residual model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping


PROTOCOL = "ING-1"
PROTOCOL_DIGEST = "c4791bccb7979a23c35479aac65669433c27954410fe349d422e2bda16fc7171"
SUPPORTED_SERIES = frozenset({"KXCPI", "KXCPICORE"})
MIN_TRAINING = 30
TENTH = Decimal("0.1")


class InvalidModelInput(ValueError):
    """The retained source rows do not satisfy the frozen model contract."""


class InsufficientHistory(ValueError):
    """Fewer than 30 usable prior target months are available."""


@dataclass(frozen=True, slots=True)
class Estimate:
    series_ticker: str
    target_month: str
    forecast_value: Decimal
    strike: Decimal
    hits: int
    training_n: int
    q_yes: float
    q_no: float


def _month(value: object, label: str) -> tuple[int, int]:
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        raise InvalidModelInput(f"{label} must be YYYY-MM")
    try:
        year, month = int(value[:4]), int(value[5:])
    except ValueError as exc:
        raise InvalidModelInput(f"{label} must be YYYY-MM") from exc
    if year < 1900 or not 1 <= month <= 12:
        raise InvalidModelInput(f"{label} must be YYYY-MM")
    return year, month


def _time(value: object, label: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidModelInput(f"{label} is invalid") from exc
    else:
        raise InvalidModelInput(f"{label} is invalid")
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidModelInput(f"{label} must be timezone-aware")
    return result.astimezone(timezone.utc)


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise InvalidModelInput(f"{label} is invalid")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidModelInput(f"{label} is invalid") from exc
    if not result.is_finite():
        raise InvalidModelInput(f"{label} is invalid")
    return result


def estimate(
    training_rows: Iterable[Mapping],
    *,
    series_ticker: str,
    target_month: str,
    decision_time: datetime,
    forecast_value: object,
    strike: object,
) -> Estimate:
    """Estimate a strict-above contract from prior first-print residuals."""
    if series_ticker not in SUPPORTED_SERIES:
        raise InvalidModelInput("unsupported series")
    target_key = _month(target_month, "target_month")
    decision = _time(decision_time, "decision_time")
    current = _decimal(forecast_value, "forecast_value")
    threshold = _decimal(strike, "strike")

    residuals: list[Decimal] = []
    seen_months: set[str] = set()
    for raw in training_rows:
        if not isinstance(raw, Mapping) or raw.get("series_ticker") != series_ticker:
            continue
        row_month_text = raw.get("target_month")
        row_month = _month(row_month_text, "training target_month")
        if row_month >= target_key:
            continue
        published = _time(raw.get("actual_published_at"), "actual_published_at")
        if published >= decision:
            continue
        cutoff = _time(raw.get("cutoff_ts"), "cutoff_ts")
        if cutoff >= published or cutoff >= decision:
            raise InvalidModelInput("training row violates its availability boundary")
        if row_month_text in seen_months:
            raise InvalidModelInput("duplicate training target month")
        seen_months.add(row_month_text)
        actual = _decimal(raw.get("actual_value"), "actual_value")
        prior_forecast = _decimal(raw.get("forecast_value"), "forecast_value")
        residuals.append(actual - prior_forecast)

    if len(residuals) < MIN_TRAINING:
        raise InsufficientHistory(
            f"ING-1 requires at least {MIN_TRAINING} distinct prior target months"
        )

    hits = sum(
        (current + residual).quantize(TENTH, rounding=ROUND_HALF_UP) > threshold
        for residual in residuals
    )
    q_yes = (hits + 0.5) / (len(residuals) + 1.0)
    return Estimate(
        series_ticker=series_ticker,
        target_month=target_month,
        forecast_value=current,
        strike=threshold,
        hits=hits,
        training_n=len(residuals),
        q_yes=q_yes,
        q_no=1.0 - q_yes,
    )


__all__ = [
    "Estimate",
    "InsufficientHistory",
    "InvalidModelInput",
    "MIN_TRAINING",
    "PROTOCOL",
    "PROTOCOL_DIGEST",
    "SUPPORTED_SERIES",
    "estimate",
]
