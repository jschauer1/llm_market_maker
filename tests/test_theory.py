import json
from datetime import datetime, timezone

import pytest

from tools import db, ledger, provenance, theories
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)
from tools.theory import JudgmentExecution, Theory, TheoryContext

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
TS = "2026-08-24T12:00:00Z"


def mkm(ticker="KXT-26", yes_ask=0.4, event="KXT"):
    return Market(platform="kalshi", ticker=ticker, yes_ask=yes_ask,
                  is_open=True, event_ticker=event, raw={})


def cand(ticker="KXT-26", event="KXT"):
    return Candidate(legs=(Leg(market=mkm(ticker, event=event), side="yes",
                               price=0.4),), days_to_close=2.0)


class Mechanical(Theory):
    id = "stub_mech"
    name = "Stub Mechanical"
    version = 1

    def screen(self, ctx):
        return [Candidate(legs=(Leg(market=m, side="yes", price=m.yes_ask),),
                          days_to_close=1.0)
                for m in ctx.board if (m.yes_ask or 1.0) <= 0.5]

    def price(self, ctx, cands, verdicts=None):
        return [ScoredCandidate(candidate=c, edge=Edge(pts_net=5.0,
                                                       basis="model"))
                for c in cands]


class MechanicalDocumented(Theory):
    """A mechanical theory that voluntarily records its deciding artifact
    -- the mention_family shape: uses_llm_judgment=False but prompts is
    non-empty, so finish() records provenance anyway."""

    id = "stub_mech_documented"
    name = "Stub Mechanical Documented"
    version = 1
    # Any committed file works as a prompt path for a test stub; provenance
    # hashes whatever is on disk.
    prompts = {"other": "theories/_TEMPLATE/THEORY.md"}

    def screen(self, ctx):
        return [cand()]

    def price(self, ctx, cands, verdicts=None):
        return [ScoredCandidate(candidate=c, edge=Edge(pts_net=5.0,
                                                       basis="model"))
                for c in cands]


class Judged(Theory):
    id = "stub_judged"
    name = "Stub Judged"
    version = 1
    uses_llm_judgment = True
    # Any committed file works as a prompt path for a test stub; provenance
    # hashes whatever is on disk.
    prompts = {"analysis": "theories/_TEMPLATE/THEORY.md"}

    def screen(self, ctx):
        return ScreenResult(candidates=(cand(),),
                            funnel={"board_markets": len(ctx.board)})

    def judgment_payload(self, cands):
        return [{"key": c.key, "title": c.title} for c in cands] or None

    def price(self, ctx, cands, verdicts=None):
        verdicts = verdicts or {}
        return [ScoredCandidate(candidate=c,
                                edge=Edge(pts_net=4.0, basis="prior"),
                                confidence=verdicts[c.key].bucket,
                                judged_blind=True)
                for c in cands if c.key in verdicts]


class JudgedNoPrompts(Theory):
    """Declares uses_llm_judgment but leaves Theory.prompts at its default
    {} -- the shape finding I3 closes off: finish() used to skip
    _record_provenance whenever prompts was empty, regardless of whether
    the theory claimed LLM judgment, so a theory like this could record
    opportunities with no provenance at all."""

    id = "stub_judged_no_prompts"
    name = "Stub Judged No Prompts"
    version = 1
    uses_llm_judgment = True

    def screen(self, ctx):
        return [cand()]

    def price(self, ctx, cands, verdicts=None):
        return [ScoredCandidate(candidate=c, edge=Edge(pts_net=5.0,
                                                       basis="model"))
                for c in cands]


class JudgedTwoStages(Judged):
    id = "stub_judged_two_stages"
    prompts = {
        "gate": "theories/_TEMPLATE/THEORY.md",
        "analysis": "theories/_TEMPLATE/THEORY.md",
    }


def fake_ctx(board=(), conn=None, judge_model=None):
    return TheoryContext(conn=conn, board=list(board), now=NOW,
                         judge_model=judge_model)


def test_theory_context_keeps_existing_positional_bucket_rates_slot():
    rates = lambda *_: {}  # noqa: E731 - identity matters in this regression
    ctx = TheoryContext(None, [], NOW, "r1", "live", "opus", rates)
    assert ctx.bucket_rates is rates
    assert ctx.judgment_executions == ()


def test_direct_theory_context_freezes_and_validates_stage_executions():
    execution = JudgmentExecution(stage="analysis", model="gpt-6-astra")
    ctx = TheoryContext(None, [], NOW, judgment_executions=[execution])
    assert ctx.judgment_executions == (execution,)

    with pytest.raises(ValueError, match="not both"):
        TheoryContext(None, [], NOW, judge_model="opus",
                      judgment_executions=[execution])
    with pytest.raises(TypeError, match="JudgmentExecution"):
        TheoryContext(None, [], NOW, judgment_executions=["analysis"])


def test_theory_is_abstract():
    with pytest.raises(TypeError):
        Theory()


def test_a_subclass_missing_price_cannot_instantiate():
    class Half(Theory):
        id, name, version = "half", "Half", 1

        def screen(self, ctx):
            return []

    with pytest.raises(TypeError):
        Half()


def test_start_wraps_a_bare_list_into_a_screen_result():
    run = Mechanical().start(fake_ctx([mkm()]))
    assert isinstance(run.screen_result, ScreenResult)
    assert run.needs_judgment is False


def test_finish_refuses_an_unjudged_judgment_run():
    run = Judged().start(fake_ctx([mkm()]))
    assert run.needs_judgment is True
    with pytest.raises(RuntimeError, match="verdicts"):
        run.finish(dry_run=True)


def test_apply_rejects_a_verdict_key_matching_no_candidate():
    run = Judged().start(fake_ctx([mkm()]))
    with pytest.raises(ValueError, match="no candidate"):
        run.apply({"NOPE": Verdict(bucket="strong")})


def test_apply_rejects_a_non_verdict_value():
    run = Judged().start(fake_ctx([mkm()]))
    with pytest.raises(TypeError, match="category, never a number"):
        run.apply({"KXT": 0.78})


def test_attach_completed_batches_rejects_duplicate_candidate_ownership():
    """Two distinct dispatches cannot both own one candidate result."""
    from tools.judgments import (BatchCompletion, BatchRequest,
                                 JudgmentBatchReceipt)

    request_a = BatchRequest.build(
        run_id="live", theory_id="stub_judged", theory_version=1,
        run_mode="live", decision_at=NOW.isoformat(),
        requested_model="m", requested_effort=None,
        requested_web_search=True, output_path="a.verdicts.json",
        stage="analysis", batch_id="a", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Prompt A")
    request_b = BatchRequest.build(
        run_id="live", theory_id="stub_judged", theory_version=1,
        run_mode="live", decision_at=NOW.isoformat(),
        requested_model="m", requested_effort=None,
        requested_web_search=True, output_path="b.verdicts.json",
        stage="analysis", batch_id="b", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Prompt B")
    completion = BatchCompletion.build(
        model="m", effort=None, web_search=True,
        results={"KXT": Verdict(bucket="strong")},
        completed_at="2026-09-04T12:00:00+00:00")
    batches = (
        JudgmentBatchReceipt(request_a, completion),
        JudgmentBatchReceipt(request_b, completion),
    )

    with pytest.raises(ValueError, match="more than one batch"):
        Judged().start(fake_ctx([mkm()])).attach_completed_batches(batches)


def test_attach_completed_batches_validates_run_identity():
    from tools.judgments import (BatchCompletion, BatchRequest,
                                 JudgmentBatchReceipt)

    request = BatchRequest.build(
        run_id="another-run", theory_id="stub_judged", theory_version=1,
        run_mode="live", decision_at=NOW.isoformat(),
        requested_model="m", requested_effort=None,
        requested_web_search=True, output_path="a.verdicts.json",
        stage="analysis", batch_id="a", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Prompt A")
    completion = BatchCompletion.build(
        model="m", effort=None, web_search=True,
        results={"KXT": Verdict(bucket="strong")},
        completed_at="2026-09-04T12:00:00+00:00")

    with pytest.raises(ValueError, match="run identity"):
        Judged().start(fake_ctx([mkm()])).attach_completed_batches(
            (JudgmentBatchReceipt(request, completion),))


def test_attach_completed_batches_uses_named_final_stage_in_a_cascade():
    from tools.judgments import (BatchCompletion, BatchRequest,
                                 JudgmentBatchReceipt)

    gate_request = BatchRequest.build(
        run_id="live", theory_id="stub_judged_two_stages", theory_version=1,
        run_mode="live", decision_at=NOW.isoformat(),
        requested_model="small", requested_effort="minimal",
        requested_web_search=False, output_path="gate.verdicts.json",
        stage="gate", batch_id="gate-a", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Gate prompt")
    analysis_request = BatchRequest.build(
        run_id="live", theory_id="stub_judged_two_stages", theory_version=1,
        run_mode="live", decision_at=NOW.isoformat(),
        requested_model="strong", requested_effort="high",
        requested_web_search=True, output_path="analysis.verdicts.json",
        stage="analysis", batch_id="analysis-a", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Analysis prompt")
    gate_completion = BatchCompletion.build(
        model="small", effort="minimal", web_search=False,
        results={"KXT": Verdict(bucket="weak")},
        completed_at="2026-09-04T12:00:00+00:00")
    analysis_completion = BatchCompletion.build(
        model="strong", effort="high", web_search=True,
        results={"KXT": Verdict(bucket="strong")},
        completed_at="2026-09-04T12:01:00+00:00")
    batches = (
        JudgmentBatchReceipt(gate_request, gate_completion),
        JudgmentBatchReceipt(analysis_request, analysis_completion),
    )

    run = JudgedTwoStages().start(fake_ctx([mkm()]))
    run.attach_completed_batches(batches, verdict_stage="analysis")

    assert run.verdicts == {"KXT": Verdict(bucket="strong")}
    assert [(execution.stage, execution.model)
            for execution in run.ctx.judgment_executions] == [
        ("gate", "small"), ("analysis", "strong"),
    ]


@pytest.mark.parametrize(
    ("run_mode", "decision_at"),
    [("backtest", NOW.isoformat()),
     ("live", "2026-08-25T12:00:00+00:00")],
)
def test_attach_completed_batches_validates_persisted_run_context(
        run_mode, decision_at):
    from tools.judgments import (BatchCompletion, BatchRequest,
                                 JudgmentBatchReceipt)

    request = BatchRequest.build(
        run_id="live", theory_id="stub_judged", theory_version=1,
        run_mode=run_mode, decision_at=decision_at,
        requested_model="m", requested_effort=None,
        requested_web_search=False, output_path="a.verdicts.json",
        stage="analysis", batch_id="a", candidate_keys=("KXT",),
        payload=[{"key": "KXT"}], rendered_prompt="Prompt A")
    completion = BatchCompletion.build(
        model="m", effort=None, web_search=False,
        results={"KXT": Verdict(bucket="strong")},
        completed_at="2026-09-04T12:00:00+00:00")

    with pytest.raises(ValueError, match="run context"):
        Judged().start(fake_ctx([mkm()])).attach_completed_batches(
            (JudgmentBatchReceipt(request, completion),))


def test_dry_run_scores_without_writing():
    run = Judged().start(fake_ctx([mkm()]))     # conn=None: any DB touch throws
    result = run.apply({"KXT": Verdict(bucket="strong")}).finish(dry_run=True)
    assert result.judged is True
    assert result.opportunity_ids == ()
    assert [s.confidence for s in result.scored] == ["strong"]
    assert result.funnel["recorded"] == 0


def test_finish_requires_judge_model_for_an_llm_theory(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    run = Judged().start(fake_ctx([mkm()], conn=conn))
    run.apply({"KXT": Verdict(bucket="strong")})
    with pytest.raises(RuntimeError, match="judge_model"):
        run.finish()
    conn.close()


def test_one_legacy_judge_model_cannot_describe_multiple_stages(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged_two_stages", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged_two_stages", True)
    run = JudgedTwoStages().start(
        fake_ctx([mkm()], conn=conn, judge_model="gpt-6-astra"))
    run.apply({"KXT": Verdict(bucket="strong")})
    with pytest.raises(RuntimeError, match="multiple.*stages"):
        run.finish()
    conn.close()


def test_stage_executions_record_distinct_models_effort_search_and_prompt(
        tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged_two_stages", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged_two_stages", True)
    executions = (
        JudgmentExecution(stage="gate", model="gpt-5.6-luna",
                          effort="minimal", web_search=False,
                          rendered_prompt="Gate the candidate from input A."),
        JudgmentExecution(stage="analysis", model="gpt-6-astra",
                          effort="high", web_search=True,
                          rendered_prompt="Analyze the candidate from input B."),
    )
    ctx = TheoryContext.build(conn=conn, board=[mkm()], now=NOW,
                              judgment_executions=executions)
    JudgedTwoStages().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")}).finish()

    rows = {r["stage"]: r for r in provenance.list_judgment_runs(
        conn, theory_id="stub_judged_two_stages")}
    assert rows["gate"]["model"] == "gpt-5.6-luna"
    assert rows["gate"]["effort"] == "minimal"
    assert rows["gate"]["web_search"] == 0
    assert rows["gate"]["prompt_text"] == "Gate the candidate from input A."
    assert rows["analysis"]["model"] == "gpt-6-astra"
    assert rows["analysis"]["effort"] == "high"
    assert rows["analysis"]["web_search"] == 1
    assert rows["analysis"]["prompt_text"] == \
        "Analyze the candidate from input B."
    conn.close()


def test_multiple_executions_in_one_stage_record_every_rendered_prompt(
        tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    executions = (
        JudgmentExecution(stage="analysis", model="gpt-6-astra",
                          effort="high", web_search=True,
                          rendered_prompt="Analyze batch A."),
        JudgmentExecution(stage="analysis", model="gpt-5.6-luna",
                          effort="medium", web_search=False,
                          rendered_prompt="Analyze batch B."),
    )
    ctx = TheoryContext.build(conn=conn, board=[mkm()], now=NOW,
                              judgment_executions=executions)
    Judged().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")}).finish()

    rows = provenance.list_judgment_runs(conn, theory_id="stub_judged")
    assert [(row["model"], row["effort"], row["web_search"],
             row["prompt_text"]) for row in rows] == [
        ("gpt-6-astra", "high", 1, "Analyze batch A."),
        ("gpt-5.6-luna", "medium", 0, "Analyze batch B."),
    ]
    conn.close()


def test_exact_duplicate_stage_execution_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    execution = JudgmentExecution(
        stage="analysis", model="gpt-6-astra", effort="high",
        web_search=True, rendered_prompt="Analyze batch A.")
    ctx = TheoryContext.build(
        conn=conn, board=[mkm()], now=NOW,
        judgment_executions=(execution, execution))
    Judged().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")}).finish()
    assert len(provenance.list_judgment_runs(
        conn, theory_id="stub_judged")) == 1
    conn.close()


@pytest.mark.parametrize(
    ("executions", "message"),
    [
        ((JudgmentExecution(stage="gate", model="m", web_search=False),),
         "missing=.*analysis"),
        ((JudgmentExecution(stage="gate", model="m", web_search=False),
          JudgmentExecution(stage="analysis", model="m", web_search=False),
          JudgmentExecution(stage="other", model="m", web_search=False)),
         "unexpected=.*other"),
    ],
)
def test_stage_executions_require_exact_prompt_stage_coverage(
        tmp_path, executions, message):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged_two_stages", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged_two_stages", True)
    ctx = TheoryContext.build(conn=conn, board=[mkm()], now=NOW,
                              judgment_executions=executions)
    run = JudgedTwoStages().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")})
    with pytest.raises(RuntimeError, match=message):
        run.finish()
    conn.close()


@pytest.mark.parametrize("web_search", [None, True])
def test_explicit_backtest_execution_requires_web_search_false(
        tmp_path, web_search):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    execution = JudgmentExecution(
        stage="analysis", model="gpt-6-astra", web_search=web_search)
    ctx = TheoryContext.build(
        conn=conn, board=[mkm()], now=NOW, run_mode="backtest",
        judgment_executions=(execution,))
    run = Judged().start(ctx).apply({"KXT": Verdict(bucket="strong")})
    with pytest.raises(RuntimeError, match="explicit.*False"):
        run.finish()
    conn.close()


def test_explicit_backtest_execution_records_web_search_false(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    execution = JudgmentExecution(
        stage="analysis", model="gpt-6-astra", web_search=False)
    ctx = TheoryContext.build(
        conn=conn, board=[mkm()], now=NOW, run_mode="backtest",
        run_id="backtest-explicit", judgment_executions=(execution,))
    Judged().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")}).finish()
    row = provenance.list_judgment_runs(conn, theory_id="stub_judged")[0]
    assert row["web_search"] == 0
    conn.close()


def test_legacy_backtest_judge_model_still_records_web_search_false(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_judged", "Stub", "x", now=TS)
    theories.set_uses_llm_judgment(conn, "stub_judged", True)
    ctx = TheoryContext.build(
        conn=conn, board=[mkm()], now=NOW, run_mode="backtest",
        run_id="backtest-legacy",
        judge_model="legacy-model")
    Judged().start(ctx).apply(
        {"KXT": Verdict(bucket="strong")}).finish()
    row = provenance.list_judgment_runs(conn, theory_id="stub_judged")[0]
    assert row["web_search"] == 0
    conn.close()


def test_finish_refuses_an_llm_theory_with_no_prompts_declared():
    """uses_llm_judgment=True with prompts={} must not slip through:
    without this, finish() would write ledger rows for a judgment theory
    with zero provenance, exactly the omission record_opportunity's
    require_provenance exists to make impossible."""
    run = JudgedNoPrompts().start(fake_ctx([mkm()]))
    assert run.needs_judgment is False   # no judgment_payload override
    with pytest.raises(RuntimeError, match="prompts"):
        run.finish(dry_run=True)


def test_a_scored_candidate_with_non_default_evidence_records_it(tmp_path):
    """A Polymarket-sourced finding (CLAUDE.md: Polymarket is a first-class
    research source) must keep its provenance through finish() --
    OpportunityRecord.from_scored must not hardcode evidence_source
    ='kalshi' or drop evidence_market_id, even though the recorded row
    still resolves to a Kalshi ticker."""
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)

    class PolySourced(Theory):
        id = "stub_poly"
        name = "Stub Poly Sourced"
        version = 1

        def screen(self, ctx):
            return [cand()]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(
                candidate=c, edge=Edge(pts_net=5.0, basis="model"),
                evidence_source="polymarket", evidence_market_id="0xabc",
            ) for c in cands]

    theories.register(conn, "stub_poly", "Stub Poly Sourced", "x", now=TS)
    ctx = TheoryContext.build(conn=conn, board=[mkm()], now=NOW)
    PolySourced().start(ctx).finish()
    row = conn.execute(
        "SELECT kalshi_ticker, evidence_source, evidence_market_id"
        "  FROM opportunities"
    ).fetchone()
    assert row["kalshi_ticker"] == "KXT-26"
    assert row["evidence_source"] == "polymarket"
    assert row["evidence_market_id"] == "0xabc"
    conn.close()


def test_mechanical_theory_records_web_search_false_on_live_run(tmp_path):
    """A run recorded as 'none (deterministic)' had no model in the loop
    at all, so it categorically did no web search -- unlike an LLM theory,
    this does not depend on run_mode. A mechanical theory's live-run
    provenance row must say web_search=False, never NULL."""
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_mech_documented", "Stub", "x", now=TS)
    ctx = TheoryContext.build(conn=conn, board=[mkm()], now=NOW,
                              run_mode="live")
    MechanicalDocumented().start(ctx).finish()
    runs = provenance.list_judgment_runs(conn, theory_id="stub_mech_documented")
    assert len(runs) == 1
    assert runs[0]["model"] == "none (deterministic)"
    assert runs[0]["web_search"] == 0
    conn.close()


def test_a_basket_candidates_floor_reaches_the_ledger(tmp_path):
    """finish() is the single ledger path, so a floor declared on the
    position must survive it -- otherwise a floor basket would record as
    all-or-nothing and be scored on the wrong event."""
    from tools import ledger, theories
    from tools.domain import Candidate, Edge, Leg, ScoredCandidate

    class FloorBasket(Theory):
        id, name, version = "stub_floor", "Stub Floor", 1

        def screen(self, ctx):
            legs = tuple(Leg(market=m, side="yes", price=0.5)
                         for m in ctx.board)
            return [Candidate(legs=legs, days_to_close=1.0,
                              min_payout=1.0, max_payout=2.0)]

        def price(self, ctx, cands, verdicts=None):
            return [ScoredCandidate(candidate=c,
                                    edge=Edge(pts_net=4.0, basis="model"))
                    for c in cands]

    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "stub_floor", "Stub Floor", "x", now=TS)
    ctx = TheoryContext.build(
        conn=conn, board=[mkm("KXA-26"), mkm("KXB-26")], now=NOW)
    result = FloorBasket().start(ctx).finish()
    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["min_payout"] == pytest.approx(1.0)
    assert row["max_payout"] == pytest.approx(2.0)
    conn.close()


# --- a theory can record structured context with its rows ---------------
#
# Found 2026-08-29. `record_opportunity` has always accepted `extra_json`,
# but `ScoredCandidate` had no field for it and `from_scored` never passed
# one, so no theory going through the contract could record structured
# per-candidate context. calibration_harvest's live path recorded 10,269
# rows whose whole stated purpose was "recorded so the cell accrues
# settlements" -- and `collect.cell_rates` reads the cell out of
# `extra_json`, so every one of them was unreadable and the rows could
# never feed the grid they existed to grow.


def _scored_with_extra(extra):
    market = Market(platform="kalshi", ticker="KXEXTRA-26", is_open=True,
                    yes_ask=0.40)
    candidate = Candidate(
        legs=(Leg(market=market, side="yes", price=0.40),),
        days_to_close=3.0,
    )
    return ScoredCandidate(
        candidate=candidate,
        edge=Edge(pts_net=1.0, basis="model"),
        extra=extra,
    )


class _ExtraTheory(Theory):
    id = "extra_theory"
    name = "Extra Theory"
    version = 1

    def __init__(self, extra):
        self._extra = extra

    def screen(self, ctx):
        return [_scored_with_extra(self._extra).candidate]

    def price(self, ctx, cands, verdicts=None):
        return [_scored_with_extra(self._extra)]


def test_scored_candidate_extra_reaches_the_ledger(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "extra_theory", "Extra Theory",
                      "theories/extra_theory", now=NOW.isoformat())

    extra = {"cell": "weather|<=2d|0.65-0.75", "domain": "weather"}
    ctx = TheoryContext.build(conn, [], NOW, run_id="live-extra")
    result = _ExtraTheory(extra).start(ctx).finish()

    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert json.loads(row["extra_json"]) == extra


def test_scored_candidate_without_extra_records_no_extra_json(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    theories.register(conn, "extra_theory", "Extra Theory",
                      "theories/extra_theory", now=NOW.isoformat())

    ctx = TheoryContext.build(conn, [], NOW, run_id="live-extra")
    result = _ExtraTheory(None).start(ctx).finish()

    row = ledger.get_opportunity(conn, result.opportunity_ids[0])
    assert row["extra_json"] is None
