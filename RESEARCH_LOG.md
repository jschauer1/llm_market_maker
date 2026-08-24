# Research Log

Append-only. Newest entries at the bottom. One entry per research session.

This is what gives sessions continuity — read the tail before starting work,
append before finishing. Without it every session starts cold and the system
repeats itself instead of accumulating.

Format:

## YYYY-MM-DD — one-line summary

**Did:** what actually happened.
**Learned:** what you now know that you didn't.
**Next:** what is worth picking up next session.

---

## 2026-08-23 — Repo built

**Did:** Built the harness — data layer, tools, theory format, skills. Ported
`insider_bias` from `kalshi_trader` with its real track record.

**Learned:** Kalshi candlesticks carry historical bid/ask and reach back ~12
months, so tier A backtests can use executable prices. Kalshi's field schema
has changed since `kalshi_trader` (decimal-dollar strings, `_fp` sizes).
Polymarket exposes per-trade wallet identity and server-side size filtering.

**Next:** Nothing has settled under the new system yet. The highest-value work
is a tier A backtest of the `insider_bias` stage-1 screen — it is
uncontaminated, has a year of history available, and would give the first real
evidence in the ledger. **Missing prerequisite:** no adapter exists from
`history.point_in_time()`'s candle shape to the market dict `screen.screen()`
expects, and `no_ask` isn't on a candle at all — derive it as
`1 - yes_bid_close`. Step one of this work is writing that candle→market
adapter in `theories/insider_bias/`; `tools.kalshi.markets.list_settled()`
gives a workable replay universe of "markets open on date X" in the meantime.

---

## 2026-08-23 — Correcting a wrong number: `list_open()` was truncating, not the 14-day filter

**Did:** Fixed a critical bug where `tools.kalshi.markets.list_open()`
defaulted to a 10-page cap. Kalshi's `/events` feed is **not** sorted by
close time, so that 10-page prefix was not a sample of the board — it was a
biased slice containing almost no near-term markets, which is exactly what
`insider_bias`'s 14-day horizon screens for. Changed the default to page to
exhaustion (`max_pages=None`), and made an explicit `max_pages` cap raise
`TruncatedFetchError` if it is hit while the cursor is still live, instead of
warning weakly.

**Learned:** An earlier measurement (uncorrected in this log until now) had
concluded the `insider_bias` screen's 14-day horizon was the bottleneck,
citing a ~0.05% pass rate (about 1 candidate out of ~14,500 markets fetched).
That number was itself an artifact of the truncation bug, not a property of
the filter. Measured against a complete board the same day, three ways:
`list_open()` with the old defaults returned 14,544 markets and 1
`insider_bias` candidate; `list_open(max_pages=60)` returned 95,779 markets
and 784 candidates (276 events); the predecessor system's raw dump of the
same board, same day, had 32,427 markets (31,561 within the 14-day horizon)
and 960 candidates kept by its filter. **The true figure is roughly 31.5k
markets inside the horizon and several hundred surviving candidates** — the
screen is not the bottleneck, and the "handful of candidates" framing that
had been written into `theories/insider_bias/THEORY.md` was wrong. Recording
this here so the ~0.05% figure is never re-cited as if it described the
filter.

**Next:** See the entry above — the candle→market adapter for a tier A
backtest is still the top prerequisite. Separately, `insider_bias` is past
its `n=20` review trigger with a negative net calibration edge; see the
Status section of its `THEORY.md` for the numbers.

---

## 2026-08-23 — `insider_bias` is `active` but already past its review trigger

**Did:** Documented, honestly, that `insider_bias`'s `active` status was set
by the one-time migration to prove the harness works end-to-end — it was
never a claim that the imported history clears the promotion bar. Measured
now: n=29, `calibration_edge_net = -0.75` points overall; restricted to rows
the predecessor actually bet (`extra_json.status` starting `BET`, i.e.
excluding declined-limit rows recorded at zero edge), `calibration_edge_net
= -1.87`. Both are negative, and n=29 is already past the `n=20` review
trigger in `CLAUDE.md`'s lifecycle rule.

**Learned:** `find-edge` defaults to `--status active`, so as things stand
today the first session that runs it will scan a theory whose own imported
track record says it currently loses after fees. That is not a reason to
silently change the status mid-branch (the migration's semantics should not
be rewritten after the fact) — it is a reason to flag it loudly here and in
`THEORY.md` so nobody mistakes `active` for "validated."

**Next:** Validating or retiring `insider_bias` is a first-order task for an
early session: either run the stage-2 backtest (tier B/C per its `THEORY.md`)
to see whether interpretation recovers the edge the raw screen does not show,
or apply the lifecycle rule and move it to `paused`/`retired` if it doesn't.

---

## 2026-08-23 — Theory status became an evidence level; retirement became the user's call

**Did:** Reworked the theory lifecycle. Status is now an evidence level —
`proposed` → `testing` → `active`, with `under_review` for a theory failing
its own bar and `paused` reserved for one blocked on a missing prerequisite.
`under_review` **keeps running**, which is the substantive change: the old
design paused a failing theory at `n=50`, freezing its sample at exactly the
size that made the verdict unreliable. `find-edge` now runs `testing`,
`active`, and `under_review`; credibility weighting, not a scan filter, is
what stops an unproven theory crowding out a proven one.

Added a diagnosis checklist (`score-theories` §5) that must be worked before
any opinion about a theory's future, and made retirement user-only:
`theories propose-retirement <id> --rationale "..."` records a standing
suggestion and leaves the theory running; `theories status <id> retired`
refuses without both `--authorized-by user` and a proposal on file.
`theories pending-retirement` surfaces unruled proposals in every orient.

Moved `insider_bias` from `active` to `under_review` and rewrote its Status
section from "flagged as questionable" to an actual diagnosis.

**Learned:** The `insider_bias` numbers do not support any verdict yet. At
n=29 the standard error on a win rate is roughly 9 points, so
`calibration_edge_net = -0.75` is well inside the noise — the theory has been
glanced at, not measured. The interesting failure modes (fees eating a real
edge, judgment inverted over a sound screen, one profitable slice, an
inverted sign, contaminated tier, mixed versions) are all indistinguishable
from death at a glance, which is why the checklist exists.

The `theories` table needed a rebuild to widen its status CHECK; SQLite
cannot alter one in place. `db.schema_statement()` extracts the DDL from
`schema.sql` so the migration cannot drift from the schema it recreates. The
live database migrated cleanly — 96 opportunities, 49 settlements, no FK
violations.

**Next:** Unchanged and now sharper: the candle→market adapter for a tier A
backtest of the `insider_bias` stage-1 screen. It is item 1 on that theory's
own diagnosis list because it separates the screen from the judgment, which
is the single most informative split available on it.

---

## 2026-08-23 — First live run: the screen has almost no thesis alignment

**Did:** First real use of the system. Pulled the complete Kalshi board
(96,084 markets, 13s, snapshotted), ran the `insider_bias` stage-1 screen →
765 candidates across 274 events, then the documented stage-2 cascade: two
strong subagents at high reasoning, judging **blind to price** (payload
programmatically asserted free of `yes_ask`/`no_ask`/`mid`/`spread`/
`fav_side`), 16 events each, returning a confidence bucket per event.
Recorded 44 opportunities under `run_id='live-2026-08-23'` — 25 endorsed,
19 rejected. These are the theory's **first-ever endorsed and rejected
rows**; every prior row was `screened`.

**Learned:**

1. **The stage-1 screen barely intersects its own thesis.** Classifying all
   274 candidate events against THEORY.md's own written gate rules, **242
   (88%) fall in categories the theory is written to reject**: aggregates of
   many independent people (61 events), live sport that leaked past
   `EXCLUDED_PREFIXES` (47), weather (32), crypto strike ladders (31),
   commodity/FX/rates (28), compute/collectible prices (20), scheduled
   indicators (16), retail price indices (7). Only 32 events could carry the
   thesis at all. The screen is a generic tradeable-favorite filter — price
   band, spread, volume, near close — with no thesis term in it. This is a
   live explanation for the flat imported record: if 88% of what reaches
   judgment cannot carry the thesis, near-zero measured edge is the expected
   result. Concrete leaks: `EXCLUDED_PREFIXES` misses `KXWNBA`, `KXUCL`,
   `KXNWSL`, `KXTESTMATCH`, `KXLMBGAME` and ~18 more live-sport families, and
   nothing excludes price-strike ladders (330 candidates on their own).

2. **Resolution rules diverge from titles at an extraordinary rate.** 19 of
   32 events (59%) carried a rules/title divergence, several decisive:
   `KXCLAUDE-NXTMYTH` excludes only Fable 5 while Mythos 5 shipped the same
   day (June 9) and is not excluded; `KXVIDEOLENGTH-GTA` never says whether
   the strike ladder measures one episode, the total, or the YouTube cut;
   `KXTRYFIRECOOK` has no "after Issuance" clause though Trump already
   attempted removal in 2025; `KXHEARNCHARGE` requires a *new* charge after
   an undefined "Issuance". THEORY.md already lists rules divergence as a
   warning sign, but at 59% it is not an occasional trap — it is the modal
   property of this candidate class, and reading rules may be a larger part
   of the edge than identifying insiders.

3. **The AGT heuristic in THEORY.md is wrong as written.** The theory says
   pre-taped competition TV is the strongest sub-case and deserves extra
   weight. The subagent correctly refused it for `KXAGTELIMINATION`: AGT's
   live quarterfinals are *not* pre-taped, and elimination is decided by
   public vote — the aggregate-of-many-people case the thesis excludes. The
   heuristic needs the qualifier "pre-taped **and** taping already
   completed"; applied to a live-vote show it inverts.

4. **Two session-level overrides**, both applying the theory's own
   warning-sign rule. `KXIPOSHEIN-DATE` strong→weak: independently verified
   that CSRC approval (Jul 10), the HKEX prospectus (Jul 26) and the ~Sep 1
   target are all in mainstream press, so there is no informational
   asymmetry — the thesis needs a group who knows what the public does not.
   `KXVIDEOLENGTH-GTA` strong→moderate on the unresolved measurement
   ambiguity.

5. **Credibility is 0.0, so every candidate ranks at 0.0.** `realization` is
   0.0 on the imported history, so `ranked_edge = 0` for every bucket. Per
   `find-edge` §6 this was reported as claimed edge plus the shrinkage
   reason, not as a table of zeros.

**Next:** The 44 rows resolve between Aug 24 and Sep 5, so
`interpretation_value` — diagnosis item 2, never computable before — becomes
available in under two weeks. Two candidate version-2 changes are now
evidence-backed enough to specify: exclude price-strike ladders and the
leaked sport families from stage 1, and add a mechanical rules-vs-title
divergence check. Both are stage-1 code, which would move part of this
theory toward tier A. Do not bump the version until the current 44 settle —
changing the procedure mid-flight is exactly what the versioning rule exists
to prevent.

**Addendum, same session — v2 bump and track-record reset.** On the user's
instruction the v1 data was **deleted** (96 imported opportunities, 28
settlements; backed up outside the repo, regenerable via
`migrate_kalshi_trader.py`) and the theory bumped to **version 2**, because
the decision procedure changed: subagent output is now an *initial*
recommendation only, and no candidate may be suggested as a bet unless the
main research session reviews and recommends it itself, with the deciding
model recorded on every row (`extra_json.final_recommendation.decided_by`).
`disposition='endorsed'` now means "the main model recommends this bet",
not "arithmetic produced a positive number". New `Stage 3` section in
`THEORY.md`.

The run was re-recorded under v2. **The mechanical v1 rule would have
endorsed 25 of 44 markets; the main model recommends 3.** That gap is the
justification for the change: the 22 it declined were dominated by a defect
visible only in the batch view — the resolution-rules divergence broadens
what counts as YES, and 543 of 765 screen candidates are NO-side favourites,
so the divergence systematically damages the exact leg the screen picked. A
per-candidate subagent cannot see that pattern; comparing candidates
side by side is what the final stage is for.

The reset means the theory is now **n=0 — unproven, not disproven**. Note the
one thing lost: the v1 rows were the only dataset that could have answered
whether LLM-introspected `q` values realize their claimed edge (see the
2026-08-23 Learnings note on `model_prob_source`). That question is now
parked behind re-running the migration, not gone.

---

## 2026-08-23 — Provenance: model + prompt are now recorded and enforced

**Did:** Made "record what judged, and what you asked it" a repo-wide
expectation with a mechanism behind it, after noticing the gap: nothing
persisted prompts anywhere, and the model was tracked only in an ad-hoc
`extra_json` field I had added to one theory an hour earlier.

- New `judgment_runs` table: `run_id`, theory, version, `stage`
  (gate/analysis/final_review/other), `model`, `effort`, `prompt_path`,
  `prompt_sha256`, `prompt_text`, `web_search`, `n_items`. A table CHECK
  requires a path or inline text, so the prompt is always recoverable.
- New `tools/provenance.py`. `prompt_sha` normalizes line endings so a CRLF
  checkout does not read as prompt drift.
- New `theories.uses_llm_judgment` flag. When set, `record_opportunity`
  **refuses** rows for a run with no provenance — the omission is impossible,
  not merely discouraged.
- `provenance record|list` on the CLI.
- Prompts moved to files: `theories/insider_bias/prompts/analysis.md` and
  `final_review.md`, so a change appears in `git diff` and is reviewed like
  any other procedure change.

**Learned:** The sharpest finding was about this session's own work. The
"gate" that produced the headline 88% number existed **only inside a shell
heredoc** — not in the repo, not in the scratchpad, only in the transcript.
A number reported as evidence in `THEORY.md` and this log was reproducible
only by re-reading the conversation. It is now `theories/insider_bias/gate.py`
with 26 tests, and re-running it against the same board reproduces **242/274
exactly**. The tests also pin the one real bug: the patterns were first
written against event-ticker shape (`RT-`, `UE-`) while they match the
*series* ticker (`KXRT`, `KXUE`), which leaked six events into the survivor
set before it was caught.

The general lesson is that the reproducibility gap does not announce itself.
Every number this session produced looked equally solid in the report; only
one of them was backed by committed code. Enforcement at the write path is
the only thing that catches this, because a discipline that depends on
remembering will fail exactly when a session is busy — which is when it
matters.

**Next:** Unchanged — the 44 v2 rows settle Aug 24–Sep 5, making
`interpretation_value` computable for the first time. Note that
`backtest_runs.uses_llm_judgment` and `model_cutoff` now overlap with
`judgment_runs`; a later session should decide whether backtests should
simply join the new table rather than keep their own copy.
