"""The orientation check that invalidates measure.py's headline.

`main` is priced at 25% of scheduled lifetime before close; `alt` at a
fixed 24h before close. Which of the two is the LATER entry therefore
depends on the market's lifetime:

    0.25 * L > 24h  (L > 4 days)  ->  main is EARLIER, alt is LATER
    0.25 * L < 24h  (L < 4 days)  ->  main is LATER,   alt is EARLIER

So `alt - main` is "later minus earlier" for long-lived markets and
"earlier minus later" for short-lived ones. Pooling them, as the
pre-registered primary statistic did, averages two opposite contrasts and
the resulting sign means nothing. This script re-orients every row so the
difference always reads later-minus-earlier, and reports the two regimes
separately as well as pooled.

Run: python tickets/study/answer/2026-08-30-entry-timing/orient.py <path-to-collect.db>
"""
from __future__ import annotations

import math
import sqlite3
import statistics
import sys
from collections import defaultdict

MDE_Z = 2.8
MDE_FLOOR = 2.0

SQL = """
SELECT series_ticker, close_time, ask, won, side,
       ask_24h, won_24h, side_24h, offset_h
FROM obs
WHERE ask IS NOT NULL AND ask_24h IS NOT NULL
"""


def load(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(SQL)]


def clustered(by_day):
    means = [statistics.fmean(v) for v in by_day.values()]
    n = len(means)
    if n < 2:
        return {"mean": means[0] if means else None, "se": None, "t": None,
                "n_days": n, "mde": None}
    m = statistics.fmean(means)
    se = statistics.stdev(means) / math.sqrt(n)
    return {"mean": m, "se": se, "n_days": n,
            "t": (m / se) if se else None, "mde": MDE_Z * se if se else None}


def oriented_delta(rows):
    """Per-day mean of (later entry edge - earlier entry edge), in points."""
    by_day = defaultdict(list)
    for r in rows:
        e_main = 100.0 * (r["won"] - r["ask"])
        e_alt = 100.0 * (r["won_24h"] - r["ask_24h"])
        # offset_h is how far before close the MAIN entry sat.
        if r["offset_h"] is None:
            continue
        if r["offset_h"] > 24.0:        # main earlier, alt later
            later, earlier = e_alt, e_main
        elif r["offset_h"] < 24.0:      # main later, alt earlier
            later, earlier = e_main, e_alt
        else:
            continue                     # identical entry points
        by_day[r["close_time"][:10]].append(later - earlier)
    return by_day


def report(label, rows):
    c = clustered(oriented_delta(rows))
    if c["t"] is None:
        print(f"  {label:34} n={len(rows):5d}  (too few days)")
        return c
    print(f"  {label:34} n={len(rows):5d} days={c['n_days']:3d} "
          f"later-earlier {c['mean']:+6.2f} SE {c['se']:5.2f} "
          f"t {c['t']:+5.2f} MDE {c['mde']:5.2f}")
    return c


def main():
    rows = load(sys.argv[1])
    long_lived = [r for r in rows if (r["offset_h"] or 0) > 24.0]
    short_lived = [r for r in rows if 0 <= (r["offset_h"] or 0) < 24.0]

    print(f"paired rows: {len(rows)}\n")
    print("How many rows have the comparison INVERTED relative to the")
    print("pre-registered framing (i.e. `alt` is the EARLIER entry):")
    print(f"  main EARLIER than alt (lifetime > 4d) : {len(long_lived):5d}"
          f"  ({100*len(long_lived)/len(rows):.1f}%)")
    print(f"  main LATER   than alt (lifetime < 4d) : {len(short_lived):5d}"
          f"  ({100*len(short_lived)/len(rows):.1f}%)  <-- INVERTED\n")

    print("=== Re-oriented: every difference reads LATER minus EARLIER ===")
    pooled = report("POOLED (all paired rows)", rows)
    print()
    report("long-lived only (>4d lifetime)", long_lived)
    report("short-lived only (<4d lifetime)", short_lived)

    print("\n=== side agreement, re-oriented ===")
    report("side agrees", [r for r in rows if r["side"] == r["side_24h"]])
    report("side flips", [r for r in rows if r["side"] != r["side_24h"]])

    print("\n=== verdict against the committed bar ===")
    print("  Bar fixed the sign NEGATIVE (later entry earns LESS).")
    if pooled["mde"] and pooled["mde"] > MDE_FLOOR:
        print(f"  Pooled MDE {pooled['mde']:.2f} > {MDE_FLOOR} -> NOT MEASURED")
    elif pooled["t"] is not None and abs(pooled["t"]) >= 2.0:
        direction = "NEGATIVE" if pooled["mean"] < 0 else "POSITIVE"
        if pooled["mean"] < 0:
            print("  CONFIRMATORY: later entry earns less, as predicted.")
        else:
            print(f"  FAILED PREDICTION: significant but {direction} — later "
                  "entry earns MORE. The bar fixed the sign in advance "
                  "precisely so this cannot be re-read as a discovery.")
    else:
        print("  GENUINE NEGATIVE: no effect at an actionable size.")


if __name__ == "__main__":
    main()
