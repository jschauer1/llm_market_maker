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


def test_attached_source_is_write_protected(source, tmp_path):
    """Reproduces backup_ledger's own ATTACH mechanism -- an `out` connection
    opened with uri=True, attaching the source via a `file:...?mode=ro` URI
    -- and proves SQLite itself rejects a write through the alias, rather
    than the read-only guarantee resting on nobody happening to write."""
    probe_path = tmp_path / "probe.db"
    conn = sqlite3.connect(f"file:{probe_path}", uri=True)
    try:
        conn.execute(
            "ATTACH DATABASE ? AS src", (f"file:{source}?mode=ro",)
        )
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO src.settlements (kalshi_ticker, result)"
                " VALUES ('T-2', 'no')"
            )
    finally:
        conn.close()


def test_backup_cleans_up_partial_artifacts_on_failure(
    source, tmp_path, monkeypatch
):
    """A failure partway through the gzip copy must not leave a partial
    .db or .gz behind for a later run or a restore to trip over."""
    dest = tmp_path / "backups"
    real_gzip_open = gzip.open

    class FlakyWriter:
        """Wraps a real gzip file, failing after its first write so the
        on-disk .gz is genuinely partial when the exception is raised."""

        def __init__(self, inner):
            self._inner = inner
            self._wrote = False

        def write(self, data):
            self._inner.write(data)
            if not self._wrote:
                self._wrote = True
                raise OSError("simulated failure mid-gzip")

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self._inner.close()
            return False

    def flaky_gzip_open(path, mode):
        return FlakyWriter(real_gzip_open(path, mode))

    monkeypatch.setattr(backup.gzip, "open", flaky_gzip_open)

    with pytest.raises(OSError):
        backup.backup_ledger(source, dest, now="2026-08-29T12:00:00Z")

    assert list(dest.glob("*.db")) == []
    assert list(dest.glob("*.gz")) == []
