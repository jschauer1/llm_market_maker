# Broad experiment — collection stopped for analysis

**Latest user direction:** Stop expanding the data and analyze performance.
All three workers were interrupted at about 20:44Z on September 5. Do not
resume unrun batches or start a replay merely from the older worklist below.
`data/analysis-stop-manifest.json` freezes the completed first outputs:
48/73 batches, 2,296/3,563 contracts, 697 events. All four method repairs
finished; remaining 1,267 contracts stay explicitly unjudged. Current task is
bounded performance/candidate-quality analysis and a candid report.

User requested full-board cheap filters followed by many Sonnet-level judgments,
then evidence for useful subsets. Do not narrow back to FDA/bills. No automation,
floor, bets, theory retirement or production calibration is authorized here.

Frozen code: screen at `4230e80`; immutable input cohort at `fbd28df`.
Current membership: shared board 2026-09-05 15:45:16Z, 115,840 rows;
final `data/census-v5` has 3,563 contracts / 1,037 events / 983 series.
73 batches at `data/judgments`, decision/source cutoff 19:53:15.489944Z.
Requested judges: gpt-5.6-sol high, web enabled, unresolved actual snapshot.
Never send receipts or books to judges; only rendered-prompt and input files.

Historical assignment: `broad_judge_0` handled indices divisible by 3;
`broad_judge_2` handled indices congruent to 2. `broad_judge_1` stopped after a quality audit:
only 001 had actual source evaluation. 004/007/010/013 are quarantined by
quality-exclusions.json, preserved unchanged, and being redone under the exact
same inputs by `broad_judge_repair` in `data/repair-judgments`. All four repairs
are complete. Most shard-1 work from016 remains unrun. Original shard2 is
complete; shard0 completed through054. Further bounded assignments were
interrupted before completed outputs. Keep the automatic-abstention failure
in quality-audit.json separate from real evidence gaps.

After completed-batch notifications run:

```
python -m theories.procedural_bottlenecks.studies.investigation.2026-09-05-broad-procedural-judgment.batches ingest --out theories/procedural_bottlenecks/studies/investigation/2026-09-05-broad-procedural-judgment/data/judgments
python -m theories.procedural_bottlenecks.studies.investigation.2026-09-05-broad-procedural-judgment.capture_books --workers 4
```

For repair books pass `--judgments-root <study>/data/repair-judgments`.
Ingestion uses valid replacements once and omits quarantined originals. Fresh
books retain first-output mtime/capture lag; they are not backdated to snapshot.
Early book curves predate the decimal-complement correction; recompute math
from saved raw books before final reporting, preserving the original captures.

Historical coverage is frozen separately: `historical-frame.md` and
`data/historical/census/closed-window-blind.json`: Aug29 full board110,628;
3,508 broad survivors,271 contracts/110 events closing by Sep5 snapshot time.
No outcomes inspected. Some mechanical metric leaks still pass conservatively;
judges return not_applicable. Do not tune this running cohort again. Historical
source packets, separate offline judgments and outcome-blind effect design are
still required before a retrospective edge result. The model cutoff receipt
in the completed FDA study hashes correctly (2026-02-16, alias unresolved).
Original four KXBILLS holdout outcomes remain sealed; never inspect them.

Review actual evidence, not only JSON schema. Early barrier labels for tariffs
and GLP-1 Part D need scrutiny: old tariff orders do not establish current
status, and delayed coverage is not necessarily delayed policy announcement.
Preserve original labels; record review separately. No label is a probability.

Run focused study tests and applicable repository checks once changes settle.
Only study files have been committed. Preserve all other dirty user/peer paths;
`.gitignore` has a new local raw-data rule among earlier uncommitted changes.
Raw board corpora are local; force-add paid inputs/outputs/receipts explicitly.
Keep final context compact and link this study from its owner's learning map.
