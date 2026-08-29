import gzip
import sqlite3

import pytest

from tools import backup, db


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.db"
    conn = db.connect(path)
    db.init_db(conn)
    with db.write(conn):
        conn.execute(
            "INSERT INTO market_snapshots (platform, market_id, captured_at,"
            " title, raw_json) VALUES ('kalshi', 'T-1',"
            " '2026-08-29T00:00:00Z', 't', '{}')"
        )
        conn.execute(
            "INSERT INTO settlements (kalshi_ticker, result)"
            " VALUES ('T-1', 'yes')"
        )
    conn.close()
    return path


def test_backup_holds_every_table_except_snapshots(source, tmp_path):
    result = backup.backup_ledger(source, tmp_path / "backups",
                                  now="2026-08-29T12:00:00Z")
    assert result["path"].endswith(".db.gz")
    assert "settlements" in result["tables"]
    assert "market_snapshots" not in result["tables"]

    from pathlib import Path
    raw = gzip.decompress(Path(result["path"]).read_bytes())
    restored = tmp_path / "restored.db"
    restored.write_bytes(raw)
    conn = sqlite3.connect(restored)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "settlements" in names and "opportunities" in names
        assert "market_snapshots" not in names
        assert conn.execute(
            "SELECT COUNT(*) FROM settlements").fetchone()[0] == 1
    finally:
        conn.close()


def test_backup_never_writes_into_the_source_directory(source, tmp_path):
    result = backup.backup_ledger(source, tmp_path / "elsewhere")
    assert str(tmp_path / "elsewhere") in result["path"]
    assert not list(source.parent.glob("*.gz"))
