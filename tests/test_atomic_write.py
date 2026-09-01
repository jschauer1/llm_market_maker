"""Crash-safe whole-file writes — the collector convention's missing half.

`record while you collect` (CLAUDE.md, Data conventions) tells every
collector to persist after each item, and the standard implementation is
_load() the whole file, mutate, _save() the whole file. Two real failures
on 2026-09-01 came from the `_save` half being a plain `write_text`:

* **OneDrive holds a handle.** This repo lives under `OneDrive/Documents`
  and the sync client intermittently locks a file mid-rewrite. A
  deadline_drift walk died at 874/960 series with `OSError: [Errno 22]
  Invalid argument` on open-for-write. It cost nothing only because the
  open failed *before* truncating; a failure a moment later leaves a
  truncated file where 1,859 markets of capture used to be, and ~60 days
  of Kalshi settled history is unrecoverable upstream.
* **Truncation windows for readers.** `write_text` opens mode `"w"`, so a
  reader — a peer session, or an analysis script in the same one — can
  catch the file empty or half-written. A real `json.load` mid-walk
  raised `JSONDecodeError: Expecting value: line 1 column 1`.

Ticket: maintenance/collector-write-lock. This module is that
ticket's cheap half. It does NOT defend against a second concurrent
writer — that needs a lock, and is tracked separately.
"""

from __future__ import annotations

import json

import pytest

from tools import atomic_write


def test_round_trips_json(tmp_path):
    p = tmp_path / "c.json"
    atomic_write.write_json(p, {"a": [1, 2], "b": "x"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": [1, 2], "b": "x"}


def test_creates_the_parent_directory(tmp_path):
    """Collectors write into a data/ dir that may not exist on a fresh clone."""
    p = tmp_path / "deep" / "nested" / "c.json"
    atomic_write.write_json(p, {"ok": True})
    assert json.loads(p.read_text(encoding="utf-8")) == {"ok": True}


def test_leaves_no_tmp_file_behind(tmp_path):
    p = tmp_path / "c.json"
    atomic_write.write_json(p, {"ok": True})
    assert [x.name for x in tmp_path.iterdir()] == ["c.json"]


def test_retries_a_transient_oserror_then_succeeds(tmp_path):
    """The OneDrive/AV case: the handle clears, so a retry is the fix."""
    p = tmp_path / "c.json"
    p.write_text('{"old": true}', encoding="utf-8")
    calls = {"n": 0}
    real = atomic_write._replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError(22, "Invalid argument")
        return real(src, dst)

    atomic_write.write_json(p, {"new": True}, _replace=flaky, _sleep=lambda s: None)
    assert calls["n"] == 3
    assert json.loads(p.read_text(encoding="utf-8")) == {"new": True}


def test_a_failed_write_never_truncates_the_existing_file(tmp_path):
    """The property that makes this worth having.

    Whatever goes wrong, the destination must still hold the last good
    payload — never empty, never half a payload. That is exactly what a
    plain `write_text` cannot promise, and what makes a lost capture
    unrecoverable when the source has aged out upstream.
    """
    p = tmp_path / "c.json"
    p.write_text('{"old": true}', encoding="utf-8")

    def always_fails(src, dst):
        raise OSError(22, "Invalid argument")

    with pytest.raises(RuntimeError) as exc:
        atomic_write.write_json(p, {"new": True}, retries=3,
                                _replace=always_fails, _sleep=lambda s: None)
    assert str(p) in str(exc.value)
    assert json.loads(p.read_text(encoding="utf-8")) == {"old": True}
    assert [x.name for x in tmp_path.iterdir()] == ["c.json"], "tmp not cleaned up"


def test_write_text_is_the_primitive(tmp_path):
    p = tmp_path / "c.txt"
    atomic_write.write_text(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"


def test_json_kwargs_are_passed_through(tmp_path):
    """Existing collectors write indent=1, sort_keys=True; keep their format."""
    p = tmp_path / "c.json"
    atomic_write.write_json(p, {"b": 1, "a": 2}, indent=1, sort_keys=True)
    assert p.read_text(encoding="utf-8") == '{\n "a": 2,\n "b": 1\n}'
