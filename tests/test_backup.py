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


def test_backup_ledger_attaches_the_source_read_only(source, tmp_path,
                                                      monkeypatch):
    """The read-only guarantee is enforced by backup_ledger's own CODE, not
    by nobody happening to write -- that is what
    `test_attached_source_is_write_protected` above already proves about
    SQLite in general, on a hand-reproduced ATTACH, not on backup_ledger
    itself. This test pins the actual mechanism: monkeypatch
    `backup.sqlite3.connect` to capture every connection backup_ledger
    opens (via `factory=`, since `sqlite3.Connection` does not allow
    reassigning `execute` on an instance) and every `ATTACH DATABASE`
    call it issues, then assert the attaching connection was opened with
    `uri=True` (required, or the ATTACH URI below is parsed as a literal
    filename and the source attaches read-write) and that the ATTACH's
    own parameter is a `mode=ro` URI. It must fail at the commit that
    reverts `tools/backup.py` to a plain-path ATTACH, even though such a
    revert would still pass every behavioral test in this file."""
    connect_calls = []
    attach_params = []
    real_connect = sqlite3.connect

    class SpyConnection(sqlite3.Connection):
        def execute(self, sql, params=()):
            if "ATTACH DATABASE" in sql:
                attach_params.append(params)
            return super().execute(sql, params)

    def spy_connect(*args, **kwargs):
        connect_calls.append(kwargs)
        return real_connect(*args, factory=SpyConnection, **kwargs)

    monkeypatch.setattr(backup.sqlite3, "connect", spy_connect)
    backup.backup_ledger(source, tmp_path / "backups",
                         now="2026-08-29T12:00:00Z")

    assert attach_params, "backup_ledger must issue an ATTACH DATABASE call"
    assert any("mode=ro" in str(p) for p in attach_params), (
        f"ATTACH DATABASE parameters must be a mode=ro URI, got "
        f"{attach_params!r} -- a plain path attaches the source "
        "read-write and the read-only guarantee is gone"
    )

    # The connection ATTACH ran on must itself have been opened with
    # uri=True -- SQLite only honours a `file:...?mode=ro` URI on ATTACH
    # when the attaching connection was opened with URI filenames enabled.
    assert any(kwargs.get("uri") is True for kwargs in connect_calls), (
        "backup_ledger must open the attaching connection with uri=True, "
        "or the mode=ro ATTACH URI is taken as a literal filename"
    )


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
