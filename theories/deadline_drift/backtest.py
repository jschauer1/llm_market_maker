"""DD-3 — replay the pre-registered cell on data the population choice never saw.

Pre-registration: `THEORY.md`, "DD-3, a replication on contemporaneous data
the population choice never saw", committed at af0e569 *before* the capture
that produces this data had finished. Read it before reading any number
printed here.

**What makes this out-of-sample.** `collect_settled`'s walk took its series
list from the live board, so it reached a series only while that series
still had something trading. The 2026-09-01 population choice was made on
exactly the 1,908 markets that walk had found. `data/preplatform_seen.json`
freezes that ticker set; anything absent from it comes from a series the
choice never saw, and is therefore a genuine test set — contemporaneous
rather than forward, so it controls for **selection** and for nothing about
**regime**.

**Not a reimplementation.** Every number here comes from `hazard.estimate`
with `side="bid", entry="first"`, the same call `hazard.main` labels "THE
PRE-REGISTERED CELL". This module only chooses which tickers go in.

**One pre-specified choice, fixed before any output was seen** (and
committed with the file, so the ordering is checkable): `partition_families`
is derived from **seen data only**. It is a function of settled *outcomes*,
so recomputing it over the test set would let test outcomes define the test
population — mild leakage, but leakage. The full-store variant is printed
underneath as a sensitivity, never as the headline.

**DD-4 and DD-5 live here too**, added 2026-09-03 while the completing
sweep was still walking and before any number from it had been printed.
Both are specified in THEORY.md under "DD-4 and DD-5, written 2026-09-02
at ~50% capture"; this module only implements the population split each
one names.

Run: python -m theories.deadline_drift.backtest          # DD-3
     python -m theories.deadline_drift.backtest --dd4    # holdout
     python -m theories.deadline_drift.backtest --dd5    # one-off contrast
     python -m theories.deadline_drift.backtest --all
"""
from __future__ import annotations

import json
from pathlib import Path

from theories.deadline_drift import hazard

DATA = Path(__file__).resolve().parent / "data"

#: DD-3's bar, from THEORY.md. Confirmation needs BOTH; below the cluster
#: floor the run settles nothing in either direction.
NET_BAR = 2.0
CLUSTER_FLOOR = 80

#: DD-5's bar, from THEORY.md: the CONTRAST net(one-off) - net(recurring)
#: must reach +3 with a CI excluding zero, and the one-off arm must be
#: positive on its own. Its underpowered floor is per-arm, not pooled.
DD5_CONTRAST_BAR = 3.0
DD5_ARM_FLOOR = 30

#: DD-2's split, restated here rather than imported from `population.py`,
#: because that module's answer is rebuilt from the WHOLE store after each
#: walk -- using it would let the test period's own settlements define the
#: test's split, which THEORY.md forbids in as many words.
RECURRING_MIN_EVENTS = 3


def peeked_tickers() -> set[str]:
    d = json.loads((DATA / "dd3_peeked.json").read_text())
    return set(d["tickers"])


def seen_tickers() -> set[str]:
    d = json.loads((DATA / "preplatform_seen.json").read_text())
    return set(d["tickers"])


def arms(anchors, candles, rules, events):
    """(seen, unseen, part) for the pre-registered population.

    The stratum is built exactly as `hazard.main` builds it: over `candles`
    keys, classifying `rules[ticker]`. Iterating `anchors` instead would
    silently admit markets with no candle series, which `estimate` then
    drops -- same answer, but the printed population size would be a
    number this theory never screens on.
    """
    seen = seen_tickers()
    vol = hazard.market_volume()
    liquid_haz = [tk for tk in candles
                  if hazard.stratum(rules.get(tk, "")) == "hazard"
                  and vol.get(tk, 0.0) >= 100.0]
    # Pre-specified: exclusions derived from SEEN data only.
    seen_anchors = {tk: a for tk, a in anchors.items() if tk in seen}
    part = hazard.partition_families(seen_anchors, events)
    clean = [tk for tk in liquid_haz
             if (anchors.get(tk) or {}).get("series") not in part]
    return ([tk for tk in clean if tk in seen],
            [tk for tk in clean if tk not in seen], part)


def _boot_line(anchors, candles, events, tickers, label) -> None:
    """An event-clustered BOOTSTRAP interval, printed beside the verdict.

    **Robustness, never the bar.** The pre-registered rule is the
    normal-approximation CI computed above, because that is what this file
    contained when it was committed before the data existed, and swapping
    estimators after seeing an answer is re-specifying the test.

    It is worth printing anyway: every in-sample number this theory has
    published (+4.6, CI [+1.0, +8.0]) came from `bootstrap.py`, and
    `bootstrap.py` exists because normal theory flatters a mean of
    `price - outcome` where most outcomes are 0 and a handful are 1. So
    the two intervals disagreeing is itself information, and comparing
    DD-3 against the in-sample figure is only like-for-like on this one.

    The interval is on the GROSS gap; the fee is a deterministic function
    of the mean price, so the net interval is this one shifted down by it.
    """
    from theories.deadline_drift import bootstrap as B

    vol = hazard.market_volume()
    obs = B.event_obs(anchors, candles, events, vol, tickers,
                      side="bid", entry="first")
    if len(obs) < 5:
        print(f"{label}: too few events to bootstrap")
        return
    lo, hi, p0 = B.boot(obs)
    r = hazard.estimate(anchors, candles, tickers=tickers, events=events,
                        side="bid", entry="first", weight="event")
    fee = r["fee_pts"]
    print(f"{label}: gross gap {B.gap(obs):+.2f}, bootstrap 95% CI "
          f"[{lo:+.2f}, {hi:+.2f}], P(gap<=0)={p0:.3f}   "
          f"-> net CI [{lo - fee:+.2f}, {hi - fee:+.2f}] after a "
          f"{fee:.2f}pt fee")


def main() -> None:
    anchors, candles, rules = hazard.load()
    events = hazard.event_map()
    seen = seen_tickers()
    print(f"store: {len(anchors)} markets;  frozen seen set: {len(seen)};  "
          f"new since freeze: {len(set(anchors) - seen)}")

    seen_arm, unseen_arm, part = arms(anchors, candles, rules, events)
    print(f"pre-registered population -> seen {len(seen_arm)}, "
          f"unseen {len(unseen_arm)}  (partition families from seen: {len(part)})")

    print("\n" + hazard.HDR)
    print("-" * len(hazard.HDR))
    kw = dict(events=events, side="bid", entry="first", weight="event")
    r_unseen = hazard.estimate(anchors, candles, tickers=unseen_arm, **kw)
    r_seen = hazard.estimate(anchors, candles, tickers=seen_arm, **kw)
    hazard._row("DD-3 UNSEEN (the test)", r_unseen)
    hazard._row("seen (control, descriptive)", r_seen)

    print("\n=== DD-3 VERDICT (bar fixed in THEORY.md before any of this ran) ===")
    if not r_unseen or r_unseen.get("markets", 0) == 0:
        print("NO DATA — the unseen arm is empty.")
        return
    net = r_unseen["net_pts"]
    ncl = r_unseen["n_clusters"]
    lo = net - 1.96 * r_unseen["se_cl_pts"]
    hi = net + 1.96 * r_unseen["se_cl_pts"]
    print(f"net {net:+.2f} pts, 95% CI [{lo:+.2f}, {hi:+.2f}], "
          f"{ncl} event clusters")
    if ncl < CLUSTER_FLOOR:
        print(f"UNDERPOWERED — {ncl} clusters is below the pre-registered "
              f"floor of {CLUSTER_FLOOR}. Settles nothing in either direction.")
    elif net >= NET_BAR and lo > 0:
        print(f"CONFIRMED — net >= +{NET_BAR} and the 95% CI excludes zero.")
    else:
        print(f"FAILED — needs net >= +{NET_BAR} with a CI excluding zero.")

    print("\n--- robustness, not the bar ---")
    _boot_line(anchors, candles, events, unseen_arm, "DD-3 unseen")
    _boot_line(anchors, candles, events, seen_arm, "seen control")


# ---------------------------------------------------------------- DD-4


def dd4() -> None:
    """DD-3's bar, on the unseen tickers captured AFTER the peek freeze.

    The peeked 509 are spent for the aggregate statistic -- they were
    computed and reported at ~45% capture -- so this is the only part of
    the unseen arm that has never been looked at in aggregate.

    Read it with THEORY.md's stated weakness: `platform_series` walks by
    category, so the holdout is a different category mix, not an
    exchangeable random half. DD-4 can corroborate; it cannot arbitrate.
    """
    anchors, candles, rules = hazard.load()
    events = hazard.event_map()
    _seen_arm, unseen_arm, _part = arms(anchors, candles, rules, events)
    peeked = peeked_tickers()
    holdout = [tk for tk in unseen_arm if tk not in peeked]
    spent = [tk for tk in unseen_arm if tk in peeked]
    print(f"unseen arm {len(unseen_arm)} -> holdout {len(holdout)}, "
          f"peeked/spent {len(spent)}")

    kw = dict(events=events, side="bid", entry="first", weight="event")
    print("\n" + hazard.HDR)
    print("-" * len(hazard.HDR))
    r_hold = hazard.estimate(anchors, candles, tickers=holdout, **kw)
    r_spent = hazard.estimate(anchors, candles, tickers=spent, **kw)
    hazard._row("DD-4 HOLDOUT (the test)", r_hold)
    hazard._row("peeked half (spent, descr.)", r_spent)

    print("\n=== DD-4 VERDICT (bar fixed in THEORY.md before any of this ran) ===")
    _verdict(r_hold, NET_BAR, CLUSTER_FLOOR)
    print("\n--- robustness, not the bar ---")
    _boot_line(anchors, candles, events, holdout, "DD-4 holdout")
    _boot_line(anchors, candles, events, spent, "peeked half")
    print("Per THEORY.md this can corroborate but cannot arbitrate -- the two "
          "halves differ by walk category, not by chance.")


def _verdict(r, bar, floor) -> None:
    if not r or r.get("markets", 0) == 0:
        print("NO DATA -- the arm is empty.")
        return
    net, ncl = r["net_pts"], r["n_clusters"]
    lo, hi = net - 1.96 * r["se_cl_pts"], net + 1.96 * r["se_cl_pts"]
    print(f"net {net:+.2f} pts, 95% CI [{lo:+.2f}, {hi:+.2f}], "
          f"{ncl} event clusters")
    if ncl < floor:
        print(f"UNDERPOWERED -- {ncl} clusters is below the pre-registered "
              f"floor of {floor}. Settles nothing in either direction.")
    elif net >= bar and lo > 0:
        print(f"CONFIRMED -- net >= +{bar} and the 95% CI excludes zero.")
    else:
        print(f"FAILED -- needs net >= +{bar} with a CI excluding zero.")


# ---------------------------------------------------------------- DD-5


def _settled_events_before(anchors, events):
    """series -> sorted [(close_ts, event)] for every settled event.

    An event is dated by the EARLIEST close among its legs: that is the
    moment the family demonstrably taught the board something, which is
    what DD-2's mechanism is about.
    """
    import datetime as _dt
    per_ev, ev_series = {}, {}
    for tk, a in anchors.items():
        ev, ct = events.get(tk), a.get("close_time")
        if not ev or not ct:
            continue
        try:
            ts = _dt.datetime.fromisoformat(
                ct.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if ev not in per_ev or ts < per_ev[ev]:
            per_ev[ev] = ts
        ev_series[ev] = a.get("series") or ""
    out = {}
    for ev, ts in per_ev.items():
        out.setdefault(ev_series[ev], []).append((ts, ev))
    for v in out.values():
        v.sort()
    return out


def dd5() -> None:
    """DD-2's contrast on the WHOLE unseen arm, peeked half included.

    The peek spent the unseen arm's AGGREGATE, not this split: DD-2's
    recurring/one-off contrast has never been examined on any unseen data,
    so the full unseen arm is clean for it. The residual contamination is
    that the reported aggregate is a weighted average of the two arms, so
    it constrains the levels somewhat and the difference barely -- stated
    in THEORY.md, and small rather than zero.
    """
    import bisect

    anchors, candles, rules = hazard.load()
    events = hazard.event_map()
    _seen_arm, unseen_arm, _part = arms(anchors, candles, rules, events)
    by_series = _settled_events_before(anchors, events)

    per_mkt, entry_ts = {}, {}
    for tk in unseen_arm:
        a, rows = anchors.get(tk), candles.get(tk)
        if not a or not rows or a.get("deadline") is None:
            continue
        got = hazard.observe(rows, a, side="bid", entry="first",
                             return_row=True)
        if not got:
            continue
        price, yes, row = got
        prior = by_series.get(a.get("series") or "", [])
        own_ev = events.get(tk)
        # Strictly before this market's own decision date, and never
        # counting the market's own event as its own reference class.
        k = bisect.bisect_left(prior, (row["end_ts"],))
        n_prior = sum(1 for _ts, ev in prior[:k] if ev != own_ev)
        per_mkt[tk] = (price, yes, n_prior >= RECURRING_MIN_EVENTS)
        entry_ts[tk] = row["end_ts"]

    # Event-weight, exactly as `hazard.estimate(weight="event")` does.
    buckets, mixed = {}, 0
    for tk, (p, y, rec) in per_mkt.items():
        buckets.setdefault(events.get(tk) or tk, []).append((p, y, rec))
    per_ev = {}
    for ev, v in buckets.items():
        recs = [r for _, _, r in v]
        if any(recs) and not all(recs):
            mixed += 1
        per_ev[ev] = (sum(p for p, _, _ in v) / len(v),
                      sum(1 for _, y, _ in v if y) / len(v),
                      sum(recs) * 2 >= len(recs))

    one = {e: (p, y) for e, (p, y, r) in per_ev.items() if not r}
    rec = {e: (p, y) for e, (p, y, r) in per_ev.items() if r}
    print(f"unseen arm: {len(per_mkt)} markets -> {len(per_ev)} events "
          f"({len(one)} one-off, {len(rec)} recurring; "
          f"{mixed} events split across arms, assigned by majority)")

    # THE CONFOUND THAT HAS TO TRAVEL WITH THIS NUMBER. `recurring` counts
    # settled events inside a ~60-day capture window, so a market entering
    # EARLY in that window has almost no prior events by construction and is
    # classified one-off whatever its family really is. The split is
    # therefore partly a proxy for entry date -- and this theory already
    # measures a timing gradient (closes before Aug 01: +2.1; from Aug 01:
    # +6.1). If the arms differ in entry date, the contrast is confounded
    # with timing and has to be read that way.
    import datetime as _dt

    def _median_entry(evs):
        ts = sorted(entry_ts[tk] for tk in per_mkt
                    if (events.get(tk) or tk) in evs)
        if not ts:
            return "n/a"
        return _dt.datetime.utcfromtimestamp(
            ts[len(ts) // 2]).strftime("%Y-%m-%d")

    print(f"median entry date -- one-off {_median_entry(set(one))}, "
          f"recurring {_median_entry(set(rec))}   "
          f"(a gap here means the contrast is confounded with timing)")

    print("\n" + hazard.HDR)
    print("-" * len(hazard.HDR))
    a_one, a_rec = _arm_stats(one), _arm_stats(rec)
    _arm_row("DD-5 one-off (predicted +)", a_one)
    _arm_row("DD-5 recurring (predicted 0)", a_rec)

    print("\n=== DD-5 VERDICT (bar fixed in THEORY.md before any of this ran) ===")
    if not a_one or not a_rec:
        print("NO DATA -- an arm is empty.")
        return
    contrast = a_one["net_pts"] - a_rec["net_pts"]
    se = (a_one["se_cl_pts"] ** 2 + a_rec["se_cl_pts"] ** 2) ** 0.5
    lo, hi = contrast - 1.96 * se, contrast + 1.96 * se
    print(f"contrast net(one-off) - net(recurring) = {contrast:+.2f} pts, "
          f"95% CI [{lo:+.2f}, {hi:+.2f}]")
    print(f"arms: one-off n={a_one['n_clusters']} net {a_one['net_pts']:+.2f} | "
          f"recurring n={a_rec['n_clusters']} net {a_rec['net_pts']:+.2f}")
    if (a_one["n_clusters"] < DD5_ARM_FLOOR
            or a_rec["n_clusters"] < DD5_ARM_FLOOR):
        print(f"UNDERPOWERED -- both arms need >= {DD5_ARM_FLOOR} event "
              f"clusters. Settles nothing in either direction.")
    elif contrast >= DD5_CONTRAST_BAR and lo > 0 and a_one["net_pts"] > 0:
        print(f"CONFIRMED -- contrast >= +{DD5_CONTRAST_BAR}, the CI excludes "
              f"zero, and the one-off arm is positive on its own.")
    else:
        print(f"FAILED -- needs contrast >= +{DD5_CONTRAST_BAR} with a CI "
              f"excluding zero AND a positive one-off arm.")


def _arm_stats(per):
    """The statistic `hazard.estimate` computes, on already-grouped events.

    Not routed back through `estimate` because the events are already the
    unit here -- re-clustering them would be a no-op that hides where the
    unit was chosen.
    """
    n = len(per)
    if not n:
        return None
    mean_p = sum(p for p, _ in per.values()) / n
    p_yes = sum(float(y) for _, y in per.values()) / n
    gap = (mean_p - p_yes) * 100.0
    d = [p - float(y) for p, y in per.values()]
    dbar = sum(d) / n
    se_cl = (sum((x - dbar) ** 2 for x in d) ** 0.5 / n) * 100.0
    no_entry = 1.0 - mean_p
    fee = hazard.FEE_RATE * no_entry * (1 - no_entry) * 100.0
    return {"markets": n, "n_clusters": n,
            "yes_n": round(sum(float(y) for _, y in per.values())),
            "mean_p": mean_p, "p_yes": p_yes, "gap_pts": gap,
            "se_cl_pts": se_cl,
            "z_cl": gap / se_cl if se_cl else float("nan"),
            "fee_pts": fee, "net_pts": gap - fee}


def _arm_row(label, r):
    if not r:
        print("{:<30}     0   (empty)".format(label))
        return
    hazard._row(label, r)


if __name__ == "__main__":
    import sys
    which = set(sys.argv[1:])
    if "--dd4" in which:
        dd4()
    elif "--dd5" in which:
        dd5()
    elif "--all" in which:
        main()
        print("\n" + "=" * 78 + "\n")
        dd4()
        print("\n" + "=" * 78 + "\n")
        dd5()
    else:
        main()
