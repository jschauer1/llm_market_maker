"""The theory contract (OOP spec sections 4.3-4.5).

A theory inherits *what to do* (`start`, `finish` -- the Template Method
half) and is handed *what it may touch* (`TheoryContext` -- the injection
half). Never a toolbox base class: publishing self.list_open() on every
theory would make the forbidden path (bypassing the shared board) the most
discoverable thing on the object.

`Theory` is stateless. All per-run state -- the ScreenResult, the stage-2
payload, applied verdicts -- lives on `TheoryRun`, so one instance can run
twice, or interleave with other theories, without corruption.

The contract is OPTIONAL FOR RUNNING and MANDATORY FOR RECORDING. Every
tool stays directly callable; ad-hoc research needs none of this. The one
non-negotiable is the ledger boundary: when a finding is recorded as
evidence, provenance, an honest edge_basis, and a Kalshi ticker hold
without exception. finish() is that boundary, and no subclass overrides it.

A verdict is a category, never a number: the judge's entire output channel
is `Verdict` (bucket + rationale). Probabilities enter downstream via
measured bucket rates or a mechanical model -- never from the judge.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
from typing import Callable, ClassVar, Iterable

from tools import ledger, provenance
from tools.domain import (Candidate, ScanResult, ScoredCandidate,
                          ScreenResult, Verdict)


@dataclass(frozen=True, slots=True)
class JudgmentExecution:
    """What actually ran for one judging dispatch.

    A cascade may use different models and effort per stage. Keeping each
    execution immutable and stage-labelled prevents one parent model string
    from being stamped across work done by several judges. `rendered_prompt`
    is optional because a prompt file with no substitutions is already exact.
    """

    stage: str
    model: str
    effort: str | None = None
    web_search: bool | None = None
    rendered_prompt: str | None = None

    def __post_init__(self) -> None:
        if not self.stage or not self.stage.strip():
            raise ValueError("judgment execution stage is required")
        if not self.model or not self.model.strip():
            raise ValueError("judgment execution model is required")


@dataclass(frozen=True, slots=True)
class TheoryContext:
    """What the harness offers a theory -- not a whitelist of what it may
    touch. A theory whose thesis needs more (a weather feed, an on-chain
    query) reaches further; ctx.conn and the Fetch convention are there."""

    conn: sqlite3.Connection | None
    board: list
    now: datetime
    run_id: str = "live"
    run_mode: str = "live"
    judge_model: str | None = None     # set by the dispatching parent (4.9)
    bucket_rates: Callable | None = None
    judgment_executions: tuple[JudgmentExecution, ...] = ()

    def __post_init__(self) -> None:
        try:
            executions = tuple(self.judgment_executions)
        except TypeError as exc:
            raise TypeError(
                "judgment_executions must contain JudgmentExecution values"
            ) from exc
        if any(not isinstance(item, JudgmentExecution) for item in executions):
            raise TypeError(
                "judgment_executions must contain JudgmentExecution values"
            )
        if self.judge_model is not None and executions:
            raise ValueError(
                "pass judge_model for the legacy single-stage path or "
                "judgment_executions for stage-specific provenance, not both"
            )
        object.__setattr__(self, "judgment_executions", executions)

    @classmethod
    def build(cls, conn, board, now, *, run_id: str = "live",
              run_mode: str = "live",
              judge_model: str | None = None,
              judgment_executions: Iterable[JudgmentExecution] = (),
              ) -> "TheoryContext":
        """The live constructor: binds score.bucket_rates to the connection
        (a per-instance binding cannot be a dataclass default). Tests build
        the dataclass directly with fakes."""
        from tools import score
        executions = tuple(judgment_executions)
        return cls(conn=conn, board=board, now=now, run_id=run_id,
                   run_mode=run_mode, judge_model=judge_model,
                   bucket_rates=partial(score.bucket_rates, conn),
                   judgment_executions=executions)


class Theory(ABC):
    """Two required methods; everything else has a default (spec 3.2)."""

    id: ClassVar[str]
    name: ClassVar[str]
    version: ClassVar[int]
    uses_llm_judgment: ClassVar[bool] = False
    prompts: ClassVar[dict[str, str]] = {}   # stage -> repo-relative path

    # ---- the two methods a new theory must write ----

    @abstractmethod
    def screen(self, ctx: TheoryContext) -> "list[Candidate] | ScreenResult":
        """Stage 1. Mechanical, no model in the decision path. Return a
        bare list, or a ScreenResult when there are funnel or gate counts
        to report; start() wraps a bare list."""

    @abstractmethod
    def price(self, ctx: TheoryContext, cands: list[Candidate],
              verdicts: dict[str, Verdict] | None = None,
              ) -> list[ScoredCandidate]:
        """Attach an Edge. verdicts is None on a mechanical run; for a
        judgment theory it maps Candidate.key -> Verdict. Must set
        edge.basis honestly. A candidate the judge did not rule on is this
        method's call -- drop it or mark it rejected -- but never price it
        as if it had been judged."""

    # ---- optional stage 2 ----

    def judgment_payload(self, cands: list[Candidate]) -> list[dict] | None:
        """Stage 2 input, or None when the theory has no stage 2 (or
        nothing survived to judge). Payloads must be blind where the
        theory's procedure requires it -- build them by whitelist."""
        return None

    # ---- the workflow, inherited and never overridden ----

    def start(self, ctx: TheoryContext) -> "TheoryRun":
        result = self.screen(ctx)
        if isinstance(result, list):
            result = ScreenResult(candidates=tuple(result))
        return TheoryRun(self, ctx, result)


@dataclass(frozen=True)
class OpportunityRecord:
    """One scored candidate, assembled by finish() and ready for the
    ledger. Internal -- never part of a theory's surface (spec 4.1)."""

    single: dict | None      # record_opportunity kwargs, or None
    basket: dict | None      # record_basket kwargs, or None

    @classmethod
    def from_scored(cls, sc: ScoredCandidate, theory: "Theory",
                    ctx: TheoryContext) -> "OpportunityRecord":
        c, e = sc.candidate, sc.edge
        common = dict(
            theory_id=theory.id, theory_version=theory.version,
            edge_pts_net=e.pts_net, edge_basis=e.basis,
            model_prob=e.model_prob, edge_pts_gross=e.pts_gross,
            fee_pts=e.fee_pts, confidence=sc.confidence,
            judged_blind=sc.judged_blind, rationale=sc.rationale,
            run_mode=ctx.run_mode, run_id=ctx.run_id,
            evidence_source=sc.evidence_source,
            evidence_market_id=sc.evidence_market_id,
            # The as-of day the theory is deciding about, not the wall-clock
            # day the code happened to run (attempt-fidelity spec section 5).
            # A backtest sets ctx.now to the replayed day, so this dates the
            # attempt correctly for free; a live run's ctx.now is today,
            # which is what record_opportunity's own wall-clock default
            # would have produced anyway.
            decision_date=ctx.now.date().isoformat(),
            # Structured context the theory wants queryable later; prose
            # in `rationale` is not (see ScoredCandidate.extra).
            extra_json=json.dumps(sc.extra) if sc.extra else None,
        )
        if c.is_basket:
            legs = [dict(kalshi_ticker=l.market.ticker, outcome=l.side,
                         entry_price=l.price, spread_at_call=l.market.spread,
                         volume_at_call=l.market.volume) for l in c.legs]
            return cls(single=None,
                       basket=dict(common, legs=legs,
                                   max_payout=c.max_payout,
                                   min_payout=c.min_payout))
        leg = c.legs[0]
        return cls(basket=None,
                   single=dict(common, kalshi_ticker=leg.market.ticker,
                               outcome=leg.side, entry_price=leg.price,
                               spread_at_call=leg.market.spread,
                               volume_at_call=leg.market.volume))

    def write(self, conn: sqlite3.Connection) -> int:
        if self.basket is not None:
            opp_id, _ = ledger.record_basket(conn, **self.basket)
        else:
            opp_id, _ = ledger.record_opportunity(conn, **self.single)
        return opp_id


class TheoryRun:
    """One execution of one theory. Holds ALL per-run state."""

    def __init__(self, theory: Theory, ctx: TheoryContext,
                 screen_result: ScreenResult):
        self._initialize(theory, ctx, screen_result)
        self.payload = theory.judgment_payload(self.candidates)

    def _initialize(self, theory: Theory, ctx: TheoryContext,
                    screen_result: ScreenResult) -> None:
        self.theory = theory
        self.ctx = ctx
        # A theory may hand back a cached or module-level ScreenResult (or
        # reuse the same funnel/gate_removed dict across calls); this run
        # must own its copies so a mutation here -- or a second start()
        # against the same theory -- cannot be observed through the other.
        # `candidates` is a tuple of frozen Candidate objects, so no copy
        # is needed there; only the mutable dicts are re-wrapped.
        self.screen_result = ScreenResult(
            candidates=screen_result.candidates,
            funnel=dict(screen_result.funnel),
            gate_removed=dict(screen_result.gate_removed),
        )
        self.candidates: list[Candidate] = list(screen_result.candidates)
        self.verdicts: dict[str, Verdict] | None = None
        self._attached_batches: tuple = ()

    @classmethod
    def from_persisted(cls, *, theory: Theory, ctx: TheoryContext,
                       screen_result: ScreenResult,
                       candidates: Iterable[Candidate],
                       payload) -> "TheoryRun":
        """Rebuild saved run state without calling screen/payload builders.

        `tools.judgments.load_run_state` is the public persistence boundary;
        this constructor exists so recovery cannot accidentally re-screen a
        newer board or recompute a changed payload after model spend.
        """
        run = cls.__new__(cls)
        run._initialize(theory, ctx, screen_result)
        run.candidates = list(candidates)
        run.payload = payload
        return run

    @property
    def needs_judgment(self) -> bool:
        return self.payload is not None

    def apply(self, verdicts: dict[str, Verdict]) -> "TheoryRun":
        """Store out-of-process verdicts on the run. Chainable."""
        for value in verdicts.values():
            if not isinstance(value, Verdict):
                raise TypeError(
                    f"verdict values must be Verdict, got {value!r} -- a "
                    "judge returns a category, never a number"
                )
        known = {c.key for c in self.candidates}
        unknown = sorted(set(verdicts) - known)
        if unknown:
            raise ValueError(
                f"verdict keys match no candidate: {unknown}; keys are "
                "Candidate.key values from this run's screen"
            )
        self.verdicts = dict(verdicts)
        return self

    def attach_completed_batches(self, batches, *, verdict_stage=None
                                 ) -> "TheoryRun":
        """Validate and attach persisted batch results to this run.

        Every declared prompt stage must be represented.  For a one-stage
        theory that stage supplies the Verdicts.  A multi-stage caller names
        the stage whose categorical results are final; earlier stages remain
        persisted and become provenance, but do not overwrite final verdicts.
        """
        from tools.judgments import JudgmentBatchReceipt

        batches = tuple(batches)
        if not batches:
            raise ValueError("completed judgment batches must not be empty")
        if any(not isinstance(batch, JudgmentBatchReceipt)
               for batch in batches):
            raise TypeError(
                "completed batches must contain JudgmentBatchReceipt values"
            )
        if self._attached_batches:
            if batches == self._attached_batches:
                return self
            raise ValueError(
                "different judgment batches are already attached to this run"
            )
        if self.ctx.judge_model is not None or self.ctx.judgment_executions:
            raise ValueError(
                "cannot attach persisted batches to a run that already has "
                "judgment execution metadata"
            )
        incomplete = [
            (batch.request.stage, batch.request.batch_id)
            for batch in batches if not batch.completed
        ]
        if incomplete:
            raise RuntimeError(
                f"judgment batches are not complete: {incomplete}"
            )
        expected_identity = (
            self.ctx.run_id, self.theory.id, self.theory.version,
        )
        unique: dict[tuple[str, str], JudgmentBatchReceipt] = {}
        known = {candidate.key for candidate in self.candidates}
        for batch in batches:
            request = batch.request
            actual_identity = (
                request.run_id, request.theory_id, request.theory_version,
            )
            if actual_identity != expected_identity:
                raise ValueError(
                    "judgment batch run identity does not match TheoryRun: "
                    f"expected={expected_identity!r}, "
                    f"actual={actual_identity!r}"
                )
            expected_context = (
                self.ctx.run_mode, self.ctx.now.isoformat(),
            )
            actual_context = (request.run_mode, request.decision_at)
            if actual_context != expected_context:
                raise ValueError(
                    "judgment batch run context does not match TheoryRun: "
                    f"expected={expected_context!r}, "
                    f"actual={actual_context!r}"
                )
            if request.stage not in self.theory.prompts:
                raise ValueError(
                    f"judgment batch stage {request.stage!r} is not declared "
                    f"by {self.theory.id}.prompts"
                )
            unknown = sorted(set(request.candidate_keys) - known)
            if unknown:
                raise ValueError(
                    f"judgment batch keys match no candidate: {unknown}"
                )
            batch_identity = (request.stage, request.batch_id)
            previous = unique.get(batch_identity)
            if previous is not None and previous != batch:
                raise ValueError(
                    f"conflicting duplicate judgment batch: {batch_identity}"
                )
            unique[batch_identity] = batch
        batches = tuple(unique.values())
        actual_stages = {batch.request.stage for batch in batches}
        expected_stages = set(self.theory.prompts)
        if actual_stages != expected_stages:
            raise ValueError(
                "judgment batches do not cover declared prompt stages; "
                f"missing={sorted(expected_stages - actual_stages)}, "
                f"unexpected={sorted(actual_stages - expected_stages)}"
            )
        if verdict_stage is None:
            if len(expected_stages) != 1:
                raise ValueError(
                    "verdict_stage is required for a multi-stage theory"
                )
            verdict_stage = next(iter(expected_stages))
        if verdict_stage not in expected_stages:
            raise ValueError(
                f"verdict_stage {verdict_stage!r} is not a declared prompt "
                "stage"
            )
        verdicts: dict[str, Verdict] = {}
        owners: dict[str, str] = {}
        for batch in batches:
            if batch.request.stage != verdict_stage:
                continue
            for key, verdict in batch.verdicts.items():
                if key in owners:
                    raise ValueError(
                        f"candidate {key!r} belongs to more than one batch: "
                        f"{owners[key]!r} and {batch.request.batch_id!r}"
                    )
                owners[key] = batch.request.batch_id
                verdicts[key] = verdict
        missing = sorted(known - set(verdicts))
        if missing:
            raise ValueError(
                f"completed {verdict_stage!r} batches are missing candidate "
                f"keys: {missing}"
            )
        executions = tuple(
            JudgmentExecution(
                stage=batch.request.stage,
                model=batch.completion.model,
                effort=batch.completion.effort,
                web_search=batch.completion.web_search,
                rendered_prompt=batch.request.rendered_prompt,
            )
            for batch in batches
        )
        self.ctx = replace(
            self.ctx, judge_model=None, judgment_executions=executions)
        self._attached_batches = batches
        return self.apply(verdicts)

    def finish(self, *, dry_run: bool = False) -> ScanResult:
        """price -> provenance -> ledger -> ScanResult. Never overridden.

        dry_run scores without writing anything -- the exploratory escape
        hatch (spec 3.2)."""
        if self.needs_judgment and self.verdicts is None:
            raise RuntimeError(
                f"{self.theory.id} produced a judgment payload but no "
                "verdicts were applied; silently recording unjudged screen "
                "output would misstate edge_basis and judged_blind on every "
                "row. Call run.apply(verdicts) first, or finish(dry_run=True)."
            )
        if self.theory.uses_llm_judgment and not self.theory.prompts:
            raise RuntimeError(
                f"{self.theory.id} declares uses_llm_judgment=True but "
                "Theory.prompts is empty; finish() only records provenance "
                "when prompts is non-empty (see _record_provenance), so "
                "this theory could write ledger rows with no record of "
                "what judged them. Declare the prompt files that governed "
                "the judgment on Theory.prompts, e.g. "
                "prompts = {'analysis': "
                "'theories/<slug>/prompts/analysis.md'}."
            )
        scored = list(self.theory.price(self.ctx, self.candidates,
                                        self.verdicts))
        ids: list[int] = []
        if not dry_run and scored:
            if self.theory.prompts:
                self._record_provenance()
            for sc in scored:
                rec = OpportunityRecord.from_scored(sc, self.theory, self.ctx)
                opp_id = rec.write(self.ctx.conn)
                if sc.disposition != "screened":
                    ledger.interpret(self.ctx.conn, opp_id, sc.disposition,
                                     sc.rationale or "")
                ids.append(opp_id)
        funnel = dict(self.screen_result.funnel)
        funnel.update({"candidates": len(self.candidates),
                       "scored": len(scored), "recorded": len(ids)})
        return ScanResult(
            theory_id=self.theory.id, theory_version=self.theory.version,
            status=self._registry_status(), scored=tuple(scored),
            opportunity_ids=tuple(ids), funnel=funnel,
            gate_removed=dict(self.screen_result.gate_removed),
            judged=self.verdicts is not None,
        )

    def _record_provenance(self) -> None:
        """Model + prompt per judging dispatch, before any row lands.

        The model recorded is the JUDGING model (ctx.judge_model -- the
        subagent's, when one was dispatched), never implicitly this
        process's. A mechanical theory with a prompts entry records
        'none (deterministic)', preserving voluntary self-documentation.

        web_search follows the same split, and for a factual reason, not a
        cosmetic one: a run recorded as 'none (deterministic)' had no model
        in the loop at all, so it categorically did no web search --
        'False' is correct regardless of run_mode, live included. New explicit
        execution metadata must say False for every backtest batch; None would
        invent certainty when coerced. The legacy one-model path still records
        the historical backtest default for compatibility."""
        model = self.ctx.judge_model
        explicit_executions = bool(self.ctx.judgment_executions)
        if self.theory.uses_llm_judgment:
            executions = self.ctx.judgment_executions
            if explicit_executions:
                expected = set(self.theory.prompts)
                actual = {execution.stage for execution in executions}
                if actual != expected:
                    missing = sorted(expected - actual)
                    unexpected = sorted(actual - expected)
                    raise RuntimeError(
                        f"{self.theory.id} judgment_executions do not match "
                        f"its prompt stages; missing={missing}, "
                        f"unexpected={unexpected}"
                    )
            else:
                if len(self.theory.prompts) != 1:
                    raise RuntimeError(
                        f"{self.theory.id} has multiple judging stages; one "
                        "ctx.judge_model cannot truthfully describe all of "
                        "them. Pass at least one JudgmentExecution for each "
                        "stage."
                    )
                if not model:
                    raise RuntimeError(
                        f"{self.theory.id} uses LLM judgment but "
                        "ctx.judge_model is not set; recording the parent's "
                        "model for a judgment it did not make would corrupt "
                        "provenance (spec 4.9)"
                    )
                only_stage = next(iter(self.theory.prompts))
                executions = (
                    JudgmentExecution(stage=only_stage, model=model),
                )
        else:
            model = model or "none (deterministic)"
            executions = ()

        if self.theory.uses_llm_judgment:
            for execution in executions:
                stage = execution.stage
                path = self.theory.prompts[stage]
                if (explicit_executions
                        and self.ctx.run_mode == "backtest"
                        and execution.web_search is not False):
                    raise RuntimeError(
                        f"{self.theory.id} stage {stage!r} backtest execution "
                        "must set web_search explicitly to False"
                    )
                stage_model = execution.model
                effort = execution.effort
                web = (execution.web_search if explicit_executions else
                       (False if self.ctx.run_mode == "backtest" else None))
                rendered_prompt = execution.rendered_prompt
                provenance.record_judgment_run(
                    self.ctx.conn, run_id=self.ctx.run_id,
                    theory_id=self.theory.id,
                    theory_version=self.theory.version,
                    stage=stage, model=stage_model, prompt_path=path,
                    rendered_prompt=rendered_prompt, effort=effort,
                    web_search=web,
                )
        else:
            for stage, path in self.theory.prompts.items():
                provenance.record_judgment_run(
                    self.ctx.conn, run_id=self.ctx.run_id,
                    theory_id=self.theory.id,
                    theory_version=self.theory.version,
                    stage=stage, model=model, prompt_path=path,
                    web_search=False,
                )

    def _registry_status(self) -> str:
        try:
            from tools import theories as theories_db
            row = theories_db.get(self.ctx.conn, self.theory.id)
            return row["status"] if row is not None else "unregistered"
        except Exception:
            return "unregistered"      # fake context in tests: no DB
