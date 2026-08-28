"""Backfill `settlements.resolved_at` for historical backtest rows.

Why this exists: `score.settlement_day_clusters` (added 2026-08-27) counts
distinct settlement DAYS, which is the effective sample size once you know
Kalshi settles in day-clumps. Every historical backtest run came back
`n_days=0` because the replays recorded settlements with no `resolved_at`
at all -- so the repo's entire body of tier-A evidence, including the
numbers `mention_family` was retired on, could not be day-clustered.

The date is recoverable with **no API call**: every backtest opportunity row
carries `entry_day_iso` (the as-of day of the reconstructed decision) and
`days_to_close_at_entry` in `extra_json`, and their sum is the market's
close date. Day resolution is all clustering needs.

Idempotent and non-destructive: only rows whose `resolved_at` is NULL or
empty are touched, so a real resolution timestamp recorded from the API is
never overwritten by this estimate.

Run:  python -m studies.2026-08-27-settlement-day-clustering.backfill_resolved_at
  or: python studies/2026-08-27-settlement-day-clustering/backfill_resolved_at.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import db  # noqa: E402


def close_iso(extra: dict) -> str | None:
    """Close date from the entry day plus days-to-close at that entry."""
    entry = extra.get("entry_day_iso")
    days = extra.get("days_to_close_at_entry")
    if not entry or days is None:
        return None
    try:
        start = datetime.fromisoformat(str(entry).replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return (start + timedelta(days=float(days))).isoformat().replace(
        "+00:00", "Z"
    )


def main(apply: bool = True) -> None:
    conn = db.connect()
    rows = conn.execute(
        "SELECT o.kalshi_ticker, o.extra_json FROM opportunities o"
        " JOIN settlements s ON s.kalshi_ticker = o.kalshi_ticker"
        " WHERE (s.resolved_at IS NULL OR s.resolved_at = '')"
        "   AND o.extra_json IS NOT NULL"
    ).fetchall()

    # One market has one close date; take the first row that yields one.
    resolved: dict[str, str] = {}
    for row in rows:
        ticker = row["kalshi_ticker"]
        if ticker in resolved:
            continue
        try:
            extra = json.loads(row["extra_json"] or "{}")
        except json.JSONDecodeError:
            continue
        iso = close_iso(extra)
        if iso:
            resolved[ticker] = iso

    print(f"recoverable: {len(resolved)} tickers")
    if not apply:
        for ticker, iso in list(resolved.items())[:5]:
            print(f"  {ticker} -> {iso}")
        return

    with db.write(conn):
        for ticker, iso in resolved.items():
            conn.execute(
                "UPDATE settlements SET resolved_at = ?"
                " WHERE kalshi_ticker = ?"
                "   AND (resolved_at IS NULL OR resolved_at = '')",
                (iso, ticker),
            )
    remaining = conn.execute(
        "SELECT COUNT(*) c FROM settlements"
        " WHERE resolved_at IS NULL OR resolved_at = ''"
    ).fetchone()["c"]
    print(f"backfilled {len(resolved)}; still missing: {remaining}")


if __name__ == "__main__":
    main(apply="--dry-run" not in sys.argv)
