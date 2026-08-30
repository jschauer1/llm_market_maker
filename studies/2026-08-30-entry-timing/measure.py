"""Entry timing — the measurement the committed bar describes.

Run:  python studies/2026-08-30-entry-timing/measure.py <path-to-collect.db>

Reads the frozen snapshot read-only. Computes exactly what STUDY.md fixed
before any of this ran: the day-clustered paired difference between the
24h entry and the 25%-of-lifetime entry, its MDE, and the exploratory
breakdowns, each labelled as such.
"""
from __future__ import annotations

import math
import sqlite3
import statistics
import sys
from collections import defaultdict

#: STUDY.md's power floor: an effect this test cannot resolve has not been
#: measured. 2.0 pts is the smallest timing effect that could change an
#: entry rule in this repo.
MDE_FLOOR = 2.0

#: 2.8 x SE is the effect an alpha=.05 two-sided test catches 80% of the
#: time -- the standard 80%-power MDE, and the same constant
#: series-bias-mining used, kept identical so the two are comparable.
MDE_Z = 2.8

SQL = """
SELECT series_ticker, close_time, ask, won, side,
       ask_24h, won_24h, side_24h, offset_h
FROM obs
WHERE ask IS NOT NULL AND ask_24h IS NOT NULL
"""


def load(path: str) -> list[dict]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(SQL)]


def _clustered(values_by_day: dict[str, list[float]]) -> dict:
    """Mean, SE and t over per-day means. One day is one draw."""
    day_means = [statistics.fmean(v) for v in values_by_day.values()]
    n_days = len(day_means)
    if n_days == 0:
        return {"mean": None, "se": None, "t": None, "n_days": 0, "mde": None}
    mean = statistics.fmean(day_means)
    if n_days < 2:
        return {"mean": mean, "se": None, "t": None, "n_days": n_days,
                "mde": None}
    se = statistics.stdev(day_means) / math.sqrt(n_days)
    return {
        "mean": mean, "se": se, "n_days": n_days,
        "t": (mean / se) if se else None,
        "mde": MDE_Z * se,
    }


def _edges(rows: list[dict], which: str) -> dict[str, list[float]]:
    """Per-day gross edge in points for one entry point."""
    ask_k, won_k = ("ask", "won") if which == "main" else ("ask_24h", "won_24h")
    by_day: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_day[r["close_time"][:10]].append(100.0 * (r[won_k] - r[ask_k]))
    return by_day


def _paired(rows: list[dict]) -> dict[str, list[float]]:
    """Per-day PAIRED difference, alt minus main, in points."""
    by_day: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        d_alt = 100.0 * (r["won_24h"] - r["ask_24h"])
        d_main = 100.0 * (r["won"] - r["ask"])
        by_day[r["close_time"][:10]].append(d_alt - d_main)
    return by_day


def _holm(pvals: list[tuple[str, float]]) -> list[tuple[str, float, bool]]:
    """Holm-Bonferroni at alpha=.05. Returns (label, p, survives)."""
    m = len(pvals)
    ordered = sorted(pvals, key=lambda x: x[1])
    out, rejected = [], True
    for i, (label, p) in enumerate(ordered):
        thresh = 0.05 / (m - i)
        rejected = rejected and p <= thresh
        out.append((label, p, rejected))
    return out


def _p_from_t(t: float | None, df: int) -> float:
    """Two-sided p from a t statistic, normal approximation above df=30."""
    if t is None or df < 1:
        return 1.0
    # Normal approximation; df here is 40+ in every reported test, where the
    # t and normal tails agree to the third decimal. Stated rather than
    # hidden: this is not exact for the small per-series families below,
    # and those are exploratory anyway.
    z = abs(t)
    return math.erfc(z / math.sqrt(2.0))


def main() -> None:
    path = sys.argv[1]
    rows = load(path)
    print(f"paired rows: {len(rows)}  "
          f"series: {len({r['series_ticker'] for r in rows})}  "
          f"close days: {len({r['close_time'][:10] for r in rows})}\n")

    # ---- PRIMARY: the pooled paired difference -------------------------
    pair = _clustered(_paired(rows))
    main_e = _clustered(_edges(rows, "main"))
    alt_e = _clustered(_edges(rows, "alt"))

    print("=== PRIMARY (confirmatory): pooled paired difference ===")
    print(f"  entry main (25% of lifetime): {main_e['mean']:+.2f} pts "
          f"(SE {main_e['se']:.2f}, {main_e['n_days']} days)")
    print(f"  entry alt  (24h before close): {alt_e['mean']:+.2f} pts "
          f"(SE {alt_e['se']:.2f}, {alt_e['n_days']} days)")
    print(f"  PAIRED delta (alt - main)    : {pair['mean']:+.2f} pts "
          f"(SE {pair['se']:.2f}, t {pair['t']:+.2f}, {pair['n_days']} days)")
    print(f"  MDE (2.8 x SE)               : {pair['mde']:.2f} pts "
          f"(floor {MDE_FLOOR})")

    powered = pair["mde"] is not None and pair["mde"] <= MDE_FLOOR
    signif = pair["t"] is not None and abs(pair["t"]) >= 2.0
    negative = (pair["mean"] or 0) < 0
    if not powered:
        verdict = "NOT MEASURED (MDE above the floor)"
    elif signif and negative:
        verdict = "CONFIRMATORY: later entry earns less, as predicted"
    elif signif and not negative:
        verdict = "FAILED PREDICTION: later entry earns MORE (sign was fixed negative)"
    else:
        verdict = "GENUINE NEGATIVE: timing does not matter at any actionable size"
    print(f"\n  VERDICT: {verdict}\n")

    # ---- SECONDARY (declared in advance): side-agreeing subset ---------
    same = [r for r in rows if r["side"] == r["side_24h"]]
    diff = [r for r in rows if r["side"] != r["side_24h"]]
    print("=== SECONDARY (declared in advance): side agreement ===")
    print(f"  side agrees   : {len(same)} rows")
    print(f"  side flips    : {len(diff)} rows")
    if same:
        s = _clustered(_paired(same))
        print(f"  paired delta, side-agreeing: {s['mean']:+.2f} pts "
              f"(SE {s['se']:.2f}, t {s['t']:+.2f}, MDE {s['mde']:.2f})")
    if diff:
        d = _clustered(_paired(diff))
        print(f"  paired delta, side-flipped : {d['mean']:+.2f} pts "
              f"(SE {d['se']:.2f}, t {d['t']:+.2f}, MDE {d['mde']:.2f})")

    # ---- EXPLORATORY: offset buckets -----------------------------------
    print("\n=== EXPLORATORY (Holm-corrected, hypotheses not findings) ===")
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        h = r["offset_h"] or 0.0
        b = ("<6h" if h < 6 else "6-24h" if h < 24 else
             "1-3d" if h < 72 else "3-7d" if h < 168 else "7d+")
        buckets[b].append(r)
    fam = []
    for b, rs in sorted(buckets.items()):
        c = _clustered(_paired(rs))
        if c["t"] is None:
            print(f"  {b:6} n={len(rs):5d}  (too few days)")
            continue
        p = _p_from_t(c["t"], c["n_days"] - 1)
        fam.append((f"offset {b}", p))
        print(f"  {b:6} n={len(rs):5d} days={c['n_days']:3d} "
              f"delta {c['mean']:+6.2f} t {c['t']:+5.2f} "
              f"MDE {c['mde']:5.2f} p {p:.4f}")
    if fam:
        print("\n  Holm across the offset family:")
        for label, p, ok in _holm(fam):
            print(f"    {label:14} p={p:.4f}  {'SURVIVES' if ok else 'no'}")

    # ---- EXPLORATORY: per series ---------------------------------------
    per: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        per[r["series_ticker"]].append(r)
    tested = []
    for s, rs in per.items():
        c = _clustered(_paired(rs))
        if c["t"] is None or c["n_days"] < 5 or len(rs) < 40:
            continue
        tested.append((s, c, _p_from_t(c["t"], c["n_days"] - 1)))
    print(f"\n  per-series tested (>=40 rows, >=5 days): {len(tested)}")
    holm = {lab: ok for lab, _p, ok in _holm([(s, p) for s, _c, p in tested])}
    survivors = [(s, c, p) for s, c, p in tested if holm.get(s)]
    for s, c, p in sorted(survivors, key=lambda x: x[1]["mean"]):
        print(f"    {s:26} delta {c['mean']:+6.2f} t {c['t']:+5.2f} "
              f"days={c['n_days']:3d} p={p:.5f} SURVIVES HOLM")
    if not survivors:
        print("    none survive Holm-Bonferroni")


if __name__ == "__main__":
    main()
