"""Series-level structural facts learned from the settled capture.

`hazard.partition_families` and `hazard.branch_families` read settlement
behaviour, so by their own docstrings they "cannot screen a live board".
That is true of the *functions* and not of their *answers*: what they
return is a set of **series**, and a series' construction is a structural
fact about the family that outlives any one settlement. This module is
the bridge -- it runs them once over the capture, persists the answers as
a small JSON file, and lets the live screen apply them without loading
9 MB of candles on every run.

**Why persist rather than recompute.** `hazard.load()` reads
`anchors.json`, `candles.json` and `settled_raw.json` -- about 9.5 MB and
several seconds. The live screen needs three small sets out of that. A
theory's screen runs in every floor, so paying seconds and hundreds of
megabytes of parsed JSON for a 15-element set is the kind of cost that
quietly makes a theory "too slow to run today".

**Refresh it whenever the capture is topped up.** The facts are learned
from settled history, so they go stale in exactly one direction: a family
that starts behaving like a partition after the file was written stays
un-excluded until the next rebuild. `build()` is cheap (seconds) and
`collect_settled` is the thing that changes its inputs, so rebuild after
capture.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from tools import atomic_write, filelock

DATA = Path(__file__).parent / "data"
FACTS_PATH = DATA / "population_facts.json"

#: DD-2's split, fixed at listing time: a series with at least this many
#: settled events has taught its own base rate, per the mechanism in
#: THEORY.md. A one-off question has no reference class on the board.
RECURRING_MIN_EVENTS = 3


def build() -> dict:
    """Recompute the facts from the capture on disk. Seconds, not free."""
    from theories.deadline_drift import hazard

    anchors, _candles, _rules = hazard.load()
    events = hazard.event_map()

    settled_events: dict[str, set[str]] = defaultdict(set)
    for tk, a in anchors.items():
        ev = events.get(tk)
        if ev:
            settled_events[a.get("series") or ""].add(ev)

    return {
        "built_from_markets": len(anchors),
        # DD-1's named exclusion. Series whose settled events pay exactly
        # one winner -- a "which branch" partition wearing a hazard's
        # phrasing.
        "partition_families": sorted(hazard.partition_families(anchors, events)),
        # NOT a DD-1 exclusion, deliberately: recorded as a per-row FIELD
        # so the pre-registered population is exactly what DD-1 names,
        # while the cleaner subset stays recoverable as a registered
        # slice. See NOTES.md 2026-09-01 (v2).
        "branch_families": sorted(hazard.branch_families(anchors)),
        # DD-2's input.
        "settled_events_per_series": {
            s: len(v) for s, v in sorted(settled_events.items()) if s
        },
    }


def save(
    facts: dict | None = None,
    *,
    lock_timeout: float | None = filelock.DEFAULT_TIMEOUT,
) -> dict:
    """Build and save against one consistent settled-capture snapshot."""
    from theories.deadline_drift.collect_settled import collector_lock_path

    with filelock.exclusive_lock(
        collector_lock_path(DATA), timeout=lock_timeout
    ):
        facts = build() if facts is None else facts
        atomic_write.write_json(FACTS_PATH, facts, indent=1, sort_keys=True)
        return facts


def load() -> dict:
    """The persisted facts, or empty sets when the file is absent.

    An absent file must not crash the screen: it degrades to "no learned
    exclusions", which is a *wider* population than intended rather than
    a silently narrower one. The funnel reports `facts_loaded` so a run
    against a missing file is visible rather than merely wrong.
    """
    if not FACTS_PATH.exists():
        return {"partition_families": [], "branch_families": [],
                "settled_events_per_series": {}, "built_from_markets": 0,
                "missing": True}
    return json.loads(FACTS_PATH.read_text(encoding="utf-8"))


def is_recurring(series_ticker: str | None, facts: dict) -> bool:
    """DD-2's split. A property of the series, fixed before the decision."""
    n = facts.get("settled_events_per_series", {}).get(series_ticker or "", 0)
    return n >= RECURRING_MIN_EVENTS


if __name__ == "__main__":  # pragma: no cover - operator entry point
    f = save()
    print(f"built from {f['built_from_markets']} settled markets")
    print(f"  partition_families: {len(f['partition_families'])}")
    print(f"  branch_families:    {len(f['branch_families'])}")
    print(f"  series with settled events: "
          f"{len(f['settled_events_per_series'])}")
