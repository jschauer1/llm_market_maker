"""The task loading map must cover the complete authoritative guide."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent


def test_every_guide_section_has_exactly_one_loading_rule():
    guide = (ROOT / "docs/RESEARCH_GUIDE.md").read_text(encoding="utf-8")
    mapping = ROOT / "docs/agents/policy-map.md"
    assert mapping.exists(), "task-scoped reading needs an explicit policy map"
    headings = re.findall(r"^## (.+)$", guide, re.MULTILINE)
    rows = re.findall(r"^\| `([^`]+)` \| ([^|]+) \|$",
                      mapping.read_text(encoding="utf-8"), re.MULTILINE)
    assert sorted(heading for heading, _ in rows) == sorted(headings)
    assert all(trigger.strip() for _, trigger in rows)


def test_a_moved_skill_rule_has_one_authoritative_owner():
    owners = {}
    for path in (ROOT / ".agents/skills").glob("*/SKILL.md"):
        for rule in re.findall(r"<!-- rule: (\S+) ", path.read_text(encoding="utf-8")):
            owners.setdefault(rule, []).append(path.parent.name)
    assert owners, "the moved rule inventory must not disappear"
    assert {rule: paths for rule, paths in owners.items() if len(paths) != 1} == {}
