# Save and resume judgment batches

Both runtimes use `tools/judgments.py` for new judged `TheoryRun` workflows.
Native dispatch remains in the runtime adapter; the theory's runbook owns
batching, payload construction, prompt substitutions, and verdict parsing.
Historical replay manifests keep their existing theory-local ingest procedure.

Use a unique run id and a run directory inside the theory's registered folder.
There are three distinct artifacts:

| Artifact | Contents | Reader |
|---|---|---|
| Bare input JSON | The theory's blind payload, in its original shape | Judge |
| Batch receipt | Immutable request identity, exact prompt, requested settings/output path, actual completion and verdicts | Operator |
| Run state | Original timestamp, screened candidates, prices, funnel and batch references | Python recovery helper; never model context |

Run state may contain the entire captured board. Restore it with
`load_run_state` and print only the needed counts or fields; do not open or
paste the full JSON into an agent's context. Store authoritative run artifacts
in the theory's run directory and link them from a floor report. A report may
hold presentation attachments without becoming the only home of recovery data.

Never point a prompt's input path at a receipt or run-state file. The theory's
whitelist and blindness checks still apply; persistence does not make an
arbitrary payload blind. Keep the normal output file too, so a verdict returned
just before an interruption can be ingested without another model call.

## Prepare before dispatch

Start the theory once using the shared board and original `TheoryContext`.
For each batch, construct the blind payload and exact rendered prompt using
the theory's runbook. `candidate_keys` names the candidates assigned to that
batch; it is operator metadata, not an addition to the judge's input.

```python
from tools import judgments

receipt = judgments.prepare_batch(
    receipt_path,
    run=run,
    stage="analysis",
    batch_id="01",
    candidate_keys=batch_candidate_keys,
    payload=blind_batch,
    rendered_prompt=rendered_prompt,
    requested_model=selected_model_or_honest_alias,
    requested_effort=selected_effort_or_none,
    requested_web_search=selected_search_setting,
    output_path=verdict_output_path,
)
judgments.write_payload(input_path, receipt)
# Save after preparing all batches and before dispatching any of them.
judgments.save_run_state(state_path, run, batch_paths=batch_receipt_paths)
```

The names above come from the runbook's batching step. The rendered prompt
must name `input_path` and the batch's separate verdict output path. Send only
that prompt and the bare input artifact through the native judge operation.
An existing identical request is reusable; a conflicting request is an error.
Use the same declared model, effort, and search settings for the actual native
call. They describe request intent; a pending receipt alone does not prove a
judge ran. The saved output path lets a later process locate a stranded result.

## Complete each returned batch

Parse the saved output using the theory's declared buckets, producing
`dict[Candidate.key, Verdict]`. Persist each batch immediately:

```python
receipt = judgments.complete_batch(
    receipt_path,
    model=actual_requested_model_or_honest_alias,
    effort=actual_effort_or_none,
    web_search=actual_search_setting,
    results=verdicts,
)
```

Record settings from that actual dispatch. An unresolved alias remains
explicitly unresolved; never infer a model from the coordinator. Replays must
record search as `False`. An identical completion is safe to repeat; a
conflicting completion is rejected. Do not dispatch a completed batch again.

## Resume after interruption

First distinguish recovering an executed judgment from making a new one.
If a live batch was still unexecuted when its session ended, start a new live
run with a fresh board when a judge becomes available. Keep the old pending
receipts as audit artifacts; do not attach later web-informed judgments to
their earlier decision time and prices. Re-quoting only the final report does
not repair a backdated ledger decision. The persistence helper does not enforce
this timing rule. Historical replays may resume under their unchanged
point-in-time evidence restrictions; original executed outputs may be recovered
without another judgment call.

Discover the same theory and open a database connection, then restore the
saved run for eligible recovery. Do not call `theory.start()` or fetch a fresh
board merely to ingest an original executed output.

```python
from pathlib import Path

run, receipts = judgments.load_run_state(state_path, theory, conn=conn)
pending = [receipt for receipt in receipts if not receipt.completed]
for receipt in pending:
    output_path = receipt.request.output_path
    if run.ctx.run_mode == "live" and not (
        output_path and Path(output_path).is_file()
    ):
        raise RuntimeError("Unexecuted live judgment needs a fresh run after restart")
    # Verify an existing output came from the original execution, then parse it.
    # Only a historical replay may dispatch a missing batch after restart,
    # under its original point-in-time restrictions and saved settings.
    # `verdicts` is the resulting dict[Candidate.key, Verdict].
    judgments.complete_batch(receipt.path, results=verdicts)
# Reload to obtain the newly completed receipts.
run, receipts = judgments.load_run_state(state_path, theory, conn=conn)
result = run.attach_completed_batches(receipts).finish()
```

Attachment checks run, theory/version, stage, candidate coverage and request
identity. Multi-stage runs explicitly select `verdict_stage` when attaching;
all declared stages still need their execution receipts. `finish()` records
each actual batch's provenance before writing opportunities. It preserves the
original decision time; re-quote separately before presenting a live bet.
Omitted completion settings come from the saved request declaration, never the
new operator's model. Explicit conflicting settings are rejected. If the
original run used a custom bucket-rate reader, pass that reader again through
`load_run_state(..., bucket_rates=...)`; callables are not serialized.

Mechanical theories need no receipts. A model/provider switch following the
same procedure shares calibration under the guide's idealized-judge policy;
aim for comparable intelligence. Deliberate experiments still use `exp/`.
An existing receipt keeps its original requested model immutable: a new model
needs a new request, not relabelled provenance or backdated live judgment.
