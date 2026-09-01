"""Cluster bootstrap over EVENTS, with liquidity cuts.

`hazard.py` reports a normal-approximation z. On this population that is
not a p-value: the gap is a mean of `price - outcome` over event clusters
where most outcomes are 0 and a handful are 1, so the sampling
distribution is skewed and small-n normal theory flatters it. This
resamples the EVENTS themselves, which makes no distributional assumption
and keeps the clustering the SE was only approximating.

It also exists to test one specific thing. **A gap that is really the
bid-ask spread must SHRINK as the spread filter tightens** -- that is
exactly what happened to this theory's `yes_ask` view, and it is what
identified that view as an artifact. A gap that survives, or grows, under
tightening spreads is not a spread artifact.

    python -m theories.deadline_drift.bootstrap
"""
from __future__ import annotations

import random

from theories.deadline_drift import hazard as H

#: The screen's own liquidity floor, in lifetime volume.
MIN_VOLUME = 100.0


def event_obs(anchors, candles, ev, vol, tks, *, minvol=MIN_VOLUME, **kw):
    """One observation per EVENT: mean price, mean outcome over its legs.

    Event, not market, is the independent unit. A 17-leg "which
    houseguest" ladder and a 7-leg date ladder are one question each, and
    market-weighting lets a single event dominate in proportion to how
    finely Kalshi chose to slice it.
    """
    per = {}
    for tk in tks:
        if vol.get(tk, 0.0) < minvol:
            continue
        a = anchors.get(tk)
        if not a or a.get("deadline") is None:
            continue
        got = H.observe(candles[tk], a, **kw)
        if got:
            per.setdefault(ev.get(tk) or tk, []).append(got)
    return [(sum(p for p, _ in v) / len(v),
             sum(1 for _, y in v if y) / len(v))
            for v in per.values()]


def gap(obs) -> float:
    n = len(obs)
    return (sum(p for p, _ in obs) / n - sum(y for _, y in obs) / n) * 100.0


def boot(obs, *, draws=20000, seed=7):
    """-> (ci_lo, ci_hi, P(gap <= 0)) resampling events with replacement."""
    rnd = random.Random(seed)
    n = len(obs)
    out = sorted(gap([obs[rnd.randrange(n)] for _ in range(n)])
                 for _ in range(draws))
    return (out[int(0.025 * draws)], out[int(0.975 * draws)],
            sum(1 for x in out if x <= 0) / draws)


def main() -> None:
    anchors, candles, rules = H.load()
    ev, vol = H.event_map(), H.market_volume()
    hazard = [tk for tk in candles if H.stratum(rules.get(tk, "")) == "hazard"]
    allow = [tk for tk in candles
             if H.in_allowlist((anchors.get(tk) or {}).get("series"))]
    part = H.partition_families(anchors, ev)
    clean = [tk for tk in hazard
             if (anchors.get(tk) or {}).get("series") not in part]

    print("event-clustered bootstrap, entry=first, lifetime volume >= 100")
    print("{:<36}{:>5}{:>8}{:>20}{:>9}".format(
        "cut", "evts", "gap", "95% CI", "P(<=0)"))
    print("-" * 78)
    cuts = [
        ("ALLOWLIST (pre-registered), bid", allow, {"side": "bid"}),
        ("ALLOWLIST, ask (the old view)", allow, {"side": "ask"}),
        ("wide hazard, bid", hazard, {"side": "bid"}),
        ("wide hazard, ask (the old view)", hazard, {"side": "ask"}),
        ("  bid, spread<=6pts", hazard, {"side": "bid", "max_spread": 6}),
        ("  bid, spread<=4pts", hazard, {"side": "bid", "max_spread": 4}),
        ("  bid, spread<=2pts", hazard, {"side": "bid", "max_spread": 2}),
        ("  ask, spread<=4pts", hazard, {"side": "ask", "max_spread": 4}),
        ("  bid, minus partition families", clean, {"side": "bid"}),
        ("  bid, minus part., spread<=4", clean,
         {"side": "bid", "max_spread": 4}),
        ("  bid, open interest>=100", hazard, {"side": "bid", "min_oi": 100}),
    ]
    for label, tks, kw in cuts:
        obs = event_obs(anchors, candles, ev, vol, tks, entry="first", **kw)
        if len(obs) < 8:
            print("{:<36}{:>5}   (too few)".format(label, len(obs)))
            continue
        lo, hi, p = boot(obs)
        print("{:<36}{:>5}{:>+8.1f}   [{:+6.1f},{:+6.1f}]{:>9.3f}".format(
            label, len(obs), gap(obs), lo, hi, p))


if __name__ == "__main__":
    main()
