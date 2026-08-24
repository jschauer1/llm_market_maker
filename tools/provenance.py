"""Provenance for LLM judgment — which model, and which prompt.

An edge you cannot reproduce is an anecdote. When a theory puts a model in
its decision path, the model identity and the exact prompt text *are* part of
the decision procedure, exactly like a threshold is. `CLAUDE.md` already says
so — "any change to a theory's decision procedure bumps its version.
Thresholds, prompts, scan logic" — but a version number is only a promise
that something was written down. This module is where it gets written down.

Without it, two runs at the same version can be two different theories: same
label, different prompt, incomparable track records merged into one number.
That is the precise failure the versioning rule exists to prevent, and it is
invisible unless the prompt is persisted.

The reproducibility argument is the point, not the bookkeeping. A theory that
demonstrates edge and can say *exactly* what produced it is worth more than
one that demonstrated the same edge and cannot — the first can be re-run,
audited, and built on; the second is a story about the past.

Prompts belong in the theory's own folder as files, so a change shows up in
`git diff` and gets reviewed like any other procedure change. `prompt_path`
records that file; `prompt_text` is the fallback for a prompt assembled
inline. One of the two is required, and the sha always is.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from tools.db import REPO_ROOT, utcnow, write

VALID_STAGES = ("gate", "analysis", "final_review", "other")


def prompt_sha(text: str) -> str:
    """SHA-256 of prompt text, newline-normalized.

    Normalizing CRLF/CR to LF keeps the hash stable across platforms and
    across a git checkout that rewrote line endings — otherwise the same
    prompt hashes differently on Windows and the guard reports drift that is
    not there.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def read_prompt(path: str | Path) -> tuple[str, str]:
    """Return (text, sha256) for a prompt file. Raises if it does not exist."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.is_file():
        raise FileNotFoundError(
            f"prompt file not found: {p}. Prompts used by a theory's decision "
            "path must exist as files in the repo so a change is reviewable."
        )
    text = p.read_text(encoding="utf-8")
    return text, prompt_sha(text)


def record_judgment_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    theory_id: str,
    theory_version: int,
    stage: str,
    model: str,
    prompt_path: str | None = None,
    prompt_text: str | None = None,
    effort: str | None = None,
    web_search: bool | None = None,
    n_items: int | None = None,
    notes: str | None = None,
    now: str | None = None,
) -> int:
    """Record one model+prompt pairing used in a theory's decision path.

    Supply `prompt_path` (preferred — a file in the repo) or `prompt_text`.
    With a path, the file is read and hashed now, so the recorded sha is what
    was actually on disk at run time rather than what someone remembers.

    Re-recording the identical (run, stage, model, prompt) is a no-op, so a
    scan that batches a stage across several calls records it once.
    """
    if stage not in VALID_STAGES:
        raise ValueError(
            f"invalid stage {stage!r}; expected one of {VALID_STAGES}"
        )
    if not model or not model.strip():
        raise ValueError(
            "model is required: the whole point is knowing what judged"
        )
    if prompt_path is None and prompt_text is None:
        raise ValueError(
            "supply prompt_path or prompt_text — a judgment run whose prompt "
            "is not recoverable is not reproducible, which defeats the record"
        )

    text = prompt_text
    if prompt_path is not None:
        file_text, sha = read_prompt(prompt_path)
        if prompt_text is not None and prompt_sha(prompt_text) != sha:
            raise ValueError(
                f"prompt_text does not match the contents of {prompt_path}; "
                "pass one or the other, not two different prompts"
            )
        text = None  # the file is the record; do not duplicate it inline
    else:
        sha = prompt_sha(text or "")

    stamp = now or utcnow()
    with write(conn):
        cur = conn.execute(
            """
            INSERT INTO judgment_runs (
                run_id, theory_id, theory_version, stage, model, effort,
                prompt_path, prompt_sha256, prompt_text, web_search, n_items,
                notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, theory_id, theory_version, stage, model,
                         prompt_sha256)
            DO UPDATE SET
                n_items = COALESCE(judgment_runs.n_items, 0)
                          + COALESCE(excluded.n_items, 0),
                notes = COALESCE(excluded.notes, judgment_runs.notes)
            """,
            (
                run_id, theory_id, theory_version, stage, model, effort,
                str(prompt_path) if prompt_path is not None else None,
                sha, text,
                None if web_search is None else int(web_search),
                n_items, notes, stamp,
            ),
        )
    return cur.lastrowid


def list_judgment_runs(
    conn: sqlite3.Connection,
    theory_id: str | None = None,
    run_id: str | None = None,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM judgment_runs"
    where, params = [], []
    if theory_id is not None:
        where.append("theory_id = ?")
        params.append(theory_id)
    if run_id is not None:
        where.append("run_id = ?")
        params.append(run_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    return conn.execute(sql + " ORDER BY created_at, stage", params).fetchall()


def has_provenance(
    conn: sqlite3.Connection, theory_id: str, theory_version: int, run_id: str
) -> bool:
    """True if this run has at least one recorded model+prompt pairing."""
    row = conn.execute(
        """
        SELECT 1 FROM judgment_runs
         WHERE theory_id = ? AND theory_version = ? AND run_id = ?
         LIMIT 1
        """,
        (theory_id, theory_version, run_id),
    ).fetchone()
    return row is not None


def require_provenance(
    conn: sqlite3.Connection, theory_id: str, theory_version: int, run_id: str
) -> None:
    """Raise unless a theory declaring LLM judgment has recorded its prompts.

    Called from `ledger.record_opportunity`. A theory with
    `uses_llm_judgment = 0` is unaffected — a fully mechanical theory has no
    prompt to record, and that is the stronger kind of theory anyway.
    """
    row = conn.execute(
        "SELECT uses_llm_judgment FROM theories WHERE id = ?", (theory_id,)
    ).fetchone()
    if row is None or not row["uses_llm_judgment"]:
        return
    if has_provenance(conn, theory_id, theory_version, run_id):
        return
    raise ValueError(
        f"theory {theory_id!r} declares uses_llm_judgment, but run "
        f"{run_id!r} (v{theory_version}) has no judgment_runs provenance. "
        "Record the model and prompt for each judging stage first:\n"
        "  from tools import provenance\n"
        "  provenance.record_judgment_run(conn, run_id=..., "
        "theory_id=..., theory_version=..., stage='analysis',\n"
        "      model='...', prompt_path='theories/<slug>/prompts/analysis.md')\n"
        "An edge nobody can reproduce is an anecdote."
    )
