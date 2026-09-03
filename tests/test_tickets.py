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

from tools import db, ideas, tickets


@pytest.fixture()
def conn(tmp_path):
    """A real ideas registry. Closing a `new-theory` spec `disproven` or
    `underpowered` reads this, so the tests that cover that coupling need
    a database rather than a stub."""
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()


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


def test_close_refuses_a_study_ticket_and_leaves_it_untouched(tmp_path):
    """The bug this guards against: close() assumed a flat file at
    `<state_dir>/<name>.md` and a lane with a `completed/` state. Called
    on a study's STUDY.md it used to compute
    `path.parent.parent / "completed"` -- for a study filed as
    `.../question/<slug>/STUDY.md` that resolves to `question/`, the
    study's own current state directory, not the lane root -- and wrote
    an orphaned `question/completed/STUDY.md`, deleted the original,
    stranded the study's sibling code/data under `question/`, and raised
    nothing, because the frontmatter still read `status: open`. This
    pins both the refusal and that nothing on disk moved."""
    path = tickets.create(
        tmp_path, lane="study", slug="entry-timing",
        title="Does entry timing matter?", body="Bar: 2pt net at n>=200.",
        created="2026-09-02",
    )
    sibling = path.parent / "collect.py"
    sibling.write_text("# collection code\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="advancing it to 'answer'"):
        tickets.close(path, resolution="Found nothing.")

    assert path.exists(), "the study must stay exactly where it was"
    assert path.read_text(encoding="utf-8") == before, "nothing rewritten"
    assert sibling.exists(), "sibling code/data must not be stranded"
    assert not (path.parent.parent / "completed").exists(), (
        "no orphaned completed/ under the study's own state directory"
    )
    assert not (tmp_path / "tickets" / "study" / "completed").exists(), (
        "the study lane must never grow a completed/ state"
    )


def test_close_still_works_on_a_maintenance_ticket(repo):
    path = tickets.create(repo, lane="maintenance", slug="b", title="B",
                          body="do b", created="2026-09-01")
    done = tickets.close(path, resolution="fixed")
    assert not path.exists()
    assert done.relative_to(repo).as_posix() == (
        "tickets/maintenance/completed/2026-09-01-b.md"
    )
    assert "fixed" in done.read_text(encoding="utf-8")


def test_close_still_works_on_a_theory_ticket(repo):
    path = tickets.create(
        repo, lane="theory", theory="insider_judgment",
        theory_path="theories/insider_bias/insider_judgment",
        slug="d", title="D", body="do d", created="2026-09-01",
    )
    done = tickets.close(path, resolution="fixed")
    assert not path.exists()
    assert done.relative_to(repo).as_posix() == (
        "theories/insider_bias/insider_judgment/tickets/completed/"
        "2026-09-01-d.md"
    )
    assert "fixed" in done.read_text(encoding="utf-8")


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


def test_closing_a_new_theory_ticket_removes_it_from_the_lane(repo, conn):
    """`smile-smoothing` is the repo's own worked example of `disproven`
    -- measured properly, and the answer was no -- so this closes the way
    a real one now has to: the registry row first, then the file goes.
    It grew a database for that reason and not because placement needs
    one."""
    path = tickets.create(
        repo, lane="new-theory", slug="smile-smoothing", title="ladder shape",
        body="Fit a monotone curve; bet the deviant strike.",
        created="2026-08-24", created_by="llm-7a",
    )
    ideas.record(conn, "smile-smoothing", "Ladder shape")
    ideas.update_status(conn, "smile-smoothing", "dead",
                        what_was_tried="isotonic fit over 959 rungs",
                        outcome="97.6% sat exactly on their own fit")
    done = tickets.close(path,
                         resolution="disproven: 97.6% of rungs sat on the fit.",
                         now="2026-08-29", conn=conn)
    assert done.relative_to(repo).as_posix() == (
        "tickets/new-theory/open/2026-08-24-smile-smoothing.md"
    )
    assert not done.exists(), "the spec leaves the tree; the registry keeps it"
    assert not (repo / "tickets" / "new-theory" / "completed").exists()


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


# --- backlog pressure -------------------------------------------------------
#
# "Are tickets a priority?" used to be re-litigated every session. These
# three pin the mechanical rule instead: a lane with five or more open
# tickets, or with even one ticket sitting open past 14 days, is flagged
# so a session has to take it or decline it with a reason, rather than
# silently skip it. `now` is passed explicitly in all three -- a test
# whose result depends on the day it happens to run is a test that fails
# mysteriously in three weeks.


def test_the_backlog_flags_a_lane_under_pressure(repo):
    for i in range(5):
        tickets.create(repo, lane="maintenance", slug=f"t{i}",
                       title=f"Ticket {i}", body="b", created="2026-09-01")
    out = tickets.render(tickets.backlog(repo, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" in out


def test_a_quiet_lane_is_not_flagged(repo):
    tickets.create(repo, lane="maintenance", slug="only", title="T",
                   body="b", created="2026-09-01")
    out = tickets.render(tickets.backlog(repo, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" not in out


def test_one_old_ticket_is_enough_to_flag_a_lane(repo):
    tickets.create(repo, lane="maintenance", slug="ancient", title="T",
                   body="b", created="2026-08-01")
    out = tickets.render(tickets.backlog(repo, brief=True),
                         now="2026-09-02")
    assert "PRESSURE" in out


# --- a study is a directory ticket, routed to the theory that owns it ------
#
# The old "a ticket about a study" concept -- a chore filed against a
# pre-existing study folder, at studies/<slug>/tickets/<state>/ -- is gone.
# A study IS the ticket now: creating one starts its own question/
# investigation/answer lifecycle, directory and all, exactly like a theory
# or a maintenance ticket starts its own open/completed one. The tests that
# pinned the old shape (`test_a_study_ticket_lands_in_that_studys_folder`,
# its "needs its study" / "no study" refusals, its backlog and close
# assertions on `studies/<slug>/tickets/...`) tested a concept this phase
# removes, so they were deleted rather than adapted -- see the commit
# message for the full accounting.


def test_a_study_owned_by_a_theory_lives_in_that_theory(tmp_path):
    got = tickets.ticket_dir(
        tmp_path, "study", theory="no_side_premium",
        theory_path="theories/no_side_premium", state="answer")
    assert got == tmp_path / "theories/no_side_premium/studies/answer"


def test_a_study_owned_by_nobody_lives_in_the_root_lane(tmp_path):
    got = tickets.ticket_dir(tmp_path, "study", state="investigation")
    assert got == tmp_path / "tickets/study/investigation"


def test_a_study_ticket_is_a_directory_holding_STUDY_md(tmp_path):
    path = tickets.create(
        tmp_path, lane="study", slug="entry-timing",
        title="Does entry timing matter?",
        body="Bar: a 2pt net difference at n>=200.",
        created="2026-09-02")
    assert path.name == "STUDY.md"
    assert path.parent.name == "2026-09-02-entry-timing"
    assert path.parent.parent.name == "question"
    assert path.read_text(encoding="utf-8").startswith("---\n")


def test_a_study_ticket_records_its_owning_theory(tmp_path):
    (tmp_path / "theories/no_side_premium").mkdir(parents=True)
    path = tickets.create(
        tmp_path, lane="study", slug="side-split",
        title="Does the side gap survive a tradeable book?",
        body="Bar: the gap holds at 100% coverage.",
        theory="no_side_premium",
        theory_path="theories/no_side_premium", created="2026-09-02")
    assert "theory: no_side_premium" in path.read_text(encoding="utf-8")
    assert path.parent.parent.parent.name == "studies"


def test_a_non_study_ticket_is_still_a_plain_file(tmp_path):
    path = tickets.create(
        tmp_path, lane="maintenance", slug="fix-thing", title="Fix it",
        body="Do the thing.", created="2026-09-02")
    assert path.name == "2026-09-02-fix-thing.md"
    assert path.parent.name == "open"


def test_the_backlog_finds_a_study_in_every_state(tmp_path):
    tickets.create(tmp_path, lane="study", slug="asked",
                   title="An open question", body="Bar: x.",
                   created="2026-09-02")
    rows = tickets.backlog(tmp_path, lane="study", status="open")
    assert [r["slug"] for r in rows] == ["asked"]
    assert rows[0]["state"] == "question"


def test_a_study_in_answer_is_reported_done_not_open(tmp_path):
    """The directory is the only source of truth for status.

    A study advanced into `answer/` never gets its frontmatter
    `status:` field rewritten -- nothing in this module does that for
    the study lane. If `backlog(status=...)` filtered on that stale
    field, a finished study would silently vanish from `--status done`
    and linger forever in `--status open`. `_scan` sets `entry["status"]`
    from the state directory precisely so the directory and the
    frontmatter can never disagree.
    """
    path = tickets.create(tmp_path, lane="study", slug="finished",
                          title="Is the gap real?", body="Bar: x.",
                          created="2026-09-01")
    answer_dir = tmp_path / "tickets" / "study" / "answer"
    answer_dir.mkdir(parents=True)
    path.parent.rename(answer_dir / path.parent.name)

    done = tickets.backlog(tmp_path, lane="study", status="done")
    assert [r["slug"] for r in done] == ["finished"]
    assert tickets.backlog(tmp_path, lane="study", status="open") == []


# --- per-lane states --------------------------------------------------------


def test_each_lane_declares_its_own_states():
    assert tickets.states_for("maintenance") == ("open", "completed")
    assert tickets.states_for("theory") == ("open", "completed")
    assert tickets.states_for("study") == ("question", "investigation",
                                           "answer")


def test_an_unknown_lane_has_no_states():
    with pytest.raises(ValueError, match="unknown lane"):
        tickets.states_for("nonsense")


def test_the_study_lane_has_no_completed_state():
    """Permanence is a consequence of the state names, not an exemption
    the purge has to remember: a finished study lives in `answer/`, so a
    query for `completed/` simply never matches one."""
    assert "completed" not in tickets.states_for("study")


def test_a_lane_refuses_a_state_belonging_to_another_lane(tmp_path):
    with pytest.raises(ValueError, match="has no state 'answer'"):
        tickets.ticket_dir(tmp_path, "maintenance", state="answer")
    with pytest.raises(ValueError, match="has no state 'open'"):
        tickets.ticket_dir(tmp_path, "study", state="open")


def test_omitting_the_state_uses_the_lanes_first(repo):
    # A study lane ticket_dir call no longer needs an existing study on
    # disk -- ownership is decided by theory/theory_path, not by a study
    # slug pointing at a folder -- so this isolates exactly what it says:
    # state=None resolving to the lane's first declared state.
    assert tickets.ticket_dir(repo, "maintenance").name == "open"
    assert tickets.ticket_dir(repo, "study").name == "question"


# --- advance: moving a ticket to its next state -----------------------------


def test_advance_moves_a_study_to_the_next_state(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="entry-timing",
                          title="Does entry timing matter?",
                          body="Bar: 2pt net at n>=200.", created="2026-09-02")
    moved = tickets.advance(path, to="investigation",
                            note="Collecting 60 days of candles.",
                            now="2026-09-03")
    assert moved.parent.parent.name == "investigation"
    assert not path.parent.exists()
    assert "Collecting 60 days of candles." in moved.read_text(encoding="utf-8")


def test_advance_carries_the_whole_directory(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="probe",
                          title="Q", body="Bar: x.", created="2026-09-02")
    (path.parent / "collect.py").write_text("# code\n", encoding="utf-8")
    moved = tickets.advance(path, to="investigation", note="Running.",
                            now="2026-09-03")
    assert (moved.parent / "collect.py").is_file()


def test_advance_refuses_a_state_the_lane_does_not_have(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    with pytest.raises(ValueError, match="has no state 'completed'"):
        tickets.advance(path, to="completed", note="nope")


def test_advance_refuses_to_go_backwards(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    moved = tickets.advance(path, to="answer", note="Done.", now="2026-09-03")
    with pytest.raises(ValueError, match="cannot move backwards"):
        tickets.advance(moved, to="question", note="reopening")


def test_advance_requires_a_note(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="q", title="Q",
                          body="Bar: x.", created="2026-09-02")
    with pytest.raises(ValueError, match="a note is required"):
        tickets.advance(path, to="investigation", note="  ")


# --- advance must never be the way into completed/ -------------------------
#
# The deletion bug, and why these two guards are separate. Before
# `advance()` existed, `close()` was the ONLY route into `completed/` and
# it rewrote `status: open` -> `status: done` as it moved the file, so
# "already completed" and "not open" were the same fact -- one guard
# covered both. `advance()` broke that equivalence: it moved a file-based
# ticket into `completed/` with its frontmatter untouched, whereupon
# `close()` computed `path.parent.parent / "completed"` (the directory the
# file was already in), wrote the closed copy over the source, and
# `path.unlink()`ed that same path. The ticket was DELETED, exit code 0,
# `close()` returned a path that did not exist, and `completed/` was
# empty. Reachable with two ordinary CLI calls.


def test_advance_refuses_to_move_a_maintenance_ticket_into_completed(repo):
    path = tickets.create(repo, lane="maintenance", slug="a", title="A",
                          body="do a", created="2026-09-01")
    with pytest.raises(ValueError, match="close"):
        tickets.advance(path, to="completed", note="done I think")

    assert path.exists(), "the ticket must not have moved"
    assert path.relative_to(repo).as_posix() == (
        "tickets/maintenance/open/2026-09-01-a.md"
    )
    assert not (repo / "tickets" / "maintenance" / "completed").exists(), (
        "advance() must not even create the terminal directory")


def test_advance_refuses_to_move_a_theory_ticket_into_completed(repo):
    path = tickets.create(
        repo, lane="theory", theory="insider_judgment",
        theory_path="theories/insider_bias/insider_judgment",
        slug="d", title="D", body="do d", created="2026-09-01")
    with pytest.raises(ValueError, match="close"):
        tickets.advance(path, to="completed", note="done I think")

    assert path.exists()
    assert path.relative_to(repo).as_posix() == (
        "theories/insider_bias/insider_judgment/tickets/open/2026-09-01-d.md"
    )
    assert not (repo / "theories" / "insider_bias" / "insider_judgment"
                / "tickets" / "completed").exists()


def test_close_refuses_a_ticket_already_in_completed_and_keeps_the_file(repo):
    """The second, independent guard. Even if something else puts a
    ticket in `completed/`, closing it must not overwrite-then-delete it."""
    path = tickets.create(repo, lane="maintenance", slug="a", title="A",
                          body="do a", created="2026-09-01")
    done = tickets.close(path, resolution="fixed")
    before = done.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="already in completed"):
        tickets.close(done, resolution="fixed again")

    assert done.exists(), "closing twice must never delete the ticket"
    assert done.read_text(encoding="utf-8") == before, "nothing rewritten"
    assert tickets.backlog(repo, status="done")[0]["slug"] == "a"


def test_the_deletion_path_is_closed_end_to_end(repo):
    """advance-then-close, the exact two calls that used to delete a
    ticket. Whichever guard fires, the file survives."""
    path = tickets.create(repo, lane="maintenance", slug="a", title="A",
                          body="do a", created="2026-09-01")
    with pytest.raises(ValueError):
        tickets.advance(path, to="completed", note="x")
    with pytest.raises(ValueError):
        tickets.close(tickets.close(path, resolution="y"),
                      resolution="y again")
    survivors = tickets.backlog(repo, status="done")
    assert [t["slug"] for t in survivors] == ["a"]


# --- malformed means something different for a study -----------------------


def test_a_study_without_frontmatter_is_not_malformed(tmp_path):
    """12 of the 15 studies migrated on 2026-09-01 carry no ticket
    frontmatter -- a STUDY.md is a study document first and a ticket
    second. Flagging them made `tickets list --lane study --status done`
    print 12 `!! MALFORMED` rows with blank titles, which is a permanent
    false positive on the one signal that exists so a genuinely
    unreadable ticket is visible."""
    folder = tmp_path / "tickets" / "study" / "answer" / "2026-08-27-probe"
    folder.mkdir(parents=True)
    (folder / "STUDY.md").write_text(
        "# Do calendar arbs ever fire?\n\n"
        "**Tier:** A -- **Verdict:** they do not\n",
        encoding="utf-8")

    entry = tickets.backlog(tmp_path, lane="study", status="done")[0]
    assert entry["malformed"] is False
    assert entry["title"] == "Do calendar arbs ever fire?", (
        "the `# ` heading is the title when there is no frontmatter")
    assert entry["slug"] == "probe"
    assert "!! MALFORMED" not in tickets.render([entry])


def test_a_file_based_ticket_without_frontmatter_is_still_malformed(repo):
    """The alarm has to keep working where the frontmatter genuinely IS
    the ticket: a maintenance ticket has nowhere else to record its
    title, lane or author context."""
    bad = repo / "tickets" / "maintenance" / "open" / "2026-08-31-broken.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("# Not frontmatter, just a heading\n", encoding="utf-8")

    entry = [t for t in tickets.backlog(repo) if t["slug"] == "broken"][0]
    assert entry["malformed"] is True


# --- the status field must not come back -----------------------------------


def test_a_new_study_carries_no_status_field(tmp_path):
    """The defect this pipeline existed to remove, regenerated inside
    the change that removed it. Nothing rewrites a study's frontmatter --
    `advance()` renames the directory and touches no fields -- so a
    `status: open` written at creation would read `open` forever, next to
    a directory saying `answer`. That is series-bias-mining's
    `**Status:** complete` against two open tickets, one layer down."""
    path = tickets.create(
        tmp_path, lane="study", slug="entry-timing", title="Q",
        body="Bar: x.", created="2026-09-02")
    assert "status:" not in path.read_text(encoding="utf-8")

    moved = tickets.advance(path, to="answer", note="Done.", now="2026-09-03")
    assert "status:" not in moved.read_text(encoding="utf-8")
    assert tickets.backlog(tmp_path, lane="study", status="done")[0][
        "state"] == "answer"


def test_a_maintenance_ticket_still_carries_status_open(tmp_path):
    """The file-based lanes keep the field: `close()` rewrites it in the
    same operation that moves the file, so the two cannot drift."""
    path = tickets.create(
        tmp_path, lane="maintenance", slug="a", title="A", body="do a",
        created="2026-09-02")
    assert "status: open" in path.read_text(encoding="utf-8")
    done = tickets.close(path, resolution="fixed")
    assert "status: done" in done.read_text(encoding="utf-8")


def test_no_study_on_disk_carries_a_status_field():
    """The migrated files, not a fixture. Two of the 17 were written with
    `status: open` by `create()` before the exception above existed."""
    from tools import db

    offenders = [
        str(p.relative_to(db.REPO_ROOT)).replace("\\", "/")
        for p in db.REPO_ROOT.rglob("STUDY.md")
        if ".git" not in p.parts
        and any(line.startswith("status:")
                for line in p.read_text(encoding="utf-8",
                                        errors="replace").splitlines())
    ]
    assert offenders == [], (
        "a study's state is its directory; a status field can only drift "
        "from it, which is the defect this pipeline removed")


# --- a ticket in an unrecognised state directory ---------------------------


def test_advance_names_the_directory_when_the_state_is_unrecognised(repo):
    """A bare `tuple.index()` raised `x not in tuple` and named neither
    the directory nor the lane."""
    stray = repo / "tickets" / "maintenance" / "wip"
    stray.mkdir(parents=True)
    path = stray / "2026-09-01-a.md"
    path.write_text("---\ntitle: A\nstatus: open\n---\n\ndo a\n",
                    encoding="utf-8")
    with pytest.raises(ValueError, match="wip"):
        tickets.advance(path, to="open", note="back to the backlog")


# --- a new-theory spec earns its way to a build order ----------------------


def test_the_new_theory_lane_ends_at_a_build_order():
    """`build/` IS the terminal state, and it means READY TO IMPLEMENT.

    A spec that clears its bar sits there as an approved build order
    until somebody builds it. There is deliberately nothing after it:
    the two things a finished spec can be -- built, or dead -- both
    LEAVE the lane rather than pile up in a directory whose name says
    neither, which is what `completed/` did until 2026-09-02.
    """
    assert tickets.states_for("new-theory") == ("open", "evidence", "build")


def test_the_new_theory_lane_has_no_completed_state():
    """The same shape as the study lane, for the same reason: `purge`
    matches `completed/`, so a lane that declares none cannot have its
    specs quietly aged out of the working tree."""
    assert "completed" not in tickets.states_for("new-theory")


def test_a_spec_advances_open_to_evidence_to_build(tmp_path):
    path = tickets.create(
        tmp_path, lane="new-theory", slug="some-thesis",
        title="A thesis", body="The mechanism, the population, the bar.",
        created="2026-09-02")
    at_evidence = tickets.advance(
        path, to="evidence", note="Probing dispersion on one board.",
        now="2026-09-03")
    assert at_evidence.parent.name == "evidence"
    at_build = tickets.advance(
        at_evidence, to="build", note="Cleared the bar at n=240.",
        now="2026-09-04")
    assert at_build.parent.name == "build"


def test_a_spec_cannot_skip_the_evidence_stage(tmp_path):
    """The evidence stage is not optional for a spec nobody has measured.
    Jumping straight to a build order is exactly how a theory gets built
    on a thesis that was never tested."""
    path = tickets.create(
        tmp_path, lane="new-theory", slug="unmeasured", title="T",
        body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="evidence"):
        tickets.advance(path, to="build", note="skipping")


def test_advance_refuses_completed_for_new_theory(tmp_path):
    """`completed` is not a state this lane has any more, so the generic
    unknown-state guard is what catches it -- no special case needed."""
    path = tickets.create(
        tmp_path, lane="new-theory", slug="x", title="T", body="b",
        created="2026-09-02")
    with pytest.raises(ValueError, match="no state 'completed'"):
        tickets.advance(path, to="completed", note="nope")


# --- four resolutions, and closing elevates the finding first ---------------


def test_a_new_theory_close_requires_a_known_resolution(tmp_path):
    path = tickets.create(tmp_path, lane="new-theory", slug="x", title="T",
                          body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="built|disproven|underpowered"):
        tickets.close(path, resolution="did not work out")


def test_built_and_superseded_need_no_registry_entry(tmp_path):
    path = tickets.create(tmp_path, lane="new-theory", slug="x", title="T",
                          body="b", created="2026-09-02")
    done = tickets.close(path, resolution="built: now theories/x")
    assert not done.exists()


def test_closing_a_new_theory_spec_deletes_it(tmp_path, conn):
    """A spec leaves this lane by being DELETED, not by being filed.

    Both exits already put the durable fact somewhere better than a
    markdown file: a kill elevates `what_was_tried`/`outcome` into the
    ideas registry (enforced below), and a build produces the theory
    itself. What `completed/` held after that was a second copy of a
    verdict the registry already owned -- and the copy drifted, which is
    how 16 of 16 specs ended up with resolutions that no longer parsed.
    Git keeps the file for anyone who wants the original prose.
    """
    ideas.record(conn, "gone", "Gone thesis")
    ideas.update_status(conn, "gone", "dead",
                        what_was_tried="replayed 90 days",
                        outcome="flat at executable prices")
    path = tickets.create(tmp_path, lane="new-theory", slug="gone",
                          title="T", body="b", created="2026-09-02")
    assert path.exists()
    done = tickets.close(path, resolution="disproven: flat", conn=conn)
    assert not done.exists()
    assert not path.exists()
    assert not (tmp_path / "tickets" / "new-theory" / "completed").exists()


def test_a_new_theory_spec_can_be_closed_from_build(tmp_path):
    """The ordinary happy path: a build order gets built, and the spec
    goes away because the theory is now its own record."""
    path = tickets.create(tmp_path, lane="new-theory", slug="shipped",
                          title="T", body="b", created="2026-09-02")
    at_evidence = tickets.advance(path, to="evidence", note="measuring",
                                  now="2026-09-03")
    at_build = tickets.advance(at_evidence, to="build", note="cleared",
                               now="2026-09-04")
    done = tickets.close(at_build, resolution="built: theories/shipped")
    assert not done.exists()


def test_disproven_refuses_without_an_ideas_entry(tmp_path, conn):
    """The purge may delete a completed spec after a week. That is only
    safe because the finding elevated OUT of the file first -- otherwise
    somebody re-proposes the same dead thesis in three weeks, which is
    exactly what the ideas registry exists to prevent."""
    path = tickets.create(tmp_path, lane="new-theory", slug="deadidea",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="ideas"):
        tickets.close(path, resolution="disproven: zero violations",
                      conn=conn)


def test_underpowered_needs_a_revisit_angle(tmp_path, conn):
    """`underpowered` means we could not tell, not that the thesis is
    dead -- so it is re-proposable, and the registry has to say what
    would have to change before anyone tries again."""
    ideas.record(conn, "thinpop", "Thin population thesis")
    ideas.update_status(conn, "thinpop", "parked",
                        what_was_tried="probed one board",
                        outcome="only 4 markets qualified")
    path = tickets.create(tmp_path, lane="new-theory", slug="thinpop",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="revisit_angle"):
        tickets.close(path, resolution="underpowered: 4 markets",
                      conn=conn)
    ideas.update_status(conn, "thinpop", "parked",
                        revisit_angle="retry when the series lists weekly")
    done = tickets.close(path, resolution="underpowered: 4 markets",
                         conn=conn)
    assert not done.exists()


def test_other_lanes_keep_free_text_resolutions(tmp_path):
    path = tickets.create(tmp_path, lane="maintenance", slug="x", title="T",
                          body="b", created="2026-09-02")
    done = tickets.close(path, resolution="not a bug, the caller was wrong")
    assert done.parent.name == "completed"


def test_disproven_refuses_without_a_connection_at_all(tmp_path):
    """No connection means nothing could have checked the registry, and a
    close that skips the check is a spec the purge may delete with its
    finding still only in the file."""
    path = tickets.create(tmp_path, lane="new-theory", slug="deadidea",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="database connection"):
        tickets.close(path, resolution="disproven: zero violations")


def test_a_disproven_close_needs_what_was_tried_and_an_outcome(tmp_path, conn):
    """A registry row that names the idea but records nothing learned is
    not the durable fact -- it is a placeholder that reads like one."""
    ideas.record(conn, "hollow", "Hollow entry")
    path = tickets.create(tmp_path, lane="new-theory", slug="hollow",
                          title="T", body="b", created="2026-09-02")
    with pytest.raises(ValueError, match="what_was_tried"):
        tickets.close(path, resolution="disproven: nothing there", conn=conn)
    ideas.update_status(conn, "hollow", "dead",
                        what_was_tried="measured one board")
    with pytest.raises(ValueError, match="outcome"):
        tickets.close(path, resolution="disproven: nothing there", conn=conn)
    ideas.update_status(conn, "hollow", "dead", outcome="zero violations")
    done = tickets.close(path, resolution="disproven: nothing there",
                         conn=conn)
    assert not done.exists()


def test_disproven_needs_no_revisit_angle(tmp_path, conn):
    """`disproven` is the one that does NOT stay re-proposable: the bar
    was met and the thesis failed, so there is nothing to say about
    trying again."""
    ideas.record(conn, "reallydead", "Really dead")
    ideas.update_status(conn, "reallydead", "dead",
                        what_was_tried="full-coverage replay",
                        outcome="flat at executable prices")
    path = tickets.create(tmp_path, lane="new-theory", slug="reallydead",
                          title="T", body="b", created="2026-09-02")
    # Case-insensitive, and the prose still fits after the colon.
    assert not tickets.close(path, resolution="Disproven: flat at the ask",
                             conn=conn).exists()


def test_the_slug_of_a_ticket_drops_its_dated_prefix(tmp_path):
    path = tickets.create(tmp_path, lane="new-theory", slug="some-thesis",
                          title="T", body="b", created="2026-09-02")
    assert tickets.slug_of(path) == "some-thesis"


def test_the_slug_of_a_study_is_its_directory(tmp_path):
    path = tickets.create(tmp_path, lane="study", slug="a-measurement",
                          title="T", body="b", created="2026-09-02")
    assert path.name == tickets.STUDY_FILE
    assert tickets.slug_of(path) == "a-measurement"


# --- the purge: long-completed, uncited tickets leave the working tree ------


def _completed_ticket(root, slug, closed):
    """A ticket that was closed on `closed`.

    Free-text resolution on the maintenance lane on purpose: the purge is
    about how long a ticket has sat in `completed/`, not about which lane
    put it there, and a `new-theory` close would drag the ideas-registry
    coupling into a test that is not about it.
    """
    path = tickets.create(root, lane="maintenance", slug=slug, title="T",
                          body="b", created=closed)
    return tickets.close(path, resolution="done", now=closed)


def test_purge_never_matches_a_new_theory_spec(tmp_path, conn):
    """Not by exemption -- by the state names. The lane declares no
    `completed/`, and the purge walk matches only `completed/`, so a
    spec is simply not a thing this query can reach. Same mechanism
    that makes a study permanent."""
    ideas.record(conn, "spec-a", "A thesis")
    ideas.update_status(conn, "spec-a", "dead", what_was_tried="measured",
                        outcome="nothing there")
    path = tickets.create(tmp_path, lane="new-theory", slug="spec-a",
                          title="T", body="b", created="2026-08-01")
    tickets.close(path, resolution="disproven: nothing there", conn=conn)
    result = tickets.purge(tmp_path, now="2026-09-02")
    assert result["purged"] == []
    assert not (tmp_path / "tickets" / "new-theory" / "completed").exists()


def test_purge_is_dry_run_by_default(tmp_path):
    """Deleting files must never be a side effect of a flag somebody
    forgot to pass."""
    path = _completed_ticket(tmp_path, "old-one", closed="2026-08-01")
    result = tickets.purge(tmp_path, now="2026-09-02")
    assert result["dry_run"] is True
    assert path.exists()
    assert str(path) in [p for p in result["purged"]]


def test_purge_keeps_a_ticket_something_cites(tmp_path):
    path = _completed_ticket(tmp_path, "cited-one", closed="2026-08-01")
    (tmp_path / "NOTES.md").write_text(
        "see 2026-08-01-cited-one for why\n", encoding="utf-8")
    result = tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert path.exists()
    assert any("cited-one" in k["path"] for k in result["kept"])


def test_purge_leaves_a_recent_ticket_alone(tmp_path):
    path = _completed_ticket(tmp_path, "fresh", closed="2026-09-01")
    tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert path.exists()


def test_purge_never_matches_a_study(tmp_path):
    """Not by exemption -- the study lane's terminal state is `answer/`,
    so a finished study is not a thing this query can match. If a study
    exemption ever appears in purge(), the design broke upstream."""
    study = tickets.create(tmp_path, lane="study", slug="a-study",
                           title="Q", body="bar", created="2026-01-01")
    answered = tickets.advance(study, to="answer", note="done",
                               now="2026-01-02")
    tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert answered.exists()


def test_purge_does_not_count_a_tickets_own_text_as_a_citation(tmp_path):
    """A completed ticket sits under `tickets/`, which is one of the
    globs the citation search reads -- so a ticket whose own body names
    its own slug would vouch for itself and never be purgeable. The
    search skips the candidate's own file."""
    path = tickets.create(tmp_path, lane="maintenance", slug="self-namer",
                          title="T", body="this is about self-namer",
                          created="2026-08-01")
    done = tickets.close(path, resolution="done", now="2026-08-01")
    result = tickets.purge(tmp_path, now="2026-09-02")
    assert str(done) in result["purged"]


def test_purge_applies_by_removing_the_file_from_git(tmp_path):
    """`--apply` really deletes, through `git rm`, so the removal is a
    commit somebody can find with `git log --diff-filter=D` rather than
    a file that merely stopped existing."""
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True)

    git("init", "-q")
    path = _completed_ticket(tmp_path, "goner", closed="2026-08-01")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    result = tickets.purge(tmp_path, apply=True, now="2026-09-02")
    assert result["dry_run"] is False
    assert str(path) in result["purged"]
    assert not path.exists()


def test_purge_apply_survives_one_unremovable_file(tmp_path):
    """One candidate `git rm` cannot remove must not abort the batch.

    `check=True` on the `git rm` call used to raise on the first failure
    -- an untracked file, say -- which meant every candidate processed
    earlier in the same loop was already deleted while everything after
    it was silently left alone: a partial application plus a traceback,
    unattended, inside the floor's receipt step. The fix collects
    failures instead of raising, so a file `git rm` cannot touch (here,
    one never added to the index) is reported in `result["failed"]`
    while every other candidate is still removed."""
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True)

    git("init", "-q")
    tracked = _completed_ticket(tmp_path, "tracked-one", closed="2026-08-01")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")

    # Written after the commit and never `git add`-ed: git has no record
    # of it, so `git rm` on it fails exactly the way an untracked file
    # does in the wild.
    untracked = _completed_ticket(tmp_path, "untracked-one",
                                  closed="2026-08-01")

    result = tickets.purge(tmp_path, apply=True, now="2026-09-02")

    assert str(tracked) in result["purged"]
    assert not tracked.exists()

    assert untracked.exists()
    assert str(tracked) not in result["failed"] and result["failed"]
    failed_paths = [f["path"] for f in result["failed"]]
    assert str(untracked) in failed_paths
    assert str(untracked) not in result["purged"]

    rendered = tickets.render_purge(result, tmp_path)
    assert "FAILED" in rendered
    assert "untracked-one" in rendered
