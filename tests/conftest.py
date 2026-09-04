"""Shared fixtures for the whole suite.

Three database tiers, because tests want three different things from a
database:

  `conn`        a working database, nothing more. The overwhelming
                majority of tests. Built by cloning a schema template into
                memory: 0.84ms, against the 55.5ms on-disk construction it
                replaces. Isolation is stronger than a temp file, not
                weaker -- the database is private and cannot outlive the
                test.

  `conn_disk`   a database that is genuinely a FILE, for the handful of
                tests whose subject IS file behaviour: backup, WAL,
                split_snapshots, legacy-schema migration, and anything
                where the code under test reopens the database by path.
                These are expected to stay slow. Their slowness is the
                thing they measure, so never "speed them up" by taking
                their files away -- that deletes the test while appearing
                to keep it.

  `db_file`     the path `conn_disk` uses, for tests that hand a path to
                the code under test.

**Tier is a per-test property, not a per-file one.** Several files hold
both kinds. Ask for what the test actually needs.

Plus `source_corpus`, which walks and reads the repo's .py and .md once per
session instead of once per scan test.

Requires Python 3.11+ for `sqlite3.Connection.serialize`/`deserialize`.

Design and measurements: docs/superpowers/specs/2026-09-02-test-suite-speed-design.md
"""

from __future__ import annotations

import shutil
import sqlite3
import sys

import pytest

from tools import db, theories

TS = "2026-08-23T12:00:00Z"

if sys.version_info < (3, 11):            # pragma: no cover - environment
    raise RuntimeError(
        "tests/conftest.py needs sqlite3.Connection.serialize (Python 3.11+)"
    )


# --------------------------------------------------------------------- #
# Tier 1: a private in-memory database, cloned from a session template
# --------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def _schema_blobs() -> tuple[bytes, bytes]:
    """The initialised schema, captured once, as raw SQLite pages.

    Session-scoped and safe because what it hands out is immutable
    `bytes`. Never session-scope a *connection*.
    """
    template = db.connect(":memory:")
    db.init_db(template)
    blobs = (template.serialize(name="main"),
             template.serialize(name="snapdb"))
    template.close()
    return blobs


def _fresh_conn(blobs: tuple[bytes, bytes]) -> sqlite3.Connection:
    """A private, schema-complete, in-memory database from the template."""
    main, snap = blobs
    c = sqlite3.connect(":memory:", timeout=30.0)
    c.row_factory = sqlite3.Row
    c.execute("ATTACH DATABASE ':memory:' AS snapdb")
    c.deserialize(main, name="main")
    c.deserialize(snap, name="snapdb")
    c.execute("PRAGMA foreign_keys = ON")
    return c


@pytest.fixture
def conn(_schema_blobs):
    """A private, schema-complete, in-memory database."""
    c = _fresh_conn(_schema_blobs)
    yield c
    c.close()


@pytest.fixture
def make_conn(_schema_blobs):
    """A factory: call it for each fresh database a single test needs.

    For tests that exercise something once per legacy shape, once per
    CHECK value, once per scenario -- anything that used to build a disk
    database inside a loop. Every connection it hands out is closed when
    the test ends.
    """
    made: list[sqlite3.Connection] = []

    def _make() -> sqlite3.Connection:
        c = _fresh_conn(_schema_blobs)
        made.append(c)
        return c

    yield _make
    for c in made:
        c.close()


@pytest.fixture
def registered_conn(conn):
    """`conn` with the standard single theory already registered.

    The seed ~20 files were each repeating locally.
    """
    theories.register(conn, "t1", "Theory One", "theories/t1", now=TS)
    return conn


# --------------------------------------------------------------------- #
# Tier 3: a database that is genuinely a file
# --------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    """One fully-initialised database FILE, built once per session.

    Copied per test rather than rebuilt: 6.8ms against 32.9ms, and the
    copy is a real file with real WAL behaviour, so tier 3 keeps exactly
    the semantics it is there to test. `db.close` checkpoints the WAL into
    the file first, which is what makes copying the .db (plus its
    snapshots sibling) sufficient.
    """
    path = tmp_path_factory.mktemp("db_template") / "template.db"
    c = db.connect(path)
    db.init_db(c)
    db.close(c)
    return path


def _copy_db(template, dest):
    """Copy a prebuilt database, and its snapshots sibling, into place."""
    shutil.copyfile(template, dest)
    src_snap = db.snapshots_path_for(template)
    if src_snap.exists():
        shutil.copyfile(src_snap, db.snapshots_path_for(dest))
    return dest


@pytest.fixture
def db_file(tmp_path):
    """Path for a real on-disk test database. Not created."""
    return tmp_path / "test.db"


@pytest.fixture
def make_db_file(tmp_path, _template_db):
    """Return a callable that lays down a ready-to-use database FILE.

    For tests that hand a path to the code under test, which then opens
    the database itself -- `cli.main(["--db", path, ...])` being the
    common case.
    """
    def _make(name: str = "test.db"):
        return _copy_db(_template_db, tmp_path / name)
    return _make


@pytest.fixture
def conn_disk(db_file, _template_db):
    """A database that is genuinely a file."""
    _copy_db(_template_db, db_file)
    c = db.connect(db_file)
    yield c
    c.close()


# --------------------------------------------------------------------- #
# The repo's own source, walked once
# --------------------------------------------------------------------- #

SKIP_DIRS = {".git", "__pycache__", "attic", ".pytest_cache",
             "node_modules", ".venv", "venv"}


class _Corpus:
    """The repo's source, walked once and read once per session.

    Read-only by contract -- which is what makes session scope safe. The
    scan tests that use it only ever read. Replaces ~11s of repeated
    rglob-and-read with a single ~510ms pass.
    """

    __slots__ = ("text", "py_files", "md_files")

    def __init__(self, text, py_files, md_files):
        self.text = text
        self.py_files = py_files
        self.md_files = md_files


@pytest.fixture(scope="session")
def source_corpus():
    root = db.REPO_ROOT
    text: dict = {}
    py: list = []
    md: list = []
    for path in root.rglob("*"):
        if SKIP_DIRS & set(path.parts):
            continue
        if path.suffix not in (".py", ".md") or not path.is_file():
            continue
        text[path] = path.read_text("utf-8", errors="replace")
        (py if path.suffix == ".py" else md).append(path)
    return _Corpus(text, tuple(sorted(py)), tuple(sorted(md)))
