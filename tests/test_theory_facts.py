"""Durable per-theory facts, and the provenance for the judgment that
established them.

Five backlog theories keep facts settled once and reused every run:
confirmed market pairings, implication edges, per-wallet scores. Left to
`ctx.conn` alone, five theories would invent five schemas.

Two rules this pins down, because both readings are defensible and a wrong
guess is expensive:

- **Facts are data, not procedure.** Adding a confirmed pair does not bump
  the theory's version. Changing how facts are *derived* does.
- A fact a model proposed carries a `construction`-stage provenance row,
  keyed to the fact rather than to a run. That is what lets a theory whose
  only LLM ran at match time still earn a tier A backtest -- the per-trade
  path really has no model in it, but the judgment that built the pair
  store still has to be recoverable.

Deliberately no Python API yet: no current theory keeps facts, so these
tests speak SQL and the first pair-store theory earns the helpers.
"""

import json
import sqlite3

import pytest

from tools import db, provenance, theories

TS = "2026-08-24T12:00:00Z"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    theories.register(c, "pairs", "Pair Store", "theories/pairs", now=TS)
    yield c
    c.close()


def _put(conn, provenance_id=None, key="KXCPI-26|0xabc"):
    with db.write(conn):
        conn.execute(
            "INSERT INTO theory_facts (theory_id, kind, key, value_json,"
            " evidence_json, established_at, provenance_id)"
            " VALUES ('pairs', 'market_pair', ?, ?, ?, ?, ?)",
            (key,
             json.dumps({"kalshi": "KXCPI-26", "poly": "0xabc"}),
             json.dumps({"how": "resolution criteria compared"}),
             TS, provenance_id),
        )


def test_a_fact_round_trips(conn):
    _put(conn)
    row = conn.execute(
        "SELECT * FROM theory_facts WHERE theory_id = 'pairs'"
    ).fetchone()
    assert json.loads(row["value_json"])["kalshi"] == "KXCPI-26"
    assert json.loads(row["evidence_json"])["how"]
    assert row["established_at"] == TS
    assert row["provenance_id"] is None


def test_the_same_fact_key_cannot_be_stored_twice(conn):
    _put(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _put(conn)


def test_facts_are_scoped_per_theory_kind_and_key(conn):
    theories.register(conn, "other", "Other", "theories/other", now=TS)
    _put(conn, key="a")
    _put(conn, key="b")
    with db.write(conn):
        conn.execute(
            "INSERT INTO theory_facts (theory_id, kind, key, value_json,"
            " established_at) VALUES ('other', 'market_pair', 'a', '{}', ?)",
            (TS,),
        )
    n = conn.execute(
        "SELECT COUNT(*) FROM theory_facts WHERE theory_id = 'pairs'"
    ).fetchone()[0]
    assert n == 2


def test_a_fact_requires_a_registered_theory(conn):
    with pytest.raises(sqlite3.IntegrityError):
        with db.write(conn):
            conn.execute(
                "INSERT INTO theory_facts (theory_id, kind, key,"
                " value_json, established_at)"
                " VALUES ('no_such_theory', 'market_pair', 'k', '{}', ?)",
                (TS,),
            )


def test_adding_a_fact_does_not_bump_the_version(conn):
    """Facts are data, not procedure -- the rule that keeps a pair store
    from orphaning its own track record every time a pair is added."""
    before = theories.get(conn, "pairs")["version"]
    _put(conn, key="one")
    _put(conn, key="two")
    assert theories.get(conn, "pairs")["version"] == before


def test_construction_is_a_valid_provenance_stage(conn):
    pid = provenance.record_judgment_run(
        conn, run_id="setup-2026-08-24", theory_id="pairs",
        theory_version=1, stage="construction", model="claude-opus-5",
        prompt_text="propose candidate market pairings", now=TS,
    )
    _put(conn, provenance_id=pid)
    row = conn.execute(
        "SELECT j.stage, j.model FROM theory_facts f"
        " JOIN judgment_runs j ON j.id = f.provenance_id"
    ).fetchone()
    assert row["stage"] == "construction"
    assert row["model"] == "claude-opus-5"


def test_an_unknown_stage_is_still_refused(conn):
    with pytest.raises(ValueError, match="invalid stage"):
        provenance.record_judgment_run(
            conn, run_id="r", theory_id="pairs", theory_version=1,
            stage="vibes", model="m", prompt_text="p", now=TS,
        )


def test_a_legacy_database_is_migrated_to_accept_construction(tmp_path):
    """A database created before this change carries the old CHECK baked
    into its DDL, and CREATE TABLE IF NOT EXISTS will not touch it."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE theories (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','testing','active',
                                  'under_review','paused','retired')),
            path TEXT NOT NULL, retirement_proposed_at TEXT,
            retirement_rationale TEXT,
            uses_llm_judgment INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE judgment_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            theory_id TEXT NOT NULL REFERENCES theories(id),
            theory_version INTEGER NOT NULL,
            stage TEXT NOT NULL
                CHECK (stage IN ('gate','analysis','final_review','other')),
            model TEXT NOT NULL, effort TEXT, prompt_path TEXT,
            prompt_sha256 TEXT NOT NULL, prompt_text TEXT,
            web_search INTEGER, n_items INTEGER, notes TEXT,
            created_at TEXT NOT NULL,
            CHECK (prompt_path IS NOT NULL OR prompt_text IS NOT NULL),
            UNIQUE (run_id, theory_id, theory_version, stage, model,
                    prompt_sha256));
        INSERT INTO theories VALUES ('t','T',1,'testing','p',NULL,NULL,0,
                                     '2026-01-01T00:00:00Z',
                                     '2026-01-01T00:00:00Z');
        INSERT INTO judgment_runs (run_id, theory_id, theory_version, stage,
            model, prompt_sha256, prompt_text, created_at)
        VALUES ('r','t',1,'analysis','m','sha','p','2026-01-01T00:00:00Z');
        """
    )
    old.commit()
    old.close()

    conn = db.connect(path)
    db.init_db(conn)

    # The pre-existing row survived the rebuild, values intact...
    rows = conn.execute("SELECT * FROM judgment_runs").fetchall()
    assert len(rows) == 1
    assert (rows[0]["run_id"], rows[0]["stage"]) == ("r", "analysis")

    # ...the widened CHECK accepts construction...
    provenance.record_judgment_run(
        conn, run_id="r2", theory_id="t", theory_version=1,
        stage="construction", model="m", prompt_text="x", now=TS,
    )
    # ...and the UNIQUE constraint came across with the rebuilt table.
    assert conn.execute(
        "SELECT COUNT(*) FROM judgment_runs"
    ).fetchone()[0] == 2
    provenance.record_judgment_run(
        conn, run_id="r2", theory_id="t", theory_version=1,
        stage="construction", model="m", prompt_text="x", now=TS,
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM judgment_runs"
    ).fetchone()[0] == 2
    conn.close()


def test_migration_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    db.init_db(conn)
    db.init_db(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM theory_facts"
    ).fetchone()[0] == 0
    conn.close()
