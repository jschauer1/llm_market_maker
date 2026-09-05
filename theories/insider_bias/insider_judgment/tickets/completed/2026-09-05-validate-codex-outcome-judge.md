---
title: Validate a Codex outcome judge against the established procedure
lane: theory
theory: insider_judgment
created: 2026-09-05
created_by: root
author_lane: maintenance
author_context: Supervised floor preflight found no established Opus judge in the Codex runtime
status: done
closed: 2026-09-05
resolution: Superseded by the user ruling: assume an idealized judge across models following the same written procedure, aim for comparable intelligence, and share applicable calibration without a mandatory experiment or model-only version bump. Actual model provenance and replay cutoff rules remain required. See docs/RESEARCH_GUIDE.md, Record what judged, and what you asked it.
---
The production runbook requires the established Claude opus outcome judge; this Codex session exposes only Codex models and no claude CLI. First inspect saved blind payloads, original judgment outputs, provenance, and eligible evidence to design the cheapest meaningful model comparison. Reuse captured inputs rather than fetching or paying for the same original judgments. Predeclare the comparison and calibration decision, then run the candidate model under exp/ with exact model/prompt/effort/search receipts. Agreement alone does not demonstrate calibration compatibility. Historical outcome evidence requires an independently verified cutoff and eligible tier B procedure; unknown cutoff or outcome contamination cannot be relabelled. If eligible A/B evidence exists, use it fully without a live-only wait. Explicitly decide the version/evidence relationship before the new judge supplies production calibration. Preserve the broad screen, the strong-moderate-no slice and its complement. Do not silently substitute models, change the production procedure, or inherit the Opus calibration merely because prompts match.
