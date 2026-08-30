"""Collect Kalshi's settled multivariate (parlay) markets before they age out.

Kalshi archives settled markets out of the public API at roughly 60 days, so
this population is perishable: what is not on disk today may be unrecoverable
upstream tomorrow. Per CLAUDE.md's data conventions this writes incrementally
(per page, with a cursor checkpoint) and resumes rather than restarting.

Every settled parlay carries `mve_selected_legs` -- the exact leg tickers AND
sides -- plus `last_price_dollars`, `open_interest_fp` and `result`. That is
the complete input for a tier-A markup measurement: parlay price versus the
product of its legs' contemporaneous prices, scored against the realized
outcome. No model anywhere in the path.

The series name separates the two populations for free, with no judgment:

    *SINGLEGAME      legs from ONE game -- genuinely correlated, so
                     product-of-legs is NOT fair value. This is the CONTROL:
                     it SHOULD deviate.
    *MULTIGAME*      legs across games -- near-independent, so product-of-legs
    CROSSCATEGORY    IS fair value. This is the spec's population.

Usage:
    python studies/2026-08-30-parlay-markup/collect.py            # all series
    python studies/2026-08-30-parlay-markup/collect.py --cross    # cross-game only
    python studies/2026-08-30-parlay-markup/collect.py --status   # progress
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from tools.kalshi.markets import BASE_URL, get_json

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "collect.db")
PAGE = 1000

# Cross-game first: it is the thesis population, and if the run is cut short
# the control matters less than the thing being tested.
CROSS_GAME = [
    "KXMVECROSSCATEGORY",
    "KXMVECROSSCATEGORY-SHARD1",
    "KXMVESPORTSMULTIGAMEEXTENDED",
    "KXMVENFLMULTIGAME",
    "KXMVENFLMULTIGAMEEXTENDED",
    "KXMVENBAMULTIGAMEEXTENDED",
]
SAME_GAME = [
    "KXMVENBASINGLEGAME",
    "KXMVENFLSINGLEGAME",
]
OTHER = [
    "KXMVEMENTIONSSINGLE",
    "KXMVEGRAMMYS",
    "KXMVEOSCARS",
    "KXMVECBCHAMPIONSHIP",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS parlay_markets (
    ticker            TEXT PRIMARY KEY,
    series_ticker     TEXT NOT NULL,
    population        TEXT NOT NULL,     -- cross_game | same_game | other
    collection_ticker TEXT,
    event_ticker      TEXT,
    status            TEXT,
    result            TEXT,
    created_time      TEXT,
    close_time        TEXT,
    last_price        REAL,
    open_interest     REAL,
    n_legs            INTEGER,
    legs_json         TEXT NOT NULL,
    raw_json          TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_parlay_series ON parlay_markets(series_ticker);
CREATE INDEX IF NOT EXISTS ix_parlay_pop    ON parlay_markets(population);
CREATE INDEX IF NOT EXISTS ix_parlay_nlegs  ON parlay_markets(n_legs);

CREATE TABLE IF NOT EXISTS collect_progress (
    series_ticker TEXT NOT NULL,
    status_filter TEXT NOT NULL,
    cursor        TEXT,
    pages         INTEGER NOT NULL DEFAULT 0,
    rows          INTEGER NOT NULL DEFAULT 0,
    done          INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT,
    PRIMARY KEY (series_ticker, status_filter)
);
"""


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def population_of(series: str) -> str:
    if series in CROSS_GAME:
        return "cross_game"
    if series in SAME_GAME:
        return "same_game"
    return "other"


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def db_size_gb():
    total = 0
    for suffix in ("", "-journal", "-wal"):
        try:
            total += os.path.getsize(DB_PATH + suffix)
        except OSError:
            pass
    return total / 1e9


def store_page(conn, series, markets, now, keep_raw=False):
    pop = population_of(series)
    rows = []
    for m in markets:
        legs = m.get("mve_selected_legs") or []
        rows.append((
            m.get("ticker"), series, pop, m.get("mve_collection_ticker"),
            m.get("event_ticker"), m.get("status"), m.get("result"),
            m.get("created_time"), m.get("close_time"),
            _f(m.get("last_price_dollars")), _f(m.get("open_interest_fp")),
            len(legs), json.dumps(legs),
            # raw_json is OPT-IN. Storing it by default took this collector to
            # 4,199,000 rows / 23.6 GB, of which 16.3 GB was payload no analysis
            # in this study reads -- and, because the repo lives inside OneDrive
            # (which does not honour .gitignore), that was also a 23.6 GB cloud
            # upload nobody asked for. "Save as much as you can, while you can"
            # is a default, not a licence to ignore a size budget.
            json.dumps(m) if keep_raw else "", now,
        ))
    conn.executemany(
        "INSERT OR REPLACE INTO parlay_markets "
        "(ticker, series_ticker, population, collection_ticker, event_ticker, "
        " status, result, created_time, close_time, last_price, open_interest, "
        " n_legs, legs_json, raw_json, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def collect_series(conn, series, status_filter="settled", max_pages=10_000,
                   keep_raw=False, max_gb=2.0):
    row = conn.execute(
        "SELECT cursor, pages, rows, done FROM collect_progress "
        "WHERE series_ticker=? AND status_filter=?", (series, status_filter)
    ).fetchone()
    if row and row["done"]:
        print(f"  {series} [{status_filter}]: already complete "
              f"({row['rows']} rows) -- skipping")
        return 0
    cursor = row["cursor"] if row else None
    pages = row["pages"] if row else 0
    total = row["rows"] if row else 0
    if cursor:
        print(f"  {series} [{status_filter}]: resuming at page {pages} "
              f"({total} rows so far)")

    added = 0
    while pages < max_pages:
        params = {"series_ticker": series, "status": status_filter, "limit": PAGE}
        if cursor:
            params["cursor"] = cursor
        try:
            payload = get_json(f"{BASE_URL}/markets", params=params)
        except Exception as exc:                      # noqa: BLE001
            # Checkpoint already holds the last good cursor; a rerun resumes.
            print(f"  {series} [{status_filter}]: FETCH ERROR at page {pages}: "
                  f"{type(exc).__name__}: {str(exc)[:160]}")
            return added
        markets = payload.get("markets", [])
        if not markets:
            break
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        n = store_page(conn, series, markets, now, keep_raw=keep_raw)
        pages += 1
        total += n
        added += n
        cursor = payload.get("cursor")
        conn.execute(
            "INSERT INTO collect_progress "
            "(series_ticker, status_filter, cursor, pages, rows, done, updated_at) "
            "VALUES (?,?,?,?,?,0,?) "
            "ON CONFLICT(series_ticker, status_filter) DO UPDATE SET "
            "cursor=excluded.cursor, pages=excluded.pages, rows=excluded.rows, "
            "updated_at=excluded.updated_at",
            (series, status_filter, cursor, pages, total, now))
        conn.commit()                                  # per page, never at the end
        size = db_size_gb()
        if size > max_gb:
            print(f"  {series} [{status_filter}]: STOPPING -- database is "
                  f"{size:.2f} GB, over the {max_gb} GB budget. Progress is "
                  f"checkpointed; raise --max-gb to continue deliberately.")
            return added
        if pages % 5 == 0:
            print(f"  {series} [{status_filter}]: {pages} pages, {total} rows")
        if not cursor:
            break

    conn.execute(
        "UPDATE collect_progress SET done=1 WHERE series_ticker=? AND status_filter=?",
        (series, status_filter))
    conn.commit()
    print(f"  {series} [{status_filter}]: COMPLETE -- {pages} pages, {total} rows")
    return added


def show_status(conn):
    print("collected so far:")
    for r in conn.execute(
            "SELECT population, COUNT(*) n, SUM(n_legs) legs, "
            "SUM(CASE WHEN open_interest>0 THEN 1 ELSE 0 END) with_oi "
            "FROM parlay_markets GROUP BY population ORDER BY n DESC"):
        print(f"  {r['population']:12s} n={r['n']:7d}  with_oi={r['with_oi']:7d}")
    print("\nprogress:")
    for r in conn.execute(
            "SELECT series_ticker, status_filter, pages, rows, done "
            "FROM collect_progress ORDER BY series_ticker"):
        flag = "done" if r["done"] else "PARTIAL"
        print(f"  {r['series_ticker']:32s} {r['status_filter']:8s} "
              f"pages={r['pages']:4d} rows={r['rows']:7d} {flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cross", action="store_true", help="cross-game series only")
    ap.add_argument("--status", action="store_true", help="print progress and exit")
    ap.add_argument("--statuses", default="settled,closed",
                    help="comma-separated market statuses to sweep")
    ap.add_argument("--keep-raw", action="store_true",
                    help="also store the full raw payload per row (large: this "
                         "is what took an earlier run to 23.6 GB)")
    ap.add_argument("--max-gb", type=float, default=2.0,
                    help="stop when the database exceeds this size (GB)")
    args = ap.parse_args()

    conn = connect()
    if args.status:
        show_status(conn)
        return

    series = CROSS_GAME if args.cross else (CROSS_GAME + SAME_GAME + OTHER)
    started = time.time()
    grand = 0
    for status_filter in [s.strip() for s in args.statuses.split(",") if s.strip()]:
        print(f"\n=== status={status_filter} ===")
        for s in series:
            grand += collect_series(conn, s, status_filter,
                                    keep_raw=args.keep_raw, max_gb=args.max_gb)
    print(f"\nadded {grand} rows in {time.time()-started:.0f}s -> {DB_PATH}")
    show_status(conn)


if __name__ == "__main__":
    main()
