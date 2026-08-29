"""deadline_drift stage-1 screen. Pins the audited population rules."""
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


def test_screen_takes_the_no_side_in_the_late_window():
    board = [_m("KXTRUMPPARDON-27-A", "KXTRUMPPARDON", "E4")]
    cands, funnel = dd.screen(board, now=NOW)
    assert len(cands) == 1
    leg = cands[0].legs[0]
    assert leg.side == "no"
    assert leg.price == 0.80, "entry is the NO ask actually payable"
    assert funnel["population"] == 1


def test_screen_drops_markets_outside_the_entry_band():
    board = [_m("KXTRUMPPARDON-27-B", "KXTRUMPPARDON", "E5", yes_ask=0.85)]
    cands, funnel = dd.screen(board, now=NOW)
    assert cands == []
    assert funnel["outside_entry_band"] == 1


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
