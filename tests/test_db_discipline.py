"""DB-usage discipline, held by scans instead of memory.

Each guard here encodes a documented, repeatedly-hit misuse of the data
layer (go-session-structure spec, 2026-08-30):

- the Kalshi board is pulled once per session through `tools.board.
  get_board` — direct `markets.list_open()` walks and `force=True` pulls
  outside the sanctioned call sites re-create the 2026-08-24 double-pull;
- every read of a snapshot payload goes through `tools.snapshot.
  payload_text` — a direct `json.loads(row["raw_json"])` breaks on any
  row written after the 2026-08-30 zlib overhaul;
- every running theory carries a standardized RUNBOOK.md, so "run the
  theory" has one meaning per theory instead of one per session.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import db, theories

ROOT = Path(__file__).resolve().parents[1]

# Production trees the board/payload rules bind. tests/ is excluded: unit
# tests exercise the underlying functions on purpose.
SCANNED_TREES = ("tools", "theories", "studies")

# The sanctioned direct users of the raw feeds.
LIST_OPEN_ALLOWED = {
    Path("tools/board.py"),          # the one board walk
    Path("tools/snapshot.py"),       # first-party capture
    Path("tools/kalshi/markets.py"),
    Path("tools/polymarket/markets.py"),
}
FORCE_ALLOWED = {
    Path("tools/board.py"),          # defines the parameter
}
PAYLOAD_ALLOWED = {
    Path("tools/snapshot.py"),       # defines payload_text
}

PAYLOAD_RE = re.compile(
    r"json\.loads\(\s*[\w\.]+\[[\"'](?:raw_json|event_json)[\"']\]"
)

# "## Sub-theories" is required even when a theory has none, and the
# section then says so. A sub-theory -- a theory over a SUBSET of this
# theory's data -- accrues its own evidence and can be strong while its
# parent is flat, so "run the theory" has to include evaluating them or a
# proven subset stays invisible. An absent section reads as "not
# applicable"; a section saying "none registered" reads as "checked".
RUNBOOK_HEADINGS = ("## Stages", "## Run", "## Record", "## Sub-theories",
                    "## Report", "## Skip")


def _calls_in_source(source: str, func_name: str, keyword: str | None = None):
    """Line numbers of calls to `func_name` — AST-based, so prose in
    docstrings and comments can never trip the guard."""
    import ast

    hits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else None)
        if name != func_name:
            continue
        if keyword is not None and not any(
            k.arg == keyword and isinstance(k.value, ast.Constant)
            and k.value.value is True for k in node.keywords
        ):
            continue
        hits.append(node.lineno)
    return hits


def find_call_offenders(
    func_name: str, allowed: set[Path], keyword: str | None = None
) -> list[str]:
    hits = []
    for tree in SCANNED_TREES:
        for path in sorted((ROOT / tree).rglob("*.py")):
            rel = path.relative_to(ROOT)
            if "__pycache__" in rel.parts or rel in allowed:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            for lineno in _calls_in_source(source, func_name, keyword):
                hits.append(f"{rel.as_posix()}:{lineno}")
    return hits


def find_pattern_offenders(pattern: re.Pattern, allowed: set[Path]) -> list[str]:
    hits = []
    for tree in SCANNED_TREES:
        for path in sorted((ROOT / tree).rglob("*.py")):
            rel = path.relative_to(ROOT)
            if "__pycache__" in rel.parts or rel in allowed:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                if pattern.search(line):
                    hits.append(f"{rel.as_posix()}:{lineno}: {line.strip()}")
    return hits


# --- the detectors themselves catch the documented failure shapes ----------


def test_detectors_flag_the_documented_misuses():
    assert _calls_in_source("b = kalshi_markets.list_open()", "list_open")
    assert _calls_in_source(
        "get_board(conn, force=True)", "get_board", keyword="force")
    assert not _calls_in_source(
        "get_board(conn)", "get_board", keyword="force")
    assert not _calls_in_source(
        '"""prose about self.list_open() in a docstring"""', "list_open")
    assert PAYLOAD_RE.search('json.loads(r["raw_json"])')
    assert PAYLOAD_RE.search("json.loads(row['event_json'])")
    assert not PAYLOAD_RE.search('json.loads(payload_text(r["raw_json"]))')


# --- repo scans ------------------------------------------------------------


def test_no_direct_list_open_outside_the_sanctioned_call_sites():
    hits = find_call_offenders("list_open", LIST_OPEN_ALLOWED)
    assert hits == [], (
        "direct markets.list_open() call(s) — go through "
        "tools.board.get_board(conn) (one board per session):\n"
        + "\n".join(hits)
    )


def test_no_forced_board_pull_in_production_code():
    hits = find_call_offenders("get_board", FORCE_ALLOWED, keyword="force")
    assert hits == [], (
        "get_board(force=True) outside go's Orient — the session's one "
        "deliberate refresh happens there and nowhere else:\n"
        + "\n".join(hits)
    )


def test_every_snapshot_payload_read_goes_through_payload_text():
    hits = find_pattern_offenders(PAYLOAD_RE, PAYLOAD_ALLOWED)
    assert hits == [], (
        "direct json.loads on a snapshot payload column — breaks on "
        "zlib rows written after 2026-08-30; use "
        "tools.snapshot.payload_text:\n" + "\n".join(hits)
    )


# --- runbooks --------------------------------------------------------------


def test_every_runbook_carries_the_standard_headings():
    missing = []
    for path in sorted((ROOT / "theories").rglob("RUNBOOK.md")):
        text = path.read_text(encoding="utf-8")
        for heading in RUNBOOK_HEADINGS:
            if not re.search(rf"^{re.escape(heading)}\b", text, re.M):
                missing.append(f"{path.relative_to(ROOT).as_posix()}: {heading}")
    assert missing == [], (
        "RUNBOOK.md files missing standard headings (go-session-structure "
        "spec §4):\n" + "\n".join(missing)
    )


def test_every_running_theory_has_a_runbook():
    """Against the real DB: 'run the theory' must have a written meaning.

    Read-only; skips on a fresh clone with no working database, same as
    test_conventions' drift check.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(f"{db.DEFAULT_DB_PATH} does not exist")
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, path FROM theories WHERE status IN "
            f"({','.join('?' * len(theories.SCANNABLE_STATUSES))})",
            theories.SCANNABLE_STATUSES,
        ).fetchall()
    finally:
        conn.close()
    missing = [
        f"{r['id']} ({r['path']})" for r in rows
        if not (ROOT / r["path"] / "RUNBOOK.md").exists()
    ]
    assert missing == [], (
        "running theories with no RUNBOOK.md — a theory cannot be in a "
        "scannable status without a written run procedure:\n"
        + "\n".join(missing)
    )
