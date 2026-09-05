"""Pure arithmetic for the frozen TRG-1 TSA remainder model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping


PROTOCOL = "TRG-1"
LOOKBACK_WEEKS = 52


class InsufficientCounts(ValueError):
    """The fixed calendar window is absent or malformed."""


@dataclass(frozen=True, slots=True)
class Forecast:
    week_end: date
    strike: int
    s4: int
    ratio_count: int
    q_yes: float
    q_no: float


def _count(counts: Mapping[str, object], day: date) -> int:
    value = counts.get(day.isoformat())
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InsufficientCounts("52 complete prior weeks and target Mon-Thu are required")
    return value


def forecast(
    daily_counts: Mapping[str, object], week_end: date, strike: int
) -> Forecast:
    """Compute the predeclared 52-week empirical remainder probability.

    Ratio comparisons use integer cross-products. This preserves the strict
    boundary without float division or rounded ratio intermediates.
    """
    if not isinstance(daily_counts, Mapping):
        raise InsufficientCounts("daily_counts must be a date-to-integer mapping")
    if not isinstance(week_end, date) or week_end.weekday() != 6:
        raise ValueError("week_end must be a Sunday date")
    if isinstance(strike, bool) or not isinstance(strike, int) or strike <= 0:
        raise ValueError("strike must be a positive integer")

    current_mon_thu = [week_end - timedelta(days=offset) for offset in range(6, 2, -1)]
    s4 = sum(_count(daily_counts, day) for day in current_mon_thu)
    if s4 <= 0:
        raise InsufficientCounts("target Mon-Thu sum must be positive")
    threshold_numerator = 7 * strike - s4

    hits = 0
    for index in range(1, LOOKBACK_WEEKS + 1):
        prior_end = week_end - timedelta(days=7 * index)
        days = [prior_end - timedelta(days=offset) for offset in range(6, -1, -1)]
        values = [_count(daily_counts, day) for day in days]
        prior_s4 = sum(values[:4])
        if prior_s4 <= 0:
            raise InsufficientCounts("prior Mon-Thu sum must be positive")
        remainder = sum(values[4:])
        if remainder * s4 > threshold_numerator * prior_s4:
            hits += 1

    q_yes = (hits + 0.5) / (LOOKBACK_WEEKS + 1)
    return Forecast(
        week_end=week_end,
        strike=strike,
        s4=s4,
        ratio_count=hits,
        q_yes=q_yes,
        q_no=1.0 - q_yes,
    )


__all__ = ["Forecast", "InsufficientCounts", "LOOKBACK_WEEKS", "PROTOCOL", "forecast"]
