"""Keep active research context bounded and its evidence reachable."""

from pathlib import Path
import re
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["Summary", "Applies to", "Finding", "Do next time", "Evidence",
          "Revisit when", "Updated"]


def _surfaces():
    cards = list((ROOT / "knowledge/lessons").glob("*.md"))
    maps = [ROOT / "knowledge/README.md", ROOT / "knowledge/theories.md",
            ROOT / "knowledge/archive/README.md"]
    maps += list((ROOT / "knowledge/topics").rglob("*.md"))
    for path in (ROOT / "theories").glob("**/learnings/**/*.md"):
        if "_TEMPLATE" in path.parts or "archive" in path.parts:
            continue
        (maps if path.name == "README.md" else cards).append(path)
    return maps, cards


def test_maps_and_lessons_have_bounded_reading_cost():
    maps, cards = _surfaces()
    assert maps and cards, "research memory must have discoverable content"
    for path in maps:
        text = path.read_text(encoding="utf-8")
        assert len(text.split()) <= 500, path
        entries = re.findall(r"^- \[.+", text, re.MULTILINE)
        assert len(entries) <= 12, path
        for entry in entries:
            if " — " in entry:
                assert len(entry.split(" — ", 1)[1].split()) <= 30, path
    for path in cards:
        text = path.read_text(encoding="utf-8")
        assert len(text.split()) <= 180, path
        assert re.findall(r"^\*\*([^*]+):\*\*", text, re.MULTILINE) == FIELDS, path
        for field in FIELDS:
            assert re.search(rf"^\*\*{re.escape(field)}:\*\* \S.+$", text,
                             re.MULTILINE), (path, field)


def test_memory_navigation_and_evidence_links_resolve():
    maps, cards = _surfaces()
    for path in maps + cards:
        text = path.read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", text)
        assert links, path
        for link in links:
            if "://" in link:
                continue
            target = (path.parent / unquote(link).split("#", 1)[0]).resolve()
            assert target.is_relative_to(ROOT) and target.exists(), (path, link)


def test_active_logs_and_notes_do_not_regrow_into_full_archives():
    log = (ROOT / "RESEARCH_LOG.md").read_text(encoding="utf-8")
    assert len(log.split()) <= 800
    entries = re.split(r"(?m)^## ", log)[1:]
    assert len(entries) <= 8
    for entry in entries:
        body = re.sub(r"<!--.*?-->", "", entry, flags=re.DOTALL)
        assert len(body.split()) <= 80
    for path in (ROOT / "theories").glob("**/NOTES.md"):
        if "archive" in path.parts or "_TEMPLATE" in path.parts:
            continue
        assert len(path.read_text(encoding="utf-8").split()) <= 500, path
    for owner in (ROOT / "theories", ROOT / "tickets/study"):
        for path in owner.glob("**/notes/**/*.md"):
            if "archive" not in path.parts:
                assert len(path.read_text(encoding="utf-8").split()) <= 1200, path
