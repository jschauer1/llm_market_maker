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

Backfill  -- book quality for observations written before 2026-09-01,
             when only the derived ask was persisted. Time-boxed by the
             ~60-day archive window; run it before `prices`.

  python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py walk
  python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py prices
  python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py backfill
  python tickets/study/investigation/2026-08-29-series-bias-mining/collect.py status
"""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[5]))

from theories.insider_bias import replay              # noqa: E402
from tools.http import get_json                       # noqa: E402
from tools.kalshi import history, markets             # noqa: E402

DB = HERE / "data" / "collect.db"

#: Settled-history window. Kalshi archives beyond ~60 days.
WINDOW_DAYS = 60

#: A series untouched this long is skipped -- a call-count optimization,
#: not a claim about the thesis.
RECENCY_DAYS = 60

#: THE decision point, single and pre-registered: **25% of the market's
#: own lifetime before close**. One observation per market. The spec's
#: 7d/3d/1d would triple the comparison count and its own section 10
#: says resist that until the guard is proven.
#:
#: AMENDED 2026-08-29, before any observation existed. The original was a
#: fixed 24h before close, which is UNRUNNABLE on this population: a
#: smoke test on the first series (KXAUDUSDAD) returned 0 of 40, because
#: those markets live **7.5 hours** -- 24h before close predates their
#: existence entirely, and the same is true of every intraday and daily
#: market on the board. A fixed wall-clock offset is also not comparable
#: across series: 24h is impossible for a 7-hour market and trivially
#: early for a 3-month one, so it does not represent a similar
#: information state.
#:
#: A fraction of lifetime is scale-free and well-defined for every
#: market. 25% is chosen to sit clear of the near-settled zone -- the
#: 2026-08-27 clustering study found favorites priced during an
#: in-progress game are close to already resolved, which would inflate
#: every edge -- while still being late enough that the market has
#: traded. Changed for WELL-DEFINEDNESS, not for any outcome: no
#: observation had been computed when this was amended.
DECISION_FRACTION = 0.25

#: Hourly-candle lookback. NOT larger: a 400-day hourly request returns
#: HttpError from Kalshi, and the first version swallowed that in a bare
#: `except Exception: continue`, so every market silently priced 0. The
#: whole population closed inside WINDOW_DAYS, so 90 days of hourly
#: candles covers any market that opened within a month of its close;
#: a longer-lived market has its early life truncated, which shortens the
#: measured span and moves its decision point later. `offset_h` is
#: recorded per observation so that bias is visible and filterable rather
#: than silent.
CANDLE_LOOKBACK_DAYS = 90

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
    close_time    TEXT,           -- OBSERVED close (may be early)
    result        TEXT,
    open_time     TEXT,
    expected_expiration_time TEXT, -- SCHEDULED close: outcome-independent
    latest_expiration_time   TEXT
);
CREATE INDEX IF NOT EXISTS idx_settled_series ON settled(series_ticker);
CREATE TABLE IF NOT EXISTS obs (
    ticker        TEXT NOT NULL PRIMARY KEY,
    series_ticker TEXT NOT NULL,
    close_time    TEXT,
    result        TEXT,
    side          TEXT,      -- favorite side at the decision point
    ask           REAL,      -- what you would have paid for it
    won           INTEGER,
    offset_h      REAL,      -- hours before close the price was taken
    n_candles     INTEGER,   -- how much price history existed at all
    -- The ORIGINAL pre-registered point (24h before scheduled close),
    -- priced from the same candles at zero extra API cost, so the
    -- amendment is measured rather than argued. NULL where the market
    -- lived < 24h, i.e. where the original rule was undefined.
    ask_24h       REAL,
    side_24h      TEXT,
    won_24h       INTEGER,
    -- Book quality AT the decision point. Added 2026-09-01 after pass 3
    -- found it could not distinguish a tradeable ask from a one-sided
    -- book; NULL for every observation captured before that date.
    spread        REAL,
    volume        REAL,
    open_interest REAL,
    spread_24h    REAL,
    -- Outcome-independence: a "by D" market that resolves early has its
    -- OBSERVED span truncated by the outcome itself. Anchoring to
    -- scheduled close removes that; this flag says when they differ.
    early_settled INTEGER
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


#: Columns added after the first collection ran. `CREATE TABLE IF NOT
#: EXISTS` is a no-op on an existing file, so widening the row needs an
#: explicit ALTER -- additive only, so every row captured earlier keeps
#: exactly the values it was written with and simply reads NULL here.
LATE_COLUMNS = (("spread", "REAL"), ("volume", "REAL"),
                ("open_interest", "REAL"), ("spread_24h", "REAL"))


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(obs)")}
    for col, typ in LATE_COLUMNS:
        if col not in have:
            conn.execute("ALTER TABLE obs ADD COLUMN %s %s" % (col, typ))
    conn.commit()
    return conn


def _ts(iso: str | None) -> int | None:
    """Unix seconds from an ISO-8601 stamp, or None."""
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(
            iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


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
        rows = [(tick, m.ticker, m.close_time, m.result,
                 (m.raw or {}).get("open_time"),
                 (m.raw or {}).get("expected_expiration_time"),
                 (m.raw or {}).get("latest_expiration_time"))
                for m in found if m.result in ("yes", "no")]
        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO settled(series_ticker,ticker,"
                "close_time,result,open_time,expected_expiration_time,"
                "latest_expiration_time) VALUES(?,?,?,?,?,?,?)", rows)
        _mark(conn, "walk", tick, f"{len(rows)} settled")
        conn.commit()                                 # per series, always
        if i % 250 == 0:
            rate = i / max(time.time() - t0, 1e-9)
            print(f"  {i}/{len(todo)}  {rate:.1f} series/s  "
                  f"eta {(len(todo)-i)/max(rate,1e-9)/60:.1f} min", flush=True)
    print("phase 1 complete")


def eligible_series(conn) -> list[tuple[str, int]]:
    return [(r["series_ticker"], r["n"]) for r in conn.execute(
        # ASCENDING by market count, deliberately. Phase 2 is ~174k
        # candle fetches at Kalshi's ~4-5/s, i.e. 10-12 hours, so it will
        # almost certainly be interrupted. Cheapest-first means the
        # maximum number of COMPLETE series exists at any stopping point,
        # and a series is the miner's unit of analysis -- half a series
        # is worth nothing to it. Ordering by n DESC would spend the
        # first hours on the few largest and leave the most series unstarted.
        "SELECT series_ticker, COUNT(*) n FROM settled GROUP BY series_ticker "
        "HAVING n >= ? AND n <= ? ORDER BY n ASC",
        (MIN_SETTLED_FOR_PRICES, MAX_SETTLED_FOR_PRICES))]


def excluded_as_combinatorial(conn) -> list[tuple[str, int]]:
    """Series above the cap, reported by name so the cut stays visible."""
    return [(r["series_ticker"], r["n"]) for r in conn.execute(
        "SELECT series_ticker, COUNT(*) n FROM settled GROUP BY series_ticker "
        "HAVING n > ? ORDER BY n DESC", (MAX_SETTLED_FOR_PRICES,))]


def decision_prices(row, cs, close_ts, sched_ts, open_ts):
    """(main, alt) observation tuples for one market, or (None, None).

    Extracted 2026-09-01 so `prices` and `backfill` cannot drift apart.
    That is not tidiness: the backfill attaches a spread to an ask that
    is ALREADY STORED, so if it computed a different decision point the
    two fields would describe different candles and nothing would say
    so. `backfill` re-derives the ask through this same function and
    refuses to write when it disagrees with the stored value.

    Each tuple is (side, ask, won, offset_h, spread, volume, oi).
    """
    def price_at(target_ts):
        elig = [c for c in cs if c["end_ts"] <= target_ts]
        c0 = elig[-1] if elig else None
        if c0 is None:
            return None
        ya, yb = c0.get("yes_ask_close"), c0.get("yes_bid_close")
        if ya is None or yb is None:
            return None
        ya, yb = float(ya), float(yb)
        if ya > 1.0 or yb > 1.0:                      # cents, not dollars
            ya, yb = ya / 100.0, yb / 100.0
        if (ya + yb) / 2.0 >= 0.5:
            side_, ask_ = "yes", ya
        else:
            side_, ask_ = "no", 1.0 - yb
        if not (0.0 < ask_ < 1.0):
            return None
        # Spread is side-independent: it is the same book either way, and
        # it is the field that says whether `ask_` was a price anyone was
        # actually offering.
        return (side_, ask_, 1 if side_ == row["result"] else 0,
                (close_ts - c0["end_ts"]) / 3600.0,
                ya - yb, c0.get("volume"), c0.get("open_interest"))

    if open_ts and sched_ts > open_ts:
        lifetime = sched_ts - open_ts
    else:
        lifetime = max(cs[-1]["end_ts"] - cs[0]["end_ts"], 0)

    main = price_at(sched_ts - max(3600.0, DECISION_FRACTION * lifetime))
    if main is None:
        # A short-lived market may have one candle and that single price
        # is all the history there is.
        main = price_at(cs[0]["end_ts"])
    alt = price_at(sched_ts - 86400) if lifetime >= 86400 else None
    return main, alt


def backfill(conn, limit_series: int | None = None) -> None:
    """Attach book quality to observations written before 2026-09-01.

    `collect.py` originally persisted only the derived ask, discarding
    the bid, volume and open interest the candle already carried. Pass 3
    could then not tell a tradeable price from a one-sided book, which
    is what made its nine flags unreadable (STUDY.md "Pass 3 result").

    This is time-boxed by Kalshi, not by preference: the fields can only
    come from candlesticks, and settled markets leave the public API
    ~60 days after close. Rows whose candles have already aged out are
    counted and REPORTED -- that count is the measure of what the
    original omission cost -- and are left exactly as they are. Nothing
    is ever deleted: dropping an un-backfillable row would silently
    shrink the population, which is a worse failure than a NULL.
    """
    todo = [r["series_ticker"] for r in conn.execute(
        "SELECT DISTINCT series_ticker FROM obs WHERE spread IS NULL "
        "ORDER BY series_ticker")]
    if limit_series:
        todo = todo[:limit_series]
    done = _done(conn, "backfill")
    print(f"backfill: {len(todo)} series carry NULL-spread rows; "
          f"{len(done)} already done")

    tot_filled = tot_aged = tot_mismatch = 0
    for si, series_ticker in enumerate(todo, 1):
        if series_ticker in done:
            continue
        rows = list(conn.execute(
            "SELECT o.ticker, o.ask, o.side, s.close_time, s.result, "
            "s.open_time, s.expected_expiration_time "
            "FROM obs o JOIN settled s ON s.ticker = o.ticker "
            "WHERE o.series_ticker=? AND o.spread IS NULL",
            (series_ticker,)))
        filled = aged = mismatch = 0
        for r in rows:
            close_ts, sched_ts = _ts(r["close_time"]),                 _ts(r["expected_expiration_time"])
            if close_ts is None or sched_ts is None:
                continue
            try:
                cs = history.candlesticks(
                    series_ticker, r["ticker"],
                    start_ts=close_ts - 86400 * CANDLE_LOOKBACK_DAYS,
                    end_ts=close_ts, period_interval=60)
            except Exception:                          # noqa: BLE001
                aged += 1
                continue
            if not cs:
                aged += 1                              # gone upstream
                continue
            main, alt = decision_prices(r, cs, close_ts, sched_ts,
                                        _ts(r["open_time"]))
            if main is None:
                aged += 1
                continue
            # The self-check. A recomputed ask that disagrees with the
            # stored one means the two fields would describe different
            # candles, so the row is left alone and counted.
            if abs(main[1] - float(r["ask"])) > 1e-9 or main[0] != r["side"]:
                mismatch += 1
                continue
            conn.execute(
                "UPDATE obs SET spread=?, volume=?, open_interest=?, "
                "spread_24h=? WHERE ticker=?",
                (main[4], main[5], main[6],
                 alt[4] if alt else None, r["ticker"]))
            filled += 1
        note = f"{filled}/{len(rows)} filled"
        if aged:
            note += f"; {aged} aged out upstream"
        if mismatch:
            note += f"; {mismatch} ask mismatch (left alone)"
        _mark(conn, "backfill", series_ticker, note)
        conn.commit()                                 # per series, always
        tot_filled += filled
        tot_aged += aged
        tot_mismatch += mismatch
        print(f"  [{si}/{len(todo)}] {series_ticker}: {note}", flush=True)
    print(f"backfill done: {tot_filled} filled, {tot_aged} aged out, "
          f"{tot_mismatch} mismatched")


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
            "SELECT ticker, close_time, result, open_time, "
            "expected_expiration_time FROM settled WHERE series_ticker=?",
            (series_ticker,)))
        got = 0
        noshed = 0
        errs: list[str] = []
        for r in rows:
            if not r["close_time"]:
                continue
            try:
                close_ts = _ts(r["close_time"])
                # SCHEDULED close, not observed. A "by D" market that
                # resolves early has its observed close pulled forward BY
                # THE OUTCOME, so anchoring the decision point to it makes
                # the information state a function of the answer -- which
                # would bias any bias the miner then measures. Scheduled
                # close is outcome-independent; fall back to observed only
                # when the field is absent.
                sched_ts = _ts(r["expected_expiration_time"])
                open_ts = _ts(r["open_time"])
                cs = history.candlesticks(
                    series_ticker, r["ticker"],
                    start_ts=close_ts - 86400 * CANDLE_LOOKBACK_DAYS,
                    end_ts=close_ts, period_interval=60)
            except Exception as exc:                  # noqa: BLE001
                errs.append(f"{type(exc).__name__}")
                continue
            if not cs:
                continue
            if sched_ts is None:
                # EXCLUDED, never fallen back to observed close. On a
                # "does X happen by D" market the actual close IS the
                # outcome variable, so using it to place the decision
                # point makes the information state a function of the
                # answer. Measured on this population: 66.8% of eligible
                # markets settled EARLY (median 3h, max 490 days), so the
                # fallback would have contaminated two thirds of it.
                # Session 78 hit exactly this and their deadline_drift
                # result flipped sign (-3.4 -> +4.7) on correction.
                # Only 114 eligible rows lack the field; dropping them is
                # cheaper than trusting them.
                noshed += 1
                continue

            main, alt = decision_prices(
                r, cs, close_ts, sched_ts, open_ts)
            if main is None:
                continue
            side, ask, won, offset_h, spread, vol, oi = main

            conn.execute(
                "INSERT OR REPLACE INTO obs(ticker,series_ticker,close_time,"
                "result,side,ask,won,offset_h,n_candles,ask_24h,side_24h,"
                "won_24h,early_settled,spread,volume,open_interest,"
                "spread_24h) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["ticker"], series_ticker, r["close_time"], r["result"],
                 side, ask, won, offset_h, len(cs),
                 alt[1] if alt else None, alt[0] if alt else None,
                 alt[2] if alt else None,
                 1 if (sched_ts - close_ts) > 3600 else 0,
                 spread, vol, oi, alt[4] if alt else None))
            got += 1
        note = f"{got}/{len(rows)} priced"
        if noshed:
            note += f"; {noshed} no scheduled close"
        if errs:
            note += f"; {len(errs)} fetch errors ({errs[0]})"
        _mark(conn, "prices", series_ticker, note)
        conn.commit()                                 # per series, always
        print(f"  [{si}/{len(todo_series)}] {series_ticker}: {note}",
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
    elif cmd == "backfill":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        backfill(conn, n)
    elif cmd == "prices":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        prices(conn, n)
    else:
        status(conn)


if __name__ == "__main__":
    main()
