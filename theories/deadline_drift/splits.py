"""Stability splits: by close date, and by allowlist membership.

Two questions a single pooled number cannot answer.

**Is it one bad fortnight?** Split the capture window in half by close
date. Both halves positive is weak evidence the effect is not a regime
artifact; one half carrying it all would be a warning.

**Which population is it in?** This is the one that matters here. The
effect is entirely OUTSIDE the audited allowlist (-1.0 vs +9.6), and
inspecting the contributors says why: the non-allowlist side is one-off
newsy questions priced $0.25-0.55 that did not happen, while the
allowlist is recurring families trading at 0.04-0.06 and pricing about
right. See THEORY.md's DD-2 and NOTES.md 2026-09-01.

    python -m theories.deadline_drift.splits
"""
import datetime as dt
from theories.deadline_drift import hazard as H
from theories.deadline_drift.bootstrap import event_obs, gap, boot

anchors, candles, rules = H.load()
ev, vol = H.event_map(), H.market_volume()
hazard = [tk for tk in candles if H.stratum(rules.get(tk, "")) == "hazard"]

def close(tk):
    c = (anchors.get(tk) or {}).get("close_time")
    return dt.datetime.fromisoformat(c.replace("Z", "+00:00")) if c else None

# Split on the median close among markets that actually CONTRIBUTE an
# observation, not among all hazard markets. Most hazard markets never
# enter the cell (wrong price band, or no candle inside 21 days of the
# deadline), so a median over all of them puts the split in the wrong
# place and produces lopsided arms that look like a median split and are
# not -- it read 32/68 before this was fixed.
contributes = {tk for tk in hazard
               if vol.get(tk, 0.0) >= 100.0
               and (anchors.get(tk) or {}).get("deadline")
               and H.observe(candles[tk], anchors[tk], side="bid",
                             entry="first")}
dated = sorted((close(tk), tk) for tk in contributes if close(tk))
mid = dated[len(dated)//2][0]
early = [tk for d, tk in dated if d < mid]
late  = [tk for d, tk in dated if d >= mid]

print(f"hazard markets with a close date: {len(dated)}")
print(f"split at {mid:%Y-%m-%d}: early {len(early)}, late {len(late)}\n")
print("{:<34}{:>5}{:>8}{:>20}{:>9}".format("cut","evts","gap","95% CI","P(<=0)"))
print("-"*76)
for label, tks in (("all hazard, bid", hazard),
                   (f"  closes before {mid:%b %d}", early),
                   (f"  closes from {mid:%b %d}", late),
                   ("  allowlist series only",
                    [tk for tk in hazard
                     if H.in_allowlist((anchors.get(tk) or {}).get("series"))]),
                   ("  NON-allowlist series only",
                    [tk for tk in hazard
                     if not H.in_allowlist((anchors.get(tk) or {}).get("series"))])):
    o = event_obs(anchors, candles, ev, vol, tks, side="bid", entry="first")
    if len(o) < 8:
        print("{:<34}{:>5}   (too few)".format(label, len(o))); continue
    lo, hi, p = boot(o)
    print("{:<34}{:>5}{:>+8.1f}   [{:+6.1f},{:+6.1f}]{:>9.3f}".format(
        label, len(o), gap(o), lo, hi, p))
