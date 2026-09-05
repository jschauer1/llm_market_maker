"""Exclusive collector ownership survives contention and process exit."""

from __future__ import annotations

import multiprocessing
import os

import pytest

from tools import filelock


def _hold_lock(lock_path: str, ready, release) -> None:
    with filelock.exclusive_lock(lock_path, timeout=5.0):
        ready.set()
        release.wait(5.0)


def _exit_while_holding(lock_path: str, ready) -> None:
    with filelock.exclusive_lock(lock_path, timeout=5.0):
        ready.set()
        os._exit(17)


def test_second_owner_gets_a_bounded_actionable_timeout(tmp_path):
    """Removing the OS lock or making acquisition unbounded breaks this."""
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    lock_path = tmp_path / "capture.lock"
    process = ctx.Process(
        target=_hold_lock, args=(str(lock_path), ready, release)
    )
    process.start()
    try:
        assert ready.wait(5.0), "child never acquired the collector lock"
        with pytest.raises(filelock.LockTimeoutError) as exc:
            with filelock.exclusive_lock(
                lock_path, timeout=0.15, poll_interval=0.01
            ):
                pytest.fail("a second writer entered the protected transaction")
        assert str(lock_path) in str(exc.value)
        assert "another collector" in str(exc.value).lower()
    finally:
        release.set()
        process.join(5.0)
        if process.is_alive():
            process.terminate()
            process.join(5.0)
    assert process.exitcode == 0


def test_process_death_releases_lock_without_deleting_its_stable_path(tmp_path):
    """A stale TTL or unlink-based lock can steal/split an active lock."""
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    lock_path = tmp_path / "capture.lock"
    process = ctx.Process(target=_exit_while_holding, args=(str(lock_path), ready))
    process.start()
    assert ready.wait(5.0), "child never acquired the collector lock"
    process.join(5.0)
    assert process.exitcode == 17

    assert lock_path.exists(), "the lock inode/path is persistent shared identity"
    with filelock.exclusive_lock(lock_path, timeout=1.0):
        pass
    assert lock_path.exists()


def test_exception_releases_lock_for_the_next_owner(tmp_path):
    lock_path = tmp_path / "capture.lock"
    with pytest.raises(RuntimeError, match="collector failed"):
        with filelock.exclusive_lock(lock_path, timeout=0.0):
            raise RuntimeError("collector failed")

    with filelock.exclusive_lock(lock_path, timeout=0.0):
        pass
