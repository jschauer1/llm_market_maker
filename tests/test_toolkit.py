"""The toolkit listing — what a session can reach, generated from disk.

CLAUDE.md used to enumerate `tools/` by hand, which went stale
immediately: ten modules of twenty-five were named, so everything added
after it was written was invisible to any session that reasoned from the
file rather than reading the directory. A hand-maintained inventory of
generated things has one honest failure mode and it is always the same
one, so this generates it instead.

The bar: a module that exists is listed, whatever else is true of it.
Grouping is a convenience and may be missing; presence is not.
"""

from __future__ import annotations

import json

from tools import cli, toolkit


def test_every_module_on_disk_is_listed():
    listed = {t["module"] for t in toolkit.list_tools()}
    from pathlib import Path

    root = Path(toolkit.__file__).resolve().parent
    on_disk = {
        str(p.relative_to(root.parent)).replace("\\", "/")
        for p in root.rglob("*.py")
        if "__pycache__" not in str(p) and p.name != "__init__.py"
    }
    assert listed == on_disk


def test_subpackage_modules_are_listed_too():
    """The platform clients are the tools a session reaches for first."""
    listed = {t["module"] for t in toolkit.list_tools()}
    assert "tools/kalshi/markets.py" in listed
    assert "tools/polymarket/trades.py" in listed


def test_each_entry_carries_its_own_docstring_summary():
    by_module = {t["module"]: t for t in toolkit.list_tools()}
    assert by_module["tools/board.py"]["summary"].startswith(
        "One Kalshi board per session"
    )


def test_an_unmapped_module_still_lists_under_other():
    """A new tool must show up the day it lands. Grouping it is a nicety;
    hiding it until someone edits a map is the failure this replaced."""
    entries = toolkit.list_tools()
    assert all(t["group"] for t in entries)
    ungrouped = [t for t in entries if t["group"] == "other"]
    for t in ungrouped:
        assert t["summary"], "an unmapped tool still needs its summary"


def test_cli_tools_json_lists_every_module(capsys):
    code = cli.main(["tools", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert {t["module"] for t in payload} == {
        t["module"] for t in toolkit.list_tools()
    }


def test_cli_tools_defaults_to_text_grouped_for_reading(capsys):
    """`tools` is a read-this command like `state`, not a parse-this one."""
    code = cli.main(["tools"])
    out = capsys.readouterr().out
    assert code == 0
    assert not out.lstrip().startswith("[")
    assert "STARTING A SESSION" in out
    assert "tools/board.py" in out


def test_every_tool_has_a_docstring_to_summarize():
    """The listing is only as useful as what it reads. A module with no
    docstring appears with an empty summary, which is a real gap rather
    than a formatting nit -- it is a tool nobody can tell the purpose of."""
    missing = [t["module"] for t in toolkit.list_tools() if not t["summary"]]
    assert not missing, f"tools with no module docstring: {missing}"
