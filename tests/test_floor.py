"""Floor duty — who runs the daily floor, and whether it is due at all.

The mechanism under test (tools/floor.py): the floor runs once per 24
hours, one session does it and nothing else, and every other session
must be able to answer "has it already run?" from the database rather
than from a peer's message. Four sessions collided on 2026-08-30 under a
message-only protocol and a defective duplicate run had to be
quarantined; a durable claim is what makes that unrepeatable.
"""

from __future__ import annotations

import pytest

from tools import db, floor


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    return c


# --- is it due? ------------------------------------------------------------


def test_the_floor_is_due_when_none_has_ever_run(conn):
    status = floor.status(conn, now="2026-08-31T12:00:00Z")
    assert status["due"] is True
    assert status["last_completed_at"] is None
    assert status["holder"] is None


def test_a_completed_floor_is_not_due_again_within_24_hours(conn):
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    status = floor.status(conn, now="2026-08-31T23:59:00Z")
    assert status["due"] is False
    assert status["last_completed_at"] == "2026-08-31T02:00:00Z"
    assert "22" in status["reason"] or "hours" in status["reason"]


def test_a_floor_completed_more_than_24_hours_ago_is_due_again(conn):
    claim = floor.claim(conn, "sess-a", now="2026-08-30T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-30T02:00:00Z")

    assert floor.status(conn, now="2026-08-31T02:00:01Z")["due"] is True


def test_an_unfinished_claim_does_not_satisfy_the_24_hour_window(conn):
    """Claiming is not doing. Only completion starts the clock."""
    floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")

    status = floor.status(conn, now="2026-08-31T01:30:00Z")
    assert status["last_completed_at"] is None
    assert status["holder"] == "sess-a"


# --- claiming --------------------------------------------------------------


def test_a_second_session_cannot_claim_a_floor_already_held(conn):
    floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")

    assert floor.claim(conn, "sess-b", now="2026-08-31T01:05:00Z") is None


def test_a_second_session_cannot_claim_a_floor_already_completed(conn):
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    assert floor.claim(conn, "sess-b", now="2026-08-31T03:00:00Z") is None


def test_an_abandoned_claim_expires_so_the_floor_is_never_blocked(conn):
    """A session that claims and dies must not cost the repo a day. The
    lease is what bounds that: past it, the claim is take-over-able."""
    floor.claim(conn, "sess-dead", now="2026-08-31T01:00:00Z")

    late = "2026-08-31T09:00:00Z"                  # well past the lease
    assert floor.status(conn, now=late)["due"] is True
    took_over = floor.claim(conn, "sess-b", now=late)
    assert took_over is not None
    assert took_over["session"] == "sess-b"


def test_a_claim_inside_its_lease_still_blocks(conn):
    floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")

    within = "2026-08-31T02:30:00Z"
    assert floor.status(conn, now=within)["due"] is False
    assert floor.claim(conn, "sess-b", now=within) is None


def test_the_user_can_always_force_a_floor(conn):
    """'Unless explicitly asked' — a direct instruction outranks the
    24-hour window."""
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    forced = floor.claim(conn, "sess-b", now="2026-08-31T03:00:00Z",
                         force=True)
    assert forced is not None
    assert forced["forced"] == 1


# --- completing ------------------------------------------------------------


def test_completing_records_when_and_where_the_report_landed(conn):
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(
        conn, claim["id"], now="2026-08-31T02:00:00Z",
        report_path="user_reports/2026-08-31/README.md",
        summary="4 theories ran, 0 promotable bets",
    )

    status = floor.status(conn, now="2026-08-31T02:05:00Z")
    assert status["last_completed_at"] == "2026-08-31T02:00:00Z"
    assert status["last_report_path"] == "user_reports/2026-08-31/README.md"


def test_a_floor_cannot_be_completed_twice(conn):
    claim = floor.claim(conn, "sess-a", now="2026-08-31T01:00:00Z")
    floor.complete(conn, claim["id"], now="2026-08-31T02:00:00Z")

    with pytest.raises(ValueError, match="already completed"):
        floor.complete(conn, claim["id"], now="2026-08-31T03:00:00Z")


def test_completing_an_unknown_claim_raises(conn):
    with pytest.raises(KeyError):
        floor.complete(conn, 999, now="2026-08-31T02:00:00Z")


# --- the report must cover every theory AND every sub-theory ---------------


def _running_theory_with_subtheory(conn):
    from tools import slices, theories
    theories.register(conn, "insider_judgment", "IJ", "theories/ij",
                      status="testing")
    theories.register(conn, "structural_arb", "SA", "theories/sa",
                      status="testing")
    slices.register_slice(
        conn, "insider_judgment", "strong-moderate-no",
        predicate={"outcome": ["no"], "confidence": ["strong", "moderate"]},
        hypothesis="the NO subset carries the edge", origin="test",
        registered_at="2026-08-26T00:00:00Z",
    )


def test_required_coverage_lists_theories_and_sub_theories(conn, tmp_path):
    _running_theory_with_subtheory(conn)

    # `root` isolates the study half of the coverage list; this test is
    # about theories, so it points at a repo with no studies in it.
    names = {c["name"] for c in floor.required_coverage(conn, root=tmp_path)}
    assert names == {"insider_judgment", "structural_arb",
                     "strong-moderate-no"}


def test_a_report_missing_a_sub_theory_is_refused(conn):
    """The 2026-09-01 floor reported all four theories and missed
    `strong-moderate-no` -- the best-evidenced result in the repo, READY
    at +3.76 over 90 clusters. Prose asking sessions to remember was not
    enough, so the omission is made impossible instead."""
    _running_theory_with_subtheory(conn)
    claim = floor.claim(conn, "sess-a", now="2026-09-02T01:00:00Z")

    report = "insider_judgment ran six stages. structural_arb ran clean."
    with pytest.raises(ValueError, match="strong-moderate-no"):
        floor.complete(conn, claim["id"], report_text=report,
                       now="2026-09-02T02:00:00Z")


def test_a_report_covering_everything_completes(conn, tmp_path):
    _running_theory_with_subtheory(conn)
    claim = floor.claim(conn, "sess-a", now="2026-09-02T01:00:00Z")

    report = (
        "insider_judgment ran six stages; its sub-theory "
        "strong-moderate-no is READY at +3.76. structural_arb ran clean."
    )
    row = floor.complete(conn, claim["id"], report_text=report,
                         now="2026-09-02T02:00:00Z", root=tmp_path)
    assert row["completed_at"] == "2026-09-02T02:00:00Z"


def test_coverage_gaps_names_exactly_what_is_missing(conn, tmp_path):
    _running_theory_with_subtheory(conn)

    gaps = floor.coverage_gaps(conn, "structural_arb ran clean.",
                               root=tmp_path)
    assert {g["name"] for g in gaps} == {"insider_judgment",
                                         "strong-moderate-no"}
    assert any(g["kind"] == "sub-theory" for g in gaps)


def test_completing_without_a_report_still_works(conn):
    """A blocked floor still closes out. The check binds a report that
    exists, and cannot become a reason not to write one."""
    _running_theory_with_subtheory(conn)
    claim = floor.claim(conn, "sess-a", now="2026-09-02T01:00:00Z")
    row = floor.complete(conn, claim["id"], now="2026-09-02T02:00:00Z")
    assert row["completed_at"] is not None


def test_a_retired_sub_theory_still_has_to_be_reported(conn):
    """Retirement must never hide a record -- that is the whole reason a
    retired slice keeps reporting."""
    from tools import slices
    _running_theory_with_subtheory(conn)
    slices.retire_slice(conn, "insider_judgment", "strong-moderate-no",
                        reason="superseded")

    names = {c["name"] for c in floor.required_coverage(conn)}
    assert "strong-moderate-no" in names
