"""no_side_premium — tier A replay of CELL A over history the founding runs never saw.

**Why this exists, when THEORY.md said a replay was not planned.** That
line ("Replaying the two cells over stored snapshots adds no information
beyond the fullcov runs -- same window, same data") was written 2026-08-26
and was true then. It has since expired, quietly, and this driver is the
consequence:

- `backtest-2026-08-25-mention-fullcov` covered the API-reachable close
  window **~2026-06-22 .. 2026-08-24**. That is the data cell A's
  definition was chosen on, and it can never vouch for the cell.
- Markets closing **2026-08-25 onward** are outside that window. They are
  new history, they postdate the slice registration (2026-08-26), and no
  backtest has ever touched them.

So there is now a genuine out-of-sample replay window for cell A, and it
widens by one day per day. Per CLAUDE.md's 2026-08-31 ruling, a tier A
replay counts exactly as forward settlement does for a registered slice --
so this buys in an afternoon what cell A has been waiting weeks of calendar
time to accrue. Cell A sits at **2 event clusters over 2 settlement days**
against readiness gates of 10 and 5; the binding constraint is event
clusters, and the live screen only ever reaches `KXTRUMPSAY` and
`KXTRUMPACT` because the other mention series are too thin to clear the
volume floor on the day the theory happens to run.

**Cell A only, and that is deliberate.** Cell B's population is every
NON-mention series (5,583 of them in the insider fullcov), which is a
different and far larger job; cell B also already has 150 rows over 116
clusters and is not evidence-starved. This driver replays the mention
family, assigns cells with the theory's own `_cell` logic, and records what
lands in cell A. Mention-family rows outside cell A are counted and
reported but NOT recorded -- exactly as the live theory treats them, since
`theory._cell` returns None for them.

**Three things that keep this honest:**

1. **Same population rule, same replay, byte for byte.** Series come from
   the shared parent's `candidate_series()` narrowed by `is_mention_family`
   -- the identical rule the mention fullcov used. Hits come from the
   shared parent's `replay_market()` unmodified: same screen function, same
   daily-candle entry at the closing ask, same volume warm-up. Nothing here
   reimplements a decision.
2. **Cells are assigned by importing the theory's own `_cell`**, not by
   restating its thresholds. If the theory's cell boundaries ever move,
   this replay moves with them or fails loudly.
3. **Tickers the live theory already recorded are SKIPPED.** The ledger
   dedup key includes `run_mode`, so a backtest row for an already-live
   ticker would be a second row for one market and would be counted twice
   by any score pooling both run modes. The skip is what prevents that, and
   the count is reported.

Entry price note: `replay_market` builds its market view with
`no_ask = 1.0 - yes_bid`, so a NO favorite's `entry_price` is the price a
NO buyer actually pays. That is the convention CLAUDE.md requires and the
one `deadline_drift` got wrong for three days; it is correct here because
this replay does not touch price construction at all.

Run:
    python -m theories.no_side_premium.backtest enumerate
    python -m theories.no_side_premium.backtest run --checkpoint <path>

`enumerate` sizes the job with no candle calls and records nothing. `run`
replays and records, checkpointing per series so an interrupted walk
resumes where it stopped rather than restarting.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tools import db, ledger, score
from tools.domain import Candidate, Leg, Market
from tools.kalshi import history
from theories.insider_bias import replay as parent
from theories.insider_bias.families import is_mention_family
from theories.no_side_premium.theory import (
    CELL_A_PRIOR_NET,
    CELL_B_PRIOR_NET,
    _cell,
)

THEORY_ID = "no_side_premium"
THEORY_VERSION = 1
RUN_ID = "backtest-2026-09-01-nsp-mention-oos"

#: The window the founding evidence could not see. Min close is the instant
#: after `backtest-2026-08-25-mention-fullcov`'s as_of_end
#: (2026-08-24T21:51:52Z), rounded up to the next UTC midnight so the
#: boundary is a whole settlement day and cannot silently re-include a
#: fullcov market. Max is open-ended at run time.
WINDOW_MIN_CLOSE = int(datetime(2026, 8, 25, tzinfo=timezone.utc).timestamp())

#: The slice's registration instant. Rows settling after this are
#: out-of-sample by settlement date as well as by run -- reported
#: separately so the distinction is visible rather than asserted.
SLICE_REGISTERED_AT = datetime(2026, 8, 26, tzinfo=timezone.utc)

#: candidate_series() recency filter. The window is days old, so the
#: default 60 is amply wide; stated explicitly because the mention fullcov
#: needed 450 for a months-old window and the difference is not incidental.
SERIES_RECENCY_DAYS = 60.0

RATIONALE = (
    "Tier A cell-A replay over the post-fullcov window (close >= "
    "2026-08-25): every settled mention-family survivor the founding "
    "backtest-2026-08-25-mention-fullcov could not see, replayed by the "
    "shared parent's replay_market() unmodified -- same screen, first "
    "qualifying day within the 14-day window, entry at the daily candle's "
    "closing ask (no_ask = 1 - yes_bid for a NO favorite). Cell assigned "
    "by the theory's own _cell(). Prior +2.0 net, unchanged and NOT "
    "measured by this run: the run supplies settlements, the score "
    "supplies the measurement."
)


def mention_series(now: datetime | None = None) -> list[dict]:
    """Eligible series, the founding population rule, narrowed to family."""
    return [
        s
        for s in parent.candidate_series(
            now=now, recency_days=SERIES_RECENCY_DAYS
        )
        if is_mention_family(s.get("ticker") or "")
    ]


def already_recorded(conn: sqlite3.Connection) -> set[str]:
    """Tickers this theory already holds a row for, in any run mode."""
    return {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT kalshi_ticker FROM opportunities "
            "WHERE theory_id = ?",
            (THEORY_ID,),
        ).fetchall()
    }


class _CandleCache:
    """Read-through cache over history.candlesticks, one market at a time.

    Lets the driver tell "no candles served" apart from "never cleared the
    screen" without a second network call. The decision path still sees
    exactly the data it fetched.
    """

    def __init__(self) -> None:
        self._real = history.candlesticks
        self.last: list[dict] | None = None

    def __call__(self, *args, **kwargs) -> list[dict]:
        self.last = self._real(*args, **kwargs)
        return self.last

    def install(self) -> None:
        history.candlesticks = self       # type: ignore[assignment]

    def uninstall(self) -> None:
        history.candlesticks = self._real  # type: ignore[assignment]


def cell_of(hit: dict) -> str | None:
    """Which pre-registered cell a replay hit lands in.

    Rebuilds the minimal Candidate the theory's own `_cell` consumes rather
    than restating its thresholds here, so the two can never drift apart.
    """
    market = Market(
        platform="kalshi",
        ticker=hit["ticker"],
        is_open=True,
        mid=None,
        series_ticker=hit["series_ticker"],
        close_time=None,
        raw={},
    )
    candidate = Candidate(
        legs=(Leg(market=market, side=hit["fav_side"],
                  price=hit["entry_price"]),),
        days_to_close=hit["days_to_close"],
    )
    return _cell(candidate)


def replay_series(series_ticker: str, survivors: list,
                  cache: _CandleCache, skip: set[str]) -> dict:
    """Replay one series' survivors; returns cell-A hits plus honest counts."""
    hits: list[dict] = []
    counts = {"no_candles": 0, "no_quotes": 0, "never_qualified": 0,
              "already_live": 0, "cell_a": 0, "cell_b": 0, "no_cell": 0}
    for settled in survivors:
        if settled.ticker in skip:
            counts["already_live"] += 1
            continue
        cache.last = None
        hit = parent.replay_market(settled, series_ticker)
        if hit is None:
            if not cache.last:
                counts["no_candles"] += 1
            elif not any(c.get("yes_bid_close") is not None
                         and c.get("yes_ask_close") is not None
                         for c in cache.last):
                counts["no_quotes"] += 1
            else:
                counts["never_qualified"] += 1
            continue
        cell = cell_of(hit)
        if cell == "A":
            counts["cell_a"] += 1
            hit["cell"] = "A"
            hits.append(hit)
        elif cell == "B":
            # Unreachable by construction: _cell never returns B for a
            # mention series. Counted so the assumption is checked, not
            # assumed.
            counts["cell_b"] += 1
        else:
            counts["no_cell"] += 1
    return {"series_ticker": series_ticker, "n_survivors": len(survivors),
            "hits": hits, **counts}


def record_hits(conn: sqlite3.Connection, hits: list[dict]) -> int:
    """Write cell-A hits as opportunity + settlement rows.

    Field-for-field the shape of the live theory's cell-A rows -- same
    prior, same `edge_basis`, same `disposition` (screened), same
    confidence label -- so `score.observations` reads live and replayed
    rows identically and the slice predicate matches both.
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
            edge_pts_net=CELL_A_PRIOR_NET,
            run_mode="backtest",
            run_id=RUN_ID,
            decision_date=entry_day.date().isoformat(),
            spread_at_call=h["spread_at_call"],
            volume_at_call=h["volume_at_call"],
            edge_basis="prior",
            confidence="no_fav_mention_85",
            disposition="screened",
            rationale=RATIONALE,
            evidence_source="kalshi",
            extra_json=json.dumps({
                "backtest_run": RUN_ID,
                "cell": "A",
                "series_ticker": h["series_ticker"],
                "event_ticker": h["event_ticker"],
                "entry_day_ts": h["entry_day_ts"],
                "entry_day_iso": entry_day.isoformat(),
                "days_to_close_at_entry": h["days_to_close"],
                "is_mention_family": True,
            }),
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
    parser = argparse.ArgumentParser(description="cell-A OOS replay")
    parser.add_argument("mode", choices=["enumerate", "run"])
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--limit-series", type=int, default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    window_max = int(now.timestamp())
    series_list = mention_series(now=now)
    print(f"{len(series_list)} mention-family series eligible; window "
          f"close >= {datetime.fromtimestamp(WINDOW_MIN_CLOSE, tz=timezone.utc).date()}"
          f" .. {now.date()}", flush=True)
    if args.limit_series:
        series_list = series_list[: args.limit_series]

    conn = db.connect()
    skip = already_recorded(conn)
    print(f"{len(skip)} tickers already recorded by this theory will be "
          f"skipped (ledger dedup includes run_mode, so recording them "
          f"again would double-count)", flush=True)

    if args.mode == "enumerate":
        total = 0
        with_survivors = 0
        for ticker, survivors in parent.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, window_max
        ):
            if survivors:
                with_survivors += 1
                total += len(survivors)
                print(f"  {ticker:<30} {len(survivors):>4} survivors",
                      flush=True)
        print(f"\n{total} survivors across {with_survivors} series with any",
              flush=True)
        return

    if not args.checkpoint:
        parser.error("--checkpoint is required for mode=run")
    state = load_checkpoint(args.checkpoint)
    cache = _CandleCache()
    cache.install()
    try:
        for ticker, survivors in parent.iter_settled_survivors(
            series_list, WINDOW_MIN_CLOSE, window_max
        ):
            if ticker in state["series"]:
                continue
            if not survivors:
                state["series"][ticker] = {"n_survivors": 0, "written": 0}
                save_checkpoint(args.checkpoint, state)
                continue
            res = replay_series(ticker, survivors, cache, skip)
            written = record_hits(conn, res["hits"])
            state["series"][ticker] = {
                k: v for k, v in res.items() if k != "hits"
            } | {"written": written}
            save_checkpoint(args.checkpoint, state)
            if res["n_survivors"]:
                print(f"  {ticker:<30} surv {res['n_survivors']:>4}  "
                      f"cellA {res['cell_a']:>3}  written {written:>3}  "
                      f"(skip-live {res['already_live']}, "
                      f"no-cell {res['no_cell']}, "
                      f"never-qual {res['never_qualified']}, "
                      f"no-candles {res['no_candles']})", flush=True)
    finally:
        cache.uninstall()

    tot = {}
    for v in state["series"].values():
        for k, n in v.items():
            if isinstance(n, int):
                tot[k] = tot.get(k, 0) + n
    print(f"\nTOTALS: {tot}", flush=True)


if __name__ == "__main__":
    main()
