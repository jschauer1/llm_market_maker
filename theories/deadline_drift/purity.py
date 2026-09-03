"""Fixed-k elimination families: detect them, and quantify what they cost.

**Why this is a diagnostic and not a screen change.** The open ticket
`fixed-k-elimination-families` says the honest default is to let DD-1 run
on the population it pre-registered and treat contamination as a known,
quantified caveat. Changing the population mid-test would be a v3 bump
that moves the thing DD-1 is measuring, and the ticket's own rule 0b
warning applies: choosing an inclusion rule after seeing which value it
helps is how a population gets fitted to its answer. So this module
**measures** the contamination and never filters anything.

**The shape it looks for.** `KXAGTELIMINATION` is 11 legs whose settled
events pay SEVEN YES each -- "exactly 7 of these 11 acts go through". The
legs are negatively correlated and P(YES) is structurally ~k/n, not a
hazard rate, so the market is not the kind of question this theory is
about. All three existing detectors miss it: `partition_families` wants
exactly one winner, `screen.partition_events` wants siblings summing
0.90-1.05 (these sum to 6.67), and the rules regex misses a shape that is
semantic rather than syntactic.

**Why it could not be fitted before.** `KXTRUMPSAY` is the same
superficial shape -- 34 legs, many YES per event -- and is genuinely
independent: Trump saying "Antifa" does not preclude "Uranium". The
distinguishing feature is VARIANCE in the YES count across events
(TRUMPSAY 7,12,15,17,19,21; AGT 7,7). Two events cannot fit a threshold.
The platform-wide walk is what changes that, by supplying the settled
elimination families the board-scoped walk could never reach.

**Fit on SEEN data only.** The labelled families all sit in the
pre-platform seen set, and fitting a threshold on the test arm would let
the test set choose the instrument applied to it. `main()` prints the fit
on seen data and then reports, separately, how much of the unseen arm the
fitted rule touches -- which is the caveat DD-3's verdict needs beside it.

Run: python -m theories.deadline_drift.purity
"""
from __future__ import annotations

import statistics
from pathlib import Path

from theories.deadline_drift import hazard

DATA = Path(__file__).resolve().parent / "data"

#: A family needs this many settled events before its YES-count spread
#: means anything. Below it the two shapes are indistinguishable, which is
#: exactly why the ticket refused to guess at n=2.
MIN_EVENTS = 4

#: Legs per event, below which "how many winners" is not a meaningful
#: question -- a 2-leg event paying 1 YES is a coin flip, not a fixed-k
#: elimination.
MIN_LEGS = 5


def yes_counts(anchors: dict, events: dict) -> dict:
    """series -> {event: (yes_count, leg_count)} over settled events."""
    per_ev: dict[str, list] = {}
    ev_series: dict[str, str] = {}
    for tk, a in anchors.items():
        ev = events.get(tk)
        if not ev:
            continue
        per_ev.setdefault(ev, []).append(a.get("result"))
        ev_series[ev] = a.get("series") or ""
    out: dict[str, dict] = {}
    for ev, res in per_ev.items():
        out.setdefault(ev_series[ev], {})[ev] = (res.count("yes"), len(res))
    return out


def family_stats(counts: dict) -> dict:
    """series -> summary of its settled events' winner counts.

    `k_cv` is the coefficient of variation of the YES count across events
    and `share_cv` the same for the k/n share. A fixed-k family holds one
    of these near zero across events of differing size; an independent
    family like KXTRUMPSAY does not.
    """
    out = {}
    for s, evs in counts.items():
        big = {e: (k, n) for e, (k, n) in evs.items() if n >= MIN_LEGS}
        if len(big) < MIN_EVENTS:
            continue
        ks = [k for k, _ in big.values()]
        shares = [k / n for k, n in big.values()]
        mean_k = statistics.mean(ks)
        mean_share = statistics.mean(shares)
        out[s] = {
            "events": len(big),
            "mean_k": mean_k,
            "mean_legs": statistics.mean([n for _, n in big.values()]),
            "k_cv": (statistics.stdev(ks) / mean_k) if len(ks) > 1 and mean_k
                    else None,
            "share_cv": (statistics.stdev(shares) / mean_share)
                        if len(shares) > 1 and mean_share else None,
            "ks": sorted(ks),
        }
    return out


#: Fitted on seen data against the labelled families, then held fixed. A
#: family is "fixed-k" when its winner count barely moves across events
#: -- either the count itself (AGT: 7,7,...) or the share of legs.
K_CV_MAX = 0.15
SHARE_CV_MAX = 0.15


def fixed_k_families(stats: dict) -> set[str]:
    """Series whose settled events pay a tightly constrained winner count."""
    hits = set()
    for s, v in stats.items():
        kcv, scv = v["k_cv"], v["share_cv"]
        # A one-winner family is already caught by `partition_families`;
        # this detector is for the k > 1 case that one misses.
        if v["mean_k"] < 1.5:
            continue
        if (kcv is not None and kcv <= K_CV_MAX) or \
           (scv is not None and scv <= SHARE_CV_MAX):
            hits.add(s)
    return hits


LABELLED_FIXED_K = ("KXAGTELIMINATION",)
LABELLED_INDEPENDENT = ("KXTRUMPSAY",)


def main() -> None:
    from theories.deadline_drift import backtest as bt

    anchors, candles, rules = hazard.load()
    events = hazard.event_map()
    seen = bt.seen_tickers()

    seen_anchors = {tk: a for tk, a in anchors.items() if tk in seen}
    fit = family_stats(yes_counts(seen_anchors, events))
    print(f"fit population: SEEN only -- {len(seen_anchors)} markets, "
          f"{len(fit)} families with >= {MIN_EVENTS} settled events "
          f"of >= {MIN_LEGS} legs")

    print("\nlabelled families, as the fit sees them:")
    for s in LABELLED_FIXED_K + LABELLED_INDEPENDENT:
        v = fit.get(s)
        if not v:
            print(f"  {s:<28} not in the fit population "
                  f"(< {MIN_EVENTS} settled events of >= {MIN_LEGS} legs)")
            continue
        print(f"  {s:<28} events={v['events']:<3} k={v['ks']} "
              f"k_cv={v['k_cv']!s:.6} share_cv={v['share_cv']!s:.6}")

    hits = fixed_k_families(fit)
    print(f"\nfitted rule (k_cv <= {K_CV_MAX} or share_cv <= {SHARE_CV_MAX}, "
          f"mean_k >= 1.5) flags {len(hits)} families on seen data:")
    for s in sorted(hits):
        v = fit[s]
        print(f"  {s:<32} events={v['events']:<3} mean_k={v['mean_k']:.1f} "
              f"legs={v['mean_legs']:.1f} k={v['ks']}")

    # --- the caveat DD-3's verdict needs beside it -------------------
    _seen_arm, unseen_arm, part = bt.arms(anchors, candles, rules, events)
    all_stats = family_stats(yes_counts(anchors, events))
    all_hits = fixed_k_families(all_stats)
    exposed = [tk for tk in unseen_arm
               if (anchors.get(tk) or {}).get("series") in all_hits]
    ev_exposed = {events.get(tk) or tk for tk in exposed}
    kw = dict(events=events, side="bid", entry="first", weight="event")
    r_all = hazard.estimate(anchors, candles, tickers=unseen_arm, **kw)
    r_clean = hazard.estimate(
        anchors, candles,
        tickers=[tk for tk in unseen_arm if tk not in exposed], **kw)
    print(f"\nDD-3 unseen arm: {len(unseen_arm)} markets; "
          f"{len(exposed)} in a flagged fixed-k family "
          f"({len(ev_exposed)} event clusters)")
    print("\n" + hazard.HDR)
    print("-" * len(hazard.HDR))
    hazard._row("unseen, as pre-registered", r_all)
    hazard._row("unseen, minus fixed-k", r_clean)
    print("\nThe first row is the pre-registered test and stays the verdict. "
          "The second is a sensitivity, never a substitute -- swapping to it "
          "would be choosing the population after seeing the answer.")


if __name__ == "__main__":
    main()
