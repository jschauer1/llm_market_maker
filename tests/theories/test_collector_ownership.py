"""Real JSON collectors lock the complete load/mutate/save transaction."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from tools import filelock


def _deadline_collect_worker(
    data_dir: str,
    series: str,
    entered,
    release,
) -> None:
    from theories.deadline_drift import collect_settled as collector

    collector.DATA = Path(data_dir)

    class Market:
        result = "no"

        def __init__(self, ticker: str):
            self.raw = {
                "ticker": ticker,
                "result": "no",
                "close_time": "2026-08-01T00:00:00Z",
                "rules_primary": "no parseable deadline",
            }

    def fetch(**kwargs):
        entered.set()
        if release is not None:
            assert release.wait(5.0)
        ticker = kwargs["series_ticker"]
        return [Market(f"{ticker}-A")]

    collector.km.list_settled = fetch
    collector.collect([series], flush_every=1, lock_timeout=5.0)


def test_competing_deadline_collectors_preserve_both_updates(tmp_path):
    """Locking only each atomic save still loses the earlier-loaded update."""
    ctx = multiprocessing.get_context("spawn")
    slow_entered = ctx.Event()
    fast_entered = ctx.Event()
    release_slow = ctx.Event()
    slow = ctx.Process(
        target=_deadline_collect_worker,
        args=(str(tmp_path), "SLOW", slow_entered, release_slow),
    )
    fast = ctx.Process(
        target=_deadline_collect_worker,
        args=(str(tmp_path), "FAST", fast_entered, None),
    )

    slow.start()
    assert slow_entered.wait(5.0), "first collector never reached its fetch"
    fast.start()
    # Without transaction ownership FAST reaches fetch against the same empty
    # snapshot. With ownership it waits here until SLOW has loaded and saved.
    fast_entered.wait(0.4)
    release_slow.set()
    slow.join(8.0)
    fast.join(8.0)
    if slow.is_alive():
        slow.terminate()
        slow.join(5.0)
    if fast.is_alive():
        fast.terminate()
        fast.join(5.0)

    assert slow.exitcode == 0
    assert fast.exitcode == 0
    stored = json.loads((tmp_path / "settled_raw.json").read_text())
    assert set(stored) == {"SLOW", "FAST"}


def test_population_rebuild_uses_the_capture_transaction_lock(tmp_path, monkeypatch):
    """Building facts while the three source files are changing is inconsistent."""
    from theories.deadline_drift import population

    monkeypatch.setattr(population, "DATA", tmp_path)
    monkeypatch.setattr(population, "FACTS_PATH", tmp_path / "population_facts.json")
    lock_path = tmp_path / ".collector.lock"
    with filelock.exclusive_lock(lock_path, timeout=0.0):
        with pytest.raises(filelock.LockTimeoutError):
            population.save(
                {"built_from_markets": 0}, lock_timeout=0.0
            )


class _FakeCacheConnection:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_backfill_owns_checkpoint_before_loading_or_fetching(tmp_path, monkeypatch):
    from theories.insider_bias import backfill_history

    checkpoint = tmp_path / "backfill.json"
    lock_path = checkpoint.with_name(checkpoint.name + ".lock")
    touched = False

    def series_for(_family):
        nonlocal touched
        touched = True
        return []

    monkeypatch.setattr(backfill_history, "series_for", series_for)
    with filelock.exclusive_lock(lock_path, timeout=0.0):
        with pytest.raises(filelock.LockTimeoutError):
            backfill_history.run("all", checkpoint, lock_timeout=0.0)
    assert not touched, "ownership must be acquired before loading external inputs"


def test_backfill_success_remains_incremental_and_resumable(tmp_path, monkeypatch):
    from theories.insider_bias import backfill_history

    checkpoint = tmp_path / "backfill.json"
    connection = _FakeCacheConnection()
    calls: list[str] = []
    stored_calls: list[int] = []

    monkeypatch.setattr(
        backfill_history, "series_for",
        lambda _family: [{"ticker": "A"}, {"ticker": "B"}],
    )

    class Market:
        close_time = None

    def survivors(series_list, _min_close, _max_close):
        for row in series_list:
            calls.append(row["ticker"])
            yield row["ticker"], [Market()]

    monkeypatch.setattr(backfill_history.sibling, "iter_settled_survivors", survivors)
    monkeypatch.setattr(backfill_history.history_cache, "connect", lambda: connection)
    monkeypatch.setattr(
        backfill_history.history_cache, "store_settled_markets",
        lambda _conn, rows: stored_calls.append(len(rows)) or len(rows),
    )

    first = backfill_history.run("all", checkpoint, lock_timeout=0.0)
    second = backfill_history.run("all", checkpoint, lock_timeout=0.0)

    assert first == second
    assert set(first["series"]) == {"A", "B"}
    assert stored_calls == [1, 1], "completed series must not be stored twice"
    assert calls == ["A", "B", "A", "B"], (
        "the upstream iterator still walks so its source behavior is unchanged"
    )
    assert connection.closed
    assert json.loads(checkpoint.read_text()) == first
