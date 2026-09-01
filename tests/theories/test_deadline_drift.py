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
