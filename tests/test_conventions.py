"""Repo-wide conventions the OOP layer promises (spec sections 3.2, 4.2,
4.5c, 9): every theory package exposes a proper singleton, nobody
overrides the workflow, a Verdict can never grow a number, and the
migration shim is only exercised from allowlisted modules."""

from dataclasses import fields

from tools import domain, registry
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
SHIM_ALLOWLIST = {
    "tools.board",
    "tools.snapshot",
    "tools.match_market",
    "theories.insider_bias.screen",
    "theories.insider_bias.insider_judgment.gate",
    "theories.insider_bias.insider_judgment.pipeline",
    "theories.insider_bias.insider_judgment.theory",
    "theories.insider_bias.insider_judgment.backtest",
    "theories.insider_bias.mention_family.mention_bucket",
    "theories.insider_bias.mention_family.theory",
}


def test_shim_is_exercised_only_from_allowlisted_modules():
    from tests.characterization import conftest as cz
    from theories.insider_bias.insider_judgment import THEORY as ij
    from theories.insider_bias.mention_family import THEORY as mf
    from tools.theory import TheoryContext

    domain.SHIM_CALLERS.clear()
    ctx = TheoryContext(conn=None, board=cz.board_input(),
                        now=cz.frozen_now())
    run = ij.start(ctx)                       # exercises the whole pipeline
    mf.screen(ctx)
    prod = {m for m in domain.SHIM_CALLERS
            if m.startswith(("tools.", "theories."))}
    assert prod <= SHIM_ALLOWLIST, sorted(prod - SHIM_ALLOWLIST)
