"""What a session can reach — the toolkit, read off disk.

`python -m tools.cli tools` prints this. It exists because CLAUDE.md used
to carry the inventory by hand and it went stale the way hand-maintained
inventories of generated things always do: ten modules of twenty-five
were named, so everything added afterwards was invisible to any session
that reasoned from the file rather than listing the directory. A tool a
session does not know about is a tool that does not get used.

So the list is generated, and each module supplies its own one-line
summary from its own docstring. That keeps the description next to the
code it describes, where it gets updated by the person changing the
behaviour rather than by someone auditing a file elsewhere.

`GROUPS` is a convenience for reading, and deliberately not a gate: a
module nobody has grouped still lists, under `other`. Presence is the
guarantee; grouping is a nicety. Getting that backwards would rebuild the
exact failure this replaced.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

#: Reading order, loosely "what is a session doing right now".
GROUP_ORDER = (
    "starting a session",
    "getting data",
    "recording",
    "measuring",
    "deciding what the user is told",
    "governance and memory",
    "the theory contract",
    "plumbing",
    "other",
)

GROUPS = {
    "tools/state.py": "starting a session",
    "tools/floor.py": "starting a session",
    "tools/board.py": "starting a session",
    # `go`'s Orient runs exactly four cheap reads -- floor status, lane
    # status, tickets list, state -- so these two belong beside the other
    # three rather than in the ungrouped fallback.
    "tools/lanes.py": "starting a session",
    "tools/tickets.py": "starting a session",
    "tools/studies.py": "starting a session",
    # Not a data source: it is read by `state`'s FRESHNESS panel so a
    # session orienting can see a long walk that stopped writing.
    "tools/collectors.py": "starting a session",
    "tools/kalshi/markets.py": "getting data",
    "tools/kalshi/history.py": "getting data",
    "tools/kalshi/cache.py": "getting data",
    "tools/polymarket/markets.py": "getting data",
    "tools/polymarket/trades.py": "getting data",
    "tools/snapshot.py": "getting data",
    "tools/match_market.py": "getting data",
    "tools/ladders.py": "getting data",
    "tools/ledger.py": "recording",
    "tools/db.py": "recording",
    "tools/provenance.py": "recording",
    "tools/judgments.py": "recording",
    "tools/backup.py": "recording",
    "tools/score.py": "measuring",
    "tools/evidence.py": "measuring",
    "tools/slices.py": "measuring",
    "tools/buckets.py": "measuring",
    "tools/book.py": "measuring",
    "tools/rank.py": "measuring",
    "tools/sizing.py": "measuring",
    "tools/promotion.py": "deciding what the user is told",
    "tools/positions.py": "deciding what the user is told",
    "tools/theories.py": "governance and memory",
    "tools/rulings.py": "governance and memory",
    "tools/ideas.py": "governance and memory",
    "tools/theory.py": "the theory contract",
    "tools/registry.py": "the theory contract",
    "tools/domain.py": "the theory contract",
    "tools/cli.py": "plumbing",
    "tools/atomic_write.py": "plumbing",
    "tools/filelock.py": "plumbing",
    "tools/http.py": "plumbing",
    "tools/timeutil.py": "plumbing",
    "tools/toolkit.py": "plumbing",
    "tools/agent_setup.py": "plumbing",
}


def _summary(path: Path) -> str:
    """The module's docstring first line, or "" if it has none.

    Parsed rather than imported: listing the toolkit must never run a
    module's import side effects, and must keep working when one of them
    is broken -- a session asking what tools exist is often a session
    trying to find out why something is broken.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return ""
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def list_tools() -> list[dict]:
    """Every module under `tools/`, with its group and its own summary.

    Sorted by `GROUP_ORDER`, then by module path. `__init__.py` is
    excluded (it holds no callable surface); everything else is included
    whether or not anyone has grouped or documented it.
    """
    entries = []
    for path in sorted(_ROOT.rglob("*.py")):
        if "__pycache__" in str(path) or path.name == "__init__.py":
            continue
        module = str(path.relative_to(_ROOT.parent)).replace("\\", "/")
        entries.append({
            "module": module,
            "group": GROUPS.get(module, "other"),
            "summary": _summary(path),
        })
    order = {name: i for i, name in enumerate(GROUP_ORDER)}
    entries.sort(key=lambda e: (order.get(e["group"], len(order)), e["module"]))
    return entries


def render() -> str:
    """The listing as text, grouped with headers — for reading, not parsing."""
    lines: list[str] = []
    current = None
    for entry in list_tools():
        if entry["group"] != current:
            current = entry["group"]
            lines.append(f"\n{current.upper()}")
        lines.append(f"  {entry['module']:<30} {entry['summary']}")
    return "\n".join(lines).lstrip("\n")
