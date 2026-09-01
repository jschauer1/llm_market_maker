"""Mine the 8-day side-asymmetry series for structure the pooled statistic hides.

The pooled paired statistic (compose.py) reads +2.91 +/- 5.51 over 8 close
days -- null. But no_side_premium's founding evidence was never "all NO
beats all YES": the two fullcov backtests measured PRICE-BAND cells (NO
favorites at 0.90+ underpriced +2.25 net; YES favorites 0.80-0.90
overpriced -3.89 net), and the theory's own two cells are defined on
bands. So the band split is the theory's pre-registered structure, not
post-hoc mining, and it is the first place to look.

Everything here is day-clustered: every figure is a mean over per-day
values, with the day-clustered SE, because the settlement-day study
measured a between-day swing wider than any effect claimed.

Run: python studies/2026-08-29-side-asymmetry-extension/slice.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DATA = Path(__file__).resolve().parent / "data"
MIN_SETTLED_FRACTION = 0.90

# The mention family, as insider_bias/families.py defines the population
# cell A draws from. Imported, never re-derived: an earlier draft of this
# file guessed the prefixes and silently disagreed with the theory.
from theories.insider_bias.families import is_mention_family    # noqa: E402


def fee_pts(price: float) -> float:
    return min(0.07 * price * (1.0 - price), 0.035) * 100.0


def series_of(ticker: str) -> str:
    return ticker.split("-", 1)[0]


def load_days():
    days = {}
    for path in sorted(DATA.glob("close-*.json")):
        d = json.loads(path.read_text())
        rows = [m for m in d["markets"] if m.get("result") in ("yes", "no")]
        if len(rows) / (d["n_population"] or 1) < MIN_SETTLED_FRACTION:
            continue
        days[d["close_day"]] = rows
    return days


def net(rs):
    if not rs:
        return None
    wr = sum(r["result"] == r["side"] for r in rs) / len(rs)
    ask = sum(r["ask"] for r in rs) / len(rs)
    fee = sum(fee_pts(r["ask"]) for r in rs) / len(rs)
    return (wr - ask) * 100 - fee


def day_stat(days, predicate, min_rows=1):
    """Day-clustered mean/SE of net edge over rows matching `predicate`."""
    vals, ns = [], 0
    for d in sorted(days):
        rs = [r for r in days[d] if predicate(r)]
        ns += len(rs)
        if len(rs) >= min_rows:
            v = net(rs)
            if v is not None:
                vals.append(v)
    if not vals:
        return None
    mean = statistics.mean(vals)
    se = (statistics.stdev(vals) / len(vals) ** 0.5) if len(vals) > 1 else None
    return {"n_rows": ns, "n_days": len(vals), "mean": mean, "se": se,
            "t": (mean / se) if se else None,
            "pos": sum(v > 0 for v in vals)}


def show(label, s):
    if s is None:
        print(f"  {label:34} --")
        return
    se = f"{s['se']:5.2f}" if s["se"] else "  -- "
    t = f"{s['t']:+5.2f}" if s["t"] else "  -- "
    print(f"  {label:34} n={s['n_rows']:<5} days={s['n_days']:<2} "
          f"mean={s['mean']:+7.2f}  SE={se}  t={t}  {s['pos']}/{s['n_days']}+")


BANDS = [(0.65, 0.80), (0.80, 0.90), (0.90, 0.97001)]


def main() -> None:
    days = load_days()
    print(f"{len(days)} complete close-days, "
          f"{sum(len(v) for v in days.values())} settled favorites\n")

    print("BY SIDE x PRICE BAND  (the two fullcov cells are marked)")
    for lo, hi in BANDS:
        for side in ("yes", "no"):
            tag = ""
            if side == "no" and lo == 0.90:
                tag = "   <- cell-A mechanism (+2.25 fullcov)"
            if side == "yes" and lo == 0.80:
                tag = "   <- cell-B mechanism (-3.89 fullcov)"
            show(f"{side.upper()} {lo:.2f}-{hi:.2f}{tag}",
                 day_stat(days, lambda r, s=side, lo=lo, hi=hi:
                          r["side"] == s and lo <= r["ask"] < hi))
    print()

    print("PAIRED NO-YES WITHIN BAND  (day-clustered; thesis says > 0)")
    for lo, hi in BANDS:
        vals = []
        rows = 0
        for d in sorted(days):
            y = [r for r in days[d]
                 if r["side"] == "yes" and lo <= r["ask"] < hi]
            n = [r for r in days[d]
                 if r["side"] == "no" and lo <= r["ask"] < hi]
            rows += len(y) + len(n)
            if y and n:
                vals.append(net(n) - net(y))
        if len(vals) > 1:
            m = statistics.mean(vals)
            se = statistics.stdev(vals) / len(vals) ** 0.5
            print(f"  {lo:.2f}-{hi:.2f}  n={rows:<5} days={len(vals):<2} "
                  f"mean={m:+7.2f}  SE={se:5.2f}  t={m/se:+5.2f}  "
                  f"{sum(v>0 for v in vals)}/{len(vals)}+")
        else:
            print(f"  {lo:.2f}-{hi:.2f}  n={rows:<5} days={len(vals)} "
                  f"-- too few paired days")
    print()

    print("BY SIDE, MENTION FAMILY vs REST  (cell A is mention-only)")
    def is_mention(r):
        return is_mention_family(series_of(r["ticker"]))
    for side in ("yes", "no"):
        show(f"{side.upper()} mention-family",
             day_stat(days, lambda r, s=side: r["side"] == s and is_mention(r)))
        show(f"{side.upper()} rest",
             day_stat(days, lambda r, s=side: r["side"] == s and not is_mention(r)))
    print()

    print("HOW MUCH DATA WOULD SETTLE THE POOLED CLAIM")
    vals = []
    for d in sorted(days):
        y = [r for r in days[d] if r["side"] == "yes"]
        n = [r for r in days[d] if r["side"] == "no"]
        if y and n:
            vals.append(net(n) - net(y))
    sd = statistics.stdev(vals)
    print(f"  paired NO-YES, all bands : between-day SD {sd:5.2f} pts "
          f"-> {(2.8*sd/2.0)**2:6.0f} days to detect +2.0")

    # The comparison that matters: the pairing was adopted to cancel a
    # common day shock, but it also imports the OTHER side's variance. For
    # the band that carries the claim, the single-side estimator is far
    # tighter, and a tighter estimator is a shorter wait.
    for label, pred in (
        ("NO 0.90-0.97, single side",
         lambda r: r["side"] == "no" and r["ask"] >= 0.90),
        ("NO all bands,  single side", lambda r: r["side"] == "no"),
        ("YES all bands, single side", lambda r: r["side"] == "yes"),
    ):
        vs = [net([r for r in days[d] if pred(r)]) for d in sorted(days)
              if [r for r in days[d] if pred(r)]]
        if len(vs) > 1:
            sd2 = statistics.stdev(vs)
            print(f"  {label}: between-day SD {sd2:5.2f} pts "
                  f"-> {(2.8*sd2/2.0)**2:6.0f} days to detect +2.0")


if __name__ == "__main__":
    main()
