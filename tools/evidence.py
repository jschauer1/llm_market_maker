"""Shared production eligibility for settled evidence.

Forward settlements and documented tier A/B replays are evidence in the
same currency.  Tier C, NULL-tier, and unregistered replays remain available
for diagnosis but cannot price a bucket, move a score, or clear a gate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import sqlite3
from typing import Iterable, Mapping


_REASON_ORDER = (
    "tier_c",
    "missing_tier",
    "unregistered_run",
    "mismatched_registration",
)


@dataclass(frozen=True)
class ExcludedObservation:
    """One diagnostic observation and every reason it cannot be evidence."""

    row: dict
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSelection:
    """Eligible production rows plus the excluded diagnostic population."""

    eligible: list[dict]
    excluded: list[ExcludedObservation]

    @property
    def counts(self) -> dict[str, int]:
        """Excluded row count, followed by counts for each applicable reason."""
        counts = Counter(
            reason for item in self.excluded for reason in item.reasons
        )
        result = {"total": len(self.excluded)}
        result.update(
            (reason, counts[reason]) for reason in _REASON_ORDER if counts[reason]
        )
        return result


def select_eligible(
    conn: sqlite3.Connection,
    observations: Iterable[Mapping],
) -> EvidenceSelection:
    """Partition settled observations under the production evidence rule.

    `score.observations` intentionally remains raw.  This function is the
    explicit boundary between that diagnostic population and decision-facing
    consumers.  A replay is eligible only when every run which contributed to
    this scored observation has a tier A/B registration for the same theory
    and version.  The all-runs rule matters because a later attempt can supply
    roll-up fields such as confidence even when another run saw the position
    first.
    """
    rows = [dict(row) for row in observations]
    registrations = {
        row["run_id"]: row
        for row in conn.execute(
            "SELECT run_id, theory_id, theory_version, tier FROM backtest_runs"
        ).fetchall()
    }
    eligible: list[dict] = []
    excluded: list[ExcludedObservation] = []

    for row in rows:
        if row.get("run_mode") != "backtest":
            eligible.append(row)
            continue

        run_ids = list(row.get("run_ids") or [])
        if not run_ids and row.get("run_id"):
            run_ids = [row["run_id"]]
        reasons: set[str] = set()
        if not run_ids:
            reasons.add("unregistered_run")

        for run_id in run_ids:
            registered = registrations.get(run_id)
            if registered is None:
                reasons.add("unregistered_run")
                continue
            if (
                registered["theory_id"] != row.get("theory_id")
                or registered["theory_version"] != row.get("theory_version")
            ):
                reasons.add("mismatched_registration")
            tier = registered["tier"]
            if tier == "C":
                reasons.add("tier_c")
            elif tier not in ("A", "B"):
                reasons.add("missing_tier")

        if reasons:
            ordered = tuple(reason for reason in _REASON_ORDER if reason in reasons)
            excluded.append(ExcludedObservation(row, ordered))
        else:
            eligible.append(row)

    return EvidenceSelection(eligible, excluded)
