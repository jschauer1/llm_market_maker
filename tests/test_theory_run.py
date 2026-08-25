"""Statelessness: the regression tests for the _last_funnel bug the spec's
section 4.4 describes. One Theory instance, many runs, no shared state.

The two stub theories in `tests/test_theory.py` happen to build a fresh
funnel dict literal on every `screen()` call, so the first two tests below
would still pass even if `TheoryRun` held `screen_result` (and its dicts)
by bare reference instead of copying them. `AliasingScreen` below closes
that gap: it deliberately returns the *same* `ScreenResult` -- and the
same `funnel`/`gate_removed` dicts -- from every call, the way a theory
caching a payload or reading a module-level constant would, and proves
the run still cannot leak state through it (spec 8.7: enforced by test,
not convention)."""

from tests.test_theory import Judged, Mechanical, cand, fake_ctx, mkm
from tools.domain import ScreenResult, Verdict
from tools.theory import Theory


def test_the_same_instance_started_twice_yields_independent_runs():
    theory = Judged()
    run1 = theory.start(fake_ctx([mkm()]))
    run2 = theory.start(fake_ctx([mkm(), mkm("KXU-26", event="KXU")]))
    assert run1 is not run2
    assert run1.screen_result is not run2.screen_result
    assert run1.screen_result.funnel is not run2.screen_result.funnel
    assert run1.screen_result.funnel == {"board_markets": 1}
    assert run2.screen_result.funnel == {"board_markets": 2}
    run1.apply({"KXT": Verdict(bucket="strong")})
    assert run2.verdicts is None


def test_two_theories_interleaved_do_not_corrupt_each_other():
    a, b = Mechanical(), Judged()
    ra = a.start(fake_ctx([mkm(yes_ask=0.3)]))
    rb = b.start(fake_ctx([mkm()]))
    fa = ra.finish(dry_run=True)
    rb.apply({"KXT": Verdict(bucket="weak")})
    fb = rb.finish(dry_run=True)
    assert fa.theory_id == "stub_mech" and fb.theory_id == "stub_judged"
    assert fa.judged is False and fb.judged is True


# A theory that hands back the identical ScreenResult -- and identical
# funnel/gate_removed dicts -- on every screen() call, e.g. a cached
# payload or a module-level constant.
_SHARED_FUNNEL = {"board_markets": 1}
_SHARED_GATE_REMOVED = {"weather": 3}
_SHARED_SCREEN_RESULT = ScreenResult(candidates=(cand(),),
                                     funnel=_SHARED_FUNNEL,
                                     gate_removed=_SHARED_GATE_REMOVED)


class AliasingScreen(Theory):
    """Deliberately misbehaves: returns one shared ScreenResult instance
    (and its shared dicts) from every screen() call, instead of building
    a fresh one per run."""

    id = "stub_aliasing"
    name = "Stub Aliasing"
    version = 1

    def screen(self, ctx):
        return _SHARED_SCREEN_RESULT

    def price(self, ctx, cands, verdicts=None):
        return []


def test_a_theory_that_reuses_one_screen_result_still_yields_independent_runs():
    theory = AliasingScreen()
    run1 = theory.start(fake_ctx())
    run2 = theory.start(fake_ctx())

    # Neither run holds the object (or the dicts) the theory handed out,
    # and the two runs do not share them with each other.
    assert run1.screen_result is not _SHARED_SCREEN_RESULT
    assert run2.screen_result is not _SHARED_SCREEN_RESULT
    assert run1.screen_result is not run2.screen_result
    assert run1.screen_result.funnel is not _SHARED_FUNNEL
    assert run2.screen_result.funnel is not _SHARED_FUNNEL
    assert run1.screen_result.funnel is not run2.screen_result.funnel
    assert run1.screen_result.gate_removed is not _SHARED_GATE_REMOVED
    assert run2.screen_result.gate_removed is not _SHARED_GATE_REMOVED
    assert run1.screen_result.gate_removed is not run2.screen_result.gate_removed

    # Mutating one run's funnel/gate_removed must not be observable
    # through the other run or through the theory's own shared dict.
    run1.screen_result.funnel["mutated"] = True
    run1.screen_result.gate_removed["mutated"] = True
    assert "mutated" not in run2.screen_result.funnel
    assert "mutated" not in run2.screen_result.gate_removed
    assert "mutated" not in _SHARED_FUNNEL
    assert "mutated" not in _SHARED_GATE_REMOVED
