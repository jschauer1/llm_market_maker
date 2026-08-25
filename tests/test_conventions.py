"""Repo-wide conventions the OOP layer promises (spec sections 3.2, 4.2,
4.5c, 9): every theory package exposes a proper singleton, nobody
overrides the workflow, a Verdict can never grow a number, the migration
shim is only exercised from allowlisted modules, and the actually-running
registry has no drift between code and DB."""

import pytest
from dataclasses import fields

from tools import db, domain, registry
from tools.theory import Theory, TheoryRun


def test_every_theory_package_exposes_a_conforming_singleton():
    for tid, theory in registry.discover().items():
        assert isinstance(theory, Theory)
        assert theory.id == tid
        assert isinstance(theory.version, int)
        for stage, path in theory.prompts.items():
            from tools.provenance import VALID_STAGES
            assert stage in VALID_STAGES


def test_no_theory_overrides_the_inherited_workflow():
    for theory in registry.discover().values():
        for cls in type(theory).__mro__[:-3]:       # up to (not incl.) Theory
            assert "start" not in vars(cls)
            assert "finish" not in vars(cls)
    assert TheoryRun.__subclasses__() == []


def test_verdict_declares_no_numeric_field():
    """CLAUDE.md's 'never state a probability you introspected', as a type
    property: an out-of-process judge has no channel to hand back a number."""
    for f in fields(domain.Verdict):
        annotation = str(f.type)
        assert "float" not in annotation and "int" not in annotation, (
            f"Verdict.{f.name} is numeric -- a judge returns a category, "
            "never a number"
        )


#: Modules still permitted to use dict-style access on domain objects.
#: Tasks 12-13 shrink this list as call sites port; Task 14 empties it and
#: deletes the shim. Test modules are exempt (they test the shim itself).
#:
#: This is the set actually OBSERVED with tracking on (see the test below),
#: not a static guess at which files contain `.get(`/`[...]` syntax.
#:
#: As of Task 12: `screen.py`, `gate.py`, and `insider_judgment/pipeline.py`
#: were ported to read Market/Candidate natively (attribute access, no more
#: `.get()`/`[...]`), so `theories.insider_bias.insider_judgment.pipeline`
#: DROPPED from this set -- running the whole insider_judgment pipeline
#: (`ij.start(ctx)`) no longer touches the shim at all.
#:
#: `theories.insider_bias.mention_family.mention_bucket` ENTERED instead,
#: for a reason that is the whole point of an incremental port: it calls
#: the SAME shared `screen.screen()` insider_judgment uses (see
#: `theories/insider_bias/screen.py`'s module docstring on the two sibling
#: theories), and that function now returns domain.Candidate objects
#: instead of dicts. `find_candidates()`'s `h.get("series_ticker")` /
#: `h["ticker"]` calls (mention_bucket.py has not been ported -- that is
#: Task 13) land on the shim for the first time as a direct consequence.
#: This is expected and temporary, exactly as the Task 12 brief predicted.
#:
#: `tools.domain` is not a "caller" migrating anywhere: `Candidate.get()`
#: (defined in domain.py) delegates to `Market.get()`, and the frame that
#: "actually indexed" is that delegating line inside domain.py itself -- an
#: artifact of the shim's own internal plumbing, gone the moment the whole
#: shim is deleted in Task 14.
SHIM_ALLOWLIST = {
    "theories.insider_bias.mention_family.mention_bucket",
    "tools.domain",
}


def test_shim_is_exercised_only_from_allowlisted_modules():
    from tests.characterization import conftest as cz
    from theories.insider_bias.insider_judgment import THEORY as ij
    from theories.insider_bias.mention_family import THEORY as mf
    from tools.theory import TheoryContext

    domain.SHIM_CALLERS.clear()
    with domain.track_shim_callers():
        ctx = TheoryContext(conn=None, board=cz.board_input(),
                            now=cz.frozen_now())
        ij.start(ctx)                          # exercises the whole pipeline
        mf.screen(ctx)
    prod = {m for m in domain.SHIM_CALLERS
            if m.startswith(("tools.", "theories."))}
    assert prod, (
        "no shim callers observed with tracking on -- this test enforces "
        "nothing when prod is empty; the theory run stopped touching the "
        "shim, or tracking is broken"
    )
    assert prod <= SHIM_ALLOWLIST, sorted(prod - SHIM_ALLOWLIST)


def test_the_real_registry_has_no_drift():
    """registry.check_drift against the ACTUAL working database.

    tests/test_registry.py only exercises check_drift on synthetic
    tmp_path databases built to agree by construction -- nothing in the
    suite ever points it at db/market_edge.db, so a real class/DB mismatch
    (running v3 code while the DB still says v2 -- exactly the silent merge
    CLAUDE.md's versioning rule exists to prevent, or uses_llm_judgment
    flipped on one side only) would ship green. This closes that hole.

    Read-only: connects to the real DB but never calls init_db or writes
    to it. Skips cleanly if the file does not exist (a fresh clone, or CI
    with no working database) rather than creating one as a side effect of
    connecting -- `db.connect` would otherwise create an empty file.
    """
    if not db.DEFAULT_DB_PATH.exists():
        pytest.skip(
            f"{db.DEFAULT_DB_PATH} does not exist -- no working database "
            "to check for drift in this environment"
        )
    conn = db.connect(db.DEFAULT_DB_PATH)
    try:
        problems = registry.check_drift(conn)
    finally:
        conn.close()
    assert problems == [], (
        "the real theory registry has drifted between code and DB -- "
        "a run recorded under this state would be recorded under the "
        "wrong procedure identity:\n" + "\n".join(problems)
    )
