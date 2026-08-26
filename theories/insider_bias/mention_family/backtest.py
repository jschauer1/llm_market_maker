"""mention_family — tier A full-coverage backtest, scoped to this family.

Motivation (2026-08-25): the theory's entire evidence base is 116 rows from
`backtest-2026-08-24-stage1-90d` — a ~3% systematic sample (600 of 18,430
survivors) of one close window, the same rows the price bins were fit on.
The audit recorded in THEORY.md's Learnings (2026-08-25) found the pooled
edge statistically weak after fees (p=0.070) and carried by sub-families
absent from the live slate.

**A backward extension to older history is impossible via Kalshi's public
API — measured 2026-08-25, not assumed.** Settled markets are archived out
of the API roughly 60 days after close: `/markets` (any status, any
window) stops returning them — a handful of never-traded husks with empty
`result` and zeroed volume linger as `status='closed'` — `/events?with_
nested_markets` returns settled event shells with no markets attached, and
the candlesticks endpoint returns nothing for archived tickers (probed
with reconstructed tickers on known old events). The events listing keeps
shells back to 2025, but nothing tradeable hangs off them. This also means
the original "90-day" run was really a ~60-day run: the earliest close the
listing could serve it was 2026-06-22ish, and that floor advances daily.
Historical evidence beyond the floor can only come from data snapshotted
before it aged out — a reason to keep running this regularly, not a thing
a longer window can recover later.

So this driver does the strongest thing the API still allows: **full
coverage of the reachable window** — every mention-family survivor, not a
3% sample. That cannot test persistence across time (same period, same
regime, World Cup summer included); it tests whether the 116-row sample
was *lucky*, on hundreds of markets the bins were never fit on. Score the
fresh-rows slice (tickers not among the original 116) separately — the
overlap rows are a re-measurement, not new evidence. Persistence across
time falls to the live runs (the 30-day preview rows settling Aug 28 –
Sep 15, and every live run after).

Two deliberate design choices:

1. **Same population definition as the original run, narrowed by family.**
   Series come from the shared parent's `candidate_series()` (same
   `NO_CATEGORIES` / `is_excluded` / recency filters the original run
   used), then narrowed to `is_mention_family`. The eligible-series rule
   stays identical, so a difference in results means different markets,
   not a different population rule.
2. **Same replay, byte for byte.** Hits come from the shared parent's
   `replay_market()` unmodified — same screen, same daily-candle entry at
   the closing ask, same volume warm-up. This module only orchestrates,
   instruments, and records. The one liberty taken is a read-through cache
   around `history.candlesticks` so a market that replays to None can be
   diagnosed (no candles at all vs. never qualified) without a second
   network call — the decision path sees exactly the data it fetched.

Run:
    python -m theories.insider_bias.mention_family.backtest enumerate
    python -m theories.insider_bias.mention_family.backtest run

`enumerate` sizes the job (survivor counts per series, no candle calls,
nothing recorded). `run` replays and records, checkpointing per series to
the path in `--checkpoint` so an interrupted walk resumes where it left
off. Both modes print a per-series line as they go.

After a completed run, record the run row and score it:
    python -m tools.cli backtest record backtest-2026-08-25-mention-fullcov \
        mention_family 1 --tier A --notes "..."
    python -m tools.cli score report mention_family --run-mode backtest \
        --run-id backtest-2026-08-25-mention-fullcov
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tools import db, ledger, score
from tools.kalshi import history
from theories.insider_bias import screen
from theories.insider_bias import replay as sibling
from theories.insider_bias.mention_family.mention_bucket import (
    THEORY_ID,
    THEORY_VERSION,
    bucket_for_price,
    is_mention_family,
)

RUN_ID = "backtest-2026-08-25-mention-fullcov"

#: Close-time window: the whole API-reachable range (see module docstring
#: on the ~60-day archival floor). Min is set below the floor on purpose —
#: the listing simply returns nothing there, and if Kalshi's floor turns
#: out softer than measured, whatever exists gets picked up rather than
#: skipped. Max matches the original run's as_of_end. Actual coverage is
#: whatever the listing serves, reported per series, never assumed.
WINDOW_MIN_CLOSE = int(datetime(2026, 5, 26, tzinfo=timezone.utc).timestamp())
WINDOW_MAX_CLOSE = int(
    datetime(2026, 8, 24, 21, 51, 52, tzinfo=timezone.utc).timestamp()
)

#: candidate_series() recency filter. The window's newest market closed ~3
#: months before this driver was written, and a series' last_updated_ts can
#: trail its markets — 450 days keeps every series that could possibly hold
#: a window market while still skipping truly dead listings.
SERIES_RECENCY_DAYS = 450.0

RATIONALE = (
    "Tier A mention-family full-coverage backtest: same shared stage-1 "
    "screen replayed by the shared parent's replay_market() over EVERY "
    "settled mention-family survivor in the API-reachable close window "
    "(~2026-06-22 .. 2026-08-24; older markets are archived out of "
    "Kalshi's API), where the original run replayed a 600-of-18,430 "
    "systematic sample. First qualifying day within the screen's 14-day "
    "window, entry at the daily candle's closing ask. No probability "
    "claim -- screen.py makes none."
)


def mention_series(now: datetime | None = None) -> list[dict]:
    """Eligible series, original population rules, narrowed to this family."""
    return [
        s
        for s in sibling.candidate_series(
            now=now, recency_days=SERIES_RECENCY_DAYS
        )
        if is_mention_family(s.get("ticker") or "")
    ]


class _CandleCache:
    """Read-through cache over history.candlesticks, one market at a time.

    Lets the driver look at the candles `replay_market` just fetched (to
    tell "no candles served" apart from "never cleared the screen") without
    a second network call. Cleared per market so memory stays flat.
    """

    def __init__(self) -> None:
        self._real = history.candlesticks
        self.last: list[dict] | None = None

    def __call__(self, *args, **kwargs) -> list[dict]:
        self.last = self._real(*args, **kwargs)
        return self.last

    def install(self) -> None:
        history.candlesticks = self  # type: ignore[assignment]

    def uninstall(self) -> None:
        history.candlesticks = self._real  # type: ignore[assignment]


def replay_series(
    series_ticker: str, survivors: list, cache: _CandleCache
) -> dict:
    """Replay one series' survivors; returns hits plus honest counts."""
    hits: list[dict] = []
    no_candles = 0
    no_quotes = 0
    never_qualified = 0
    for settled in survivors:
        cache.last = None
        hit = sibling.replay_market(settled, series_ticker)
        if hit is not None:
            hits.append(hit)
        elif not cache.last:
            no_candles += 1
        elif not any(
            c.get("yes_bid_close") is not None
            and c.get("yes_ask_close") is not None
            for c in cache.last
        ):
            no_quotes += 1
        else:
            never_qualified += 1
    return {
        "series_ticker": series_ticker,
        "n_survivors": len(survivors),
        "n_hits": len(hits),
        "no_candles": no_candles,
        "no_quotes": no_quotes,
        "never_qualified": never_qualified,
        "hits": hits,
    }


def record_hits(conn: sqlite3.Connection, hits: list[dict]) -> int:
    """Write one series' hits as opportunity + settlement rows.

    Field-for-field the shape of the original run's rows (edge fields zero
    with edge_basis='prior' -- the screen claims no edge; bucket_rates
    measures one from settlements), so score.bucket_rates reads both runs
    identically.
    """
    written = 0
    for h in hits:
        entry_day = datetime.fromtimestamp(h["entry_day_ts"], tz=timezone.utc)
        ledger.record_opportunity(
            conn,
            theory_id=THEORY_ID,
            theory_version=THEORY_VERSION,
            kalshi_ticker=h["ticker"],
            outcome=h["fav_side"],
            entry_price=h["entry_price"],
            edge_pts_net=0.0,
            run_mode="backtest",
            run_id=RUN_ID,
            spread_at_call=h["spread_at_call"],
            volume_at_call=h["volume_at_call"],
            edge_basis="prior",
            confidence=bucket_for_price(h["entry_price"]),
            rationale=RATIONALE,
            evidence_source="kalshi",
            extra_json=json.dumps(
                {
                    "backtest_run": RUN_ID,
                    "series_ticker": h["series_ticker"],
                    "event_ticker": h["event_ticker"],
                    "entry_day_ts": h["entry_day_ts"],
                    "entry_day_iso": entry_day.isoformat(),
                    "days_to_close_at_entry": h["days_to_close"],
                    "is_mention_family": True,
                }
            ),
        )
        if h["result"]:
            score.record_settlement(conn, h["ticker"], h["result"])
        written += 1
    return written


def load_checkpoint(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"series": {}}


def save_checkpoint(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["enumerate", "run"])
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="state file; required for mode=run")
    parser.add_argument("--limit-series", type=int, default=None,
                        help="stop after N series (smoke-testing)")
    args = parser.parse_args()

    series_list = mention_series()
    print(f"{len(series_list)} mention-family series eligible "
          f"(window {WINDOW_MIN_CLOSE}..{WINDOW_MAX_CLOSE})")
    if args.limit_series:
        series_list = series_list[: args.limit_series]

    if args.mode == "enumerate":
        total = 0
        for ticker, survivors in sibling.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, WINDOW_MAX_CLOSE
        ):
            if survivors:
                print(f"  {ticker:30s} {len(survivors)} survivors")
            total += len(survivors)
        print(f"total survivors: {total}")
        return

    if args.checkpoint is None:
        parser.error("--checkpoint is required for mode=run")
    state = load_checkpoint(args.checkpoint)
    conn = db.connect()
    cache = _CandleCache()
    cache.install()
    try:
        for ticker, survivors in sibling.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, WINDOW_MAX_CLOSE
        ):
            if ticker in state["series"]:
                continue
            outcome = replay_series(ticker, survivors, cache)
            record_hits(conn, outcome["hits"])
            state["series"][ticker] = outcome
            save_checkpoint(args.checkpoint, state)
            print(
                f"  {ticker:30s} survivors={outcome['n_survivors']:4d} "
                f"hits={outcome['n_hits']:3d} "
                f"no_candles={outcome['no_candles']:3d} "
                f"no_quotes={outcome['no_quotes']:3d} "
                f"never_qualified={outcome['never_qualified']:4d}"
            )
    finally:
        cache.uninstall()
        conn.close()

    done = state["series"].values()
    print(
        f"done: {len(done)} series, "
        f"{sum(s['n_survivors'] for s in done)} survivors, "
        f"{sum(s['n_hits'] for s in done)} hits, "
        f"{sum(s['no_candles'] for s in done)} no_candles"
    )


if __name__ == "__main__":
    main()
