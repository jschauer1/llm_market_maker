"""Both apps must discover the same procedures without maintaining copies."""

from pathlib import Path
import json

import pytest

from tools import agent_setup


FRONTMATTER = "---\nname: probe\ndescription: Investigate a bounded question.\n---\n"


def canonical(root: Path, body: str = "Run the investigation.\n") -> Path:
    path = root / ".agents/skills/probe/SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FRONTMATTER + body, encoding="utf-8")
    return path


def test_check_reports_missing_discovery_without_writing(tmp_path):
    canonical(tmp_path)
    assert agent_setup.sync(tmp_path, check=True) == [".claude/skills/probe/SKILL.md"]
    assert not (tmp_path / ".claude").exists()


def test_generation_keeps_metadata_and_points_to_full_canonical_procedure(tmp_path):
    canonical(tmp_path, "The only authoritative procedure.\n")
    assert agent_setup.sync(tmp_path) == [".claude/skills/probe/SKILL.md"]
    wrapper = tmp_path / ".claude/skills/probe/SKILL.md"
    text = wrapper.read_text(encoding="utf-8")
    assert text.startswith(FRONTMATTER)
    assert ".agents/skills/probe/SKILL.md" in text
    assert "The only authoritative procedure." not in text
    stamp = wrapper.stat().st_mtime_ns
    assert agent_setup.sync(tmp_path) == []
    assert wrapper.stat().st_mtime_ns == stamp


def test_changed_discovery_metadata_is_detected_but_body_edits_need_no_sync(tmp_path):
    source = canonical(tmp_path)
    agent_setup.sync(tmp_path)
    source.write_text(FRONTMATTER + "Changed research procedure.\n", encoding="utf-8")
    assert agent_setup.sync(tmp_path, check=True) == []
    source.write_text(FRONTMATTER.replace("bounded", "new") + "Procedure.\n", encoding="utf-8")
    wrapper = tmp_path / ".claude/skills/probe/SKILL.md"
    before = wrapper.read_bytes()
    assert agent_setup.sync(tmp_path, check=True) == [".claude/skills/probe/SKILL.md"]
    assert wrapper.read_bytes() == before
    agent_setup.sync(tmp_path)
    assert "Investigate a new question." in wrapper.read_text(encoding="utf-8")


def test_old_resource_paths_resolve_and_unrelated_local_skills_survive(tmp_path):
    source = canonical(tmp_path)
    (source.parent / "brief.md").write_text("Canonical brief.\n", encoding="utf-8")
    local = tmp_path / ".claude/skills/personal/SKILL.md"
    local.parent.mkdir(parents=True)
    local.write_text("Unrelated local skill.\n", encoding="utf-8")
    agent_setup.sync(tmp_path)
    brief = tmp_path / ".claude/skills/probe/brief.md"
    assert ".agents/skills/probe/brief.md" in brief.read_text(encoding="utf-8")
    assert local.read_text(encoding="utf-8") == "Unrelated local skill.\n"
    assert agent_setup.sync(tmp_path, check=True) == []


def test_invalid_metadata_fails_before_any_wrapper_is_written(tmp_path):
    canonical(tmp_path)
    broken = tmp_path / ".agents/skills/z-broken/SKILL.md"
    broken.parent.mkdir(parents=True)
    broken.write_text("No discovery metadata.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        agent_setup.sync(tmp_path)
    assert not (tmp_path / ".claude").exists()


def test_removed_source_reports_orphan_and_only_removes_generated_file(tmp_path):
    source = canonical(tmp_path)
    agent_setup.sync(tmp_path)
    local = tmp_path / ".claude/skills/probe/notes.md"
    local.write_text("Personal notes.\n", encoding="utf-8")
    source.unlink()
    assert agent_setup.sync(tmp_path, check=True) == [".claude/skills/probe/SKILL.md"]
    assert (tmp_path / ".claude/skills/probe/SKILL.md").exists()
    agent_setup.sync(tmp_path)
    assert not (tmp_path / ".claude/skills/probe/SKILL.md").exists()
    assert local.read_text(encoding="utf-8") == "Personal notes.\n"


def test_missing_canonical_tree_never_removes_discovery_files(tmp_path):
    local = tmp_path / ".claude/skills/probe/SKILL.md"
    local.parent.mkdir(parents=True)
    local.write_text("Existing procedure.\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        agent_setup.sync(tmp_path)
    assert local.read_text(encoding="utf-8") == "Existing procedure.\n"


def test_repository_discovery_matches_the_canonical_sources():
    assert agent_setup.sync(agent_setup.REPO_ROOT, check=True) == []


def test_shared_bootstrap_fits_codex_automatic_instruction_budget():
    # The former 63 KB copy lost its second half at the default 32 KiB cap.
    root = agent_setup.REPO_ROOT
    assert (root / "AGENTS.md").stat().st_size < 32 * 1024


def test_cli_check_has_machine_readable_status_and_does_not_write(tmp_path, monkeypatch, capsys):
    canonical(tmp_path)
    monkeypatch.setattr(agent_setup, "REPO_ROOT", tmp_path)
    assert agent_setup.main(["--check"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False, "check": True, "changed": [".claude/skills/probe/SKILL.md"]
    }
    assert not (tmp_path / ".claude").exists()
    assert agent_setup.main([]) == 0
    capsys.readouterr()
    assert agent_setup.main(["--check"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True, "check": True, "changed": []
    }
