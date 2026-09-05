"""OS-released exclusive ownership for whole-file collector transactions.

Atomic replacement keeps readers from observing a partial file, but it cannot
protect a read/modify/write transaction from another writer that loaded the
same old snapshot.  Collectors use a persistent sibling lock file and hold its
OS lock from the first read through the last save.  The operating system drops
the lock when a process exits; the path itself is never unlinked, so two live
processes cannot end up locking different file identities.
"""

from __future__ import annotations

import errno
import os
import time
from pathlib import Path
from typing import BinaryIO

DEFAULT_TIMEOUT = 30.0
DEFAULT_POLL_INTERVAL = 0.1


class LockTimeoutError(TimeoutError):
    """Another process retained a collector lock for the allowed wait."""


if os.name == "nt":
    import msvcrt

    def _try_lock(handle: BinaryIO) -> bool:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                return False
            raise
        return True

    def _unlock(handle: BinaryIO) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(handle: BinaryIO) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return False
            raise
        return True

    def _unlock(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ExclusiveFileLock:
    """A bounded, non-reentrant exclusive lock on one persistent path."""

    def __init__(
        self,
        path: str | Path,
        *,
        timeout: float | None = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative or None")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.path = Path(path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle: BinaryIO | None = None
        self._acquired = False

    def acquire(self) -> "ExclusiveFileLock":
        if self._handle is not None:
            raise RuntimeError(f"lock is already in use: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b", buffering=0)
        self._handle = handle
        try:
            # Windows byte-range locking needs the byte to exist.  The path and
            # this sentinel remain forever; only the OS-held ownership expires.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                os.fsync(handle.fileno())

            started = time.monotonic()
            while not _try_lock(handle):
                elapsed = time.monotonic() - started
                if self.timeout is not None and elapsed >= self.timeout:
                    raise LockTimeoutError(
                        f"timed out after {self.timeout:.3f}s acquiring "
                        f"collector lock {self.path}; another collector owns "
                        "this load/mutate/save transaction"
                    )
                remaining = (
                    None if self.timeout is None else self.timeout - elapsed
                )
                delay = self.poll_interval
                if remaining is not None:
                    delay = min(delay, max(0.0, remaining))
                time.sleep(delay)
            self._acquired = True
            return self
        except BaseException:
            handle.close()
            self._handle = None
            raise

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            if self._acquired:
                _unlock(handle)
        finally:
            self._acquired = False
            self._handle = None
            handle.close()

    def __enter__(self) -> "ExclusiveFileLock":
        return self.acquire()

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


def exclusive_lock(
    path: str | Path,
    *,
    timeout: float | None = DEFAULT_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
) -> ExclusiveFileLock:
    """Return a context manager that exclusively owns ``path``.

    ``timeout=None`` is the explicit opt-in to waiting forever.  The bounded
    default prevents a duplicate multi-hour collector from hanging silently.
    """
    return ExclusiveFileLock(
        path, timeout=timeout, poll_interval=poll_interval
    )
