"""Fetch the raw Kalshi payload for every ticker in the three judged runs.

**Capture is separate from classification, and only capture is perishable.**
Kalshi archives settled markets out of its public API roughly 60 days after
close (`tools/kalshi/markets.list_settled` documents the measurement). The
judged campaigns replayed markets closing ~2026-06-22..2026-08-24, so the
oldest of them are already at that boundary as this runs. Whatever is not
on disk tonight may be unanswerable tomorrow, so this writes the **complete
raw payload** rather than the four fields the study happens to need --
a future session gets to ask questions nobody thought of tonight.

Resumable by construction: one JSON object per line, flushed per ticker.
Re-running skips whatever is already in the file, so an interrupted run
continues instead of restarting. A ticker that 404s is recorded as a
`gone` line rather than retried forever -- an aged-out market is an answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools import db
from tools.http import HttpError, get_json
from tools.kalshi.markets import BASE_URL

HERE = Path(__file__).parent
OUT = HERE / "raw_markets.jsonl"

RUNS = (
    "backtest-2026-08-26-insider-judged-s200",
    "backtest-2026-08-26-insider-judged-s200b",
    "backtest-2026-08-26-insider-judged-s57",
)


def tickers(conn) -> list[str]:
    """Every distinct ticker attempted by the three judged runs."""
    rows = conn.execute(
        """
        SELECT DISTINCT o.kalshi_ticker
        FROM opportunities o
        JOIN opportunity_attempts a ON a.opportunity_id = o.id
        WHERE a.run_id IN (?, ?, ?)
        ORDER BY o.kalshi_ticker
        """,
        RUNS,
    ).fetchall()
    return [r[0] for r in rows]


def done() -> set[str]:
    """Tickers already on disk, from a previous (possibly killed) run."""
    if not OUT.exists():
        return set()
    seen = set()
    for line in OUT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            seen.add(json.loads(line)["ticker"])
        except (json.JSONDecodeError, KeyError):
            continue        # a torn final line just gets re-fetched
    return seen


def main() -> None:
    conn = db.connect()
    want = tickers(conn)
    have = done()
    todo = [t for t in want if t not in have]
    print(f"{len(want)} tickers in the three judged runs; "
          f"{len(have)} already captured; {len(todo)} to fetch",
          flush=True)

    gone = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for i, ticker in enumerate(todo, 1):
            try:
                payload = get_json(f"{BASE_URL}/markets/{ticker}")
                rec = {"ticker": ticker, "ok": True,
                       "market": payload.get("market")}
            except HttpError as exc:
                # A 404 on a settled market is the archive window closing,
                # not a transient failure. Record it and move on.
                gone += 1
                rec = {"ticker": ticker, "ok": False, "error": str(exc)[:200]}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()          # per ticker: a kill loses at most one row
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}  unreachable so far: {gone}",
                      flush=True)

    print(f"done. {len(todo)} fetched, {gone} unreachable -> {OUT}",
          flush=True)


if __name__ == "__main__":
    sys.exit(main())
