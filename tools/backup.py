"""Ledger backup: every table except market_snapshots, gzipped.

The working database is one WAL-mode file inside a OneDrive sync root --
a total-loss single point of failure for the entire track record. The
snapshots are excluded because they are 98% of the bytes and rebuildable
in spirit (prices re-fetch; judgments and settlements do not).
"""

from __future__ import annotations

import gzip
import os
import sqlite3
from pathlib import Path

from tools.db import DEFAULT_DB_PATH, utcnow


def default_dest() -> Path:
    """A non-synced local directory: %LOCALAPPDATA%\\market_edge\\backups."""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "market_edge" / "backups"


def backup_ledger(
    source_path: str | Path = DEFAULT_DB_PATH,
    dest_dir: str | Path | None = None,
    now: str | None = None,
) -> dict:
    """Copy every table except market_snapshots into a gzipped SQLite file.

    Reads the source through a read-only URI so a backup can never write
    to the live database, and builds a real .db (not a text dump) so a
    restore is `gunzip` + open.
    """
    source_path = Path(source_path)
    dest_dir = Path(dest_dir) if dest_dir else default_dest()
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = (now or utcnow()).replace("-", "").replace(":", "").replace("Z", "")
    raw_path = dest_dir / f"market_edge_ledger_{stamp}.db"

    src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    out = sqlite3.connect(raw_path)
    tables: list[str] = []
    try:
        ddl_rows = src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%' AND name != 'market_snapshots'"
            " AND sql IS NOT NULL"
        ).fetchall()
        # Parameterized plain-path ATTACH: a `file:...?mode=ro` URI string
        # is only honoured when the connection enables URIs, and silently
        # opens a literal file named `file:...` otherwise. The read-only
        # guarantee lives on `src` above; this handle only SELECTs.
        out.execute("ATTACH DATABASE ? AS src", (str(source_path),))
        for row in ddl_rows:
            out.execute(row["sql"])
            out.execute(
                f'INSERT INTO main."{row["name"]}"'
                f' SELECT * FROM src."{row["name"]}"'
            )
            tables.append(row["name"])
        out.commit()
        out.execute("DETACH DATABASE src")
    finally:
        out.close()
        src.close()

    gz_path = raw_path.with_suffix(".db.gz")
    with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        while chunk := f_in.read(1 << 20):
            f_out.write(chunk)
    raw_path.unlink()
    return {
        "path": str(gz_path),
        "tables": sorted(tables),
        "bytes": gz_path.stat().st_size,
    }
