"""SQLite connection and schema management for the market edge finder.

Every connection enforces foreign keys and returns dict-like rows.
All timestamps produced here are UTC ISO-8601 with a trailing Z.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DB_PATH = REPO_ROOT / "db" / "market_edge.db"


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string, e.g. 2026-08-23T17:30:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and named row access."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables. Safe to call repeatedly."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
