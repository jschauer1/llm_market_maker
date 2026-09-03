"""deadline_drift stage-1 screen. Pins the audited population rules."""
import json
from datetime import datetime, timezone

from tools.domain import Market
from theories.deadline_drift import screen as dd


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _m(ticker, series, ev, rules="If X happens before Jan 1, 2027, "
       "then the market resolves to Yes.", **kw):
    base = dict(platform="kalshi", ticker=ticker, series_ticker=series,
                event_ticker=ev, rules_primary=rules, status="active",
                is_open=True, close_time="2026-09-05T00:00:00Z",
                yes_ask=0.20, no_ask=0.80, mid=0.20, volume=500.0)
    base.update(kw)
    return Market(**base)


def test_allowlist_accepts_known_families():
    assert dd.in_allowlist("KXTRUMPPARDON")
    assert dd.in_allowlist("KXMLBDEBUT")
    assert dd.in_allowlist("KXIPOANTHROPIC")     # prefix, so new IPO series join
    assert dd.in_allowlist("KXHEGSETHOUT")       # suffix
    assert dd.in_allowlist("KXKASHANNOUNCEOUT")
    assert not dd.in_allowlist("KX1ALBUM")
    assert not dd.in_allowlist("KXSUPERBOWLHEADLINE")


def test_kxukcabout_is_removed_by_the_venue_flag():
    """The suffix rule admits KXUKCABOUT ('who is NEXT to leave the
    Burnham Cabinet') -- 23 markets that are ONE partition, not 23
    hazards. The guard is the only thing that removes it, which is why
    the family rule alone is not the screen."""
    assert dd.in_allowlist("KXUKCABOUT")
    board = [_m(f"KXUKCABOUT-BURNN28JAN01-{i}", "KXUKCABOUT",
                "KXUKCABOUT-BURNN28JAN01", mid=0.039, yes_ask=0.039,
                event={"mutually_exclusive": True})
             for i in range(23)]
    assert dd.population(board) == []


def test_a_tightly_priced_partition_is_caught_without_the_flag():
    """Belt and braces: the real KXUKCABOUT sums to 0.90, exactly on the
    lower bound, so the price test alone is a thin margin there. It is
    caught anyway because the venue flag also fires. This pins the price
    path independently, with the flag absent."""
    board = [_m(f"KXFOOOUT-{i}", "KXFOOOUT", "E9", mid=0.039, yes_ask=0.039)
             for i in range(23)]                      # sums to 0.897
    assert dd.population(board) != [], (
        "0.897 is below the 0.90 floor -- documents that the price test "
        "alone would MISS the real KXUKCABOUT on a small downward drift")
    tighter = [_m(f"KXFOOOUT-{i}", "KXFOOOUT", "E9", mid=0.041, yes_ask=0.041)
               for i in range(23)]                    # sums to 0.943
    assert dd.population(tighter) == []


def test_partition_test_is_two_sided():
    """Session 09's defect: with no LOWER bound, three unrelated longshots
    summing 0.30 counted as a partition. 281 of 318 exclusions in round 5's
    frozen classifier were spurious for exactly this reason."""
    longshots = [_m(f"KXFOOOUT-{i}", "KXFOOOUT", "E1", mid=0.05, yes_ask=0.05)
                 for i in range(3)]
    assert dd.partition_events(longshots) == set(), \
        "0.15 is a coincidence, not a partition of one outcome"

    partition = [_m(f"KXFOOOUT-{i}", "KXFOOOUT", "E2", mid=0.33, yes_ask=0.33)
                 for i in range(3)]
    assert dd.partition_events(partition) == {"E2"}, "0.99 is a partition"


def test_date_ladders_are_exempt_from_the_partition_test():
    """KXALITOOUT is the same question at four deadlines -- nested, not
    exclusive. Without this exemption the rule cost 88 false positives."""
    ladder = [
        _m("KXALITOOUT-26JUL01", "KXALITOOUT", "E3", mid=0.10,
           rules="If Alito retires before Jul 1, 2026, resolves Yes."),
        _m("KXALITOOUT-26SEP01", "KXALITOOUT", "E3", mid=0.20,
           rules="If Alito retires before Sep 1, 2026, resolves Yes."),
        _m("KXALITOOUT-27JAN01", "KXALITOOUT", "E3", mid=0.60,
           rules="If Alito retires before Jan 1, 2027, resolves Yes."),
    ]
    assert dd.partition_events(ladder) == set()


# --- v2: the DD-1 population -----------------------------------------

#: A deadline inside the 21-day window from NOW (2026-08-29).
SOON = "If X happens before Sep 5, 2026, then the market resolves to Yes."
#: Same shape, far outside it.
LATER = "If X happens before Jan 1, 2027, then the market resolves to Yes."

#: v2's screen reads learned facts off disk. Tests pass them explicitly so
#: they pin the rules rather than the current capture.
NO_FACTS: dict = {"partition_families": [], "branch_families": [],
                  "settled_events_per_series": {}, "built_from_markets": 0}


def test_screen_takes_the_no_side_in_the_late_window():
    board = [_m("KXTRUMPPARDON-27-A", "KXTRUMPPARDON", "E4", rules=SOON)]
    cands, funnel, _removed = dd.screen(board, now=NOW, facts=NO_FACTS)
    assert len(cands) == 1
    leg = cands[0].legs[0]
    assert leg.side == "no"
    assert leg.price == 0.80, "entry is the NO ask actually payable"
    assert funnel["population"] == 1


def test_screen_drops_markets_outside_the_entry_band():
    board = [_m("KXTRUMPPARDON-27-B", "KXTRUMPPARDON", "E5", yes_ask=0.85,
                rules=SOON)]
    cands, funnel, _removed = dd.screen(board, now=NOW, facts=NO_FACTS)
    assert cands == []
    assert funnel["outside_entry_band"] == 1


def test_the_horizon_is_the_stated_deadline_not_the_close_time():
    """Correction 1 (2026-08-29), applied to the LIVE screen.

    Both markets close in a week. One states a deadline inside the
    window and one states a deadline four months out; only the stated
    deadline decides, because on a 'by D' market the close time is a
    function of the outcome and stops being a sound anchor exactly when
    it starts to matter.
    """
    close_soon = dict(close_time="2026-09-05T00:00:00Z")
    board = [
        _m("KXFOO-A", "KXFOO", "EA", rules=SOON, **close_soon),
        _m("KXFOO-B", "KXFOO", "EB", rules=LATER, **close_soon),
    ]
    cands, funnel, _removed = dd.screen(board, now=NOW, facts=NO_FACTS)
    assert [c.legs[0].market.ticker for c in cands] == ["KXFOO-A"]
    assert funnel["outside_horizon"] == 1


def test_v2_admits_non_allowlist_hazard_markets():
    """The whole point of v2: the allowlist measured -1.0 over 22 event
    clusters and the wide hazard stratum +4.6 over 94. A one-off newsy
    'will X happen by D' is not in any allowlist family and IS the
    population where the in-sample effect lives."""
    m = _m("KXSENATECLARITY-26SEP05", "KXSENATECLARITY", "EC", rules=SOON)
    assert not dd.in_allowlist("KXSENATECLARITY")
    cands, _funnel, _removed = dd.screen([m], now=NOW, facts=NO_FACTS)
    assert len(cands) == 1


def test_learned_partition_families_are_excluded_and_reported():
    """`partition_families` reads settled outcomes, so live it is applied
    as the SERIES set it returned. KXBIGBROTHERELIMINATION is the worked
    example: 8 events of 11-17 legs paying exactly one winner each, which
    the rules regex misses and the venue flag does not carry."""
    facts = dict(NO_FACTS, partition_families=["KXBIGBROTHERELIMINATION"])
    board = [_m("KXBIGBROTHERELIMINATION-26SEP03-TAY",
                "KXBIGBROTHERELIMINATION", "EBB", rules=SOON)]
    cands, _funnel, removed = dd.screen(board, now=NOW, facts=facts)
    assert cands == []
    assert removed["partition_family_learned"] == 1


def test_stratum_removals_are_reported_by_category():
    """A code gate drops silently inside families it thinks it knows, so
    it must always say what it removed."""
    board = [
        _m("KXTHRESH-1", "KXTHRESH", "E1",
           rules="If the price is above 100 before Sep 5, 2026, resolves Yes."),
        _m("KXNEXT-1", "KXNEXT", "E2",
           rules="If the next team Ronaldo joins is the first such subject "
                 "before Sep 5, 2026, resolves Yes."),
    ]
    cands, _funnel, removed = dd.screen(board, now=NOW, facts=NO_FACTS)
    assert cands == []
    assert removed["stratum_threshold"] == 1
    assert removed["stratum_multi_destination"] == 1


def test_branch_family_and_recurrence_are_recorded_not_filtered():
    """DD-1 names `partition_families` and nothing else, so branch
    families and DD-2's recurrence split are FIELDS. Filtering on them
    would test a population DD-1 did not pre-register; recording them
    keeps the cleaner subset available as a registered slice later."""
    facts = dict(NO_FACTS, branch_families=["KXFOO"],
                 settled_events_per_series={"KXFOO": 7})
    board = [_m("KXFOO-1", "KXFOO", "EF", rules=SOON)]
    cands, _funnel, _removed = dd.screen(board, now=NOW, facts=facts)
    assert len(cands) == 1, "a branch family is recorded, never screened out"

    feats = dd.features(board[0], {"EF": board}, facts)
    assert feats["branch_family"] is True
    assert feats["recurring"] is True and feats["settled_events"] == 7
    assert feats["event_legs"] == 1


def test_observation_rows_claim_zero_edge_and_say_they_are_not_bets():
    """The 2026-08-30 ruling: rows recorded so cells accrue must claim
    edge <= 0 and say they are not recommendations. Zero is load bearing
    -- ranked_edge is edge x credibility, so these can never promote."""
    from types import SimpleNamespace
    from theories.deadline_drift.theory import DeadlineDriftTheory

    board = [_m("KXTRUMPPARDON-27-C", "KXTRUMPPARDON", "E6", rules=SOON)]
    cands, _f, _r = dd.screen(board, now=NOW, facts=NO_FACTS)
    ctx = SimpleNamespace(board=board, now=NOW)
    scored = DeadlineDriftTheory()._observations(ctx, cands)
    assert len(scored) == 1
    sc = scored[0]
    assert sc.edge.pts_net == 0.0
    assert sc.disposition == "screened"
    assert "NOT A RECOMMENDATION" in sc.rationale
    assert sc.extra["test"] == "DD-1"


def test_parse_deadline_reads_the_stated_date_not_the_close(tmp_path):
    """The correction of 2026-08-29: actual close is a FUNCTION OF THE
    OUTCOME on a 'by D' market -- a NO runs to the deadline, a YES stops
    when the event fires (median 210 days early). Only the stated deadline
    is a sound anchor."""
    from theories.deadline_drift.collect_settled import parse_deadline
    assert parse_deadline(
        "If Alito retires before Jul 1, 2026, then the market resolves to Yes."
    ).startswith("2026-07-01")
    assert parse_deadline(
        "If X is traded on or before Feb 12, 2027, resolves Yes."
    ).startswith("2027-02-12")
    assert parse_deadline("If X happens, resolves Yes.") is None


def test_capture_staleness_marker_roundtrips(tmp_path):
    """Sessions die; the top-up obligation has to outlive them, so it is a
    marker any session's orient can read rather than a background job."""
    from tools import db, theories
    from theories.deadline_drift import collect_settled as cs
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "deadline_drift", "Deadline Drift",
                      "theories/deadline_drift")
    assert cs.days_since_capture(conn) is None      # never captured
    cs.mark_captured(conn, when="2026-08-01T00:00:00+00:00")
    got = cs.days_since_capture(conn, now="2026-08-29T00:00:00+00:00")
    assert round(got) == 28, "28 days stale -> RUNBOOK says top it up"
    conn.close()


def test_the_implied_probability_recorded_is_the_bid_not_the_ask():
    """Correction 2 (2026-09-01) pinned as a test.

    This theory buys NO, so the probability it bets against is `yes_bid`
    -- which is `1 - no_ask`, not the field named `yes_ask`. Reading the
    optimistic field credited the strategy with the whole bid-ask spread
    and roughly doubled the apparent edge. It is pinned here because it
    does not look like a bug; it looks like following the rule.
    """
    from types import SimpleNamespace
    from theories.deadline_drift.theory import DeadlineDriftTheory

    # A wide book: yes_ask 0.20 but no_ask 0.87, so yes_bid is 0.13.
    board = [_m("KXWIDE-1", "KXWIDE", "EW", rules=SOON,
                yes_ask=0.20, no_ask=0.87, mid=0.165)]
    cands, _f, _r = dd.screen(board, now=NOW, facts=NO_FACTS)
    ctx = SimpleNamespace(board=board, now=NOW)
    extra = DeadlineDriftTheory()._observations(ctx, cands)[0].extra
    assert extra["yes_bid_implied"] == 0.13, "1 - no_ask, the payable side"
    assert extra["yes_ask_optimistic"] == 0.20


def test_the_event_is_recorded_under_the_key_scoring_reads():
    """`score.cluster_key` reads `extra_json.event_ticker` exactly, and
    falls back to stripping the ticker's last dash-segment otherwise.

    On this theory's first live run that fallback was wrong for 4 of 46
    rows, and for KXMEDIARELEASEDATEAHS-26-SEP19-AME (whose event is
    KXMEDIARELEASEDATEAHS-26) it SPLIT one event into several -- which
    manufactures precision rather than losing it. Clustering matters more
    here than almost anywhere: one event supplied 22 of those 46 rows, so
    the run is 20 independent questions, not 46.
    """
    from tools import score

    m = _m("KXMEDIARELEASEDATEAHS-26-SEP19-AME", "KXMEDIARELEASEDATEAHS",
           "KXMEDIARELEASEDATEAHS-26", rules=SOON)
    feats = dd.features(m, {"KXMEDIARELEASEDATEAHS-26": [m]}, NO_FACTS)
    assert feats["event_ticker"] == "KXMEDIARELEASEDATEAHS-26"

    row = {"extra_json": json.dumps(feats),
           "kalshi_ticker": m.ticker}
    assert score.cluster_key(row) == ("KXMEDIARELEASEDATEAHS-26", True)
    # ... and what the fallback would have done instead.
    assert score.cluster_key({"extra_json": None,
                              "kalshi_ticker": m.ticker}) == (
        "KXMEDIARELEASEDATEAHS-26-SEP19", True)


# --------------------------------------------------------------- DD-5


def test_observe_can_return_the_entry_row_without_changing_the_price():
    """`return_row` is additive: same price, same outcome, plus the row.

    DD-5's split is point-in-time, so it needs the DECISION DATE, and that
    date is not recoverable from the (price, outcome) pair. Exposing the
    row beats reimplementing "which candle qualifies" in the caller --
    two copies of that predicate is how they would silently diverge.
    """
    from theories.deadline_drift import hazard

    rows = [
        # Outside the 21-day window: must not be chosen.
        {"end_ts": 100, "yes_ask": 0.30, "yes_bid": 0.28,
         "days_to_deadline": 40.0, "volume": 10, "open_interest": 10},
        # First qualifying day.
        {"end_ts": 200, "yes_ask": 0.30, "yes_bid": 0.25,
         "days_to_deadline": 20.0, "volume": 10, "open_interest": 10},
        {"end_ts": 300, "yes_ask": 0.30, "yes_bid": 0.10,
         "days_to_deadline": 5.0, "volume": 10, "open_interest": 10},
    ]
    anchor = {"result": "no"}
    plain = hazard.observe(rows, anchor, side="bid", entry="first")
    withrow = hazard.observe(rows, anchor, side="bid", entry="first",
                             return_row=True)
    assert plain == withrow[:2]
    assert withrow[2]["end_ts"] == 200, "the FIRST qualifying day, not the last"
    assert withrow[0] == 0.25


def test_dd5_recurring_is_point_in_time_and_excludes_the_markets_own_event():
    """THEORY.md: recurring means >= 3 settled events with a close_time
    STRICTLY BEFORE that market's own decision date.

    Two ways this goes wrong silently, both pinned here:
      * counting events that settled AFTER the decision date, which lets
        the test period's own settlements define the test's split;
      * counting the market's OWN event, which would make a family look
        like its own reference class.
    """
    from theories.deadline_drift import backtest as bt

    anchors = {
        # Three prior events in series S, closing at ts 10, 20, 30.
        "S-E1-A": {"series": "S", "close_time": "2026-01-01T00:00:00Z"},
        "S-E2-A": {"series": "S", "close_time": "2026-02-01T00:00:00Z"},
        "S-E3-A": {"series": "S", "close_time": "2026-03-01T00:00:00Z"},
        # The market under test, in its own event.
        "S-E4-A": {"series": "S", "close_time": "2026-04-01T00:00:00Z"},
    }
    events = {"S-E1-A": "S-E1", "S-E2-A": "S-E2", "S-E3-A": "S-E3",
              "S-E4-A": "S-E4"}
    by_series = bt._settled_events_before(anchors, events)
    prior = by_series["S"]
    assert [ev for _ts, ev in prior] == ["S-E1", "S-E2", "S-E3", "S-E4"]

    import bisect
    import datetime as dt

    def n_prior(decision_iso, own_ev):
        ts = dt.datetime.fromisoformat(
            decision_iso.replace("Z", "+00:00")).timestamp()
        k = bisect.bisect_left(prior, (ts,))
        return sum(1 for _t, ev in prior[:k] if ev != own_ev)

    # Deciding in March: only E1 and E2 have closed -> one-off.
    assert n_prior("2026-02-15T00:00:00Z", "S-E4") == 2
    # Deciding after E3 closed -> recurring, and E4 (its own) never counts.
    assert n_prior("2026-03-15T00:00:00Z", "S-E4") == 3
    # Even deciding after its own close, the market's own event is excluded.
    assert n_prior("2026-05-01T00:00:00Z", "S-E4") == 3


def test_dd5_arm_stats_matches_hazard_estimate_on_the_same_events():
    """`_arm_stats` must be the SAME statistic `hazard.estimate` computes.

    DD-5's contrast is a difference of two `net_pts`, so an arm computed
    by a subtly different formula would make the contrast meaningless
    while still printing a plausible number.
    """
    from theories.deadline_drift import backtest as bt
    from theories.deadline_drift import hazard

    # One market per event, so event-weighting is the identity and the two
    # code paths are directly comparable.
    per = {"E1": (0.30, False), "E2": (0.20, False), "E3": (0.40, True)}
    mine = bt._arm_stats(per)

    anchors, candles, events = {}, {}, {}
    for i, (ev, (p, y)) in enumerate(per.items()):
        tk = f"T{i}"
        anchors[tk] = {"result": "yes" if y else "no", "deadline": "x",
                       "series": "S"}
        candles[tk] = [{"end_ts": 1, "yes_ask": p, "yes_bid": p,
                        "days_to_deadline": 10.0, "volume": 1,
                        "open_interest": 1}]
        events[tk] = ev
    theirs = hazard.estimate(anchors, candles, events=events, side="bid",
                             entry="first", weight="event")

    for k in ("mean_p", "p_yes", "gap_pts", "se_cl_pts", "fee_pts", "net_pts"):
        assert abs(mine[k] - theirs[k]) < 1e-9, k
    assert mine["n_clusters"] == theirs["n_clusters"] == 3


def test_dd4_holdout_excludes_every_peeked_ticker():
    """The 509 peeked tickers are SPENT for the aggregate statistic.

    They were computed and reported at ~45% capture, so a second look at
    them is a second look at the same data. DD-4 exists precisely to test
    the part that has never been looked at, and a holdout that leaked one
    peeked ticker would quietly be a re-look wearing a holdout's name.
    """
    from theories.deadline_drift import backtest as bt

    peeked = bt.peeked_tickers()
    seen = bt.seen_tickers()
    assert peeked, "the freeze file must not be empty"
    # The peek was taken on the UNSEEN arm, so no peeked ticker may also be
    # in the pre-platform seen set -- if one were, the two freezes disagree
    # about what the test set is.
    assert not (peeked & seen), "peeked tickers must all be outside the seen set"


# ------------------------------------------------------- fixed-k purity


def _anchors_for(series, per_event_results):
    """Build an anchors/events pair from {event: [result, ...]}."""
    anchors, events = {}, {}
    for ev, results in per_event_results.items():
        for i, r in enumerate(results):
            tk = f"{ev}-L{i}"
            anchors[tk] = {"series": series, "result": r,
                           "close_time": "2026-08-01T00:00:00Z"}
            events[tk] = ev
    return anchors, events


def test_fixed_k_detector_clears_the_labelled_independent_family():
    """KXTRUMPSAY is the negative label and must never be flagged.

    It is the same superficial shape as a fixed-k elimination -- 30-odd
    legs, many YES per event -- but the legs are genuinely independent
    (Trump saying 'Antifa' does not preclude 'Uranium'), and the tell is
    that the winner count MOVES: 7, 12, 12, 15, 17, 17, 19, 19, 21.
    Flagging it would delete a legitimate population, so this is the test
    that has to hold even if the positive side is never fittable.
    """
    from theories.deadline_drift import purity

    real = {"7": 7, "12a": 12, "12b": 12, "15": 15, "17a": 17, "17b": 17,
            "19a": 19, "19b": 19, "21": 21}
    per_event = {ev: ["yes"] * k + ["no"] * (31 - k) for ev, k in real.items()}
    anchors, events = _anchors_for("KXTRUMPSAY", per_event)
    stats = purity.family_stats(purity.yes_counts(anchors, events))
    assert "KXTRUMPSAY" in stats
    assert stats["KXTRUMPSAY"]["k_cv"] > purity.K_CV_MAX
    assert "KXTRUMPSAY" not in purity.fixed_k_families(stats)


def test_fixed_k_detector_flags_a_constant_winner_count_above_one():
    """The AGT shape: many legs, the SAME k every event, k > 1.

    k == 1 is deliberately left to `partition_families`, which already
    catches it; this detector exists only for the k > 1 case that one
    misses by construction.
    """
    from theories.deadline_drift import purity

    per_event = {f"E{i}": ["yes"] * 7 + ["no"] * 4 for i in range(4)}
    anchors, events = _anchors_for("KXAGTELIMINATION", per_event)
    stats = purity.family_stats(purity.yes_counts(anchors, events))
    assert purity.fixed_k_families(stats) == {"KXAGTELIMINATION"}

    # The same constancy at k == 1 is a one-winner partition, not this.
    per_event1 = {f"E{i}": ["yes"] + ["no"] * 10 for i in range(4)}
    a1, e1 = _anchors_for("KXWHICHONE", per_event1)
    s1 = purity.family_stats(purity.yes_counts(a1, e1))
    assert purity.fixed_k_families(s1) == set(), \
        "k==1 belongs to partition_families, not to the fixed-k detector"


def test_fixed_k_detector_refuses_to_judge_a_family_with_too_few_events():
    """Two settled events cannot fit a variance threshold.

    This is the whole reason the ticket refused to ship a rule in 2026-09:
    at n=2 the AGT shape and the TRUMPSAY shape are indistinguishable, and
    guessing would bake an inclusion rule into the population DD-1 is
    being measured on.
    """
    from theories.deadline_drift import purity

    per_event = {f"E{i}": ["yes"] * 7 + ["no"] * 4 for i in range(2)}
    anchors, events = _anchors_for("KXAGTELIMINATION", per_event)
    stats = purity.family_stats(purity.yes_counts(anchors, events))
    assert "KXAGTELIMINATION" not in stats, \
        f"below {purity.MIN_EVENTS} events the family must not be judged"
    assert purity.fixed_k_families(stats) == set()


def test_collect_reports_progress_so_a_stall_is_visible(tmp_path, monkeypatch):
    """A walk that prints nothing makes 'running' and 'died an hour ago'
    look identical from outside.

    That is not hypothetical: the 2026-09-02 platform capture sat dead at
    56% for three hours and was found by stat-ing the store's mtime. The
    line is emitted on a flush that has ALREADY happened, so it can never
    claim progress the store does not hold.
    """
    from theories.deadline_drift import collect_settled as cs

    monkeypatch.setattr(cs, "DATA", tmp_path)

    class _Mkt:
        def __init__(self, tk):
            self.raw = {"ticker": tk, "result": "no",
                        "close_time": "2026-08-01T00:00:00Z",
                        "rules_primary": "nothing parseable here"}
            self.result = "no"

    monkeypatch.setattr(cs.km, "list_settled",
                        lambda **kw: [_Mkt(kw["series_ticker"] + "-A")])

    seen = []
    out = cs.collect([f"S{i}" for i in range(6)], flush_every=2,
                     progress=seen.append)

    assert out["series"] == 6
    assert len(seen) == 3, "one line per flush, not per series"
    assert seen[0].startswith("[2/6]"), seen[0]
    assert "series=" in seen[0] and "markets=" in seen[0]
    # The final partial batch lands in the `finally`, which deliberately
    # does not print -- it has no index and the return value says the same
    # thing. Six series at flush_every=2 divides evenly, so 3 is exact.
    assert seen[-1].startswith("[6/6]"), seen[-1]


def test_collect_persists_everything_walked_even_when_a_series_raises(
        tmp_path, monkeypatch):
    """The data is perishable, so a crash mid-walk must not lose the walk.

    Pins the `finally`-flush: whatever was fetched before the failure is
    on disk, and the resume skips it.
    """
    import json

    from theories.deadline_drift import collect_settled as cs

    monkeypatch.setattr(cs, "DATA", tmp_path)

    class _Mkt:
        def __init__(self, tk):
            self.raw = {"ticker": tk, "result": "no",
                        "close_time": "2026-08-01T00:00:00Z",
                        "rules_primary": "nothing parseable here"}
            self.result = "no"

    def _boom(**kw):
        if kw["series_ticker"] == "S3":
            raise KeyboardInterrupt
        return [_Mkt(kw["series_ticker"] + "-A")]

    monkeypatch.setattr(cs.km, "list_settled", _boom)

    try:
        cs.collect([f"S{i}" for i in range(6)], flush_every=100)
    except KeyboardInterrupt:
        pass

    stored = json.loads((tmp_path / "settled_raw.json").read_text())
    assert set(stored) == {"S0", "S1", "S2"}, \
        "everything walked before the interrupt must be on disk"


def test_a_transient_series_failure_is_retried_but_a_page_cap_skip_is_not(
        tmp_path, monkeypatch):
    """A failed fetch is not an answer, and must not be stored as one.

    `collect` records `{"__error__": ...}` when a series raises, and the
    resume test used to be `s not in raw` -- so one 429 permanently
    recorded 'nothing here'. On data Kalshi ages out at ~60 days that is
    unrecoverable. The page-cap skip is the opposite case: it IS a
    decision (a combinatorial shard this theory does not want), so it
    stays permanent.
    """
    import json

    from theories.deadline_drift import collect_settled as cs

    monkeypatch.setattr(cs, "DATA", tmp_path)

    class _Mkt:
        def __init__(self, tk):
            self.raw = {"ticker": tk, "result": "no",
                        "close_time": "2026-08-01T00:00:00Z",
                        "rules_primary": "nothing parseable here"}
            self.result = "no"

    calls = []

    def _flaky(**kw):
        s = kw["series_ticker"]
        calls.append(s)
        if s == "BOOM" and calls.count("BOOM") == 1:
            raise RuntimeError("transient")
        return [_Mkt(s + "-A")]

    monkeypatch.setattr(cs.km, "list_settled", _flaky)

    cs.collect(["BOOM", "FINE"], flush_every=1)
    stored = json.loads((tmp_path / "settled_raw.json").read_text())
    assert isinstance(stored["BOOM"], dict) and "__error__" in stored["BOOM"]
    assert cs._is_retryable(stored["BOOM"])

    # Second run: the poisoned series is re-walked and now succeeds.
    cs.collect(["BOOM", "FINE"], flush_every=1)
    stored = json.loads((tmp_path / "settled_raw.json").read_text())
    assert isinstance(stored["BOOM"], list), "a transient failure must be retried"
    assert calls.count("FINE") == 1, "a successful series is never re-walked"

    # The deliberate page-cap skip is permanent.
    assert not cs._is_retryable({"__error__": "skipped: exceeded 15 pages"})
    assert not cs._is_retryable([])          # a real (empty) answer
