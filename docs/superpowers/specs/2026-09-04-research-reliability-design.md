# Research reliability and agent efficiency

The user approved the ranked refactors and explicitly clarified that valid
backtests must influence production probabilities immediately. Tier A/B replay
evidence counts fully, can satisfy evidence gates by itself, and pools with live
outcomes. No live-only waiting period or second discount is introduced.

## Deliverables

1. A shared eligibility primitive for scoring, bucket pricing, and slice input.
   Exclude tier C and undocumented replays from production evidence, retain
   explicit diagnostic access, and report why rows were excluded. Preserve
   experiment isolation, version carry chains, event clustering, and slice
   mining exclusions. A/B-only fixtures must earn measured probabilities and
   clear the existing gates. Do not infer or rewrite historical tier metadata.
2. Exclusive collector ownership spanning the full load/mutate/save cycle,
   process-death recovery, and unique temporary files for atomic writes. Apply
   this to actual JSON read/modify/write collectors; use existing storage formats.
3. Recoverable, idempotent ticket transitions. A retry after an interrupted move
   must retain the explanation exactly once, preserve contents, and refuse to
   overwrite an unrelated destination. Test real filesystem failure points.
4. A narrow persistent judgment-batch receipt, with validation and a supported
   way to attach completed batches to an existing TheoryRun. Resume without
   re-screening or re-judging completed batches; retain exact request identities,
   prompts, payload identity, and results. Keep native dispatch and theory-local
   replay under their existing owners; do not build a generic dispatcher.
5. Shared position facts for settlement and supersession, reused by the ledger,
   promotion, and orientation queue. Preserve each consumer's own filters and
   correctly handle baskets, experiments, versions, and opposite outcomes.
6. Concise universal agent invariants plus an explicit map to task-specific
   policy. Preserve every existing rule and historical rationale in its owned
   source, require the relevant sections before acting, and verify rule coverage
   and both runtime workflows. Reduce universal startup reading without a second
   independently maintained policy copy.

## Constraints

- Python 3.11+, stdlib and existing dependencies. Windows is the tested host.
- Continue in the existing working tree on `codex/dual-agent-support`, preserving
  all previous compatibility edits. No branch reset, staging, or remote push.
- Private test databases and temporary capture directories only. No live research
  collection, pricing run, score recomputation, or ledger migration in this pass.
- No strategy, prompt semantics, theory-version changes, or evidence reclassification.
- Root integrates and reviews; workers have disjoint file ownership. Phase-two
  tasks wait for earlier owners of any shared interface to finish.
- Meaningful regressions before fixes, focused checks per task, one complete
  offline suite after integration, and independent review of statistical and
  concurrency changes.
