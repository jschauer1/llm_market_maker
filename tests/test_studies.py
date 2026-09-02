"""Studies, surveyed from disk — what exists, what it concluded, what stalled.

A study's verdict used to live only inside its own STUDY.md, which broke
the supervisor contract in CLAUDE.md: every fact a supervisor needs has
to surface in a shared structure. Fourteen studies meant fourteen files
to read before anyone could say what had been measured.

The survey reads the files rather than duplicating them into an index.
A hand-maintained index of documents that live elsewhere is exactly what
went stale on the theory spec tree -- 22 documents all claiming "not yet
proposed as a theory" weeks after four had become theories.
"""

from __future__ import annotations

import pytest

from tools import studies


@pytest.fixture()
def repo(tmp_path):
    def add(slug, header, *, body=""):
        d = tmp_path / "studies" / slug
        d.mkdir(parents=True)
        (d / "STUDY.md").write_text(header + "\n" + body, encoding="utf-8")
        return d

    add("2026-08-27-calendar-arb-firing-rate",
        "# calendar-arb does not fire, and its premise is false\n\n"
        "**Date:** 2026-08-27 · **Status:** complete · **Tier:** A · "
        "**Verdict:** do not build the spec as written")
    add("2026-08-30-parlay-markup",
        "# Parlay markup — pre-registration\n\n"
        "**Date:** 2026-08-30 · **Status:** collecting · **Tier:** A")
    return tmp_path


def test_the_survey_finds_every_study_with_its_title_and_status(repo):
    rows = {r["slug"]: r for r in studies.survey(repo)}
    assert set(rows) == {"2026-08-27-calendar-arb-firing-rate",
                         "2026-08-30-parlay-markup"}
    done = rows["2026-08-27-calendar-arb-firing-rate"]
    assert done["status"].startswith("complete")
    assert done["complete"] is True
    assert "calendar-arb does not fire" in done["title"]
    assert done["date"] == "2026-08-27"


def test_a_study_still_collecting_is_not_complete(repo):
    row = next(r for r in studies.survey(repo)
               if r["slug"] == "2026-08-30-parlay-markup")
    assert row["status"] == "collecting"
    assert row["complete"] is False


def test_the_verdict_is_carried_when_the_study_states_one(repo):
    row = next(r for r in studies.survey(repo)
               if r["slug"] == "2026-08-27-calendar-arb-firing-rate")
    assert row["verdict"] == "do not build the spec as written"


def test_a_directory_without_a_study_md_is_not_a_study(repo):
    (repo / "studies" / "__pycache__").mkdir()
    assert len(studies.survey(repo)) == 2


def test_a_study_with_no_status_line_is_reported_not_skipped(repo):
    d = repo / "studies" / "2026-09-01-undated"
    d.mkdir()
    (d / "STUDY.md").write_text("# no header at all", encoding="utf-8")
    row = next(r for r in studies.survey(repo) if r["slug"] == "2026-09-01-undated")
    assert row["status"] == ""
    assert row["complete"] is False


def test_render_is_one_line_per_study(repo):
    text = studies.render(studies.survey(repo))
    assert "calendar-arb-firing-rate" in text
    assert "parlay-markup" in text
    assert len(text.splitlines()) <= 6


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
        conn, "studies in flight: 2026-08-30-parlay-markup, collecting",
        root=repo) == []


def test_a_complete_study_is_not_required_in_the_report(repo):
    from tools import db, floor
    conn = db.connect(":memory:")
    db.init_db(conn)
    names = {c["name"] for c in floor.required_coverage(conn, root=repo)}
    assert "2026-08-27-calendar-arb-firing-rate" not in names
