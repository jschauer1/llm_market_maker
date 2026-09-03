"""Mining pass on the DD-3 arms.  Run: python -m theories.deadline_drift.mine_arms

 ALL cuts declared before running, ALL
reported -- including the ones that look bad -- so the multiplicity is
visible rather than hidden by selective reporting.

Nothing here is a test. The aggregate is underpowered; every cell below is
smaller than the aggregate and therefore more underpowered. This exists to
answer "is the negative concentrated somewhere, or is it everywhere", which
is a question about MECHANISM, and to satisfy go-theory's requirement that
settled data be mined before a theory is called exhausted.
"""
import math

from theories.deadline_drift import hazard, backtest as bt

anchors, candles, rules = hazard.load()
events = hazard.event_map()
seen_arm, unseen_arm, _part = bt.arms(anchors, candles, rules, events)
vol = hazard.market_volume()

KW = dict(events=events, side="bid", entry="first", weight="event")


def est(tks):
    return hazard.estimate(anchors, candles, tickers=tks, **KW)


def row(label, tks, floor=5):
    r = est(tks)
    if not r or r.get("markets", 0) < floor:
        print(f"  {label:<34}{(r or {}).get('markets', 0):>5}   (too few)")
        return None
    lo = r["net_pts"] - 1.96 * r["se_cl_pts"]
    hi = r["net_pts"] + 1.96 * r["se_cl_pts"]
    print(f"  {label:<34}{r['n_clusters']:>5}{r['mean_p']:>8.3f}"
          f"{r['p_yes']:>8.3f}{r['net_pts']:>+8.1f}   [{lo:+6.1f},{hi:+6.1f}]")
    return r


def entry_row(tk):
    a, rows = anchors.get(tk), candles.get(tk)
    if not a or not rows or a.get("deadline") is None:
        return None
    got = hazard.observe(rows, a, side="bid", entry="first", return_row=True)
    return got[2] if got else None


def hdr(title):
    print(f"\n{title}")
    print(f"  {'cut':<34}{'evts':>5}{'price':>8}{'P(YES)':>8}{'net':>8}"
          f"   {'95% CI':>15}")
    print("  " + "-" * 74)


CUTS = []          # (name, predicate) -- declared here, all reported below

# 1. price band at entry
for lo, hi in ((0.05, 0.15), (0.15, 0.30), (0.30, 0.60)):
    CUTS.append((f"price [{lo:.2f},{hi:.2f})",
                 lambda tk, lo=lo, hi=hi: (
                     (r := entry_row(tk)) is not None
                     and lo <= r["yes_ask"] < hi)))

# 2. days to the stated deadline at entry
for lo, hi in ((0, 7), (7, 14), (14, 22)):
    CUTS.append((f"days-to-deadline [{lo},{hi})",
                 lambda tk, lo=lo, hi=hi: (
                     (r := entry_row(tk)) is not None
                     and lo <= r["days_to_deadline"] < hi)))

# 3. liquidity
for lo in (100, 1000, 5000):
    CUTS.append((f"lifetime volume >= {lo}",
                 lambda tk, lo=lo: vol.get(tk, 0.0) >= lo))

# 4. spread at entry -- the artifact test that convicted the yes_ask view
for mx in (2, 4, 10):
    CUTS.append((f"spread <= {mx}pts",
                 lambda tk, mx=mx: (
                     (r := entry_row(tk)) is not None
                     and r.get("yes_bid") is not None
                     and (r["yes_ask"] - r["yes_bid"]) * 100 <= mx)))

# 5. single-leg events vs multi-leg -- a one-question market vs a ladder
CUTS.append(("single-leg event",
             lambda tk: sum(1 for t in anchors
                            if events.get(t) == events.get(tk)) == 1))
CUTS.append(("multi-leg event",
             lambda tk: sum(1 for t in anchors
                            if events.get(t) == events.get(tk)) > 1))

for arm_name, arm in (("UNSEEN (the test arm)", unseen_arm),
                      ("SEEN (control)", seen_arm)):
    hdr(f"=== {arm_name} -- {len(CUTS)} declared cuts, all reported ===")
    row("ALL", arm)
    print("  " + "-" * 74)
    for name, pred in CUTS:
        row(name, [tk for tk in arm if pred(tk)])

print(f"\n{len(CUTS)} cuts x 2 arms = {len(CUTS) * 2} comparisons. At the "
      f"5% level ~{len(CUTS) * 2 * 0.05:.1f} would clear by chance alone.")
print("The aggregate is underpowered at 73 clusters; every cell above is "
      "smaller. Nothing here is a test, and nothing here is registrable "
      "without a forward or out-of-sample pass of its own.")
