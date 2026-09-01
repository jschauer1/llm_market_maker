"""Evidence carries across versions unless a bump explicitly breaks it.

User ruling 2026-08-31: a backtest run against a different version of a
theory is still valid evidence for it. A version bump does not, by
itself, invalidate what the theory has already demonstrated -- only an
explicit `breaking` declaration does, and that declaration has to say
why.

This reverses the previous default. `breaking` used to be what a bump was
unless someone proved otherwise, and the proof bar (a replay reproducing
every recorded decision exactly) was high enough that almost nobody
cleared it: three of the four running theories reached n=0 that way,
discarding real evidence to protect against a merge nobody had actually
attempted. Three kinds now:

  carry     -- proven identical, equivalence replay on file (strongest)
  continues -- the default: the procedure changed, the evidence stands
  breaking  -- an explicit sever, justified in the bump

Only `breaking` stops the chain.
"""

from __future__ import annotations

import pytest

from tools import db, theories
from tools.domain import EquivalenceResult


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    theories.register(c, "t", "T", "theories/t")
    return c


def test_a_bump_continues_the_evidence_chain_by_default(conn):
    theories.bump_version(conn, "t", justification="tightened a threshold")

    assert theories.carry_chain(conn, "t", 2) == [1, 2]


def test_an_explicit_break_severs_the_chain(conn):
    theories.bump_version(conn, "t", kind="breaking",
                          justification="different population entirely")

    assert theories.carry_chain(conn, "t", 2) == [2]


def test_a_proven_carry_still_continues_the_chain(conn):
    proof = EquivalenceResult(
        theory_id="t", from_version=1, n_attempts=1, divergences=(),
        n_divergent=0, label="carry-proof/t-v1-to-v2",
    )
    theories.bump_version(conn, "t", kind="carry",
                          justification="no-op refactor", equivalence=proof)

    assert theories.carry_chain(conn, "t", 2) == [1, 2]


def test_the_chain_walks_back_through_several_continuing_bumps(conn):
    for n in range(3):
        theories.bump_version(conn, "t", justification=f"change {n}")

    assert theories.carry_chain(conn, "t", 4) == [1, 2, 3, 4]


def test_a_break_anywhere_stops_the_walk_at_that_point(conn):
    theories.bump_version(conn, "t", justification="v2: tweak")
    theories.bump_version(conn, "t", kind="breaking",
                          justification="v3: new thesis")
    theories.bump_version(conn, "t", justification="v4: tweak")

    assert theories.carry_chain(conn, "t", 4) == [3, 4], (
        "everything from the break forward pools; nothing before it"
    )


def test_continues_needs_no_equivalence_proof(conn):
    """The proof bar is what made the old default unaffordable. A
    continuing bump records what changed and why, and that is enough."""
    version = theories.bump_version(
        conn, "t", justification="reworded the analysis prompt")

    row = theories.list_versions(conn, "t")[-1]
    assert version == 2
    assert row["kind"] == "continues"
    assert row["equivalence_run"] is None


def test_breaking_still_requires_a_justification(conn):
    """Severing a track record is the consequential direction now, so it
    is the one that must argue for itself."""
    with pytest.raises(TypeError):
        theories.bump_version(conn, "t", kind="breaking")


# --- correcting a bump recorded under the old default ----------------------


def test_reclassifying_a_bump_relinks_the_evidence_chain(conn):
    theories.bump_version(conn, "t", kind="breaking",
                          justification="pre-dates the ruling; not adjudicated")
    assert theories.carry_chain(conn, "t", 2) == [2]

    theories.reclassify_bump(
        conn, "t", 2, kind="continues",
        reason="recorded as breaking only because breaking was the default",
    )

    assert theories.carry_chain(conn, "t", 2) == [1, 2]


def test_reclassifying_keeps_the_original_justification_visible(conn):
    """Correcting a governance record must never erase what it said. The
    original reasoning is the audit trail for the correction itself."""
    theories.bump_version(conn, "t", kind="breaking",
                          justification="the original wording")
    theories.reclassify_bump(conn, "t", 2, kind="continues",
                             reason="never adjudicated")

    row = theories.list_versions(conn, "t")[-1]
    assert "the original wording" in row["justification"]
    assert "never adjudicated" in row["justification"]


def test_reclassifying_demands_a_reason(conn):
    theories.bump_version(conn, "t", justification="x")
    with pytest.raises(ValueError, match="reason"):
        theories.reclassify_bump(conn, "t", 2, kind="breaking", reason="")


def test_reclassifying_to_carry_still_needs_its_proof(conn):
    """The strongest claim keeps the strongest bar -- a correction is not
    a side door around the equivalence replay."""
    theories.bump_version(conn, "t", kind="breaking", justification="x")
    with pytest.raises(ValueError, match="proof"):
        theories.reclassify_bump(conn, "t", 2, kind="carry",
                                 reason="looks equivalent to me")
