import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools import db, judgments, provenance, theories
from tools.domain import (Candidate, Edge, Leg, Market, ScoredCandidate,
                          ScreenResult, Verdict)
from tools.theory import Theory, TheoryContext


NOW = datetime(2026, 9, 4, 13, 14, 15, tzinfo=timezone.utc)


def _candidate(ticker="KXJUDGE-26", event="KXJUDGE"):
    market = Market(
        platform="kalshi", ticker=ticker, title="Will the test pass?",
        yes_ask=0.41, no_ask=0.60, event_ticker=event, is_open=True,
        raw={"yes_ask_dollars": "0.4100"},
        event={"mutually_exclusive": False},
    )
    return Candidate(
        legs=(Leg(market=market, side="yes", price=0.41),),
        days_to_close=2.5,
    )


class PersistedJudgmentTheory(Theory):
    id = "persisted_judgment"
    name = "Persisted Judgment"
    version = 3
    uses_llm_judgment = True
    prompts = {"analysis": "theories/_TEMPLATE/THEORY.md"}
    screen_calls = 0

    def screen(self, ctx):
        type(self).screen_calls += 1
        return ScreenResult(
            candidates=(_candidate(),),
            funnel={"board_markets": 17, "screened": 1},
            gate_removed={"known_family": 16},
        )

    def judgment_payload(self, cands):
        return [{"key": c.key, "title": c.title} for c in cands]

    def price(self, ctx, cands, verdicts=None):
        verdicts = verdicts or {}
        return [
            ScoredCandidate(
                candidate=c,
                edge=Edge(pts_net=4.0, basis="prior"),
                confidence=verdicts[c.key].bucket,
                rationale=verdicts[c.key].rationale,
                judged_blind=True,
            )
            for c in cands if c.key in verdicts
        ]


def _run(*, run_id="live-2026-09-04", conn=None):
    ctx = TheoryContext.build(
        conn=conn, board=[], now=NOW, run_id=run_id, run_mode="live")
    return PersistedJudgmentTheory().start(ctx)


def _prepare(path, run=None, *, payload=None, prompt="Judge batch 1 exactly.",
             output_path=None):
    run = run or _run()
    output_path = output_path or path.with_suffix(".verdicts.json")
    return judgments.prepare_batch(
        path,
        run=run,
        stage="analysis",
        batch_id="01",
        candidate_keys=("KXJUDGE",),
        payload=(payload if payload is not None else
                 [{"key": "KXJUDGE", "title": "Will the test pass?"}]),
        rendered_prompt=prompt,
        requested_model="gpt-6-astra",
        requested_effort="high",
        requested_web_search=True,
        output_path=output_path,
    )


def _complete(path, *, bucket="strong", model="gpt-6-astra"):
    return judgments.complete_batch(
        path,
        model=model,
        effort="high",
        web_search=True,
        results={
            "KXJUDGE": Verdict(bucket=bucket, rationale="Evidence read.")
        },
        completed_at="2026-09-04T13:20:00+00:00",
    )


def test_prepare_batch_keeps_dispatch_payload_separate_from_operator_state(
        tmp_path):
    run = _run()
    batch_path = tmp_path / "batch-01.json"
    payload_path = tmp_path / "batch-01.payload.json"
    state_path = tmp_path / "run-state.json"

    receipt = _prepare(batch_path, run)
    judgments.write_payload(payload_path, receipt)
    judgments.save_run_state(state_path, run, batch_paths=(batch_path,))

    request_doc = json.loads(batch_path.read_text(encoding="utf-8"))
    dispatch_doc = json.loads(payload_path.read_text(encoding="utf-8"))
    state_doc = json.loads(state_path.read_text(encoding="utf-8"))
    assert receipt.completed is False
    assert request_doc["request"]["payload"] == [
        {"key": "KXJUDGE", "title": "Will the test pass?"}
    ]
    assert request_doc["request"]["rendered_prompt"] == \
        "Judge batch 1 exactly."
    # Only the bare whitelist array is dispatched. Both receipt metadata and
    # the recoverable, price-bearing run state stay operator-side.
    assert dispatch_doc == [
        {"key": "KXJUDGE", "title": "Will the test pass?"}
    ]
    assert "request" not in dispatch_doc[0]
    assert "completion" not in dispatch_doc[0]
    assert "yes_ask" not in payload_path.read_text(encoding="utf-8")
    assert state_doc["screen_result"]["candidates"][0]["legs"][0][
        "market"]["yes_ask"] == 0.41
    assert state_doc["payload"] == run.payload
    assert "rendered_prompt" not in state_doc


def test_write_payload_skips_an_exact_retry_and_rejects_an_existing_change(
        tmp_path):
    receipt_path = tmp_path / "batch.json"
    payload_path = tmp_path / "payload.json"
    receipt = _prepare(receipt_path)
    judgments.write_payload(payload_path, receipt)
    original = payload_path.read_text(encoding="utf-8")
    judgments.write_payload(payload_path, receipt)
    assert payload_path.read_text(encoding="utf-8") == original

    payload_path.write_text('[{"key":"different"}]', encoding="utf-8")
    with pytest.raises(judgments.ReceiptConflictError, match="payload"):
        judgments.write_payload(payload_path, receipt)


def test_prepare_batch_is_idempotent_and_rejects_conflicting_payload(tmp_path):
    path = tmp_path / "batch.json"
    first = _prepare(path)
    assert _prepare(path) == first

    with pytest.raises(judgments.ReceiptConflictError, match="request"):
        _prepare(path, payload=[{"key": "KXJUDGE", "title": "changed"}])

    assert judgments.load_batch(path) == first


def test_complete_batch_is_idempotent_and_rejects_conflicting_result(tmp_path):
    path = tmp_path / "batch.json"
    _prepare(path)
    first = _complete(path)
    assert first.completed is True
    assert first.completion.model == "gpt-6-astra"
    assert first.completion.effort == "high"
    assert first.completion.web_search is True
    assert first.verdicts == {
        "KXJUDGE": Verdict(bucket="strong", rationale="Evidence read.")
    }
    assert _complete(path) == first

    with pytest.raises(judgments.ReceiptConflictError, match="completion"):
        _complete(path, bucket="weak")

    assert judgments.load_batch(path) == first


def test_complete_batch_rejects_execution_settings_that_differ_from_dispatch(
        tmp_path):
    path = tmp_path / "batch.json"
    _prepare(path)

    with pytest.raises(judgments.ReceiptConflictError,
                       match="declared dispatch"):
        judgments.complete_batch(
            path, model="different-model", results={
                "KXJUDGE": Verdict(bucket="strong")
            })
    with pytest.raises(judgments.ReceiptConflictError,
                       match="declared dispatch"):
        judgments.complete_batch(
            path, effort=None, web_search=None, results={
                "KXJUDGE": Verdict(bucket="strong")
            })

    assert judgments.load_batch(path).completed is False


def test_load_batch_rejects_payload_tampering(tmp_path):
    path = tmp_path / "batch.json"
    _prepare(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["request"]["payload"][0]["title"] = "tampered"
    path.write_text(json.dumps(doc), encoding="utf-8")

    with pytest.raises(ValueError, match="payload_sha256"):
        judgments.load_batch(path)


def test_real_restart_loads_original_screen_without_rescreening(tmp_path):
    PersistedJudgmentTheory.screen_calls = 0
    batch_path = tmp_path / "batch.json"
    state_path = tmp_path / "run-state.json"
    original = _run(run_id="restart-me")
    _prepare(batch_path, original)
    judgments.save_run_state(state_path, original, batch_paths=(batch_path,))
    assert PersistedJudgmentTheory.screen_calls == 1

    # This is the new process: only disk artifacts and a theory class remain.
    resumed, pending = judgments.load_run_state(
        state_path, PersistedJudgmentTheory())
    assert PersistedJudgmentTheory.screen_calls == 1
    assert resumed.ctx.now == NOW
    assert resumed.ctx.run_id == "restart-me"
    assert resumed.screen_result.funnel == {
        "board_markets": 17, "screened": 1,
    }
    assert resumed.screen_result.gate_removed == {"known_family": 16}
    assert resumed.candidates == original.candidates
    assert [batch.request.batch_id for batch in pending] == ["01"]
    with pytest.raises(RuntimeError, match="not complete"):
        resumed.attach_completed_batches(pending)

    _complete(batch_path)
    resumed, batches = judgments.load_run_state(
        state_path, PersistedJudgmentTheory())
    result = resumed.attach_completed_batches(batches).finish(dry_run=True)
    assert PersistedJudgmentTheory.screen_calls == 1
    assert result.judged is True
    assert [item.confidence for item in result.scored] == ["strong"]


def test_restart_with_a_connection_restores_the_bucket_rate_binding(tmp_path):
    batch_path = tmp_path / "batch.json"
    state_path = tmp_path / "run-state.json"
    run = _run()
    _prepare(batch_path, run)
    judgments.save_run_state(state_path, run, batch_paths=(batch_path,))
    conn = db.connect(tmp_path / "rates.db")
    db.init_db(conn)

    resumed, _ = judgments.load_run_state(
        state_path, PersistedJudgmentTheory(), conn=conn)

    assert resumed.ctx.bucket_rates(
        PersistedJudgmentTheory.id,
        PersistedJudgmentTheory.version,
    ) == {}
    conn.close()


def test_restart_preserves_the_operator_narrowed_candidate_set(tmp_path):
    class TwoCandidateTheory(PersistedJudgmentTheory):
        id = "two_candidate_judgment"

        def screen(self, ctx):
            return ScreenResult(candidates=(
                _candidate("KXFIRST-26", "KXFIRST"),
                _candidate("KXSECOND-26", "KXSECOND"),
            ))

    theory = TwoCandidateTheory()
    run = theory.start(TheoryContext.build(
        conn=None, board=[], now=NOW, run_id="narrowed"))
    run.candidates = [run.candidates[1]]
    batch_path = tmp_path / "batch.json"
    state_path = tmp_path / "run-state.json"
    judgments.prepare_batch(
        batch_path, run=run, stage="analysis", batch_id="01",
        candidate_keys=("KXSECOND",),
        payload=[{"key": "KXSECOND"}], rendered_prompt="Judge second.",
        requested_model="gpt-6-astra", requested_effort="high",
        requested_web_search=True,
        output_path=tmp_path / "second.verdicts.json")
    judgments.save_run_state(state_path, run, batch_paths=(batch_path,))

    resumed, _ = judgments.load_run_state(state_path, TwoCandidateTheory())

    assert [candidate.key for candidate in resumed.screen_result.candidates] == [
        "KXFIRST", "KXSECOND",
    ]
    assert [candidate.key for candidate in resumed.candidates] == ["KXSECOND"]


def test_restart_restores_exact_board_and_payload_not_receipt_concatenation(
        tmp_path):
    class TwoStageTheory(PersistedJudgmentTheory):
        id = "two_stage_persisted"
        prompts = {
            "gate": "theories/_TEMPLATE/THEORY.md",
            "analysis": "theories/_TEMPLATE/THEORY.md",
        }

    board_market = _candidate("KXBOARD-26", "KXBOARD").legs[0].market
    board_mapping = {"ticker": "mapping-board", "yes_ask": 0.22}
    ctx = TheoryContext.build(
        conn=None, board=[board_market, board_mapping], now=NOW,
        run_id="exact-state")
    run = TwoStageTheory().start(ctx)
    run.payload = {"original": ["keep", "this", "order"], "stage": 0}
    gate_path = tmp_path / "gate.json"
    analysis_path = tmp_path / "analysis.json"
    state_path = tmp_path / "run-state.json"
    judgments.prepare_batch(
        gate_path, run=run, stage="gate", batch_id="g1",
        candidate_keys=("KXJUDGE",), payload=[{"stage": "gate"}],
        rendered_prompt="Gate.", requested_model="small",
        requested_effort="minimal", requested_web_search=False,
        output_path=tmp_path / "gate.verdicts.json")
    judgments.prepare_batch(
        analysis_path, run=run, stage="analysis", batch_id="a1",
        candidate_keys=("KXJUDGE",), payload=[{"stage": "analysis"}],
        rendered_prompt="Analyze.", requested_model="strong",
        requested_effort="high", requested_web_search=True,
        output_path=tmp_path / "analysis.verdicts.json")
    judgments.save_run_state(
        state_path, run, batch_paths=(analysis_path, gate_path))

    resumed, _ = judgments.load_run_state(state_path, TwoStageTheory())

    assert resumed.payload == {
        "original": ["keep", "this", "order"], "stage": 0,
    }
    assert resumed.ctx.board[0] == board_market
    assert isinstance(resumed.ctx.board[0], Market)
    assert resumed.ctx.board[1] == board_mapping
    assert isinstance(resumed.ctx.board[1], dict)


def test_load_run_state_rejects_a_different_theory_or_version(tmp_path):
    batch_path = tmp_path / "batch.json"
    state_path = tmp_path / "run-state.json"
    run = _run()
    _prepare(batch_path, run)
    judgments.save_run_state(state_path, run, batch_paths=(batch_path,))

    class Wrong(PersistedJudgmentTheory):
        id = "wrong"

    with pytest.raises(ValueError, match="theory identity"):
        judgments.load_run_state(state_path, Wrong())


def test_load_run_state_rejects_a_valid_but_changed_request(tmp_path):
    batch_path = tmp_path / "batch.json"
    changed_path = tmp_path / "changed.json"
    state_path = tmp_path / "run-state.json"
    run = _run()
    _prepare(batch_path, run)
    judgments.save_run_state(state_path, run, batch_paths=(batch_path,))

    # Simulate replacement by another individually valid request after the
    # operator snapshot was saved. Its internal payload hash is valid, but it
    # is not the immutable request identity named by this run.
    _prepare(
        changed_path, run,
        payload=[{"key": "KXJUDGE", "title": "another valid request"}],
    )
    batch_path.write_text(
        changed_path.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="request identity changed"):
        judgments.load_run_state(state_path, PersistedJudgmentTheory())


def test_completed_receipt_records_provenance_before_the_ledger(tmp_path):
    conn = db.connect(tmp_path / "ledger.db")
    db.init_db(conn)
    theories.register(conn, PersistedJudgmentTheory.id,
                      PersistedJudgmentTheory.name, "x",
                      now="2026-09-04T13:00:00Z")
    theories.set_uses_llm_judgment(conn, PersistedJudgmentTheory.id, True)
    run = _run(run_id="persisted-live", conn=conn)
    batch_path = tmp_path / "batch.json"
    _prepare(batch_path, run)
    receipt = _complete(batch_path)

    result = run.attach_completed_batches((receipt,)).finish()

    rows = provenance.list_judgment_runs(
        conn, theory_id=PersistedJudgmentTheory.id,
        run_id="persisted-live")
    assert len(rows) == 1
    assert rows[0]["model"] == "gpt-6-astra"
    assert rows[0]["prompt_text"] == "Judge batch 1 exactly."
    assert len(result.opportunity_ids) == 1
    conn.close()


@pytest.mark.parametrize("field,value", [
    ("model", "contradictory-model"), ("effort", None), ("web_search", False),
])
def test_load_rejects_completion_that_contradicts_saved_dispatch(tmp_path, field, value):
    path = tmp_path / "batch.json"
    _prepare(path)
    _complete(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["completion"][field] = value
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(judgments.ReceiptConflictError, match="settings"):
        judgments.load_batch(path)


def test_disk_only_recovery_ingests_stranded_output_without_redispatch(
        tmp_path):
    PersistedJudgmentTheory.screen_calls = 0
    conn = db.connect(tmp_path / "disk-only.db")
    db.init_db(conn)
    theories.register(conn, PersistedJudgmentTheory.id,
                      PersistedJudgmentTheory.name, "x",
                      now="2026-09-04T13:00:00Z")
    theories.set_uses_llm_judgment(conn, PersistedJudgmentTheory.id, True)
    receipt_path = tmp_path / "batch.json"
    payload_path = tmp_path / "batch.payload.json"
    output_path = tmp_path / "batch.verdicts.json"
    state_path = tmp_path / "run-state.json"
    original = _run(run_id="disk-only", conn=conn)
    receipt = _prepare(
        receipt_path, original, output_path=output_path,
        prompt=f"Read {payload_path}; write {output_path}.")
    judgments.write_payload(payload_path, receipt)
    judgments.save_run_state(
        state_path, original, batch_paths=(receipt_path,))
    output_path.write_text(json.dumps([{
        "key": "KXJUDGE", "bucket": "strong", "rationale": "On disk.",
    }]), encoding="utf-8")
    del original, receipt

    resumed, pending = judgments.load_run_state(
        state_path, PersistedJudgmentTheory(), conn=conn)
    assert PersistedJudgmentTheory.screen_calls == 1
    assert pending[0].completed is False
    assert pending[0].path == str(receipt_path.resolve())
    assert pending[0].request.output_path == str(output_path.resolve())
    assert pending[0].request.requested_model == "gpt-6-astra"
    assert pending[0].request.requested_effort == "high"
    assert pending[0].request.requested_web_search is True
    raw_results = json.loads(
        Path(pending[0].request.output_path).read_text(encoding="utf-8"))
    verdicts = {
        item["key"]: Verdict(
            bucket=item["bucket"], rationale=item["rationale"])
        for item in raw_results
    }
    judgments.complete_batch(pending[0].path, results=verdicts)

    resumed, completed = judgments.load_run_state(
        state_path, PersistedJudgmentTheory(), conn=conn)
    result = resumed.attach_completed_batches(completed).finish()
    row = provenance.list_judgment_runs(
        conn, theory_id=PersistedJudgmentTheory.id,
        run_id="disk-only")[0]
    assert row["model"] == "gpt-6-astra"
    assert row["effort"] == "high"
    assert row["web_search"] == 1
    assert len(result.opportunity_ids) == 1
    assert PersistedJudgmentTheory.screen_calls == 1
    conn.close()
