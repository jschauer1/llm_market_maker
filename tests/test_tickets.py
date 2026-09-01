"""Tickets — one .md per unit of work, read as a backlog at session start.

A ticket says what to do and lives next to the thing it is about: theory
work in that theory's own folder, everything else under `tickets/<lane>/`.
That placement is the point rather than a filing convention — a theory
folder is supposed to hold everything its expert needs, and work queued
against it is part of that.

Sessions read the backlog to choose a lane, and write tickets for lanes
they are not in: a maintenance session that spots a theory problem files
it rather than pivoting, and a theory session that trips over broken
tooling files maintenance rather than fixing it mid-thought. The ticket
is what makes staying focused affordable — and it is also the
low-interrupt way to tell a working peer something, since a message
costs them their focus and a ticket does not.
"""

from __future__ import annotations

import pytest

from tools import tickets


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "tickets" / "maintenance").mkdir(parents=True)
    (tmp_path / "tickets" / "research").mkdir(parents=True)
    (tmp_path / "theories" / "insider_judgment").mkdir(parents=True)
    return tmp_path


# --- writing ---------------------------------------------------------------


def test_a_maintenance_ticket_lands_under_its_lane(repo):
    path = tickets.create(
        repo, lane="maintenance", slug="fix-state-encoding",
        title="state crashes on cp1252", body="Force UTF-8 in cli.main.",
        created="2026-08-31", created_by="llm-7a",
    )
    assert path.relative_to(repo).as_posix() == (
        "tickets/maintenance/open/2026-08-31-fix-state-encoding.md"
    )
    assert path.read_text(encoding="utf-8").startswith("---")


def test_a_theory_ticket_lands_in_that_theorys_folder(repo):
    path = tickets.create(
        repo, lane="theory", theory="insider_judgment",
        slug="adopt-strong-moderate-no", title="Adopt the NO rule at v5",
        body="The slice is ready at v4.", created="2026-08-31",
        created_by="llm-7a",
    )
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_judgment/tickets/open/"
        "2026-08-31-adopt-strong-moderate-no.md"
    )


def test_a_theory_ticket_without_a_theory_is_refused(repo):
    with pytest.raises(ValueError, match="theory"):
        tickets.create(repo, lane="theory", slug="x", title="x", body="x")


def test_an_unknown_lane_is_refused(repo):
    with pytest.raises(ValueError, match="lane"):
        tickets.create(repo, lane="wandering", slug="x", title="x", body="x")


def test_a_ticket_needs_a_body_that_says_what_to_do(repo):
    """A title alone is a note, not a task. The next session has only
    this file to work from."""
    with pytest.raises(ValueError, match="body"):
        tickets.create(repo, lane="maintenance", slug="x", title="x", body="")


# --- reading ---------------------------------------------------------------


def test_the_backlog_spans_theory_and_main_tickets(repo):
    tickets.create(repo, lane="maintenance", slug="a", title="A", body="do a",
                   created="2026-08-30")
    tickets.create(repo, lane="new-theory", slug="b", title="B",
                   body="do b", created="2026-08-31")
    tickets.create(repo, lane="theory", theory="insider_judgment", slug="c",
                   title="C", body="do c", created="2026-08-29")

    found = tickets.backlog(repo)
    assert [t["slug"] for t in found] == ["c", "a", "b"], "oldest first"
    assert {t["lane"] for t in found} == {
        "maintenance", "new-theory", "theory"}


def test_the_backlog_filters_by_lane(repo):
    tickets.create(repo, lane="maintenance", slug="a", title="A", body="x")
    tickets.create(repo, lane="new-theory", slug="b", title="B", body="x")

    assert [t["slug"] for t in tickets.backlog(repo, lane="maintenance")] == ["a"]


def test_a_theory_ticket_reports_which_theory_it_belongs_to(repo):
    tickets.create(repo, lane="theory", theory="insider_judgment", slug="c",
                   title="C", body="x")
    entry = tickets.backlog(repo)[0]
    assert entry["theory"] == "insider_judgment"


def test_a_malformed_ticket_is_reported_not_skipped(repo):
    """A ticket nobody can parse is work nobody will do. Silently
    dropping it is the one behaviour a backlog must not have."""
    (repo / "tickets" / "maintenance" / "open").mkdir(parents=True)
    bad = repo / "tickets" / "maintenance" / "open" / "2026-08-31-broken.md"
    bad.write_text("no frontmatter here", encoding="utf-8")

    entry = [t for t in tickets.backlog(repo) if t["slug"] == "broken"][0]
    assert entry["malformed"] is True
    assert entry["lane"] == "maintenance", "the directory still says the lane"


# --- open / completed layout ----------------------------------------------


def test_a_new_ticket_lands_in_open(repo):
    path = tickets.create(repo, lane="maintenance", slug="a", title="A",
                          body="do a", created="2026-09-01")
    assert path.relative_to(repo).as_posix() == (
        "tickets/maintenance/open/2026-09-01-a.md"
    )


def test_a_theory_ticket_also_lands_in_open(repo):
    path = tickets.create(repo, lane="theory", theory="insider_judgment",
                          slug="c", title="C", body="do c",
                          created="2026-09-01")
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_judgment/tickets/open/2026-09-01-c.md"
    )


def test_closing_moves_the_file_into_completed(repo):
    """The backlog is a directory listing, so a done ticket has to leave
    it physically -- a status field alone means every session reads every
    ticket ever filed to find the few that are open."""
    path = tickets.create(repo, lane="maintenance", slug="a", title="A",
                          body="do a", created="2026-09-01")
    done = tickets.close(path, resolution="fixed in 21b3fe4")

    assert not path.exists()
    assert done.relative_to(repo).as_posix() == (
        "tickets/maintenance/completed/2026-09-01-a.md"
    )
    assert tickets.backlog(repo) == []
    assert tickets.backlog(repo, status="done")[0]["slug"] == "a"
    assert "fixed in 21b3fe4" in done.read_text(encoding="utf-8")


# --- the filing session's context ------------------------------------------


def test_a_ticket_records_what_its_author_was_doing(repo):
    """`created_by: llm-market-identifier-86` alone says who, not what.
    The lane and task the author was on is most of what makes a ticket
    readable later -- it says what they were looking at when they hit
    this, which is the context a reader cannot reconstruct."""
    path = tickets.create(
        repo, lane="maintenance", slug="a", title="A", body="do a",
        created="2026-09-01", created_by="llm-market-identifier-86",
        author_lane="theory", author_focus="insider_judgment",
        author_context="backtesting the v4 screen over 90 days when the "
                       "payload reader crashed on a zlib row",
    )
    text = path.read_text(encoding="utf-8")
    assert "created_by: llm-market-identifier-86" in text
    assert "author_lane: theory" in text
    assert "author_focus: insider_judgment" in text
    assert "backtesting the v4 screen" in text

    entry = tickets.backlog(repo)[0]
    assert entry["author_lane"] == "theory"
    assert entry["author_focus"] == "insider_judgment"
