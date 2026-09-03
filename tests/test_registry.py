import pytest

from tools import db, registry, theories

TS = "2026-08-24T12:00:00Z"


def test_discover_finds_the_real_theories():
    found = registry.discover()
    assert set(found) >= {"insider_judgment", "structural_arb"}
    assert found["insider_judgment"].version == 6
    assert found["insider_judgment"].uses_llm_judgment is True
    assert found["structural_arb"].uses_llm_judgment is False
    # `mention_family` was asserted here as the second real theory until
    # 2026-09-02, when it was retired and its code deleted. A retired
    # theory is deliberately NOT discoverable -- see
    # test_a_retired_theory_is_not_discovered below, which is now the
    # test that pins that half of the behaviour.
    assert "mention_family" not in found


def test_theory_packages_skips_template_and_studies(tmp_path):
    (tmp_path / "real_one").mkdir()
    (tmp_path / "real_one" / "THEORY.md").write_text("h", encoding="utf-8")
    (tmp_path / "_TEMPLATE").mkdir()
    (tmp_path / "_TEMPLATE" / "THEORY.md").write_text("t", encoding="utf-8")
    (tmp_path / "a_study").mkdir()
    (tmp_path / "a_study" / "THEORY.md").write_text("s", encoding="utf-8")
    (tmp_path / "a_study" / "STUDY.md").write_text("s", encoding="utf-8")
    got = registry._theory_packages(root=tmp_path)
    assert got == [f"{tmp_path.name}.real_one"]


def test_a_retired_theory_is_not_discovered(tmp_path):
    """A retired theory keeps its THEORY.md -- it is the record of what
    the theory claimed -- but its code is gone, so importing it would
    raise. Discovery has to skip the subtree, exactly as it already skips
    a folder marked STUDY.md."""
    root = tmp_path / "theories"
    (root / "retired" / "dead_theory").mkdir(parents=True)
    (root / "retired" / "dead_theory" / "THEORY.md").write_text(
        "# Dead\n", encoding="utf-8")
    (root / "retired" / "dead_theory" / "RETIRED.md").write_text(
        "# Retired\n", encoding="utf-8")
    assert registry._theory_packages(root) == []


def test_a_retired_marker_excludes_a_folder_wherever_it_sits(tmp_path):
    """Belt and braces: the path check catches the normal case, the
    marker catches a retired theory somebody files somewhere else."""
    root = tmp_path / "theories"
    (root / "stray").mkdir(parents=True)
    (root / "stray" / "THEORY.md").write_text("# Stray\n", encoding="utf-8")
    (root / "stray" / "RETIRED.md").write_text("# Retired\n", encoding="utf-8")
    assert registry._theory_packages(root) == []


def test_a_live_theory_beside_a_retired_one_is_still_discovered(tmp_path):
    root = tmp_path / "theories"
    (root / "retired" / "dead").mkdir(parents=True)
    (root / "retired" / "dead" / "THEORY.md").write_text("#\n", encoding="utf-8")
    (root / "retired" / "dead" / "RETIRED.md").write_text("#\n", encoding="utf-8")
    (root / "alive").mkdir(parents=True)
    (root / "alive" / "THEORY.md").write_text("#\n", encoding="utf-8")
    assert registry._theory_packages(root) == ["theories.alive"]


def _register_matching(conn):
    for tid, name, version, uses in (
        ("insider_judgment", "Insider Judgment", 6, True),
        ("structural_arb", "Structural Arb", 4, False),
        ("no_side_premium", "No-Side Premium", 1, False),
    ):
        theories.register(conn, tid, name, f"theories/{tid}", now=TS)
        with db.write(conn):
            conn.execute("UPDATE theories SET version=?, status='testing'"
                         " WHERE id=?", (version, tid))
        theories.set_uses_llm_judgment(conn, tid, uses, now=TS)
    # calibration_harvest joined the running set on 2026-08-29 and was
    # RETIRED by the user on 2026-09-01, on its own pre-registered kill
    # criterion. Its code was deleted on 2026-09-02 and its folder moved
    # to theories/retired/calibration_harvest, so `discover()` no longer
    # finds a class for it. It is registered here anyway, and precisely
    # because of that: a `retired` row with no class is NOT drift (retired
    # is not in SCANNABLE_STATUSES), and this fixture is the only place
    # that combination is exercised against the real repo. Registering it
    # as `testing` -- as this fixture did until the migration -- would
    # fail check_drift the moment the code was deleted, which is exactly
    # what the status field is for.
    theories.register(conn, "calibration_harvest", "Calibration Harvest",
                      "theories/retired/calibration_harvest", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET version=4, status='retired'"
                     " WHERE id='calibration_harvest'")
    theories.set_uses_llm_judgment(conn, "calibration_harvest", False, now=TS)
    # mention_family is the same shape and was moved here for the same
    # reason on 2026-09-02: retired by the user 2026-08-27, migrated to
    # theories/retired/mention_family and its code deleted, so discover()
    # finds no class. It stayed in the matching loop above as `testing`
    # for six days after the retirement -- which is exactly the drift the
    # status field exists to catch, and it went uncaught only because the
    # code was still sitting in the tree.
    theories.register(conn, "mention_family", "Mention Family",
                      "theories/retired/mention_family", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET version=1, status='retired'"
                     " WHERE id='mention_family'")
    theories.set_uses_llm_judgment(conn, "mention_family", False, now=TS)
    # taker_flow registered 2026-09-01 and is `testing`: fully mechanical,
    # its tier A replay over 3,585 settled decisions is recorded, and the
    # only positive population is the `extreme-imbalance` slice, which is
    # still accruing out-of-sample evidence.
    theories.register(conn, "taker_flow", "Taker Flow",
                      "theories/taker_flow", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET version=2, status='testing'"
                     " WHERE id='taker_flow'")
    theories.set_uses_llm_judgment(conn, "taker_flow", False, now=TS)
    # deadline_drift went `testing` at v2 on 2026-09-01: v1 shipped the
    # 70-series allowlist and recorded nothing, which measured -1.0 pts
    # over 22 event clusters -- no evidence either way rather than
    # evidence against. v2 ships DD-1's pre-registered population (the
    # by-deadline hazard stratum minus partition families, +4.6 in sample
    # over 94 clusters) and records observation rows so the out-of-sample
    # set accrues. `hazard_bins.json` is still absent by design, so
    # price() claims edge 0 and nothing here can promote to a bet.
    theories.register(conn, "deadline_drift", "Deadline Drift",
                      "theories/deadline_drift", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET version=2, status='testing'"
                     " WHERE id='deadline_drift'")
    theories.set_uses_llm_judgment(conn, "deadline_drift", False, now=TS)


def test_check_drift_is_empty_when_code_and_db_agree(conn):
    _register_matching(conn)
    assert registry.check_drift(conn) == []


def test_check_drift_catches_all_four_mismatch_kinds(conn):
    # 1. class with no DB row (nothing registered yet)
    problems = registry.check_drift(conn)
    assert any("no DB registry row" in p for p in problems)

    _register_matching(conn)

    # 2. version disagreement. Uses structural_arb, not mention_family as
    # it did until 2026-09-02: these two kinds compare a DB row against a
    # DISCOVERED class, so they need a theory that still has one, and
    # mention_family's was deleted at retirement.
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='structural_arb'")
    assert any("version" in p for p in registry.check_drift(conn))
    with db.write(conn):
        conn.execute("UPDATE theories SET version=4"
                     " WHERE id='structural_arb'")

    # 3. uses_llm_judgment disagreement
    theories.set_uses_llm_judgment(conn, "structural_arb", True, now=TS)
    assert any("uses_llm_judgment" in p for p in registry.check_drift(conn))
    theories.set_uses_llm_judgment(conn, "structural_arb", False, now=TS)

    # 4. scannable DB row with no class
    theories.register(conn, "ghost", "Ghost", "theories/ghost", now=TS)
    with db.write(conn):
        conn.execute("UPDATE theories SET status='testing' WHERE id='ghost'")
    assert any("ghost" in p for p in registry.check_drift(conn))


def test_a_proposed_row_without_code_is_not_drift(conn):
    _register_matching(conn)
    theories.register(conn, "someday", "Someday", "theories/someday", now=TS)
    assert registry.check_drift(conn) == []      # proposed: no code required


def test_running_returns_scannable_theories_and_raises_on_drift(conn):
    _register_matching(conn)
    ids = [t.id for t in registry.running(conn)]
    # calibration_harvest and mention_family are registered by the fixture
    # but `retired`, so both are absent here: running() is
    # SCANNABLE_STATUSES only.
    assert ids == ["deadline_drift", "insider_judgment",
                   "no_side_premium", "structural_arb", "taker_flow"]
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='structural_arb'")
    with pytest.raises(RuntimeError, match="drift"):
        registry.running(conn)
