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
