"""Studies, surveyed from disk — what exists, what it concluded, what stalled.

A study's verdict used to live only inside its own STUDY.md, which broke
the supervisor contract in CLAUDE.md: every fact a supervisor needs has
to surface in a shared structure. Fourteen studies meant fourteen files
to read before anyone could say what had been measured.

The survey reads the files rather than duplicating them into an index.
A hand-maintained index of documents that live elsewhere is exactly what
went stale on the theory spec tree -- 22 documents all claiming "not yet
proposed as a theory" weeks after four had become theories.

A study's STATE is its directory, never a header field -- see
`test_a_status_header_is_ignored_entirely` for the incident that made
that non-negotiable.
"""

from __future__ import annotations

import pytest

from tools import studies


@pytest.fixture()
def repo(tmp_path):
    def add(where, slug, header, *, body=""):
        d = tmp_path / where / slug
        d.mkdir(parents=True)
        (d / "STUDY.md").write_text(header + "\n" + body, encoding="utf-8")
        return d

    add("tickets/study/answer", "2026-08-27-calendar-arb-firing-rate",
        "# calendar-arb does not fire, and its premise is false\n\n"
        "**Date:** 2026-08-27 · **Tier:** A · "
        "**Verdict:** do not build the spec as written")
    add("tickets/study/investigation", "2026-08-30-parlay-markup",
        "# Parlay markup — pre-registration\n\n"
        "**Date:** 2026-08-30 · **Tier:** A")
    add("theories/no_side_premium/studies/answer",
        "2026-09-01-side-split-60day-obs",
        "# Splitting the 60-day observation set by side\n\n"
        "**Date:** 2026-09-01 · **Tier:** A · **Verdict:** a composition "
        "artifact explains it")
    return tmp_path


def test_the_state_comes_from_the_directory_not_a_header(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-08-27-calendar-arb-firing-rate"]["state"] == "answer"
    assert rows["2026-08-30-parlay-markup"]["state"] == "investigation"


def test_only_an_answered_study_is_complete(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-08-27-calendar-arb-firing-rate"]["complete"] is True
    assert rows["2026-08-30-parlay-markup"]["complete"] is False


def test_a_study_carries_the_theory_that_owns_it(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert rows["2026-09-01-side-split-60day-obs"]["owner"] == "no_side_premium"
    assert rows["2026-08-30-parlay-markup"]["owner"] is None


def test_a_status_header_is_ignored_entirely(tmp_path):
    """The Status field is gone. A stale one left in a file must not be
    able to contradict the directory -- that contradiction is the exact
    failure this pipeline removes (series-bias-mining read 'complete'
    while two open tickets said the sweep was unfinished)."""
    d = tmp_path / "tickets/study/investigation" / "2026-08-29-stale"
    d.mkdir(parents=True)
    (d / "STUDY.md").write_text(
        "# Stale\n\n**Date:** 2026-08-29 · **Status:** complete · "
        "**Tier:** A\n", encoding="utf-8")
    row = studies.survey(tmp_path)[0]
    assert row["state"] == "investigation"
    assert row["complete"] is False
    assert "status" not in row


def test_the_render_names_the_owner(repo):
    out = studies.render(studies.survey(repo))
    assert "no_side_premium" in out


def test_the_survey_finds_every_study_with_its_title_and_date(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert set(rows) == {"2026-08-27-calendar-arb-firing-rate",
                         "2026-08-30-parlay-markup",
                         "2026-09-01-side-split-60day-obs"}
    done = rows["2026-08-27-calendar-arb-firing-rate"]
    assert "calendar-arb does not fire" in done["title"]
    assert done["date"] == "2026-08-27"


def test_the_verdict_is_carried_when_the_study_states_one(repo):
    row = next(r for r in studies.survey(repo)
               if r["slug"] == "2026-08-27-calendar-arb-firing-rate")
    assert row["verdict"] == "do not build the spec as written"


def test_a_directory_without_a_study_md_is_not_a_study(repo):
    (repo / "tickets/study/answer" / "__pycache__").mkdir()
    assert len(studies.survey(repo)) == 3


def test_render_is_one_line_per_study(repo):
    text = studies.render(studies.survey(repo))
    assert "calendar-arb-firing-rate" in text
    assert "parlay-markup" in text
    assert "side-split-60day-obs" in text


def test_render_says_so_when_there_are_no_studies(tmp_path):
    assert "no studies" in studies.render(studies.survey(tmp_path))


# --- the floor must name a study that is still in flight -------------------


def test_the_floor_requires_an_in_flight_study_to_be_named(repo, tmp_path):
    """Same guard sub-theories needed, for the same reason.

    An unfinished collector against Kalshi's ~60-day archive window is
    losing rows upstream while it sits. That stall has gone unnoticed
    twice; a name check on the daily report is the cheap fix.
    """
    from tools import db, floor
    conn = db.connect(":memory:")
    db.init_db(conn)
    required = floor.required_coverage(conn, root=repo)
    assert {c["name"] for c in required} == {"2026-08-30-parlay-markup"}
    assert required[0]["kind"] == "study"

    gaps = floor.coverage_gaps(conn, "nothing here", root=repo)
    assert [g["name"] for g in gaps] == ["2026-08-30-parlay-markup"]
    assert floor.coverage_gaps(
        conn, "studies in flight: 2026-08-30-parlay-markup, investigation",
        root=repo) == []


def test_a_complete_study_is_not_required_in_the_report(repo):
    from tools import db, floor
    conn = db.connect(":memory:")
    db.init_db(conn)
    names = {c["name"] for c in floor.required_coverage(conn, root=repo)}
    assert "2026-08-27-calendar-arb-firing-rate" not in names
