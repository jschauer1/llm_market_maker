"""Crash-safe whole-file writes for collectors that persist as they go.

CLAUDE.md's "record while you collect" tells every collector to write
after each item rather than once at the end, and the standard shape is
`_load()` the whole file, mutate, `_save()` the whole file. The `_save`
half was a plain `Path.write_text` everywhere, and that lost data twice
on 2026-09-01:

* **A sync client holds the handle.** This repo lives under
  `OneDrive/Documents`, and OneDrive intermittently locks a file being
  rewritten. A `deadline_drift` walk died at 874 of 960 series with
  `OSError: [Errno 22] Invalid argument` on open-for-write. That one was
  survivable only by luck: the open failed *before* truncating, and the
  collector is resumable. A failure a moment later leaves a truncated
  file where 1,859 markets of capture used to be — and Kalshi archives
  settled markets out of its public API ~60 days after close, so the
  difference between "retry" and "truncate" is the difference between a
  lost second and data that cannot be bought back at any price.
* **Truncation windows for readers.** `write_text` opens with mode `"w"`,
  which empties the file before the new bytes land. Any reader in that
  window — a peer session, or an analysis script in the same session —
  sees an empty or half-written file. A real `json.load` mid-walk raised
  `JSONDecodeError: Expecting value: line 1 column 1`.

Both are fixed by writing to a unique private sibling temporary file, then
using `os.replace` on the destination (atomic on Windows within a volume),
retrying a transient `OSError` with a backoff. A reader always observes either
the whole old file or the whole new one, and a sync lock costs a retry instead
of a run. Unique temporary paths keep independent atomic writes from corrupting
each other's staging file; collector transaction locks separately prevent lost
updates between a load and its later save.

**What this deliberately does NOT do: defend the read/modify/write cycle.**
Two processes can still load the same snapshot and atomically replace each
other's update. Real collectors hold `tools.filelock.exclusive_lock` across
that entire cycle; do not read a call to this module alone as transaction
ownership.

Elevated from `theories/deadline_drift/collect_settled.py::_save`, which
proved the shape under a real failing walk, once the second and third
callers appeared (`tools/README.md`'s promotion criterion).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

RETRIES = 6

# Indirected so a test can inject a failing replace without monkeypatching
# the stdlib for every other test in the process.
_replace = os.replace


def _write_file(path: Path, text: str, encoding: str) -> None:
    """Write and flush one private temp before it becomes visible."""
    with path.open("w", encoding=encoding) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    retries: int = RETRIES,
    _replace: Callable[[Any, Any], None] | None = None,
    _write: Callable[[Path, str, str], None] = _write_file,
    _sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Replace `path`'s contents with `text`, atomically.

    Creates the parent directory. On persistent failure the destination
    is left holding its previous contents and a `RuntimeError` naming the
    path is raised — never a truncated file and never a silent pass.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    replace = _replace or globals()["_replace"]
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{dest.name}.", suffix=".tmp", dir=dest.parent
    )
    os.close(fd)
    tmp = Path(tmp_name)
    last: Exception | None = None
    try:
        for attempt in range(retries):
            try:
                _write(tmp, text, encoding)
                replace(tmp, dest)
                return
            except OSError as exc:      # transient sync / AV / reader lock
                last = exc
                _sleep(0.5 * (attempt + 1))
    finally:
        # A real replace moved the temp away.  This also cleans a partial temp
        # after write failure and test doubles that deliberately do not move it.
        try:
            tmp.unlink()
        except OSError:
            pass
    raise RuntimeError(
        f"could not write {dest} after {retries} attempts: {last}"
    ) from last


def write_json(
    path: str | Path,
    obj: Any,
    *,
    indent: int | None = None,
    sort_keys: bool = False,
    default: Callable[[Any], Any] | None = None,
    **kw: Any,
) -> None:
    """`write_text` with the payload serialized as JSON.

    `indent`/`sort_keys` are passed through because existing collectors
    write human-diffable checkpoints and migrating them must not change
    their on-disk format.
    """
    write_text(
        path,
        json.dumps(obj, indent=indent, sort_keys=sort_keys, default=default),
        **kw,
    )
