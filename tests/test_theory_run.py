"""Statelessness: the regression tests for the _last_funnel bug the spec's
section 4.4 describes. One Theory instance, many runs, no shared state."""

from tests.test_theory import Judged, Mechanical, fake_ctx, mkm
from tools.domain import Verdict


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
