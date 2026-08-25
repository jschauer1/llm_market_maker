from datetime import datetime, timezone

import pytest

from tools import db, provenance, theories
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)
from tools.theory import Theory, TheoryContext

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


def fake_ctx(board=(), conn=None, judge_model=None):
    return TheoryContext(conn=conn, board=list(board), now=NOW,
                         judge_model=judge_model)


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
