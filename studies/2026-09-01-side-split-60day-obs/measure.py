"""Split the 60-day series-bias observation set by side -- no_side_premium's
hypothesis, on a population it was never measured over.

`studies/2026-08-29-series-bias-mining/data/collect.db` holds tens of
thousands of settled markets priced at a point-in-time decision anchored to
SCHEDULED close, spanning ~61 close days. Pass 3 of that study published an
ask-band calibration table pooled across YES and NO favorites. The `obs`
table has a `side` column and nobody had split it. That split is exactly
no_side_premium's claim, and this dataset covers ~61 settlement days where
the theory's own forward series covers 8.

WHAT THIS IS AND IS NOT (ticket 2026-09-01-side-split-on-series-bias-obs):

  * It is an OUT-OF-POPULATION replication of the SIDE-LEVEL direction
    claim. `obs` came from a board-wide sweep, not from
    `insider_bias.screen.screen()` (favorites 0.65-0.97, spread <= 0.07,
    volume >= 500, <= 14d to close). THEORY.md already names the
    side-level direction as the durable part and band structure as the
    part that moves between populations.
  * It is NOT no_side_premium's own tier-A backtest and must not be
    recorded as one. Nothing here is written to the ledger.
  * The window (2026-06-30 -> 2026-08-29) OVERLAPS the two fullcov runs
    the theory's cells were mined from, so the full-window figure is NOT
    out-of-sample. A pre-window split is reported alongside as the clean
    number.

Three data properties inherited from the source study, honoured here:

  * The decision point is anchored to SCHEDULED close, so the lookahead
    bug that flipped deadline_drift's sign cannot occur. `early_settled`
    is a robustness STRATUM, not a contaminant, on that study's
    pre-registered reading that a result driven only by the
    early-settling stratum is suspect.
  * `ask_24h`/`side_24h`/`won_24h` are the alternative decision point
    (24h before scheduled close), NULL where the market lived under 24h.
    A result present at only one decision point is a property of the
    timing choice.
  * The family is size-truncated toward LOWER-FREQUENCY series
    (`eligible_series` walks ascending by settled count), so this
    generalizes to those; the high-frequency tail is unmeasured.

Run: python studies/2026-09-01-side-split-60day-obs/measure.py <path-to-copy.db>
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from pathlib import Path

# The band the screen itself caps at. Using it is not a post-hoc cap: 0.97
# is insider_bias.screen's own upper bound, fixed long before this dataset
# existed, and it happens to exclude the 0.980-0.995 liquidity artifact
# (23% of the population realizing 0.801 -- a book with no offer, not a
# mispricing) by construction rather than by choice.
BAND_LO, BAND_HI = 0.90, 0.97

#: Everything closing before this is clear of the 2026-08-25 fullcov runs
#: the theory's cells were mined from.
OOS_BEFORE = "2026-08-20"


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def net(rows) -> float | None:
    """Day-level net edge in points: (win rate - mean ask) - mean fee."""
    if not rows:
        return None
    wr = sum(r["won"] for r in rows) / len(rows)
    ask = sum(r["ask"] for r in rows) / len(rows)
    fee = sum(fee_pts(r["ask"]) for r in rows) / len(rows)
    return (wr - ask) * 100 - fee


def day_stat(rows, min_rows_per_day: int = 1):
    """Day-clustered mean/SE. Days are close days; rows within a day are
    not independent draws (2026-08-27 settlement-day clustering study)."""
    by_day: dict[str, list] = {}
    for r in rows:
        by_day.setdefault(r["close_time"][:10], []).append(r)
    vals = [net(rs) for rs in by_day.values() if len(rs) >= min_rows_per_day]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    mean = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else None
    return {"n": len(rows), "days": len(vals), "mean": mean, "se": se,
            "t": (mean / se) if se else None,
            "pos": sum(v > 0 for v in vals)}


def show(label: str, s, width: int = 44) -> None:
    if s is None:
        print(f"  {label:{width}} --")
        return
    se = f"{s['se']:5.2f}" if s["se"] else "  -- "
    t = f"{s['t']:+5.2f}" if s["t"] is not None else "  -- "
    print(f"  {label:{width}} n={s['n']:<6} days={s['days']:<3} "
          f"mean={s['mean']:+7.2f}  SE={se}  t={t}  {s['pos']}/{s['days']}+")


def paired(rows):
    """Within-day NO minus YES. Retained for comparability with the
    theory's current headline -- but see the 2026-09-01 finding that this
    estimator IMPORTS the YES side's variance in this domain rather than
    cancelling a shared shock, because the two sides are different markets
    on different subjects."""
    by_day: dict[str, list] = {}
    for r in rows:
        by_day.setdefault(r["close_time"][:10], []).append(r)
    vals = []
    for rs in by_day.values():
        y = [r for r in rs if r["side"] == "yes"]
        n = [r for r in rs if r["side"] == "no"]
        if y and n:
            vals.append(net(n) - net(y))
    if len(vals) < 2:
        return None
    mean = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5
    return {"n": len(rows), "days": len(vals), "mean": mean, "se": se,
            "t": mean / se, "pos": sum(v > 0 for v in vals)}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path or not Path(path).exists():
        sys.exit("usage: measure.py <path to a COPY of collect.db>\n"
                 "Copy it first -- a peer session runs a multi-hour backfill "
                 "against the live file and a long read risks locking it.")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM obs")]

    days = len({r["close_time"][:10] for r in rows})
    print(f"COLLECTION STATE: {len(rows)} observations, "
          f"{len({r['series_ticker'] for r in rows})} series, {days} close days, "
          f"{min(r['close_time'] for r in rows)[:10]} -> "
          f"{max(r['close_time'] for r in rows)[:10]}")
    print("(the source study's one-run rule: a number belongs to the "
          "collection state that produced it)\n")

    band = [r for r in rows if BAND_LO <= r["ask"] < BAND_HI]
    print(f"=== 1. THE CELL: ask in [{BAND_LO}, {BAND_HI}) ===")
    for side in ("no", "yes"):
        show(f"{side.upper()} favorites",
             day_stat([r for r in band if r["side"] == side]))
    show("PAIRED NO-YES (see docstring)", paired(band))
    print()

    print("=== 2. SIDE x BAND, whole population ===")
    for lo, hi in ((0.50, 0.65), (0.65, 0.80), (0.80, 0.90),
                   (0.90, 0.97), (0.97, 0.98), (0.98, 1.01)):
        for side in ("no", "yes"):
            tag = "  <- ARTIFACT ZONE" if lo == 0.98 and side == "no" else ""
            show(f"{side.upper()} {lo:.2f}-{hi:.2f}{tag}",
                 day_stat([r for r in rows if r["side"] == side
                           and lo <= r["ask"] < hi]))
    print()

    print(f"=== 3. OUT-OF-SAMPLE SPLIT (cells mined from 2026-08-25 fullcov runs) ===")
    for label, pred in (
        (f"close < {OOS_BEFORE}  (clean of the mining window)",
         lambda r: r["close_time"][:10] < OOS_BEFORE),
        (f"close >= {OOS_BEFORE} (overlaps it)",
         lambda r: r["close_time"][:10] >= OOS_BEFORE),
    ):
        sub = [r for r in band if pred(r)]
        for side in ("no", "yes"):
            show(f"{side.upper()} | {label}",
                 day_stat([r for r in sub if r["side"] == side]), width=54)
    print()

    print("=== 4. ROBUSTNESS STRATUM: early vs on-time settlement ===")
    print("    (source study's pre-registered reading: a result driven only")
    print("     by the early-settling stratum is suspect)")
    for flag, label in ((0, "on-time"), (1, "early-settled")):
        for side in ("no", "yes"):
            show(f"{side.upper()} | {label}",
                 day_stat([r for r in band if r["side"] == side
                           and r["early_settled"] == flag]), width=54)
    print()

    print("=== 5. ROBUSTNESS: the alternative decision point (24h pre-close) ===")
    print("    (NULL where the market lived under 24h, so this is a subset)")
    alt = [{"close_time": r["close_time"], "side": r["side_24h"],
            "ask": r["ask_24h"], "won": r["won_24h"]}
           for r in rows if r["ask_24h"] is not None
           and BAND_LO <= r["ask_24h"] < BAND_HI]
    for side in ("no", "yes"):
        show(f"{side.upper()} favorites @24h",
             day_stat([r for r in alt if r["side"] == side]))
    print()

    print("=== 6. LIQUIDITY CONTROL (backfilled columns; still filling) ===")
    have = [r for r in band if r["spread"] is not None]
    print(f"    {len(have)} of {len(band)} cell rows carry spread/OI yet "
          f"({len(have)/max(len(band),1):.0%}) -- the backfill is running "
          f"under another session")
    for side in ("no", "yes"):
        show(f"{side.upper()} | spread known",
             day_stat([r for r in have if r["side"] == side]), width=54)
    for side in ("no", "yes"):
        show(f"{side.upper()} | spread<=0.07 AND open_interest>=500",
             day_stat([r for r in have if r["side"] == side
                       and (r["spread"] or 1) <= 0.07
                       and (r["open_interest"] or 0) >= 500]), width=54)

    print()
    print("=== 7. COMPOSITION CONTROL -- the one that decides this study ===")
    composition_control(rows)


def composition_control(rows) -> None:
    """The control that decides this study: same series, same close day.

    NO favorites outnumber YES roughly 5:2 here, and the two sides are
    largely DIFFERENT SERIES -- so a pooled NO-minus-YES gap can be a fact
    about which markets happen to be NO-favorite rather than about sides at
    all. Differencing within (series, close day) removes that entirely.

    This is the control calibration_harvest's gradient review needed (38%
    of its one-week step turned out to be composition). Here it is more
    than the whole effect: the pooled gap is +3.95 and this is negative.
    """
    import collections

    band = [r for r in rows if BAND_LO <= r["ask"] < BAND_HI]
    by_ser = collections.defaultdict(collections.Counter)
    for r in band:
        by_ser[r["series_ticker"]][r["side"]] += 1
    both = {s for s, cc in by_ser.items() if cc["yes"] >= 5 and cc["no"] >= 5}
    sub = [r for r in band if r["series_ticker"] in both]

    print(f"    {len(by_ser)} series in the cell; {len(both)} carry >= 5 rows "
          f"on BOTH sides ({len(sub)} rows)")
    for side in ("no", "yes"):
        show(f"{side.upper()} | both-sides series only",
             day_stat([r for r in sub if r["side"] == side]), width=54)

    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sub:
        cells[(r["series_ticker"], r["close_time"][:10])][r["side"]].append(r)
    pairs = [(k[0], k[1], net(v["no"]) - net(v["yes"]))
             for k, v in cells.items() if v["yes"] and v["no"]]

    by_day = collections.defaultdict(list)
    by_s = collections.defaultdict(list)
    for ser, day, x in pairs:
        by_day[day].append(x)
        by_s[ser].append(x)
    dayvals = [statistics.mean(v) for v in by_day.values()]
    servals = [statistics.mean(v) for v in by_s.values()]

    def line(label, vals):
        m = statistics.mean(vals)
        se = statistics.stdev(vals) / len(vals) ** 0.5
        print(f"    {label:34} k={len(vals):<4} mean={m:+6.2f}  SE={se:5.2f}  "
              f"t={m/se:+5.2f}")

    print(f"    within-series within-day pairs: {len(pairs)}")
    line("day-clustered", dayvals)
    line("series-equal-weighted", servals)
    print(f"    {'pair-equal-weighted':34} k={len(pairs):<4} "
          f"mean={statistics.mean([x for _, _, x in pairs]):+6.2f}")
    print(f"    series with a positive mean diff: "
          f"{sum(v > 0 for v in servals)}/{len(servals)}")


if __name__ == "__main__":
    main()
