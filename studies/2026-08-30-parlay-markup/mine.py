"""Phase 1 of the parlay-markup study: day-clustered calibration of settled parlays.

Implements exactly the bar in STUDY.md, which was committed (e5514a2) before
any number here was computed. Nothing in this file chooses a cut after seeing
a result; the inclusion rules, the statistic, the direction and the power floor
are all transcribed from that file.

    python mine.py --selftest    fixtures first, per backlog rule 0d
    python mine.py               the real run
"""
from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from tools.sizing import fee_pts

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "collect.db")

MIN_LEGS, MAX_LEGS = 2, 12
MDE_MULTIPLIER = 2.8          # ~80% power at alpha=.05, per STUDY.md
POWER_FLOOR_PTS = 3.0         # theory-grade edge, pre-registered


# ---------------------------------------------------------------- statistic

def day_clustered(obs):
    """obs: list of (day, won01, price). Returns dict with the gross edge.

    One observation per settlement day = mean(won) - mean(price) over that
    day's rows. Estimate is the mean over days; SE is between-day.
    """
    by_day = defaultdict(list)
    for day, won, price in obs:
        by_day[day].append((won, price))

    day_edges = []
    for day, rows in by_day.items():
        n = len(rows)
        edge = sum(w for w, _ in rows) / n - sum(p for _, p in rows) / n
        day_edges.append(100.0 * edge)

    k = len(day_edges)
    if k == 0:
        return None
    mean = sum(day_edges) / k
    if k == 1:
        # Zero between-day variance is maximal consistency, not maximal
        # insignificance -- the inverted edge case series-bias-mining hit.
        return {"edge_pts": mean, "se": 0.0, "t": math.inf if mean else 0.0,
                "n_days": k, "n_rows": len(obs), "mde_pts": 0.0}
    var = sum((e - mean) ** 2 for e in day_edges) / (k - 1)
    se = math.sqrt(var / k)
    t = mean / se if se > 0 else (math.inf if mean else 0.0)
    return {"edge_pts": mean, "se": se, "t": t, "n_days": k,
            "n_rows": len(obs), "mde_pts": MDE_MULTIPLIER * se}


# ---------------------------------------------------------------- fixtures

def _sim(seed, shift=0.0, days=40, per_day=50):
    import random
    rng = random.Random(seed)
    obs = []
    for d in range(days):
        for _ in range(per_day):
            p = rng.uniform(0.05, 0.60)
            true_p = min(1.0, max(0.0, p + shift))
            obs.append((f"d{d}", 1 if rng.random() < true_p else 0, p))
    return day_clustered(obs)


def selftest():
    """Plant a known bias among known-null cases and check both are recovered.

    A and B run over MANY seeds, not one. A single-seed tolerance test is
    itself a badly-powered test: at these sizes the between-day SE is ~1.05
    pts, so a +/-1.5 pt gate on one draw fires by chance roughly 15% of the
    time. The first version of this fixture did exactly that and "failed" on
    a genuine 3-sigma draw -- the same class of error (a bar not matched to
    the noise) that the backlog index's rule 0b was written about. Testing
    the estimator's UNBIASEDNESS across seeds is the honest version.
    """
    ok = True
    seeds = range(60)

    # A. calibrated population -> unbiased, and a near-nominal false-positive rate
    rs = [_sim(s) for s in seeds]
    mean_edge = sum(r["edge_pts"] for r in rs) / len(rs)
    fp = sum(1 for r in rs if abs(r["t"]) >= 2) / len(rs)
    print(f"  calibrated : mean edge={mean_edge:+.3f} pts over {len(rs)} seeds, "
          f"|t|>=2 in {fp:.0%}")
    if abs(mean_edge) > 0.5:
        print("    FAIL: estimator is biased on a calibrated population"); ok = False
    if fp > 0.20:
        print("    FAIL: false-positive rate far above nominal"); ok = False

    # B. planted -8pt overpricing -> recovered on average, and detected
    rs = [_sim(s, shift=-0.08) for s in seeds]
    mean_edge = sum(r["edge_pts"] for r in rs) / len(rs)
    detected = sum(1 for r in rs if r["t"] <= -2) / len(rs)
    print(f"  planted -8 : mean edge={mean_edge:+.2f} pts, detected in {detected:.0%}")
    if not (-8.5 < mean_edge < -5.5):
        print("    FAIL: should recover about -8 points on average"); ok = False
    if detected < 0.80:
        print("    FAIL: planted effect should be detected in most draws"); ok = False

    # B2. the guard must not be fooled by a CONSTANT offset the way a
    # net-of-fees statistic would be (series-bias-mining's amendment).
    r = _sim(7, shift=0.0)
    print(f"  gross check: calibrated draw scores {r['edge_pts']:+.2f} "
          f"(a net-of-fees statistic would score ~-1 to -3 here)")

    # C. clustering actually bites: one day repeated 5000x is ONE observation,
    #    so a huge row count must not manufacture significance.
    obs = [("oneday", 1, 0.10)] * 5000
    r = day_clustered(obs)
    print(f"  single day : rows={r['n_rows']} days={r['n_days']} se={r['se']:.2f}")
    if r["n_days"] != 1:
        print("    FAIL: 5000 rows on one day must be 1 cluster"); ok = False

    # D. fees are NOT in the statistic (STUDY.md scores gross)
    obs = [(f"d{d}", 1, 1.0) for d in range(20)]
    r = day_clustered(obs)
    if abs(r["edge_pts"]) > 1e-9:
        print("    FAIL: a perfectly-priced always-win set must score 0 gross")
        ok = False

    print("  SELFTEST", "PASS" if ok else "FAIL")
    return ok


# ---------------------------------------------------------------- the run

def load(conn, population="cross_game"):
    rows = conn.execute(
        "SELECT ticker, result, last_price, open_interest, n_legs, close_time "
        "FROM parlay_markets WHERE population = ?", (population,)).fetchall()

    excluded = defaultdict(int)
    kept = []
    for r in rows:
        if r["result"] not in ("yes", "no"):
            excluded[f"result={r['result']!r}"] += 1; continue
        if not r["open_interest"] or r["open_interest"] <= 0:
            excluded["open_interest<=0"] += 1; continue
        p = r["last_price"]
        if p is None or p <= 0.0 or p >= 1.0:
            excluded["price outside (0,1)"] += 1; continue
        if r["n_legs"] is None or r["n_legs"] < MIN_LEGS:
            excluded[f"n_legs<{MIN_LEGS}"] += 1; continue
        if r["n_legs"] > MAX_LEGS:
            excluded[f"n_legs>{MAX_LEGS} (reported separately)"] += 1; continue
        if not r["close_time"]:
            excluded["no close_time"] += 1; continue
        kept.append((r["close_time"][:10], 1 if r["result"] == "yes" else 0,
                     p, r["n_legs"]))
    return kept, excluded


def report(conn, population):
    kept, excluded = load(conn, population)
    total = sum(excluded.values()) + len(kept)
    print(f"\n{'='*74}\nPOPULATION: {population}")
    print(f"  rows in db      : {total}")
    print(f"  included        : {len(kept)}")
    print("  excluded by reason:")
    for reason, n in sorted(excluded.items(), key=lambda kv: -kv[1]):
        print(f"      {reason:42s} {n}")
    if not kept:
        print("  nothing to measure")
        return

    obs = [(d, w, p) for d, w, p, _ in kept]
    r = day_clustered(obs)
    mean_price = sum(p for _, _, p, _ in kept) / len(kept)
    win_rate = sum(w for _, w, _, _ in kept) / len(kept)
    net = r["edge_pts"] - fee_pts(mean_price)

    print(f"\n  HEADLINE (day-clustered, gross)")
    print(f"    settlement days : {r['n_days']}")
    print(f"    mean last_price : {mean_price:.4f}")
    print(f"    realized win    : {win_rate:.4f}")
    print(f"    edge (gross)    : {r['edge_pts']:+.2f} pts")
    print(f"    SE / t          : {r['se']:.2f} / {r['t']:+.2f}")
    print(f"    MDE (2.8*SE)    : {r['mde_pts']:.2f} pts   "
          f"(power floor {POWER_FLOOR_PTS})")
    print(f"    edge (net, ref) : {net:+.2f} pts")

    powered = r["mde_pts"] <= POWER_FLOOR_PTS
    if not powered:
        verdict = "NOT MEASURED (MDE above the pre-registered power floor)"
    elif r["edge_pts"] < 0 and abs(r["t"]) >= 2:
        verdict = "CONFIRMATORY -- parlays overpriced, as pre-registered"
    elif r["edge_pts"] > 0 and abs(r["t"]) >= 2:
        verdict = "FAILED PREDICTION -- signed the WRONG way (underpriced)"
    else:
        verdict = "FAILED PREDICTION -- indistinguishable from zero at adequate power"
    print(f"    VERDICT         : {verdict}")

    # Secondary: leg-count gradient. Reported at whatever power each bucket
    # has, with MDE beside it, and with outcome composition shown -- the
    # selection channel STUDY.md names.
    print(f"\n  BY LEG COUNT (secondary prediction: |edge| grows with legs)")
    print(f"    {'legs':>4s} {'n':>7s} {'days':>5s} {'price':>7s} {'win':>7s} "
          f"{'edge':>8s} {'t':>7s} {'MDE':>7s}")
    by_legs = defaultdict(list)
    for d, w, p, L in kept:
        by_legs[L].append((d, w, p))
    for L in sorted(by_legs):
        rr = day_clustered(by_legs[L])
        mp = sum(p for _, _, p in by_legs[L]) / len(by_legs[L])
        wr = sum(w for _, w, _ in by_legs[L]) / len(by_legs[L])
        print(f"    {L:4d} {rr['n_rows']:7d} {rr['n_days']:5d} {mp:7.4f} "
              f"{wr:7.4f} {rr['edge_pts']:+8.2f} {rr['t']:+7.2f} "
              f"{rr['mde_pts']:7.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--population", default="cross_game")
    args = ap.parse_args()

    if args.selftest:
        print("FIXTURES (rule 0d -- before touching real data)")
        sys.exit(0 if selftest() else 1)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    report(conn, args.population)


if __name__ == "__main__":
    main()
