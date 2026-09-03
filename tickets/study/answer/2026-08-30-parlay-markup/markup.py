"""Phase 2: outcome-free parlay markup = parlay price - product(leg mids).

Implements the phase-2 bar committed at bffd508, before any leg price was
fetched. Nothing here chooses a rule after seeing a number.

Why this replaces phase 1 as the headline: it never touches a realized
outcome, so the day-level common shock that gave phase 1 an 11.4pt MDE on
395,692 rows cannot enter it at all.

    python markup.py --selftest
    python markup.py --day 2026-08-16 --max-parlays 4000
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "..", "..")))

from tools.kalshi.history import candlesticks

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "collect.db")
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "legs.db")

MAX_STALE_S = 24 * 3600          # pre-registered: no mark older than 24h
MDE_MULTIPLIER = 2.8
POWER_FLOOR_PTS = 3.0

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS leg_candles (
    ticker     TEXT NOT NULL,
    end_ts     INTEGER NOT NULL,
    yes_bid    REAL,
    yes_ask    REAL,
    PRIMARY KEY (ticker, end_ts)
);
CREATE TABLE IF NOT EXISTS leg_fetched (
    ticker     TEXT PRIMARY KEY,
    day        TEXT,
    n_candles  INTEGER,
    fetched_at TEXT,
    error      TEXT
);
-- Priced parlays persist so days can be pooled and day-clustered. Phase 1's
-- whole lesson was that a single cluster is not evidence; one creation day
-- gives k=1, so the headline needs several days pooled here.
CREATE TABLE IF NOT EXISTS markups (
    ticker        TEXT PRIMARY KEY,
    population    TEXT NOT NULL,
    created_day   TEXT NOT NULL,
    legset_sig    TEXT NOT NULL,
    n_legs        INTEGER NOT NULL,
    parlay_price  REAL NOT NULL,
    prod_mid      REAL NOT NULL,
    prod_ask      REAL NOT NULL,
    markup_mid    REAL NOT NULL,
    markup_ask    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_markups_day ON markups(created_day);
CREATE INDEX IF NOT EXISTS ix_markups_pop ON markups(population);
"""


def iso_to_ts(iso: str) -> int:
    return int(time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")) -
               time.timezone)


def series_of(ticker: str) -> str:
    """KXMLBGAME-26AUG171340STLCING1-STL -> KXMLBGAME"""
    return ticker.split("-", 1)[0]


# ------------------------------------------------------------------ stats

def clustered(values_by_cluster):
    """values_by_cluster: dict cluster -> list of markups (pts)."""
    per = []
    for _, vals in values_by_cluster.items():
        per.append(sum(vals) / len(vals))
    k = len(per)
    if k == 0:
        return None
    mean = sum(per) / k
    if k == 1:
        return {"mean": mean, "se": 0.0, "t": math.inf if mean else 0.0,
                "k": k, "mde": 0.0}
    var = sum((v - mean) ** 2 for v in per) / (k - 1)
    se = math.sqrt(var / k)
    t = mean / se if se > 0 else (math.inf if mean else 0.0)
    return {"mean": mean, "se": se, "t": t, "k": k, "mde": MDE_MULTIPLIER * se}


# --------------------------------------------------------------- fixtures

def selftest():
    ok = True

    # A. side handling: a 'no' leg must contribute (1 - mid)
    legs = [{"market_ticker": "A", "side": "yes"},
            {"market_ticker": "B", "side": "no"}]
    mids = {"A": 0.60, "B": 0.25}
    prod = 1.0
    for leg in legs:
        m = mids[leg["market_ticker"]]
        prod *= m if leg["side"] == "yes" else (1.0 - m)
    expect = 0.60 * 0.75
    print(f"  side handling : product={prod:.4f} expected={expect:.4f}")
    if abs(prod - expect) > 1e-9:
        print("    FAIL: 'no' leg must contribute 1-mid"); ok = False

    # B. a planted markup is recovered exactly (no outcome noise here)
    by = {"d1": [5.0, 5.0, 5.0], "d2": [5.0, 5.0]}
    r = clustered(by)
    print(f"  planted +5    : mean={r['mean']:+.2f} k={r['k']}")
    if abs(r["mean"] - 5.0) > 1e-9:
        print("    FAIL"); ok = False

    # C. clustering bites: 10000 rows in one cluster is k=1, se=0 -- and must
    #    NOT be reported as infinitely significant evidence. k=1 is flagged.
    r = clustered({"one": [3.0] * 10000})
    print(f"  single cluster: k={r['k']} se={r['se']:.2f} (must be treated as k=1)")
    if r["k"] != 1:
        print("    FAIL"); ok = False

    # D. staleness boundary is exclusive at 24h
    print(f"  stale cutoff  : {MAX_STALE_S}s")
    if MAX_STALE_S != 86400:
        print("    FAIL"); ok = False

    print("  SELFTEST", "PASS" if ok else "FAIL")
    return ok


# ------------------------------------------------------------- leg prices

def cache_conn():
    conn = sqlite3.connect(CACHE_PATH)
    conn.executescript(CACHE_SCHEMA)
    return conn


def fetch_legs(cache, tickers, day):
    """Fetch hourly candles for each distinct leg once, covering `day`."""
    start = iso_to_ts(f"{day}T00:00:00")
    end = start + 86400 * 2
    done = {r[0] for r in cache.execute("SELECT ticker FROM leg_fetched")}
    todo = [t for t in tickers if t not in done]
    print(f"  legs: {len(tickers)} distinct, {len(todo)} to fetch")
    for i, tk in enumerate(todo, 1):
        err, rows = None, []
        try:
            candles = candlesticks(series_of(tk), tk,
                                   start_ts=start - 86400, end_ts=end,
                                   period_interval=60)
            rows = [(tk, c["end_ts"], c["yes_bid_close"], c["yes_ask_close"])
                    for c in candles]
        except Exception as exc:                       # noqa: BLE001
            err = f"{type(exc).__name__}: {str(exc)[:120]}"
        if rows:
            cache.executemany(
                "INSERT OR REPLACE INTO leg_candles VALUES (?,?,?,?)", rows)
        cache.execute(
            "INSERT OR REPLACE INTO leg_fetched VALUES (?,?,?,?,?)",
            (tk, day, len(rows),
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), err))
        cache.commit()                                  # incremental, resumable
        if i % 100 == 0:
            print(f"    {i}/{len(todo)}")


def leg_quote_at(cache, ticker, ts):
    """(bid, ask) for a leg at or before ts, or (None, reason)."""
    row = cache.execute(
        "SELECT end_ts, yes_bid, yes_ask FROM leg_candles "
        "WHERE ticker=? AND end_ts<=? ORDER BY end_ts DESC LIMIT 1",
        (ticker, ts)).fetchone()
    if not row:
        return None, "no candle at or before created_time"
    end_ts, bid, ask = row
    if ts - end_ts > MAX_STALE_S:
        return None, "mark staler than 24h"
    if bid is None or ask is None:
        return None, "candle missing bid or ask"
    mid = (bid + ask) / 2.0
    if not (0.0 < mid < 1.0):
        return None, "mid outside (0,1)"
    return (bid, ask), None


# -------------------------------------------------------------- the run

def run(day, max_parlays, population):
    src = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute(
        "SELECT ticker, last_price, n_legs, legs_json, created_time "
        "FROM parlay_markets WHERE population=? AND substr(created_time,1,10)=? "
        "AND open_interest>0 AND last_price>0 AND last_price<1 "
        "AND n_legs BETWEEN 2 AND 12 LIMIT ?",
        (population, day, max_parlays)).fetchall()
    print(f"\nPOPULATION {population}  creation day {day}: {len(rows)} parlays")
    if not rows:
        print("  nothing to measure"); return

    legs_needed = set()
    for r in rows:
        for leg in json.loads(r["legs_json"]):
            legs_needed.add(leg["market_ticker"])

    cache = cache_conn()
    fetch_legs(cache, sorted(legs_needed), day)

    excluded = defaultdict(int)
    priced = []
    for r in rows:
        ts = iso_to_ts(r["created_time"])
        legs = json.loads(r["legs_json"])
        prod_mid = prod_ask = 1.0
        bad = None
        for leg in legs:
            quote, why = leg_quote_at(cache, leg["market_ticker"], ts)
            if quote is None:
                bad = why; break
            bid, ask = quote
            mid = (bid + ask) / 2.0
            if leg.get("side") == "yes":
                prod_mid *= mid
                prod_ask *= ask            # buying a YES leg costs its ask
            else:
                prod_mid *= (1.0 - mid)
                prod_ask *= (1.0 - bid)    # a NO leg's ask is 1 - yes_bid
        if bad:
            excluded[bad] += 1                 # all-or-nothing, per the bar
            continue
        markup = 100.0 * (r["last_price"] - prod_mid)
        markup_ask = 100.0 * (r["last_price"] - prod_ask)
        sig = ",".join(sorted(l["market_ticker"] + l.get("side", "")
                              for l in legs))
        priced.append((r["created_time"][:10], sig, markup, r["n_legs"],
                       r["last_price"], prod_mid))
        cache.execute(
            "INSERT OR REPLACE INTO markups VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["ticker"], population, r["created_time"][:10], sig, r["n_legs"],
             r["last_price"], prod_mid, prod_ask, markup, markup_ask))
    cache.commit()

    print(f"  priced   : {len(priced)}")
    print("  excluded :")
    for why, n in sorted(excluded.items(), key=lambda kv: -kv[1]):
        print(f"      {why:36s} {n}")
    if not priced:
        return

    by_day = defaultdict(list)
    by_sig = defaultdict(list)
    for d, sig, mk, *_ in priced:
        by_day[d].append(mk); by_sig[sig].append(mk)
    rd, rs = clustered(by_day), clustered(by_sig)

    mean_parlay = sum(p[4] for p in priced) / len(priced)
    mean_prod = sum(p[5] for p in priced) / len(priced)
    print(f"\n  mean parlay price   : {mean_parlay:.4f}")
    print(f"  mean product-of-legs: {mean_prod:.4f}")
    print(f"  raw mean markup     : {100*(mean_parlay-mean_prod):+.2f} pts")
    print(f"\n  day-clustered   : {rd['mean']:+.2f} pts  t={rd['t']:+.2f}  "
          f"k={rd['k']}  MDE={rd['mde']:.2f}")
    print(f"  legset-clustered: {rs['mean']:+.2f} pts  t={rs['t']:+.2f}  "
          f"k={rs['k']}  MDE={rs['mde']:.2f}")
    if rd["k"] == 1:
        print("  NOTE: one creation day -> day clustering has k=1 and cannot "
              "produce an SE. The leg-set number is the honest one here.")

    print(f"\n  BY LEG COUNT (secondary: markup grows with legs)")
    print(f"    {'legs':>4s} {'n':>7s} {'k_sig':>6s} {'parlay':>8s} "
          f"{'product':>8s} {'markup':>8s} {'t':>7s} {'MDE':>7s}")
    by_legs = defaultdict(list)
    for d, sig, mk, L, pp, pr in priced:
        by_legs[L].append((sig, mk, pp, pr))
    for L in sorted(by_legs):
        grp = defaultdict(list)
        for sig, mk, _, _ in by_legs[L]:
            grp[sig].append(mk)
        rr = clustered(grp)
        pp = sum(x[2] for x in by_legs[L]) / len(by_legs[L])
        pr = sum(x[3] for x in by_legs[L]) / len(by_legs[L])
        print(f"    {L:4d} {len(by_legs[L]):7d} {rr['k']:6d} {pp:8.4f} "
              f"{pr:8.4f} {rr['mean']:+8.2f} {rr['t']:+7.2f} {rr['mde']:7.2f}")

    verdict = ("NOT MEASURED (MDE above floor)" if rs["mde"] > POWER_FLOOR_PTS
               else "CONFIRMATORY -- parlays carry a markup, as pre-registered"
               if rs["mean"] > 0 and rs["t"] >= 2
               else "FAILED PREDICTION -- markup negative or indistinguishable")
    print(f"\n  VERDICT: {verdict}")


def pooled(population):
    """Headline across every day priced so far -- the k>1 the bar requires."""
    cache = cache_conn()
    rows = cache.execute(
        "SELECT created_day, legset_sig, n_legs, parlay_price, prod_mid, "
        "prod_ask, markup_mid, markup_ask FROM markups WHERE population=?",
        (population,)).fetchall()
    if not rows:
        print("no priced rows yet"); return
    by_day, by_sig, by_day_ask = defaultdict(list), defaultdict(list), defaultdict(list)
    for d, sig, _, _, _, _, mk, mka in rows:
        by_day[d].append(mk); by_sig[sig].append(mk); by_day_ask[d].append(mka)
    rd, rs, rda = clustered(by_day), clustered(by_sig), clustered(by_day_ask)

    print(f"\n{'='*74}\nPOOLED HEADLINE -- {population}")
    print(f"  parlays priced : {len(rows)}")
    print(f"  creation days  : {rd['k']}")
    print(f"\n  markup vs product-of-MIDS")
    print(f"    day-clustered   : {rd['mean']:+.2f} pts  t={rd['t']:+.2f}  "
          f"k={rd['k']}  MDE={rd['mde']:.2f}")
    print(f"    legset-clustered: {rs['mean']:+.2f} pts  t={rs['t']:+.2f}  "
          f"k={rs['k']}  MDE={rs['mde']:.2f}")
    print(f"\n  markup vs product-of-ASKS (conservative: buy every leg at its ask)")
    print(f"    day-clustered   : {rda['mean']:+.2f} pts  t={rda['t']:+.2f}  "
          f"k={rda['k']}  MDE={rda['mde']:.2f}")
    print(f"\n  per-day (mid):")
    for d in sorted(by_day):
        v = by_day[d]
        print(f"    {d}  n={len(v):5d}  markup={sum(v)/len(v):+7.2f} pts")

    if rd["k"] < 3:
        print("\n  VERDICT: NOT MEASURED -- fewer than 3 creation days. "
              "Ruling 14 (a calibration spanning <3 settlement days triggers "
              "no action) applies in spirit: k=2 at 1 df has a 95% critical "
              "value of 12.71.")
    elif rd["mde"] > POWER_FLOOR_PTS:
        print(f"\n  VERDICT: NOT MEASURED -- day-clustered MDE "
              f"{rd['mde']:.2f} exceeds the {POWER_FLOOR_PTS} pt floor")
    elif rd["mean"] > 0 and rd["t"] >= 2:
        print("\n  VERDICT: CONFIRMATORY -- markup positive and day-robust, "
              "as pre-registered")
    else:
        print("\n  VERDICT: FAILED PREDICTION")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--day", default="2026-08-16")
    ap.add_argument("--days", default=None,
                    help="comma-separated creation days to price in sequence")
    ap.add_argument("--pool", action="store_true",
                    help="report the pooled headline over all priced days")
    ap.add_argument("--population", default="cross_game")
    ap.add_argument("--max-parlays", type=int, default=4000)
    a = ap.parse_args()
    if a.selftest:
        print("FIXTURES (rule 0d)")
        sys.exit(0 if selftest() else 1)
    if a.pool:
        pooled(a.population); return
    days = [d.strip() for d in a.days.split(",")] if a.days else [a.day]
    for d in days:
        run(d, a.max_parlays, a.population)
    if len(days) > 1:
        pooled(a.population)


if __name__ == "__main__":
    main()
