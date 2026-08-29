"""Reproduce the hazard estimate from disk, under BOTH time anchors.

The whole point of keeping both is that the difference between them is the
correction recorded in NOTES.md on 2026-08-29. Run it and the retraction is
a number you can see rather than a claim you have to trust:

    python -m theories.deadline_drift.hazard

**Why "days to close" is wrong.** On a "does X happen by D" market, actual
close is a FUNCTION OF THE OUTCOME -- a NO market runs to its deadline, a
YES market stops the moment the event fires (measured: median 210 days
early, 32/34). Anchoring on it puts the two arms on different clocks and
measures "prices rise before events happen".

**Why dropping early-YES markets is not survivorship bias.** Conditioning
on "still open at deadline − h" is the hazard-analysis *at-risk set*: a
market that already resolved YES is not available to bet at that moment, so
excluding it is exactly what makes P(YES) the right conditional. The number
this produces answers "given I can still buy NO here, how often does YES
come in?", which is the only question a bettor can act on.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

DATA = Path(__file__).parent / "data"

LATE_WINDOW_DAYS = 21
ENTRY_BAND = (0.05, 0.60)
FEE_RATE = 0.07


def load() -> tuple[dict, dict]:
    anchors = json.loads((DATA / "anchors.json").read_text(encoding="utf-8"))
    candles = json.loads((DATA / "candles.json").read_text(encoding="utf-8"))
    return anchors, {k: v for k, v in candles.items() if isinstance(v, list)}


def estimate(anchors: dict, candles: dict, *, anchor: str) -> dict:
    """Pooled late-window estimate, clustered by market.

    `anchor` is "days_to_deadline" (correct) or "days_to_close"
    (contaminated -- kept so the difference is reproducible).
    """
    lo, hi = ENTRY_BAND
    per_market: dict[str, tuple[float, int, bool]] = {}
    for tk, rows in candles.items():
        a = anchors.get(tk)
        if not a:
            continue
        yes = a["result"] == "yes"
        for r in rows:
            d, ask = r[anchor], r["yes_ask"]
            if not 0 <= d <= LATE_WINDOW_DAYS or not lo <= ask <= hi:
                continue
            s, n, _ = per_market.get(tk, (0.0, 0, yes))
            per_market[tk] = (s + ask, n + 1, yes)
    n = len(per_market)
    if not n:
        return {"markets": 0}
    mean_ask = sum(s / c for s, c, _ in per_market.values()) / n
    p_yes = sum(1 for _, _, y in per_market.values() if y) / n
    gap = (mean_ask - p_yes) * 100.0
    se = math.sqrt(p_yes * (1 - p_yes) / n) * 100.0
    no_entry = 1.0 - mean_ask
    fee = FEE_RATE * no_entry * (1 - no_entry) * 100.0
    return {"markets": n, "mean_ask": mean_ask, "p_yes": p_yes,
            "gap_pts": gap, "se_pts": se, "z": gap / se if se else float("nan"),
            "fee_pts": fee, "net_pts": gap - fee,
            "yes_n": sum(1 for _, _, y in per_market.values() if y)}


def main() -> None:
    anchors, candles = load()
    early = [a["closed_early_days"] for a in anchors.values()
             if a.get("closed_early_days") is not None]
    by_res = {"yes": [], "no": []}
    for a in anchors.values():
        if a.get("closed_early_days") is not None:
            by_res[a["result"]].append(a["closed_early_days"])
    print(f"{len(anchors)} settled markets, {len(candles)} with candles\n")
    print("early settlement (deadline - actual close), days:")
    for k, v in by_res.items():
        if v:
            # statistics.median, not v[len(v)//2]: for even n the latter
            # returns the upper-middle element, not the median. That bug
            # printed 212.9 against the data's true 209.6 and was caught in
            # review -- a reproducible script is only worth as much as its
            # arithmetic.
            print(f"  {k.upper():>4} n={len(v):>3}  median {statistics.median(v):7.1f}"
                  f"   closed >3d early: {sum(1 for x in v if x > 3)}/{len(v)}")
    print()
    hdr = f"{'anchor':<20}{'mkts':>6}{'mean_ask':>10}{'P(YES)':>9}{'gap':>9}{'SE':>7}{'z':>7}{'net':>8}"
    print(hdr); print("-" * len(hdr))
    for anchor, label in (("days_to_close", "actual close (BAD)"),
                          ("days_to_deadline", "stated deadline")):
        r = estimate(anchors, candles, anchor=anchor)
        print(f"{label:<20}{r['markets']:>6}{r['mean_ask']:>10.3f}"
              f"{r['p_yes']:>9.3f}{r['gap_pts']:>+9.1f}{r['se_pts']:>7.1f}"
              f"{r['z']:>7.2f}{r['net_pts']:>+8.1f}")
    r = estimate(anchors, candles, anchor="days_to_deadline")
    print(f"\ncorrected estimate rests on {r['yes_n']} YES outcomes of "
          f"{r['markets']} markets -- far too few to reject zero.")


if __name__ == "__main__":
    main()
