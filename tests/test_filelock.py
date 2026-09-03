"""Tests for `tools.filelock` -- the lost-update race atomic writes cannot fix.

`tools/atomic_write.py` fixed the two SINGLE-writer failures (a sync
client holding a handle mid-rewrite, a reader catching a truncated file).
It says so itself, and says what it does not do: two processes doing
load-mutate-save each hold a snapshot from their own start time, so
whichever replaces last erases everything the other added -- ATOMICALLY,
which makes the loss well-formed and therefore harder to spot.

The measured incident: `anchors.json` went 332 -> 294 markets while the
walk was still adding, noticed only because a monotonically-increasing
count went down. Several sessions run in this repo at once (four were
live when it happened), and CLAUDE.md tells every one of them to top up a
capture whose marker is stale -- so this is the documented procedure
colliding with itself, not bad luck. The loss is also partly
UNRECOVERABLE: Kalshi ages settled markets out ~60 days after close.
"""

from __future__ import annotations

import json
import multiprocessing
import time

import pytest

# `tools/filelock.py` does not exist yet -- this is a deliberate RED spec
# (201d113), and it stays red until someone implements it.
#
# What changed here is only HOW it is red. A module-level
# `from tools import filelock` raises at COLLECTION, and a collection
# error is fatal to the whole run: `python -m pytest` exited before
# executing any of the other ~1478 tests, so the suite was unrunnable for
# every other lane. `importorskip` turns that into nine skips, which
# report as skips (`pytest -rs`) and block nothing.
#
# Nothing in this spec is weakened or deleted. Every assertion below is
# untouched, and the moment `tools/filelock.py` lands, all nine run for
# real with no further edit.
filelock = pytest.importorskip(
    "tools.filelock",
    reason="tools/filelock.py is not implemented yet (RED spec 201d113)",
)


def test_an_uncontended_lock_is_acquired_and_released(tmp_path):
    target = tmp_path / "anchors.json"
    with filelock.hold(target, owner="sess-a") as lock:
        assert lock.path.exists()
        held = json.loads(lock.path.read_text(encoding="utf-8"))
        assert held["owner"] == "sess-a"
        assert held["pid"] == filelock.os.getpid()
    assert not lock.path.exists(), "the lock must not outlive the block"


def test_a_second_holder_is_refused_while_the_first_is_live(tmp_path):
    target = tmp_path / "anchors.json"
    with filelock.hold(target, owner="sess-a"):
        with pytest.raises(filelock.LockHeld) as err:
            with filelock.hold(target, owner="sess-b"):
                pass
    # The refusal names the holder, so the second session knows who to ask
    # rather than guessing whether the lock is junk.
    assert "sess-a" in str(err.value)


def test_the_lock_is_released_even_when_the_body_raises(tmp_path):
    """A collector that dies mid-walk must not leave a lock nobody can
    clear -- 'a lock nobody can clear is worse than the race'."""
    target = tmp_path / "anchors.json"
    with pytest.raises(ZeroDivisionError):
        with filelock.hold(target, owner="sess-a") as lock:
            path = lock.path
            1 / 0
    assert not path.exists()


def test_a_stale_lock_is_broken_rather_than_honoured_forever(tmp_path):
    """The session that died is the common case, not the rare one. A lock
    whose heartbeat stopped is reclaimable, or the first crash wedges the
    capture permanently."""
    target = tmp_path / "anchors.json"
    lock_path = filelock.lock_path(target)
    lock_path.write_text(json.dumps({
        "owner": "dead-session", "pid": 999999, "token": "old",
        "acquired_at": "2020-01-01T00:00:00+00:00",
        "heartbeat": time.time() - 3600,
    }), encoding="utf-8")
    with filelock.hold(target, owner="sess-b", stale_after=60) as lock:
        held = json.loads(lock.path.read_text(encoding="utf-8"))
        assert held["owner"] == "sess-b"


def test_a_fresh_heartbeat_is_not_treated_as_stale(tmp_path):
    """The control. A staleness rule that fires too eagerly is worse than
    no lock: it hands two writers the same file while telling both they
    are exclusive."""
    target = tmp_path / "anchors.json"
    lock_path = filelock.lock_path(target)
    lock_path.write_text(json.dumps({
        "owner": "live-session", "pid": 999999, "token": "cur",
        "acquired_at": "2026-09-03T00:00:00+00:00",
        "heartbeat": time.time(),
    }), encoding="utf-8")
    with pytest.raises(filelock.LockHeld):
        with filelock.hold(target, owner="sess-b", stale_after=60):
            pass


def test_touch_keeps_a_long_walk_from_declaring_itself_stale(tmp_path):
    """A platform-wide walk runs for hours. Without a refresh it would
    cross any sane staleness threshold and invite a peer to break a lock
    that is doing exactly what it should."""
    target = tmp_path / "anchors.json"
    with filelock.hold(target, owner="sess-a") as lock:
        first = json.loads(lock.path.read_text(encoding="utf-8"))["heartbeat"]
        time.sleep(0.01)
        lock.touch()
        second = json.loads(lock.path.read_text(encoding="utf-8"))["heartbeat"]
        assert second > first


def test_releasing_a_lock_that_was_broken_does_not_delete_the_successor(
        tmp_path):
    """THE CORRECTNESS DETAIL. If A is declared stale and B takes the
    lock, A's cleanup must not unlink B's lock -- that would hand a third
    writer the file while B is mid-walk, which is the very race this
    module exists to stop. Ownership is a token, not the filename."""
    target = tmp_path / "anchors.json"
    a = filelock.acquire(target, owner="sess-a")
    # B breaks A's lock the way a stale reclaim does, and takes it.
    a.path.unlink()
    b = filelock.acquire(target, owner="sess-b")
    a.release()                       # A finishes, unaware it was broken
    assert b.path.exists(), "A deleted B's lock"
    assert json.loads(b.path.read_text(encoding="utf-8"))["owner"] == "sess-b"
    b.release()
    assert not b.path.exists()


def test_the_lock_file_sits_beside_the_data_and_not_inside_it(tmp_path):
    """A lock inside the data directory gets swept by a collector that
    rewrites the directory, and shows up in `git status` as junk."""
    target = tmp_path / "data" / "anchors.json"
    target.parent.mkdir()
    assert filelock.lock_path(target).parent == target.parent
    assert filelock.lock_path(target).name.startswith("anchors.json")
    assert filelock.lock_path(target).suffix == ".lock"


def _worker(target, results, i):
    """Child process: hold the lock, read-modify-write, release."""
    from tools import filelock as fl
    import json as j
    try:
        with fl.hold(target, owner=f"w{i}", stale_after=300, timeout=30):
            data = j.loads(target.read_text(encoding="utf-8"))
            time.sleep(0.02)          # widen the window the race needs
            data[str(i)] = i
            target.write_text(j.dumps(data), encoding="utf-8")
        results.append(i)
    except Exception as e:             # pragma: no cover - diagnostic
        results.append(f"{type(e).__name__}: {e}")


@pytest.mark.skipif(multiprocessing.get_start_method() != "spawn",
                    reason="needs spawn semantics")
def test_concurrent_writers_do_not_lose_each_others_updates(tmp_path):
    """The incident itself, reproduced: N processes each add one key to a
    shared JSON file. Without the lock the last writer wins and the file
    ends with roughly one key; with it, every update survives."""
    target = tmp_path / "anchors.json"
    target.write_text("{}", encoding="utf-8")
    with multiprocessing.Manager() as mgr:
        results = mgr.list()
        procs = [multiprocessing.Process(target=_worker,
                                         args=(target, results, i))
                 for i in range(5)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
        final = json.loads(target.read_text(encoding="utf-8"))
    assert sorted(int(k) for k in final) == [0, 1, 2, 3, 4], (
        f"updates were lost: {final} (workers reported {list(results)})")
