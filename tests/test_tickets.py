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
    (tmp_path / "tickets" / "new-theory").mkdir(parents=True)
    # The real shape: a theory folder is wherever its registry row
    # says, and insider_judgment sits under a shared family parent.
    (tmp_path / "theories" / "insider_bias"
     / "insider_judgment").mkdir(parents=True)
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
        theory_path="theories/insider_bias/insider_judgment",
        slug="adopt-strong-moderate-no", title="Adopt the NO rule at v5",
        body="The slice is ready at v4.", created="2026-08-31",
        created_by="llm-7a",
    )
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_bias/insider_judgment/tickets/open/"
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
                   theory_path="theories/insider_bias/insider_judgment",
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
                   theory_path="theories/insider_bias/insider_judgment",
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
                          theory_path="theories/insider_bias/insider_judgment",
                          slug="c", title="C", body="do c",
                          created="2026-09-01")
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_bias/insider_judgment/tickets/open/2026-09-01-c.md"
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


def test_a_theory_ticket_follows_the_registry_path(repo):
    """A theory's folder is wherever its registry row says, not
    theories/<slug>. insider_judgment moved under a shared family parent
    when mention_family split off, so hardcoding the slug filed its
    tickets into a phantom directory holding nothing else."""
    (repo / "theories" / "insider_bias" / "insider_judgment").mkdir(
        parents=True, exist_ok=True)
    path = tickets.create(
        repo, lane="theory", theory="insider_judgment",
        theory_path="theories/insider_bias/insider_judgment",
        slug="c", title="C", body="do c", created="2026-09-01",
    )
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_bias/insider_judgment/tickets/open/2026-09-01-c.md"
    )
    entry = tickets.backlog(repo)[0]
    assert entry["theory"] == "insider_judgment", (
        "the owning theory is read from the ticket, not from the folder "
        "name, so a nested path still reports the right theory"
    )


def test_a_theory_ticket_without_its_registry_path_is_refused(tmp_path):
    """The phantom-directory guard, and it must stay a refusal.

    `ticket_dir` used to fall back to `theories/<slug>` when a caller
    omitted `theory_path`. That silently created
    `theories/insider_judgment/` -- a directory holding nothing but
    tickets, sitting beside the real theory at
    `theories/insider_bias/insider_judgment`, where that theory's expert
    would never look. Nothing failed and nothing warned; the work simply
    went somewhere nobody reads.

    Refusing is what makes the wrong location impossible rather than
    merely documented, so this test pins the refusal, not the message.
    """
    with pytest.raises(ValueError, match="registry path"):
        tickets.ticket_dir(tmp_path, "theory", theory="insider_judgment")

    with pytest.raises(ValueError, match="registry path"):
        tickets.create(tmp_path, lane="theory", theory="insider_judgment",
                       slug="x", title="x", body="x")

    assert not (tmp_path / "theories" / "insider_judgment").exists(), (
        "a refused theory ticket must not leave a phantom directory behind")


def test_the_cli_files_a_theory_ticket_under_its_registry_path(
        tmp_path, monkeypatch, capsys):
    """The other half of the guard, end to end.

    `ticket_dir` can only refuse what reaches it. This pins that the CLI
    -- the one production caller -- looks the theory up in the registry
    instead of assuming its folder is named after its slug, by filing a
    real ticket for a theory whose path does NOT match its slug and
    checking where it lands.
    """
    from tools import cli, db, theories

    root = tmp_path / "repo"
    (root / "theories" / "fam" / "child").mkdir(parents=True)
    monkeypatch.setattr(db, "REPO_ROOT", root)

    dbpath = tmp_path / "t.db"
    conn = db.connect(dbpath)
    db.init_db(conn)
    # Path deliberately unlike the slug, as insider_judgment's is.
    theories.register(conn, "child", "Child", "theories/fam/child",
                      now="2026-09-01T00:00:00Z")
    conn.close()

    assert cli.main(["--db", str(dbpath), "tickets", "new",
                     "--lane", "theory", "--theory", "child",
                     "--slug", "s", "--title", "T", "--body", "B",
                     "--session", "test"]) == 0
    capsys.readouterr()

    assert (root / "theories" / "fam" / "child" / "tickets" / "open"
            ).exists(), "the ticket must land inside the theory's folder"
    assert not (root / "theories" / "child").exists(), (
        "filing by slug would create a phantom directory beside the theory")


# --- the lane's directory is named for the lane ----------------------------


def test_the_new_theory_lane_lives_in_a_directory_named_for_it(repo):
    """`--lane new-theory` files into `tickets/new-theory/`, not `research/`.

    The directory used to be called `research`, so every session had to
    know that the lane `new-theory` and the folder `research` were the
    same thing. Nothing gained by the translation, and a reader looking
    for "the new-theory backlog" had to be told where it was.
    """
    path = tickets.create(
        repo, lane="new-theory", slug="vol-crossing",
        title="barrier-option model for crossing markets",
        body="Mechanism, population, kill criteria.",
        created="2026-08-24", created_by="llm-7a",
    )
    assert path.relative_to(repo).as_posix() == (
        "tickets/new-theory/open/2026-08-24-vol-crossing.md"
    )


def test_closing_a_new_theory_ticket_stays_inside_its_lane(repo):
    path = tickets.create(
        repo, lane="new-theory", slug="smile-smoothing", title="ladder shape",
        body="Fit a monotone curve; bet the deviant strike.",
        created="2026-08-24", created_by="llm-7a",
    )
    done = tickets.close(path, resolution="Dead: 97.6% of rungs sat on the fit.",
                         now="2026-08-29")
    assert done.relative_to(repo).as_posix() == (
        "tickets/new-theory/completed/2026-08-24-smile-smoothing.md"
    )


# --- the brief listing -----------------------------------------------------


def test_the_brief_backlog_carries_identity_without_bodies(repo):
    """A session choosing work needs to see every ticket, not read them.

    The backlog is read at the start of every session. Once tickets
    carry full spec content it runs to hundreds of KB, so the listing
    that everyone runs must be the cheap one: what each ticket is, and
    enough to decide whether to open it.
    """
    tickets.create(
        repo, lane="new-theory", slug="whale-follow",
        title="mirror proven Polymarket wallets into matched Kalshi markets",
        body="X" * 8000, created="2026-08-24", created_by="llm-7a",
        author_context="found while surveying the board",
    )
    brief = tickets.backlog(repo, brief=True)
    assert len(brief) == 1
    entry = brief[0]
    assert entry["slug"] == "whale-follow"
    assert entry["title"].startswith("mirror proven Polymarket")
    assert entry["lane"] == "new-theory"
    assert entry["created"] == "2026-08-24"
    assert "body" not in entry
    assert entry["body_chars"] == 8000


def test_the_brief_backlog_reports_a_malformed_ticket_too(repo):
    """A ticket nobody can parse is still work nobody will do."""
    bad = repo / "tickets" / "new-theory" / "open" / "2026-08-24-broken.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("no frontmatter here", encoding="utf-8")
    brief = tickets.backlog(repo, brief=True)
    assert [e["slug"] for e in brief] == ["broken"]
    assert brief[0]["malformed"] is True


def test_the_full_backlog_still_carries_the_body(repo):
    tickets.create(
        repo, lane="new-theory", slug="vol-crossing", title="barrier model",
        body="The whole spec.", created="2026-08-24", created_by="llm-7a",
    )
    full = tickets.backlog(repo)
    assert full[0]["body"] == "The whole spec."


def test_the_brief_render_is_one_line_per_ticket(repo):
    for n, slug in enumerate(("aggregation-gap", "vol-crossing")):
        tickets.create(
            repo, lane="new-theory", slug=slug, title=f"title {n}",
            body="Y" * 5000, created="2026-08-24", created_by="llm-7a",
        )
    tickets.create(
        repo, lane="maintenance", slug="http-429", title="backoff",
        body="Z" * 5000, created="2026-08-31", created_by="llm-7a",
    )
    text = tickets.render(tickets.backlog(repo, brief=True))
    assert "aggregation-gap" in text and "http-429" in text
    # Cheap is the whole point: the three bodies alone are 15,000 chars.
    assert len(text) < 1000
