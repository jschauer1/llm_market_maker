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

Both are fixed by the same three lines: write to a sibling `.tmp`, then
`os.replace` onto the destination (atomic on Windows within a volume),
retrying a transient `OSError` with a backoff. A reader always observes
either the whole old file or the whole new one, and a sync lock costs a
retry instead of a run.

**What this deliberately does NOT do: defend against a second concurrent
writer.** Two processes doing load-mutate-save each hold a snapshot from
their own start time, so whichever replaces last still erases everything
the other added — atomically, and therefore invisibly. That is a
lost-update race and it needs a lock, not an atomic replace; it is
tracked as `maintenance/collector-write-lock`. Do not read a
call to this module as making concurrent collection safe.

Elevated from `theories/deadline_drift/collect_settled.py::_save`, which
proved the shape under a real failing walk, once the second and third
callers appeared (`tools/README.md`'s promotion criterion).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

RETRIES = 6

# Indirected so a test can inject a failing replace without monkeypatching
# the stdlib for every other test in the process.
_replace = os.replace


def write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    retries: int = RETRIES,
    _replace: Callable[[Any, Any], None] | None = None,
    _sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Replace `path`'s contents with `text`, atomically.

    Creates the parent directory. On persistent failure the destination
    is left holding its previous contents and a `RuntimeError` naming the
    path is raised — never a truncated file and never a silent pass.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    replace = _replace or globals()["_replace"]
    last: Exception | None = None
    for attempt in range(retries):
        try:
            tmp.write_text(text, encoding=encoding)
            replace(tmp, dest)
            return
        except OSError as exc:          # transient sync / AV / reader lock
            last = exc
            _sleep(0.5 * (attempt + 1))
    # Leave no half-written sibling behind for the next reader to find.
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
