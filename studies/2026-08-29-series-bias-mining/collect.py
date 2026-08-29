"""Broad settled-history collector for the series-bias miner.

The miner's blocker was never method, it was population: pass 1 tested 7
non-control series and pass 2 tested 1, because both reused populations
fetched for other theories. This walks the whole board's recent settled
history so a run can test hundreds.

**Why per-series and not one unscoped walk.** `markets.list_settled`'s
own docstring: a single combinatorial series (`KXMVECROSSCATEGORY`)
produces 400,000+ settled markets *per day*, so an unscoped window is
tens of millions of rows. The documented pattern is list `/series`,
narrow, then walk once per series. Measured 2026-08-29: 0.05s per series
over a 12-series sample, so ~8,500 recent series is ~8 minutes.

**Why its own SQLite file.** This is a study, not a theory: it records
measurements and never writes the ledger. A separate file also keeps it
off the database three concurrent sessions are using.

**Resumable, per CLAUDE.md's collection rule.** Every series is committed
as it completes and recorded in `progress`, so an interrupted run resumes
where it stopped and never restarts from zero. That is not politeness:
Kalshi archives settled markets out of its public API ~60 days after
close, so rows a crashed run failed to persist may be unrecoverable
upstream by the time anyone re-runs.

Phase 1 (`walk`)   -- settled markets per series. Cheap, ~8 min.
Phase 2 (`prices`) -- for series with enough settled markets, the ask at
                      a single pre-registered decision point. Expensive;
                      Kalshi serialises candlesticks at ~4-5/s.

  python studies/2026-08-29-series-bias-mining/collect.py walk
  python studies/2026-08-29-series-bias-mining/collect.py prices
  python studies/2026-08-29-series-bias-mining/collect.py status
"""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from theories.insider_bias import replay              # noqa: E402
from tools.http import get_json                       # noqa: E402
from tools.kalshi import history, markets             # noqa: E402

DB = HERE / "data" / "collect.db"

#: Settled-history window. Kalshi archives beyond ~60 days.
WINDOW_DAYS = 60

#: A series untouched this long is skipped -- a call-count optimization,
#: not a claim about the thesis.
RECENCY_DAYS = 60

#: THE decision point, single and pre-registered: the ask 24h before
#: close. One observation per market. The spec's 7d/3d/1d would triple
#: the comparison count and its own section 10 says resist that until the
#: guard is proven.
DECISION_OFFSET_S = 86400

#: Only fetch prices for series with at least this many settled markets.
#: Below it a series cannot clear the miner's own n>=40 floor anyway, so
#: the candles would be wasted.
MIN_SETTLED_FOR_PRICES = 40

#: ...and at most this many. A series settling more than ~17 markets a
#: day over the window is a COMBINATORIAL PRODUCT, not a recurring series
#: -- KXBTCD alone settled 257,632 in 60 days (~4,300/day: Bitcoin price
#: across many strikes x many intraday times). Three reasons this cap is
#: not merely convenience:
#:   1. Thesis. The hypothesis is habitual retail flow on a *recurring*
#:      series. A 4,300/day combinatorial grid is a different object.
#:   2. Tractability. Kalshi serialises candlesticks at ~4-5/s, so
#:      pricing KXBTCD alone is 14+ hours.
#:   3. Weighting. One such series would supply 98% of all observations
#:      and dominate every pooled figure computed from them.
#: Chosen after seeing the COUNT distribution and before computing any
#: outcome; excluded series are reported by name so the cut is visible.
MAX_SETTLED_FOR_PRICES = 1000

#: Abort a single series' WALK once it exceeds this many rows.
#: `list_settled` has no partial-fetch option by design -- a prefix of
#: pages is not a representative sample -- so a combinatorial series is
#: walked to exhaustion or not at all. KXBTCD (257,632 rows) took minutes
#: and held every row in memory; the docstring's KXMVECROSSCATEGORY is
#: 400,000 settled markets PER DAY, which over a 60-day window would be
#: ~24M rows and would hang or exhaust memory outright.
#:
#: `on_page` is a callback, not an abort hook -- but raising from it
#: propagates out of the walk, which is the only bail-out available. The
#: series is then recorded as aborted, BY NAME, so an oversized series is
#: never silently missing: it is visibly excluded, which is the
#: distinction between a bounded population and an unexplained gap.
#: Well above MAX_SETTLED_FOR_PRICES, so nothing priceable is ever lost.
WALK_ROW_BUDGET = 20000


class SeriesTooLarge(Exception):
    """Raised from `on_page` to abort a combinatorial series' walk."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS settled (
    series_ticker TEXT NOT NULL,
    ticker        TEXT NOT NULL PRIMARY KEY,
    close_time    TEXT,
    result        TEXT
);
CREATE INDEX IF NOT EXISTS idx_settled_series ON settled(series_ticker);
CREATE TABLE IF NOT EXISTS obs (
    ticker        TEXT NOT NULL PRIMARY KEY,
    series_ticker TEXT NOT NULL,
    close_time    TEXT,
    result        TEXT,
    side          TEXT,      -- favorite side at the decision point
    ask           REAL,      -- what you would have paid for it
    won           INTEGER
);
CREATE INDEX IF NOT EXISTS idx_obs_series ON obs(series_ticker);
CREATE TABLE IF NOT EXISTS progress (
    phase  TEXT NOT NULL,
    key    TEXT NOT NULL,
    done_at TEXT NOT NULL,
    note   TEXT,
    PRIMARY KEY (phase, key)
);
"""


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _done(conn, phase: str) -> set[str]:
    return {r["key"] for r in
            conn.execute("SELECT key FROM progress WHERE phase=?", (phase,))}


def _mark(conn, phase: str, key: str, note: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO progress(phase,key,done_at,note) VALUES(?,?,?,?)",
        (phase, key, datetime.now(timezone.utc).isoformat(), note))


def recent_series(now=None) -> list[dict]:
    """Every series touched inside RECENCY_DAYS.

    Deliberately does NOT use `replay.candidate_series`: that applies
    insider_bias's `NO_CATEGORIES`, which excludes Climate and Weather,
    Elections, Economics and more -- exactly the recurring families this
    miner exists to test. Only the recency filter is borrowed.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - RECENCY_DAYS * 86400
    payload = get_json(f"{markets.BASE_URL}/series", params={"limit": 1000})
    return [s for s in payload.get("series", [])
            if s.get("ticker") and replay._is_recent(s, cutoff)]


def walk(conn, now=None) -> None:
    """Phase 1: settled markets per series, committed as each completes."""
    now = now or datetime.now(timezone.utc)
    lo = int(now.timestamp() - WINDOW_DAYS * 86400)
    hi = int(now.timestamp())
    series = recent_series(now)
    done = _done(conn, "walk")
    todo = [s for s in series if s["ticker"] not in done]
    print(f"phase 1: {len(series)} recent series, {len(done)} already walked, "
          f"{len(todo)} to go")
    t0 = time.time()
    for i, s in enumerate(todo, 1):
        tick = s["ticker"]
        def _budget(pages, seen, _t=tick):
            if seen > WALK_ROW_BUDGET:
                raise SeriesTooLarge(f"{_t}: >{WALK_ROW_BUDGET} rows")

        try:
            found = markets.list_settled(min_close_ts=lo, max_close_ts=hi,
                                         series_ticker=tick, on_page=_budget)
        except SeriesTooLarge:
            # Visibly excluded, never silently missing.
            _mark(conn, "walk", tick,
                  f"ABORTED combinatorial (>{WALK_ROW_BUDGET} rows)")
            conn.commit()
            print(f"  aborted {tick}: combinatorial", flush=True)
            continue
        except Exception as exc:                      # noqa: BLE001
            _mark(conn, "walk", tick, f"ERROR {exc!r}"[:200])
            conn.commit()
            continue
        rows = [(tick, m.ticker, m.close_time, m.result)
                for m in found if m.result in ("yes", "no")]
        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO settled(series_ticker,ticker,"
                "close_time,result) VALUES(?,?,?,?)", rows)
        _mark(conn, "walk", tick, f"{len(rows)} settled")
        conn.commit()                                 # per series, always
        if i % 250 == 0:
            rate = i / max(time.time() - t0, 1e-9)
            print(f"  {i}/{len(todo)}  {rate:.1f} series/s  "
                  f"eta {(len(todo)-i)/max(rate,1e-9)/60:.1f} min", flush=True)
    print("phase 1 complete")


def eligible_series(conn) -> list[tuple[str, int]]:
    return [(r["series_ticker"], r["n"]) for r in conn.execute(
        "SELECT series_ticker, COUNT(*) n FROM settled GROUP BY series_ticker "
        "HAVING n >= ? AND n <= ? ORDER BY n DESC",
        (MIN_SETTLED_FOR_PRICES, MAX_SETTLED_FOR_PRICES))]


def excluded_as_combinatorial(conn) -> list[tuple[str, int]]:
    """Series above the cap, reported by name so the cut stays visible."""
    return [(r["series_ticker"], r["n"]) for r in conn.execute(
        "SELECT series_ticker, COUNT(*) n FROM settled GROUP BY series_ticker "
        "HAVING n > ? ORDER BY n DESC", (MAX_SETTLED_FOR_PRICES,))]


def prices(conn, limit_series: int | None = None) -> None:
    """Phase 2: the ask at the decision point, per market, per series."""
    todo_series = eligible_series(conn)
    if limit_series:
        todo_series = todo_series[:limit_series]
    done = _done(conn, "prices")
    print(f"phase 2: {len(todo_series)} series with >= "
          f"{MIN_SETTLED_FOR_PRICES} settled; {len(done)} already priced")
    for si, (series_ticker, n) in enumerate(todo_series, 1):
        if series_ticker in done:
            continue
        rows = list(conn.execute(
            "SELECT ticker, close_time, result FROM settled WHERE "
            "series_ticker=?", (series_ticker,)))
        got = 0
        for r in rows:
            if not r["close_time"]:
                continue
            try:
                close_ts = int(datetime.fromisoformat(
                    r["close_time"].replace("Z", "+00:00")).timestamp())
                candle = history.point_in_time(
                    series_ticker, r["ticker"], close_ts - DECISION_OFFSET_S)
            except Exception:                         # noqa: BLE001
                continue
            if not candle:
                continue
            ya = candle.get("yes_ask")
            na = candle.get("no_ask")
            if ya is None or na is None:
                continue
            # The favorite side and the price actually payable for it.
            if ya <= na:
                side, ask = "yes", ya
            else:
                side, ask = "no", na
            if not (0.0 < ask < 1.0):
                continue
            conn.execute(
                "INSERT OR REPLACE INTO obs(ticker,series_ticker,close_time,"
                "result,side,ask,won) VALUES(?,?,?,?,?,?,?)",
                (r["ticker"], series_ticker, r["close_time"], r["result"],
                 side, ask, 1 if side == r["result"] else 0))
            got += 1
        _mark(conn, "prices", series_ticker, f"{got}/{len(rows)} priced")
        conn.commit()                                 # per series, always
        print(f"  [{si}/{len(todo_series)}] {series_ticker}: {got}/{len(rows)}",
              flush=True)
    print("phase 2 complete")


def status(conn) -> None:
    w = conn.execute("SELECT COUNT(*) c FROM progress WHERE phase='walk'").fetchone()["c"]
    s = conn.execute("SELECT COUNT(*) c FROM settled").fetchone()["c"]
    ns = conn.execute("SELECT COUNT(DISTINCT series_ticker) c FROM settled").fetchone()["c"]
    o = conn.execute("SELECT COUNT(*) c FROM obs").fetchone()["c"]
    no = conn.execute("SELECT COUNT(DISTINCT series_ticker) c FROM obs").fetchone()["c"]
    print(f"walked series      : {w}")
    print(f"settled markets    : {s} across {ns} series")
    print(f"  eligible ({MIN_SETTLED_FOR_PRICES}-{MAX_SETTLED_FOR_PRICES}) : "
          f"{len(eligible_series(conn))}")
    ex = excluded_as_combinatorial(conn)
    print(f"  excluded as combinatorial : {len(ex)}"
          + (f"  {', '.join(f'{t}({n})' for t, n in ex[:4])}" if ex else ""))
    ab = [r["key"] for r in conn.execute(
        "SELECT key FROM progress WHERE phase='walk' AND note LIKE 'ABORTED%'")]
    err = [r["key"] for r in conn.execute(
        "SELECT key FROM progress WHERE phase='walk' AND note LIKE 'ERROR%'")]
    print(f"  walk aborted (too large)  : {len(ab)}"
          + (f"  {', '.join(ab[:5])}" if ab else ""))
    print(f"  walk errored              : {len(err)}"
          + (f"  {', '.join(err[:5])}" if err else ""))
    print(f"priced observations: {o} across {no} series")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    conn = connect()
    if cmd == "walk":
        walk(conn)
    elif cmd == "prices":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        prices(conn, n)
    else:
        status(conn)


if __name__ == "__main__":
    main()
