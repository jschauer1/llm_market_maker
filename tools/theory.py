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

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Callable, ClassVar

from tools import ledger, provenance
from tools.domain import (Candidate, ScanResult, ScoredCandidate,
                          ScreenResult, Verdict)


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

    @classmethod
    def build(cls, conn, board, now, *, run_id: str = "live",
              run_mode: str = "live",
              judge_model: str | None = None) -> "TheoryContext":
        """The live constructor: binds score.bucket_rates to the connection
        (a per-instance binding cannot be a dataclass default). Tests build
        the dataclass directly with fakes."""
        from tools import score
        return cls(conn=conn, board=board, now=now, run_id=run_id,
                   run_mode=run_mode, judge_model=judge_model,
                   bucket_rates=partial(score.bucket_rates, conn))


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
            evidence_source="kalshi",
        )
        if c.is_basket:
            legs = [dict(kalshi_ticker=l.market.ticker, outcome=l.side,
                         entry_price=l.price, spread_at_call=l.market.spread,
                         volume_at_call=l.market.volume) for l in c.legs]
            return cls(single=None,
                       basket=dict(common, legs=legs,
                                   max_payout=c.max_payout))
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
        self.theory = theory
        self.ctx = ctx
        self.screen_result = screen_result
        self.candidates: list[Candidate] = list(screen_result.candidates)
        self.payload = theory.judgment_payload(self.candidates)
        self.verdicts: dict[str, Verdict] | None = None

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
        """Model + prompt per judging stage, before any row lands.

        The model recorded is the JUDGING model (ctx.judge_model -- the
        subagent's, when one was dispatched), never implicitly this
        process's. A mechanical theory with a prompts entry records
        'none (deterministic)', preserving voluntary self-documentation."""
        model = self.ctx.judge_model
        if self.theory.uses_llm_judgment:
            if not model:
                raise RuntimeError(
                    f"{self.theory.id} uses LLM judgment but "
                    "ctx.judge_model is not set; recording the parent's "
                    "model for a judgment it did not make would corrupt "
                    "provenance (spec 4.9)"
                )
        else:
            model = model or "none (deterministic)"
        web = False if self.ctx.run_mode == "backtest" else None
        for stage, path in self.theory.prompts.items():
            provenance.record_judgment_run(
                self.ctx.conn, run_id=self.ctx.run_id,
                theory_id=self.theory.id,
                theory_version=self.theory.version,
                stage=stage, model=model, prompt_path=path, web_search=web,
            )

    def _registry_status(self) -> str:
        try:
            from tools import theories as theories_db
            row = theories_db.get(self.ctx.conn, self.theory.id)
            return row["status"] if row is not None else "unregistered"
        except Exception:
            return "unregistered"      # fake context in tests: no DB
