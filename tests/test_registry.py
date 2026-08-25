import pytest

from tools import db, registry, theories

TS = "2026-08-24T12:00:00Z"


def test_discover_finds_both_real_theories():
    found = registry.discover()
    assert set(found) >= {"insider_judgment", "mention_family"}
    assert found["insider_judgment"].version == 3
    assert found["insider_judgment"].uses_llm_judgment is True
    assert found["mention_family"].uses_llm_judgment is False


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


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    yield c
    c.close()


def _register_matching(conn):
    for tid, name, version, uses in (
        ("insider_judgment", "Insider Judgment", 3, True),
        ("mention_family", "Mention Family", 1, False),
    ):
        theories.register(conn, tid, name, f"theories/{tid}", now=TS)
        with db.write(conn):
            conn.execute("UPDATE theories SET version=?, status='testing'"
                         " WHERE id=?", (version, tid))
        theories.set_uses_llm_judgment(conn, tid, uses, now=TS)


def test_check_drift_is_empty_when_code_and_db_agree(conn):
    _register_matching(conn)
    assert registry.check_drift(conn) == []


def test_check_drift_catches_all_four_mismatch_kinds(conn):
    # 1. class with no DB row (nothing registered yet)
    problems = registry.check_drift(conn)
    assert any("no DB registry row" in p for p in problems)

    _register_matching(conn)

    # 2. version disagreement
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='mention_family'")
    assert any("version" in p for p in registry.check_drift(conn))
    with db.write(conn):
        conn.execute("UPDATE theories SET version=1"
                     " WHERE id='mention_family'")

    # 3. uses_llm_judgment disagreement
    theories.set_uses_llm_judgment(conn, "mention_family", True, now=TS)
    assert any("uses_llm_judgment" in p for p in registry.check_drift(conn))
    theories.set_uses_llm_judgment(conn, "mention_family", False, now=TS)

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
    assert ids == ["insider_judgment", "mention_family"]
    with db.write(conn):
        conn.execute("UPDATE theories SET version=99"
                     " WHERE id='mention_family'")
    with pytest.raises(RuntimeError, match="drift"):
        registry.running(conn)
