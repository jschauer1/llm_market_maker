"""Crash-safe receipts for out-of-process judgment batches.

This module owns persistence only.  It does not dispatch judges or decide how
a theory batches its work.  A receipt locks the blind payload identity and
exact rendered prompt; :func:`write_payload` creates the separate bare JSON
file a judge may read.  Receipt metadata and the price-bearing run state stay
operator-side.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from tools import atomic_write
from tools.domain import Candidate, Leg, Market, ScreenResult, Verdict
from tools.filelock import exclusive_lock

if TYPE_CHECKING:
    from tools.theory import Theory, TheoryRun


SCHEMA_VERSION = 1
_UNSET = object()


class ReceiptConflictError(ValueError):
    """A persisted request or completion disagrees with a retry."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("judgment payload must be finite JSON data") from exc


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class BatchRequest:
    """Immutable identity and blind input for one judging dispatch."""

    run_id: str
    theory_id: str
    theory_version: int
    run_mode: str
    decision_at: str
    requested_model: str
    requested_effort: str | None
    requested_web_search: bool | None
    output_path: str
    stage: str
    batch_id: str
    candidate_keys: tuple[str, ...]
    payload_sha256: str
    rendered_prompt: str
    _payload_json: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.run_id, "run_id"), (self.theory_id, "theory_id"),
            (self.run_mode, "run_mode"), (self.decision_at, "decision_at"),
            (self.requested_model, "requested_model"),
            (self.output_path, "output_path"),
            (self.stage, "stage"), (self.batch_id, "batch_id"),
            (self.rendered_prompt, "rendered_prompt"),
        ):
            _required_text(value, label)
        if (isinstance(self.theory_version, bool)
                or not isinstance(self.theory_version, int)
                or self.theory_version < 1):
            raise ValueError("theory_version must be a positive integer")
        if self.requested_effort is not None:
            _required_text(self.requested_effort, "requested_effort")
        if (self.requested_web_search is not None
                and not isinstance(self.requested_web_search, bool)):
            raise ValueError(
                "requested_web_search must be true, false, or null"
            )
        if not Path(self.output_path).is_absolute():
            raise ValueError("output_path must be absolute")
        if not self.candidate_keys:
            raise ValueError("candidate_keys must not be empty")
        if any(not isinstance(key, str) or not key.strip()
               for key in self.candidate_keys):
            raise ValueError("candidate_keys must contain non-empty strings")
        if len(set(self.candidate_keys)) != len(self.candidate_keys):
            raise ValueError("candidate_keys must be unique within a batch")
        payload = json.loads(self._payload_json)
        if _sha256_json(payload) != self.payload_sha256:
            raise ValueError("payload_sha256 does not match the stored payload")

    @classmethod
    def build(
        cls,
        *,
        run_id: str,
        theory_id: str,
        theory_version: int,
        run_mode: str,
        decision_at: str,
        requested_model: str,
        requested_effort: str | None,
        requested_web_search: bool | None,
        output_path: str | Path,
        stage: str,
        batch_id: str | int,
        candidate_keys: Iterable[str],
        payload: Any,
        rendered_prompt: str,
    ) -> "BatchRequest":
        payload_json = _canonical_json(payload)
        normalized_keys = tuple(candidate_keys)
        return cls(
            run_id=run_id,
            theory_id=theory_id,
            theory_version=theory_version,
            run_mode=run_mode,
            decision_at=decision_at,
            requested_model=requested_model,
            requested_effort=requested_effort,
            requested_web_search=requested_web_search,
            output_path=str(Path(output_path).resolve()),
            stage=stage,
            batch_id=str(batch_id),
            candidate_keys=normalized_keys,
            payload_sha256=hashlib.sha256(
                payload_json.encode("utf-8")).hexdigest(),
            rendered_prompt=rendered_prompt,
            _payload_json=payload_json,
        )

    @property
    def payload(self) -> Any:
        """Return a fresh JSON value so the frozen receipt stays immutable."""
        return json.loads(self._payload_json)

    @property
    def identity_sha256(self) -> str:
        """Digest of every immutable request field, including the payload."""
        return _sha256_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "theory_id": self.theory_id,
            "theory_version": self.theory_version,
            "run_mode": self.run_mode,
            "decision_at": self.decision_at,
            "requested_model": self.requested_model,
            "requested_effort": self.requested_effort,
            "requested_web_search": self.requested_web_search,
            "output_path": self.output_path,
            "stage": self.stage,
            "batch_id": self.batch_id,
            "candidate_keys": list(self.candidate_keys),
            "payload_sha256": self.payload_sha256,
            "rendered_prompt": self.rendered_prompt,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BatchRequest":
        expected = {
            "run_id", "theory_id", "theory_version", "run_mode",
            "decision_at", "requested_model", "requested_effort",
            "requested_web_search", "output_path", "stage", "batch_id",
            "candidate_keys", "payload_sha256", "rendered_prompt", "payload",
        }
        if set(raw) != expected:
            raise ValueError(
                "judgment request fields do not match schema: "
                f"missing={sorted(expected - set(raw))}, "
                f"unexpected={sorted(set(raw) - expected)}"
            )
        keys = raw["candidate_keys"]
        if not isinstance(keys, list):
            raise ValueError("candidate_keys must be a JSON array")
        payload_json = _canonical_json(raw["payload"])
        request = cls(
            run_id=raw["run_id"], theory_id=raw["theory_id"],
            theory_version=raw["theory_version"],
            run_mode=raw["run_mode"], decision_at=raw["decision_at"],
            requested_model=raw["requested_model"],
            requested_effort=raw["requested_effort"],
            requested_web_search=raw["requested_web_search"],
            output_path=raw["output_path"],
            stage=raw["stage"],
            batch_id=raw["batch_id"], candidate_keys=tuple(keys),
            payload_sha256=raw["payload_sha256"],
            rendered_prompt=raw["rendered_prompt"],
            _payload_json=payload_json,
        )
        return request


@dataclass(frozen=True, slots=True)
class BatchCompletion:
    """Actual execution metadata and categorical results for one batch."""

    model: str
    effort: str | None
    web_search: bool | None
    completed_at: str
    _results: tuple[tuple[str, Verdict], ...]

    def __post_init__(self) -> None:
        _required_text(self.model, "model")
        _required_text(self.completed_at, "completed_at")
        if self.effort is not None:
            _required_text(self.effort, "effort")
        if self.web_search is not None and not isinstance(
                self.web_search, bool):
            raise ValueError("web_search must be true, false, or null")
        keys = [key for key, _ in self._results]
        if len(keys) != len(set(keys)):
            raise ValueError("completion results contain duplicate keys")
        if any(not isinstance(value, Verdict) for _, value in self._results):
            raise TypeError("completion results must contain Verdict values")

    @classmethod
    def build(
        cls,
        *,
        model: str,
        effort: str | None,
        web_search: bool | None,
        results: Mapping[str, Verdict],
        completed_at: str,
    ) -> "BatchCompletion":
        return cls(
            model=model, effort=effort, web_search=web_search,
            completed_at=completed_at,
            _results=tuple(sorted(dict(results).items())),
        )

    @property
    def results(self) -> dict[str, Verdict]:
        return dict(self._results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "effort": self.effort,
            "web_search": self.web_search,
            "completed_at": self.completed_at,
            "results": {
                key: {"bucket": verdict.bucket,
                      "rationale": verdict.rationale}
                for key, verdict in self._results
            },
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BatchCompletion":
        expected = {
            "model", "effort", "web_search", "completed_at", "results",
        }
        if set(raw) != expected:
            raise ValueError(
                "judgment completion fields do not match schema: "
                f"missing={sorted(expected - set(raw))}, "
                f"unexpected={sorted(set(raw) - expected)}"
            )
        result_rows = raw["results"]
        if not isinstance(result_rows, dict):
            raise ValueError("completion results must be a JSON object")
        results: dict[str, Verdict] = {}
        for key, value in result_rows.items():
            if not isinstance(value, dict) or set(value) != {
                    "bucket", "rationale"}:
                raise ValueError(
                    f"completion result {key!r} must contain bucket and "
                    "rationale"
                )
            results[key] = Verdict(
                bucket=value["bucket"], rationale=value["rationale"])
        return cls.build(
            model=raw["model"], effort=raw["effort"],
            web_search=raw["web_search"], results=results,
            completed_at=raw["completed_at"],
        )


@dataclass(frozen=True, slots=True)
class JudgmentBatchReceipt:
    request: BatchRequest
    completion: BatchCompletion | None = None
    path: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, BatchRequest):
            raise TypeError("request must be a BatchRequest")
        if self.completion is not None:
            if not isinstance(self.completion, BatchCompletion):
                raise TypeError("completion must be a BatchCompletion or None")
            completion_settings = (
                self.completion.model,
                self.completion.effort,
                self.completion.web_search,
            )
            requested_settings = (
                self.request.requested_model,
                self.request.requested_effort,
                self.request.requested_web_search,
            )
            if completion_settings != requested_settings:
                raise ReceiptConflictError(
                    "completion settings do not match the declared dispatch: "
                    f"requested={requested_settings!r}, "
                    f"completed={completion_settings!r}"
                )
            if set(self.completion.results) != set(
                    self.request.candidate_keys):
                missing = sorted(
                    set(self.request.candidate_keys)
                    - set(self.completion.results))
                unexpected = sorted(
                    set(self.completion.results)
                    - set(self.request.candidate_keys))
                raise ValueError(
                    "completed batch results do not match candidate_keys; "
                    f"missing={missing}, unexpected={unexpected}"
                )

    @property
    def completed(self) -> bool:
        return self.completion is not None

    @property
    def verdicts(self) -> dict[str, Verdict]:
        return {} if self.completion is None else self.completion.results

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "request": self.request.to_dict(),
            "completion": (
                None if self.completion is None else self.completion.to_dict()
            ),
        }


def load_batch(path: str | Path) -> JudgmentBatchReceipt:
    """Load and fully validate one receipt, including its payload hash."""
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load judgment receipt {source}: {exc}") \
            from exc
    if not isinstance(raw, dict) or set(raw) != {
            "schema_version", "request", "completion"}:
        raise ValueError(f"judgment receipt {source} does not match schema")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported judgment receipt schema "
            f"{raw['schema_version']!r} in {source}"
        )
    if not isinstance(raw["request"], dict):
        raise ValueError("judgment request must be a JSON object")
    request = BatchRequest.from_dict(raw["request"])
    completion_raw = raw["completion"]
    if completion_raw is not None and not isinstance(completion_raw, dict):
        raise ValueError("judgment completion must be an object or null")
    completion = (
        None if completion_raw is None
        else BatchCompletion.from_dict(completion_raw)
    )
    return JudgmentBatchReceipt(
        request=request, completion=completion, path=str(source.resolve()))


def _write_receipt(path: Path, receipt: JudgmentBatchReceipt) -> None:
    atomic_write.write_json(
        path, receipt.to_dict(), indent=2, sort_keys=True)


def prepare_batch(
    path: str | Path,
    *,
    run: "TheoryRun",
    stage: str,
    batch_id: str | int,
    candidate_keys: Iterable[str],
    payload: Any,
    rendered_prompt: str,
    requested_model: str,
    requested_effort: str | None,
    requested_web_search: bool | None,
    output_path: str | Path,
) -> JudgmentBatchReceipt:
    """Persist a blind request before dispatch, or validate an exact retry."""
    if stage not in run.theory.prompts:
        raise ValueError(
            f"stage {stage!r} is not declared by {run.theory.id}.prompts"
        )
    request = BatchRequest.build(
        run_id=run.ctx.run_id, theory_id=run.theory.id,
        theory_version=run.theory.version, run_mode=run.ctx.run_mode,
        decision_at=run.ctx.now.isoformat(),
        requested_model=requested_model,
        requested_effort=requested_effort,
        requested_web_search=requested_web_search,
        output_path=output_path,
        stage=stage, batch_id=batch_id,
        candidate_keys=candidate_keys, payload=payload,
        rendered_prompt=rendered_prompt,
    )
    known = {candidate.key for candidate in run.candidates}
    unknown = sorted(set(request.candidate_keys) - known)
    if unknown:
        raise ValueError(
            f"batch candidate keys match no screened candidate: {unknown}"
        )
    destination = Path(path)
    receipt = JudgmentBatchReceipt(
        request=request, path=str(destination.resolve()))
    with exclusive_lock(destination.with_name(destination.name + ".lock")):
        if destination.exists():
            existing = load_batch(destination)
            if existing.request != request:
                raise ReceiptConflictError(
                    f"persisted judgment request conflicts with retry: "
                    f"{destination}"
                )
            return existing
        _write_receipt(destination, receipt)
    return receipt


def write_payload(
    path: str | Path,
    receipt: JudgmentBatchReceipt | BatchRequest,
) -> None:
    """Write the bare blind JSON value that a judge receives as input.

    The receipt itself is never a dispatch payload: it also contains request
    identity and, after ingestion, completion metadata.  An existing exact
    payload is a safe retry; different contents are refused.
    """
    request = receipt.request if isinstance(
        receipt, JudgmentBatchReceipt) else receipt
    if not isinstance(request, BatchRequest):
        raise TypeError("receipt must be a JudgmentBatchReceipt or BatchRequest")
    destination = Path(path)
    with exclusive_lock(destination.with_name(destination.name + ".lock")):
        if destination.exists():
            try:
                existing = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ReceiptConflictError(
                    f"persisted judgment payload is unreadable: {destination}"
                ) from exc
            if _sha256_json(existing) != request.payload_sha256:
                raise ReceiptConflictError(
                    f"persisted judgment payload conflicts with receipt: "
                    f"{destination}"
                )
            return
        atomic_write.write_json(
            destination, request.payload, indent=2, sort_keys=True)


def complete_batch(
    path: str | Path,
    *,
    model: str | None | object = _UNSET,
    effort: str | None | object = _UNSET,
    web_search: bool | None | object = _UNSET,
    results: Mapping[str, Verdict],
    completed_at: str | None = None,
) -> JudgmentBatchReceipt:
    """Fill one immutable completion, skipping an identical persisted retry."""
    destination = Path(path)
    with exclusive_lock(destination.with_name(destination.name + ".lock")):
        existing = load_batch(destination)
        request = existing.request
        supplied = (
            ("model", model, request.requested_model),
            ("effort", effort, request.requested_effort),
            ("web_search", web_search, request.requested_web_search),
        )
        mismatches = [
            f"{name}: declared={declared!r}, supplied={value!r}"
            for name, value, declared in supplied
            if value is not _UNSET and value != declared
        ]
        if mismatches:
            raise ReceiptConflictError(
                "completion settings conflict with the declared dispatch: "
                + "; ".join(mismatches)
            )
        if existing.completion is not None:
            retry = BatchCompletion.build(
                model=request.requested_model,
                effort=request.requested_effort,
                web_search=request.requested_web_search,
                results=results,
                completed_at=(completed_at or existing.completion.completed_at),
            )
            if retry != existing.completion:
                raise ReceiptConflictError(
                    f"persisted judgment completion conflicts with retry: "
                    f"{destination}"
                )
            return existing
        completion = BatchCompletion.build(
            model=request.requested_model,
            effort=request.requested_effort,
            web_search=request.requested_web_search,
            results=results,
            completed_at=(completed_at or datetime.now(
                timezone.utc).isoformat()),
        )
        receipt = JudgmentBatchReceipt(existing.request, completion)
        _write_receipt(destination, receipt)
    return receipt


def _market_to_dict(market: Market) -> dict[str, Any]:
    return {item.name: getattr(market, item.name) for item in fields(Market)}


def _candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    return {
        "legs": [
            {
                "market": _market_to_dict(leg.market),
                "side": leg.side,
                "price": leg.price,
            }
            for leg in candidate.legs
        ],
        "days_to_close": candidate.days_to_close,
        "max_payout": candidate.max_payout,
        "min_payout": candidate.min_payout,
    }


def _candidate_from_dict(raw: Mapping[str, Any]) -> Candidate:
    expected = {"legs", "days_to_close", "max_payout", "min_payout"}
    if set(raw) != expected or not isinstance(raw["legs"], list):
        raise ValueError("persisted candidate does not match schema")
    legs = []
    for item in raw["legs"]:
        if not isinstance(item, dict) or set(item) != {
                "market", "side", "price"}:
            raise ValueError("persisted candidate leg does not match schema")
        if not isinstance(item["market"], dict):
            raise ValueError("persisted candidate market must be an object")
        legs.append(Leg(
            market=Market.from_mapping(item["market"]),
            side=item["side"], price=item["price"],
        ))
    return Candidate(
        legs=tuple(legs), days_to_close=raw["days_to_close"],
        max_payout=raw["max_payout"], min_payout=raw["min_payout"],
    )


def _board_item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, Market):
        return {"kind": "market", "value": _market_to_dict(item)}
    # Preserve mapping/list/scalar representation exactly rather than
    # normalizing caller-owned board data into a Market.
    _canonical_json(item)
    return {"kind": "json", "value": item}


def _board_item_from_dict(raw: Mapping[str, Any]) -> Any:
    if not isinstance(raw, dict) or set(raw) != {"kind", "value"}:
        raise ValueError("persisted board item does not match schema")
    if raw["kind"] == "market":
        if not isinstance(raw["value"], dict):
            raise ValueError("persisted Market board item must be an object")
        return Market.from_mapping(raw["value"])
    if raw["kind"] == "json":
        return raw["value"]
    raise ValueError(f"unknown persisted board item kind {raw['kind']!r}")


def _relative_reference(state_path: Path, receipt_path: Path) -> str:
    try:
        return os.path.relpath(receipt_path.resolve(), state_path.parent.resolve())
    except ValueError:  # different Windows drives
        return str(receipt_path.resolve())


def save_run_state(
    path: str | Path,
    run: "TheoryRun",
    *,
    batch_paths: Iterable[str | Path],
) -> None:
    """Persist screened operator state and immutable receipt references.

    Judge payloads and prompts stay in their receipt files.  This state file
    contains candidates (including prices) and must never be dispatched.
    """
    destination = Path(path)
    receipt_refs = []
    seen: set[tuple[str, str]] = set()
    for item in batch_paths:
        receipt_path = Path(item)
        receipt = load_batch(receipt_path)
        request = receipt.request
        expected = (
            run.ctx.run_id, run.theory.id, run.theory.version,
        )
        actual = (request.run_id, request.theory_id, request.theory_version)
        if actual != expected:
            raise ValueError(
                "judgment batch run identity does not match TheoryRun: "
                f"expected={expected!r}, actual={actual!r}"
            )
        expected_context = (run.ctx.run_mode, run.ctx.now.isoformat())
        actual_context = (request.run_mode, request.decision_at)
        if actual_context != expected_context:
            raise ValueError(
                "judgment batch run context does not match TheoryRun: "
                f"expected={expected_context!r}, actual={actual_context!r}"
            )
        batch_key = (request.stage, request.batch_id)
        if batch_key in seen:
            raise ValueError(f"duplicate judgment batch identity: {batch_key}")
        seen.add(batch_key)
        receipt_refs.append({
            "path": _relative_reference(destination, receipt_path),
            "request_identity_sha256": request.identity_sha256,
        })
    if not receipt_refs:
        raise ValueError("batch_paths must contain at least one receipt")
    state = {
        "schema_version": SCHEMA_VERSION,
        "theory": {"id": run.theory.id, "version": run.theory.version},
        "context": {
            "run_id": run.ctx.run_id,
            "run_mode": run.ctx.run_mode,
            "now": run.ctx.now.isoformat(),
        },
        "board": [_board_item_to_dict(item) for item in run.ctx.board],
        "screen_result": {
            "candidates": [
                _candidate_to_dict(candidate)
                for candidate in run.screen_result.candidates
            ],
            "funnel": dict(run.screen_result.funnel),
            "gate_removed": dict(run.screen_result.gate_removed),
        },
        "candidates": [
            _candidate_to_dict(candidate) for candidate in run.candidates
        ],
        "payload": run.payload,
        "batch_receipts": receipt_refs,
    }
    # Validate every value, including raw/event fields, before acquiring the
    # state lock; a failed serialization must not leave a partial artifact.
    _canonical_json(state)
    with exclusive_lock(destination.with_name(destination.name + ".lock")):
        if destination.exists():
            try:
                existing = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"could not load judgment run state {destination}: {exc}"
                ) from exc
            if existing != state:
                raise ReceiptConflictError(
                    f"persisted judgment run state conflicts with retry: "
                    f"{destination}"
                )
            return
        atomic_write.write_json(
            destination, state, indent=2, sort_keys=True)


def load_run_state(
    path: str | Path,
    theory: "Theory",
    *,
    conn=None,
    bucket_rates=None,
) -> tuple["TheoryRun", tuple[JudgmentBatchReceipt, ...]]:
    """Rebuild a run from operator state without screening again."""
    from tools.theory import TheoryContext, TheoryRun

    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load judgment run state {source}: {exc}") \
            from exc
    expected_top = {
        "schema_version", "theory", "context", "screen_result",
        "board", "candidates", "payload", "batch_receipts",
    }
    if not isinstance(raw, dict) or set(raw) != expected_top:
        raise ValueError(f"judgment run state {source} does not match schema")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported judgment run-state schema "
            f"{raw['schema_version']!r} in {source}"
        )
    theory_identity = raw["theory"]
    expected_identity = {"id": theory.id, "version": theory.version}
    if theory_identity != expected_identity:
        raise ValueError(
            "persisted theory identity does not match supplied theory: "
            f"expected={theory_identity!r}, actual={expected_identity!r}"
        )
    context = raw["context"]
    if not isinstance(context, dict) or set(context) != {
            "run_id", "run_mode", "now"}:
        raise ValueError("persisted judgment context does not match schema")
    try:
        now = datetime.fromisoformat(context["now"])
    except (TypeError, ValueError) as exc:
        raise ValueError("persisted judgment context has an invalid now") \
            from exc
    board_raw = raw["board"]
    if not isinstance(board_raw, list):
        raise ValueError("persisted board must be a JSON array")
    board = [_board_item_from_dict(item) for item in board_raw]
    if conn is not None and bucket_rates is None:
        ctx = TheoryContext.build(
            conn=conn, board=board, now=now, run_id=context["run_id"],
            run_mode=context["run_mode"],
        )
    else:
        ctx = TheoryContext(
            conn=conn, board=board, now=now, run_id=context["run_id"],
            run_mode=context["run_mode"], bucket_rates=bucket_rates,
        )
    screen_raw = raw["screen_result"]
    if not isinstance(screen_raw, dict) or set(screen_raw) != {
            "candidates", "funnel", "gate_removed"}:
        raise ValueError("persisted screen result does not match schema")
    if not isinstance(screen_raw["candidates"], list):
        raise ValueError("persisted candidates must be a JSON array")
    screen_result = ScreenResult(
        candidates=tuple(_candidate_from_dict(item)
                         for item in screen_raw["candidates"]),
        funnel=dict(screen_raw["funnel"]),
        gate_removed=dict(screen_raw["gate_removed"]),
    )
    candidates_raw = raw["candidates"]
    if not isinstance(candidates_raw, list):
        raise ValueError("persisted active candidates must be a JSON array")
    candidates = tuple(_candidate_from_dict(item) for item in candidates_raw)
    references = raw["batch_receipts"]
    if not isinstance(references, list) or not references:
        raise ValueError("persisted batch_receipts must be a non-empty array")
    receipts = []
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {
                "path", "request_identity_sha256"}:
            raise ValueError("persisted receipt reference does not match schema")
        receipt_path = Path(reference["path"])
        if not receipt_path.is_absolute():
            receipt_path = source.parent / receipt_path
        receipt = load_batch(receipt_path)
        if receipt.request.identity_sha256 != reference[
                "request_identity_sha256"]:
            raise ValueError(
                f"judgment request identity changed after run state was "
                f"saved: {receipt_path}"
            )
        expected = (context["run_id"], theory.id, theory.version)
        actual = (
            receipt.request.run_id, receipt.request.theory_id,
            receipt.request.theory_version,
        )
        if actual != expected:
            raise ValueError(
                "judgment batch run identity does not match persisted state: "
                f"expected={expected!r}, actual={actual!r}"
            )
        expected_context = (context["run_mode"], context["now"])
        actual_context = (
            receipt.request.run_mode, receipt.request.decision_at,
        )
        if actual_context != expected_context:
            raise ValueError(
                "judgment batch run context does not match persisted state: "
                f"expected={expected_context!r}, "
                f"actual={actual_context!r}"
            )
        receipts.append(receipt)
    run = TheoryRun.from_persisted(
        theory=theory, ctx=ctx, screen_result=screen_result,
        candidates=candidates, payload=raw["payload"],
    )
    return run, tuple(receipts)
