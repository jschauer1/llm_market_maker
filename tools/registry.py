"""Discovery: join each theory's code with its DB registry row.

Separation of authority (spec section 4.6): the database is the source of
truth for a theory's STATUS and VERSION; the Python class is the source of
truth for its PROCEDURE. running() joins them; check_drift() fails loudly
when they disagree, because silent drift lets a session run v3 code while
recording v2 rows -- the silent-merge failure the versioning rule exists
to prevent.

What is discovered: every folder under theories/ carrying a THEORY.md,
excluding _TEMPLATE and any folder that also carries STUDY.md -- a study
produces theories, not bets, and stays a plain script (spec section 4.5c).
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from tools import theories as theories_db
from tools.db import REPO_ROOT
from tools.theory import Theory

THEORIES_ROOT = REPO_ROOT / "theories"

#: Retired theories live here, and discovery never imports them. A
#: retired theory KEEPS its THEORY.md -- that document is the record of
#: what it claimed and how it decided -- but its code is deleted, so
#: `importlib.import_module` on it would raise. The subtree is skipped
#: by path, and `RETIRED.md` is checked as well so a retired theory
#: filed anywhere else is still excluded. Same shape as the STUDY.md
#: exclusion right below it, and for the same reason: a folder with a
#: THEORY.md that is not a runnable theory.
RETIRED_DIRNAME = "retired"
RETIRED_MARKER = "RETIRED.md"


def _theory_packages(root: Path = THEORIES_ROOT) -> list[str]:
    """Dotted module paths for every theory package under `root`."""
    out = []
    for marker in sorted(root.rglob("THEORY.md")):
        folder = marker.parent
        if folder.name == "_TEMPLATE" or (folder / "STUDY.md").exists():
            continue
        if (folder / RETIRED_MARKER).exists():
            continue
        rel = folder.relative_to(root.parent)
        if RETIRED_DIRNAME in rel.parts:
            continue
        out.append(".".join(rel.parts))
    return out


def discover() -> dict[str, Theory]:
    """Import every theory package and collect its THEORY singleton."""
    found: dict[str, Theory] = {}
    for module_path in _theory_packages():
        module = importlib.import_module(module_path)
        instance = getattr(module, "THEORY", None)
        if instance is None:
            raise RuntimeError(
                f"{module_path} has a THEORY.md but exposes no THEORY "
                "singleton; add `THEORY = <YourTheory>()` to its "
                "__init__.py, or mark the folder as a study with STUDY.md"
            )
        if not isinstance(instance, Theory):
            raise RuntimeError(f"{module_path}.THEORY is not a Theory")
        if instance.id in found:
            raise RuntimeError(f"duplicate theory id {instance.id!r}")
        found[instance.id] = instance
    return found


def check_drift(conn: sqlite3.Connection) -> list[str]:
    """Mismatches between code and DB. Empty means healthy.

    The class side is checked unconditionally; the DB side only for
    SCANNABLE_STATUSES -- a proposed or paused row legitimately has no
    code yet, but a scannable one with no class cannot run and a version
    or uses_llm_judgment disagreement records rows under the wrong
    procedure identity.
    """
    problems: list[str] = []
    by_id = discover()
    rows = {r["id"]: r for r in theories_db.list_theories(conn)}
    for tid, theory in sorted(by_id.items()):
        row = rows.get(tid)
        if row is None:
            problems.append(f"class {tid!r} has no DB registry row")
            continue
        if theory.version != row["version"]:
            problems.append(
                f"{tid}: class version {theory.version} != DB version "
                f"{row['version']}")
        if bool(theory.uses_llm_judgment) != bool(row["uses_llm_judgment"]):
            problems.append(
                f"{tid}: uses_llm_judgment ClassVar "
                f"{theory.uses_llm_judgment} != DB flag "
                f"{bool(row['uses_llm_judgment'])}")
    for tid, row in sorted(rows.items()):
        if (row["status"] in theories_db.SCANNABLE_STATUSES
                and tid not in by_id):
            problems.append(
                f"DB row {tid!r} is {row['status']} but has no class")
    return problems


def running(conn: sqlite3.Connection) -> list[Theory]:
    """Discovered theories restricted to SCANNABLE_STATUSES, drift-checked."""
    problems = check_drift(conn)
    if problems:
        raise RuntimeError("registry drift: " + "; ".join(problems))
    by_id = discover()
    return [by_id[r["id"]]
            for r in theories_db.list_theories(conn, running_only=True)
            if r["id"] in by_id]
