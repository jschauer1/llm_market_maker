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

---

## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false
## start that took 47 minutes to fail

**Did:** Orient found nothing new to settle (all 44 v2 rows from yesterday
still open) and no theory besides `insider_bias` on the board, so I picked
THEORY.md's own top-priority item: a tier A backtest of the stage-1 screen
alone, which the theory had never had. Built the candle→market adapter
(`theories/insider_bias/backtest.py`, `replay_market`), then ran it.

**Learned, the expensive way first:** A naive `list_settled(min_close_ts=...,
max_close_ts=...)` walk is not usable for a recent window. One series,
`KXMVECROSSCATEGORY` (a combinatorial "shard" product), settles **400,000+
markets per day** on its own — confirmed by an exhaustive count that hadn't
finished at 400 pages for a single day. A 30-day walk ran for 47 minutes
without completing before I killed it, on the user's instruction to
investigate a better approach rather than just wait longer or shrink the
window. Two compounding mistakes made this worse than it needed to be even
before the volume problem: the fetch phase had no incremental checkpoint, so
47 minutes of API calls were unrecoverable the moment the process was
killed; and I didn't check the true scale before committing to a window size
— a few density-sampling probe calls would have caught the problem before
launching an hour-long run instead of after.

**The fix:** Kalshi's `/series` listing (one call, ~13k series) exposes a
`category` field, and `/markets?status=settled` honours an (undocumented)
`series_ticker` filter. `candidate_series()` narrows 13,437 series to ~2,200
by dropping `screen.is_excluded` ticker prefixes, `NO_CATEGORIES`
(Sports/Crypto/Weather/Commodities/Economics/Elections/Financials — the same
families `screen.is_excluded`/`gate.py` already reject downstream), and
series untouched in 60+ days — all *before* issuing a single settled-market
request. `iter_settled_survivors` then walks one series at a time, which
Kalshi's API returns dramatically smaller pages for. Result: a 90-day window
that the old approach hadn't finished in 47 minutes ran in **~9 minutes** for
the fetch phase, ~2.5 more for a 600-candidate candlestick replay. Both
`tools/kalshi/markets.py::list_settled` (new `series_ticker`/`raw_filter`/
`on_page` params) and the driver script now checkpoint incrementally —
survivors every 100 series, replay results every 25 candidates — so this
class of mistake cannot repeat.

**Result:** `run_id=backtest-2026-08-24-stage1-90d`, tier A, no LLM in the
decision path. 18,430 candidates survived the cheap pre-filter; a systematic
sample of 600 replayed against real point-in-time candles; 200 actually
cleared the screen at some point in their last 14 days. Overall:
`win_rate=85.0%`, `calibration_edge_net=+1.38pts`. That number is a
composite of a strongly negative slice (n=47, the "aggregate of many
independent people" family `gate.py` already excludes: `-11.12pts` — direct
mechanical confirmation that exclusion is correct) and two positive slices
(n=116 "MENTION"-suffix series `gate.py`'s regex currently misses:
`+5.48pts`; n=37 everything else, the cleanest thesis-eligible slice,
including `KXBIGBROTHERELIMINATION` — the same series as a live v2 endorsed
opportunity: `+4.40pts`). Full breakdown in `THEORY.md` Learnings,
2026-08-24. Moved the theory `under_review` → `testing`: the specific v1
diagnosis that kept it under review (is the screen itself broken) is now
answered — no — but the theory's actual claim (does judgment add value) is
still n=0 on the live side, so `active` isn't justified yet.

**Next:** The 44 live v2 rows still settle Aug 24–Sep 5 — once they do,
`interpretation_value` becomes computable and should be read alongside this
backtest, not in isolation. The MENTION-family question (Status item 3) is a
real open thread: is it thesis-relevant or a distinct, still-profitable
phenomenon? Deciding that is a judgment call, not more plumbing, and
probably wants a small subagent batch reading a sample of those markets'
actual resolution rules. The `KXMVECROSSCATEGORY`-style volume trap is not
insider_bias-specific — any future theory doing historical Kalshi analysis
will hit the same wall; `list_settled`'s docstring and `backtest.py`'s module
docstring both carry the account now, so it should not need rediscovering.

---

## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother
## bet, and a new mechanical path for the MENTION-family edge

**Did:** Two direct challenges from the user, both acted on rather than just
answered. (1) "Isn't Big Brother all live?" — checked, and the original
Stage 3 endorsement of `KXBIGBROTHERELIMINATION-26AUG27-DRE` had overstated
its case: this season resolves eviction through a genuinely live "BB Block
Buster" competition, not a pre-decided vote. Verified via web search (fair
game for live research on an open opportunity, unlike a backtest) that the
NO bet still holds on a narrower basis — the house's plan protects Drew
across every branch of that live competition — and corrected the ledger's
stored interpretation rather than leave the overstated version standing.
Added an explicit Stage 3 checklist item: verify the resolution *mechanism*,
not just the facts fed into it. (2) "If I put $10 into 20 mentions I should
make $16?" — no: `calibration_edge_net` is percentage points of
win-rate-minus-price, not a percentage ROI. Computed the real number
(`roi_all=6.7%`; 20 contracts actually cost ~$16, not $10) and then, per the
user's follow-up request, built the functionality to actually run this edge
rather than just discuss it: `screen.is_mention_family` (the classifier,
now real code with tests, not an ad hoc lambda in a scratch script) and
`theories/insider_bias/mention_bucket.py` — a wholly separate, mechanical,
`edge_basis='measured'` decision path with no gate, no subagent, no Stage 3.
Bumped the theory to **v3** for it (screen/gate/prompts/Stage 3 unchanged;
the bump is because the theory now has two decision procedures, not because
the old one changed). Retagged the 116 mention-family backtest rows with
`confidence='mention_family'` so `score.bucket_rates` measures it properly
per the existing bucket infrastructure, rather than inventing a parallel one.

**Learned:** Ran the new path against a freshly forced board pull (101,856
markets). Result: **0 live candidates**, and confirmed why rather than
assumed a bug — 490 mention-family markets are currently open, but the
nearest close is 14.6 days out against the screen's 14-day cutoff, with 157
more sitting in the 14–20 day range. This reads as a recently-issued batch
with long horizons, not the family disappearing; it should start clearing
the screen within days. Also worth remembering going forward: a
mechanical-edge bucket like this one gives every candidate the *same*
probability (there is no per-market signal, only the family's aggregate
rate), so "rank by edge" is really "rank by lowest price in the qualifying
band" — worth being explicit about that whenever this path's output gets
reported, since "most likely to win" reads like a per-market claim this
model cannot actually make.

**Next:** Re-run `mention_bucket.py` in a few days once the 14–20-day batch
ages into the eligible window — this is genuinely a "try again shortly," not
a dead end. Once it has live settlements of its own, check whether its own
measured rate holds up against the backtest's bootstrapped one (the real
test of durability, not the 90-day retrospective window). The underlying
"informed minority vs. base-rate quirk" question for the MENTION family is
still open — idea `insider-bias-mention-family` — and now lower-urgency
since the mechanical path captures the edge regardless of the answer, but
still worth resolving for its own sake.

**Addendum, same session — 30-day preview, and making "extension not
replacement" explicit.** Two follow-up requests: make sure v3 reads as an
addition to insider_bias, not a revision of it (added an unmissable callout
at the top of THEORY.md's Hypothesis section and the top of
`mention_bucket.py`'s docstring, not just buried in the Version section);
and widen the window to see actual live candidates, since 0 at 14 days was
correct but not useful for "what can I bet today."

Added `max_days_ahead` to `find_candidates` and a new `rank_preview`
function that reuses the validated bucket's measured rate as a point
estimate but always labels the result `edge_basis='model'`, never
`'measured'` — the backtest never tested eligibility past 14 days, so
applying that rate further out is a modeling assumption, not a
measurement, and the two should not look identical in the ledger. Recording
also takes an explicit `confidence` label now, so a preview run's rows
land in a distinct bucket (`mention_family_preview_30d`) that can never
pool into the validated `mention_family` bucket's `bucket_rates()`.

Ran it at 30 days against a fresh board: **69 candidates**, top 20 recorded
under `run_id=live-2026-08-24-mention-preview30`. Same caveat as always
applies harder here: every candidate still shares one flat probability, so
the ranking is by price, and now additionally by an untested-horizon
assumption on top of that. These are more "here is what the mechanical
model surfaces" than "here is proven edge" — said plainly when reporting
them.

**Addendum, same session — the flat rate was a real bug, caught by a user
who trusted their own trading experience over the model's output.** Asked
to also weigh volume and asked "from what point was the edge considering" —
pointed at a real problem: one flat win rate (0.871) for the whole
$0.65-$0.97 band meant the ranking put $0.65-0.70 favorites at the top,
which contradicted the user's stated experience that 80%+ is where this
kind of edge usually shows up. Checked the backtest data rather than argue
either way: it agreed with the user sharply — win rate rises from 0.73
below $0.75 to 0.87 at $0.75-0.85 to 1.00 at $0.85+, so the cheap end has
close to zero real edge and the flat model was crediting it with the most.

Fixed properly rather than patched: retagged the 116 backtest rows from one
`confidence='mention_family'` into three price-bin labels
(`mention_family_lt75`/`_75_85`/`_85plus`), added `bucket_for_price` and
`PRICE_BINS` to `mention_bucket.py`, and made `rank`/`rank_preview` score
each candidate against its own bin. Checked volume too before adding it:
not predictive of win rate here (bins bounce between +0.9 and +11pts with
no trend), so it is a tiebreaker and a reported field, not part of the edge
— folding in a checked-non-signal would have been worse than leaving it out.

Old preview run (`...preview30`, ids 403-422) marked `skipped` in the
ledger with a correction note rather than silently overwritten. Corrected
re-run (`...preview30-v2`) is dominated by the $0.85+ bin. Did not bump the
theory version for this: nothing had settled yet under the buggy version
(all 20 rows were `screened`/`untouched`), so there is no track-record
mixing risk the versioning rule exists to prevent — this is a bug fix to
v3's own implementation, not a new decision procedure layered on top.
Flagged one more thing for a future session rather than fixing it now: the
$0.85+ bin's 1.000 win rate (n=41, zero losses) will very likely regress
with more data, and nothing in `buckets.py` shrinks it — reporting `+8pts`
on that bin deserves more hedging than a bin that has actually lost a few.

---

## 2026-08-24 — mention_family becomes a real, separate theory; insider_bias
## renamed insider_judgment and folded into a shared parent folder

**Did:** The user asked, twice, for the mechanical mention-family mechanism
to stop being a sub-path of `insider_bias` and become its own theory —
first a quick confirmation of the tradeoff (worth it: two genuinely
different claims, informed-minority-by-judgment vs. mechanical-family-rate,
had been sharing one version number), then, after a further steer on the
layout, a specific directory shape: `theories/insider_bias/` as a shared
parent, with the LLM-judged theory (renamed `insider_judgment`, since
`insider_bias` was no longer its name once it stopped being a leaf folder)
and `mention_family` as sibling subfolders underneath it, and the shared
`screen.py` living at that parent level rather than in generic `tools/`.

Executed as a real migration, not a fresh start:
- Extracted the mechanical favorite screen to `tools/screen.py` first (the
  textbook move per this repo's "moves to tools/ once there's a second
  caller" convention), then relocated it to `theories/insider_bias/
  screen.py` once the user clarified the directory shape they wanted —
  `tools/` was the more generic-infrastructure-conventional home, but not
  what was actually asked for once the fuller structure was clear.
- Moved `gate.py`, `pipeline.py`, `backtest.py`, `prompts/`, and that
  theory's `THEORY.md`/`RUNBOOK.md` into a new `insider_judgment/`
  subfolder; moved the standalone `mention_family/` folder to become
  `insider_bias/mention_family/`.
- Renamed `theory_id='insider_bias'` → `'insider_judgment'` across every
  table that references it (128 opportunities, 4 judgment_runs, 1
  backtest_runs row) — version number carried over unchanged (3, not reset
  to 1), since this is the same decision procedure and history under a
  corrected name, not a new theory. `mention_family` kept its own
  `theory_id` throughout; only its `path` column and package import path
  changed.
- Updated every import, CLI example, and prompt-path string across both
  theories' `THEORY.md`/`RUNBOOK.md` and `CLAUDE.md` itself (which named
  `insider_bias` as the reference theory in five places) to match. Left
  historical log entries and already-recorded `judgment_runs.prompt_path`
  values alone — they are accurate records of what was true when they were
  written, not something to retcon.

**Learned:** Splitting the evidence apart changed what insider_judgment's
own remaining tier-A backtest evidence actually says. The original
`+1.38pts` headline (n=200, everything the stage-1 screen touched) was
mostly the mention family's positive edge canceling out insider_judgment's
own negative slice. With mention_family's 116 rows now properly attributed
elsewhere, insider_judgment's own remaining 84 non-mention rows score
`calibration_edge_net=-4.28pts` — negative. That number is itself a
blend of the "aggregate of many independent people" family `gate.py`
already excludes (-11.12pts, n=47) and the genuinely gate-plausible slice
that actually reaches judgment in the live pipeline (+4.40pts, n=37) — so
the theory's `testing` status still rests on real footing (gate.py's
filtering is doing real, measurable work), but the raw, ungated number is
a more sobering thing to see next to `insider_judgment` now that it isn't
diluted by a family that turned out to belong to a different theory.

**Next:** Both theories are independently re-runnable and independently
scoreable now (`score report insider_judgment` / `score report
mention_family`), which was the actual point of the split — future
sessions comparing theories or deciding what to backtest next should treat
them as two unrelated entries on the board, sharing only a mechanical
favorite filter, not one theory with an asterisk. `mention_family`'s live
preview run (`...-preview30-v2`) and `insider_judgment`'s 44 v1/v2 rows are
both still settling Aug 24–Sep 5 — check both when reporting on progress,
not just one.

## 2026-08-24 — A researched theory-idea backlog: 12 implementable specs in docs/theory-specs/

Session pivoted from "define one novel theory" to "write out many, well
enough that a fresh session can implement any of them cold." Brainstormed,
then did an actual literature pass (two arXiv papers read in full via
extracted text, plus targeted searches) before writing anything down, so
each idea carries documented evidence for *why* the edge should exist, not
just a hunch.

The two load-bearing findings from the reading, both now cited inline where
they matter: (1) Le 2026 (arXiv:2602.19520, 353M trades) measures Kalshi
calibration slopes by domain x horizon — politics is compressed toward 50%
at nearly all horizons (a 70c political contract a week out is really
~83%), short-horizon weather is miscalibrated the *opposite* way (prices
too extreme), and everything compresses beyond a month. Direction flips by
cell, so any calibration-harvesting theory must carry a per-cell sign. (2)
Angelini & De Angelis 2026 (arXiv:2606.07811) find Kalshi NBA in-play
prices adjust only 0.64-for-one to public news with predictable drift — but
the drift dies to bid-ask at minute scale, which repositions any news-drift
theory to daily-scale non-sports moves and pre-registers its likeliest
failure mode (real gross, dead net).

Deliverable: docs/theory-specs/ — one spec file per theory (user asked for
each theory as its own spec mid-session; an earlier single-file draft was
split), each with thesis, evidence, mechanical procedure, backtest plan
with idea-specific lookahead traps, kill criteria, and build notes, plus a
README carrying the shared repo-contract checklist and priority table. All 12 recorded in the idea registry
(slugs: calibration-harvest, deadline-drift, structural-arb,
series-bias-mining, news-drift, cross-venue-fair-value, smile-smoothing,
settled-but-trading, whale-follow, vol-crossing, new-market-anchor,
implication-graph; registry ids 2-13). Ranked by information-per-effort:
calibration-harvest first (mention_family math, whole board, huge n),
deadline-drift second (design already agreed with the user this session),
structural-arb third (near-free to run forever). Ten of twelve have no LLM
anywhere in the decision path; implication-graph quarantines judgment at
construction time; cross-venue-fair-value needs judgment only for one-time
pair confirmation.

Nothing was implemented — the backlog is the artifact. Next session: pick
from the top of the table, propose-theory, build.

## 2026-08-24 — Backlog v2: official spec format, second literature pass, 5 new theories, honest scoring

User direction, three parts in sequence this session: split the backlog
into one spec per theory (done earlier as docs/theory-specs/), then
"official superpowers-type specs" plus more literature hunting, then a
scored assessment on every spec because "another fable model will review
your specs."

Migration: docs/theory-specs/ is gone; the canonical home is now
docs/superpowers/specs/2026-08-24-theory-<slug>-design.md, matching the
house exemplar (numbered sections: Hypothesis, Evidence, Non-goals,
Decision procedure, Data requirements, Backtest design, Kill criteria,
Implementation plan, Testing approach, Open risks, Sources), with
2026-08-24-theory-backlog-index.md carrying the shared contracts, rubric,
ranking table, parked ideas, and sources. Registry ids 2-13 repointed.

Second literature pass found four load-bearing results that became five
new specs (registry ids 14-18): Becker's wealth-transfer microstructure
(takers -1.12%/trade vs makers +1.12%; YES underperforms NO by up to 64pp
at equal longshot prices; entertainment 4.79-7.32pp inefficiency vs
finance 0.17pp) -> no-side-premium and maker-mode-execution; Clinton &
Huang 2025 ($2.4B, 2,500+ political markets, negative daily
autocorrelation) -> overreaction-fade, designed against news-drift via a
shared sign-measurement so the two continuation/reversal theories can
never both claim the same cell; Campbell-Sharpe consensus anchoring
(JFQA 2009, re-confirmed FEDS 2026) -> econ-anchoring; documented
on-chain insider lead windows plus the Columbia wash-trading numbers
(~25% of PM volume fake, 45% in sports) -> insider-flow-radar, and the
wash caveat also folded into whale-follow and cross-venue-fair-value.
Palumbo 2026 (Kalshi NFL passive LPs profitable but adversely selected --
"underwriters, not market makers") is the maker-mode spec's central
tension.

Every spec now carries an Assessment block: applicability /
implementability / likelihood-of-success, 1-5 ordinal with stated
reasoning (rubric in the index; explicitly not introspected
probabilities). Scored honestly rather than promotionally: news-drift and
vol-crossing rate their own likelihood 2/5 because the best direct
evidence points against them (drift measured dead net of spread at minute
scale; Kalshi crypto measured near-calibrated short-dated). Composite
ranking and priority order diverge in three places; the index explains
each (sequencing and information-value, not score, break the ties).

Coordination: session -cc committed my in-flight files in d419fed (git
add -A, pre-protocol) and later added a public remote
(github.com/jschauer1/llm_market_maker) and pushed this branch. I
committed the follow-ups with explicit paths and did NOT push -- session
-d3 has flagged the public-remote question (real trade data in
db/opportunities.json) to the user, and pushing before that ruling would
publish these specs plus that data further. Next session: pick from the
top of the index table, propose-theory, build. calibration-harvest is the
fastest to evidence; deadline-drift has the user-agreed design.

## 2026-08-24 — Backlog round 3: five more specs from a third literature pass (22 total)

Same process as rounds 1-2 at the user's request: hunt for edges not
already covered, research properly, spec in official format with honest
Assessment scores. Five new specs (registry ids 19-23, priorities 8, 9,
12, 17, 18 of a re-ranked 22), one parked idea (id 24), all existing spec
priority lines renumbered to "of 22".

The find of the round is parlay-fade: arXiv 2607.14430 measured, on 23M
Kalshi moneyline trades, that cross-game parlays are systematically
overpriced relative to the product of their leg prices -- with the legs
themselves essentially perfectly calibrated in mid-life TTE buckets,
which removes the alternative explanation. Kalshi combos are peer-to-peer
(RFQ plus a post-fill order book), so the fade side is accessible; the
open question is workflow fit for a manual user, priced into its
applicability score. Its L=4 is the highest-quality new evidence in the
backlog.

The rest: weather-model-gap (per-station NWS settlement, keyless
Open-Meteo forecast archive enables honest as-of tier-A backtests;
heavily tooled competition is the named risk -- the backtest must show
edge surviving the crowded era); calendar-arb (date-ladder nesting is
hard logic across separate event pages nobody compares -- the pure-code
middle ground between structural-arb and implication-graph; the by-vs-in
window trap is the concentrated risk); attention-model (Wikipedia
pageviews predict openings a month out per Mestyan et al. 2013, and
entertainment is Kalshi's measured-least-efficient category);
metaculus-gap (skill-weighted forecaster aggregate as fair value, with a
freshness gate because a stale forecast gap is lag, not edge).

Settlement-spillover considered and parked with a revisit angle (mine
measured co-movement pairs first); same-game parlay correlation parked
as the hard version of parlay-fade. Both recorded in the index's parked
list and the registry.

Still holding the push to origin pending the user's ruling on the public
remote. Next: same top of the table -- calibration-harvest, then
deadline-drift -- unless the user wants another round of this.

## 2026-08-24 — Evidence folder: reading notes and a graded claims ledger for spec reviewers

User asked whether the specs are referenced well enough for reviewing
LLMs to check what was found. They were cited (inline + Sources sections
+ annotated index bibliography) but two gaps existed: the two papers
read in full lived only in session scratchpad, and nothing distinguished
a primary-verified number from one that arrived via a search summary.

Added docs/superpowers/specs/evidence/: reading notes for Le 2026 (full
Table 4/5 transcriptions with locators, isotonic checks, the
half-of-variation-is-noise caveat) and Angelini & De Angelis 2026
(0.64/0.51 coefficients, full Table 6 drift matrix, the verbatim
"executable-style returns ... are negative" quote), plus an evidence
ledger grading every load-bearing claim across all 22 specs A/B/C/D by
verification status. The ledger is honest about weak spots: the
"60-70% reversion" figure in overreaction-fade is grade D (forum
synthesis, not found in the abstract read directly), Becker's 64pp
YES/NO figure needs its exact conditioning verified before
no-side-premium is built, and the FEDS 2026 claim in econ-anchoring
must be checked against the actual paper scope. Maintenance rule
written in: first-hand backtest measurements supersede grades;
D-grade claims get upgraded or struck at the ledger, not silently.

Index now points reviewers at the ledger first. Push to origin still
held pending the user's public-remote ruling.

## 2026-08-24 — Specs grouped into theories/ subfolder; build-plans folder added

User request: group the theory specs into their own folder. All 22 spec
files, the backlog index, and the evidence/ folder moved as a unit
(git mv, history preserved) from docs/superpowers/specs/ to
docs/superpowers/specs/theories/. All cross-links are relative within
the set, so nothing broke; registry ids 2-24 repointed to the new
paths. One correction caught by the user mid-move: the theory-*.md glob
swept in 2026-08-24-theory-layer-oop-design.md, which is another
session's spec about the theory LAYER's design, not a backlog theory --
moved back untouched. An untracked multi-leg-positions spec (also
another session's) was never touched.

Also added docs/superpowers/plans/theories/ with a README defining the
build side of the pipeline (spec -> propose-theory -> plan file here ->
code in theories/<slug>/) and a build tracker table, currently empty.

## 2026-08-25 — Theory-layer OOP migration complete; migration shim deleted

The theory-layer OOP migration (docs/superpowers/specs/2026-08-24-theory-
layer-oop-design.md) landed end to end: frozen domain value types
(Market, PolymarketMarket, Leg, Candidate, Edge, Verdict, ScoredCandidate,
ScreenResult, ScanResult) in tools/domain.py, the Theory contract and
TheoryContext in tools/theory.py, and the running-theory registry in
tools/registry.py. Both theories -- insider_judgment and mention_family --
were adapted to the contract and then ported to read domain objects
natively, with no version bump on either (insider_judgment stays v3,
mention_family v1) and no change to any decision logic. Every
characterization golden held unchanged throughout.

This session did the final step: deleted the temporary migration shim
(_MappingShim, SHIM_CALLERS, track_shim_callers) from tools/domain.py now
that nothing in production code depends on dict-style access to a domain
object -- Market, PolymarketMarket, and Candidate are no longer mappings,
enforced by tests/test_conventions.py::test_the_migration_shim_is_gone.
The only tests deleted anywhere in this migration were the shim's own
(five test_shim_* cases plus the allowlist-exercise test), deleted
together with the feature they tested; every other test conversion was a
mechanical dict-access -> attribute-access rewrite with the asserted
value unchanged. A mechanical grep sweep of tools/ and theories/ for
remaining subscript/`.get()` use on domain-shaped values turned up
nothing left to convert -- every remaining hit operates on a genuine
plain dict (raw wire payloads, DB rows, candlesticks, ledger leg kwargs,
JSON blind-judgment payloads), which is exactly the boundary the shim was
never meant to cover. Full suite: 621 passed, 4 deselected, zero
failures.

The Verdict type's no-numeric-field rule (CLAUDE.md's "never state a
probability you introspected") is now enforced structurally at the judge
boundary, not just by convention -- an out-of-process judge has no field
to hand a probability back through. This also discharges the multi-leg
spec's success criterion 4 (deferred pending this migration):
Candidate's single-leg conveniences (.ticker, .entry_price, .fav_side,
.title, .event_key) raise ValueError on a basket rather than silently
returning leg 0, per tests/test_domain.py::
test_basket_conveniences_raise_rather_than_guess. Criterion 2 and section
10.1 of that spec -- how a variable-payout basket should be scored --
remain open, unchanged, and are the user's call.

## 2026-08-25 — mention_family edge audited on user suspicion: mechanics clean, inference weak, live slate mismatched

**Did:** The user was suspicious of the mention_family edge, so this
session audited it end to end rather than defending it. Checked the
replay mechanics first: no lookahead found — `replay_market` enters at
the daily candle's closing ask with `screen()` evaluated at that same
timestamp, `no_ask = 1 - yes_bid_close` is exact on Kalshi's
complementary book, fees are in `edge_pts_net`, and the +5.48pts
headline re-derives from the rows exactly. Event clustering is a
non-issue (113 distinct events in 116 rows, max 2 markets per event).
Sampled candle traces around nine 85plus entries show stable pre-event
favorites with real entry-day volume (e.g. 0.95 → 0.95 → settle 1.00),
not post-news stale quotes — so the "entered after the mention already
happened" hypothesis is rejected for the sampled rows.

**Learned:** The problem is inferential, not mechanical, and it is
three-layered. (1) *Significance:* against the null "the ask was
already fair," exact heterogeneous-probability binomial tails give
lt75 p=0.40, 75_85 p=0.17, 85plus p=0.026 (41/41 at mean price 0.916
is only ~2σ), pooled family p=0.0395 gross and **p=0.070 net of
fees** — and this family was *selected* as the best-looking slice of
a 200-row backtest containing 115 series families, with the price-bin
boundaries then fit on the same 116 rows. Nothing here survives a
selection-aware read. (2) *Heterogeneity:* the family's positive edge
decomposes into World Cup sponsor mentions (+8.3pts net, n=28 — the
tournament is over), earnings-call mentions (+6.1, n=38 — episodic),
and a +12.7 long tail of n=1 series (n=24), against **-5.2pts net
(n=26)** for the persistent political slice (KXTRUMPMENTION/SAY/ACT).
The bins average these; no bin is a homogeneous population. (3) *Live
mismatch:* the current preview slate (…preview30-v2, 20 rows, all
`untouched`, so no money at risk) is 100% political-speech series —
TRUMPMENTION, WARSHMENTION, FEDMENTION, SECPRESSMENTION — i.e. the
bootstrapped rates are currently being applied to exactly the
sub-population that measured negative. Recorded all of this in
THEORY.md's Learnings (2026-08-25 entry).

**Next:** Treat the bucket table as a hypothesis, not a measured edge,
for anything political-speech shaped. The 40 unsettled preview rows
settle Aug 28–Sep 15 and are a free out-of-sample test — score them
before any live recommendation from this theory. If the theory is to
earn its bins back, the right move is a longer-window tier-A rerun
with the sub-family split (sponsor/broadcast vs earnings vs political
speech) pre-registered, and per-sub-family buckets if n allows;
that is a decision-procedure change and would bump the version.

## 2026-08-25 — Kalshi archives settled markets after ~60 days; backward extension impossible; full-coverage rerun launched instead

**Did:** Tried to extend mention_family's tier-A evidence backward
(closes 2025-08-25 .. 2026-05-26, abutting the original window) with a
new family-scoped driver, `theories/insider_bias/mention_family/
backtest.py`. The walk returned zero survivors, and systematic probing
(windows bisected, every status value, unstatused listings, nested-event
markets, reconstructed tickers against known old events) established why:
**Kalshi's public API archives settled markets out of existence roughly
60 days after close.** The markets listing serves only never-traded husks
(`status='closed'`, empty result, zeroed volume) beyond the floor; events
keep shells back to 2025 with no markets attached; candlesticks for
archived tickers return empty. Corrected `list_settled`'s
whole-lifetime docstring claim in place. Two corollaries: the original
"90-day" backtest was effectively a ~60-day one (earliest close it could
see was 2026-06-22ish), and the floor advances daily — historical
evidence only survives if captured before it ages out, which is the same
lesson as the record-while-collecting convention added to CLAUDE.md and
tools/README.md today (user-prompted, after a previous session lost a
long collection by holding it all in memory).

**Doing (pending as of this entry):** Since backward extension is dead,
the strongest available move is **full coverage of the reachable
window**: the original run replayed a 600-of-18,430 systematic sample;
the new run (`run_id=backtest-2026-08-25-mention-fullcov`, tier A)
replays *every* mention-family survivor — 11,084 across 379 series vs
the 116 rows the price bins were fit on. This cannot test persistence
across time (same window, same World Cup-summer regime); it tests
whether the 116-row sample was lucky, on ~95x the markets. Persistence
across time falls to the live preview rows settling Aug 28–Sep 15 and
every live run after. The replay is running in the background,
recording per series with a resumable checkpoint. When it lands:
record the backtest_runs row, score fresh-rows-only (exclude the
original 116 tickers) with the sub-family split from the 2026-08-25
audit entry, update THEORY.md, and report against the audit's nulls.

## 2026-08-25 — Full-coverage rerun: mention_family has no edge; under_review, retirement proposed

**Did:** The full-coverage replay finished: 379 series, 11,084 survivors,
3,441 screen hits, all settled and recorded under
`run_id=backtest-2026-08-25-mention-fullcov` (tier A, run row recorded).
2,103 survivors returned no candles — markets already past Kalshi's
archival floor — so effective coverage is closes ~2026-06-22..2026-08-24,
the same window as the original sampled run by construction.

**Learned:** The edge does not exist. Win rate 0.797 vs mean price 0.802:
`calibration_edge=-0.49` gross, `-1.53` net, `roi_all=-1.9%` (repo scorer
and independent script agree). Fresh rows only (excluding the 116 the
bins were fit on): -1.78 net. The 85plus bin lands at n=1,190, win rate
0.913 vs price 0.909 — perfectly calibrated; its bootstrap 41/41 was
sampling luck, exactly as the morning audit suspected. lt75 and 75_85
are negative outright. Every sub-family is ~zero or negative on fresh
rows — including worldcup (-0.94) and earnings (-3.82), the two that
carried the bootstrap — so the audit's "the positive slices are
seasonal" concern resolves even more sharply: they were not seasonal
edges, they were noise. Per-series means at small n scatter +22..-45pts,
mean-zero. The market prices this family fairly; buying favorites loses
the fee. The first live out-of-sample settlement agreed
(KXTRUMPMENTION-26AUG24B-IRAN, no @0.89 → yes, lost; settled in the
ledger). Status set to `under_review`, retirement proposal filed with
the full diagnosis (n, gross-vs-net, inversion, slices, version mixing,
regime change all ruled out). The user rules on retirement.

Method note for future theories: a ~3% systematic sample (116 rows)
produced +5.48pts net with an all-positive bin table on the same window
where full coverage measures -1.53. Small backtest samples of a
screen's own selection are not weak evidence of the sample's claim —
they can be *confidently wrong*. Prefer full coverage of a scoped
population wherever the fetch allows it, and treat any sampled result
as unconfirmed until it survives the full walk. Also: one live test
run (pytest with network marks) caught Polymarket's `filterAmount`
returning a $9,200 trade under a $10,000 floor —
`test_live_whale_trades_are_actually_large`, the canary built for
exactly this drift; logged here for a future session, deliberately not
chased today.

**Next:** The user rules on retirement (proposal on file). The 39
remaining preview rows still settle Aug 28–Sep 15 and will be scored,
but no recommendations come from this theory. If anything survives
here, it is a *new*, pre-registered, per-series question (is any single
recurring mention series persistently mispriced?) — which requires
snapshotting settled markets before Kalshi's ~60-day archival eats
them, per the record-while-collecting convention.

## 2026-08-25 — Pattern-mining the fullcov rows: timing and price-level dead, but a side asymmetry survives every stress and feeds no-side-premium

**Did:** User pushed back on stopping at the dead aggregate — asked
specifically whether the 0-4d timing marker or 80+ pricing still carries
edge, and to hunt patterns at high effort. Ran a structured slicing pass
over the 3,441 settled fullcov rows (366 events, 135 series): timing
bins, fine price bins, side x price, dtc x price, volume quartiles,
spread bands, sub-family interactions, per-series z-scores — every cell
with exact heterogeneous-null binomial tails plus an event-clustered
t so correlated sibling strikes can't fake significance. Then stressed
the one survivor across sub-families, window halves, timing slices, and
with the ended World Cup series excluded, and tested its mirror trade.

**Learned:** (1) The 0-4d marker is dead at scale: -0.95 net (n=2,418);
the bootstrap's entire timing table reverses (10-14d: +10.2 claimed,
-3.06 measured). Only the literal last day (0-1d) is even breakeven
(+0.29 net). (2) Price 0.80+ is dead as such (-0.51 net, n=1,767); the
old 85plus bin lands perfectly calibrated (+0.11 net, n=1,231) — its
meaning was always just "ask in $0.85-0.97", and price level alone
carries nothing. (3) No series-level skill: z-variance 1.19 vs 1.0
binomial across the 96 series with n>=10; the best series (KXMTPMENTION
z=+2.27) is within the expected max for 96 draws of noise. (4) The one
real survivor: **side x price.** YES favorites are overpriced in every
band (-1.7 to -4.2 net; YES 0.80-0.90 is significantly *worse* than
fair). NO favorites at ask>=0.90: +2.25pts net after fees (n=450,
213 events, p_fair=0.0084), positive in all four sub-families, both
window halves, both dtc slices, +1.86 excluding World Cup; NO 0.85+
pooled +1.88 (n=685, p=0.011). The synthetic mirror — fading YES
favorites by buying NO longshots at 1-yes_bid — is NEGATIVE at every
band because the spread eats the mispricing: the optimism tax is only
harvestable standing on the NO-favorite side near certainty. Honest
status: found in a ~50-cell post-hoc scan, event-clustered t +1.4 —
a hypothesis to pre-register, not a measured edge. Recorded on idea 14
`no-side-premium` (status → investigating), whose Becker-based spec
predicted exactly this asymmetry; mention_family's own retirement
proposal stands, since its both-sides price-bin procedure is what was
measured dead. Also added the repo standard the user asked for
(CLAUDE.md): a dead headline number is not a dead dataset — mine the
slices with honest statistics before moving on, and pre-register
whatever the mining finds.

**Next:** If the user wants it pursued: build no-side-premium as a
pre-registered theory (NO favorites at ask>=0.90 on mention markets as
the first population; 0.85-0.90 as a secondary bucket), bootstrap rates
from the fullcov run, and require live settlements to confirm before
any size. The forward test is nearly free — the screen already sees
these markets daily.

## 2026-08-25 — insider_judgment tier-A full coverage: the gate separates, but what it keeps is only breakeven; judged sample launched

**Did:** The non-mention full-coverage walk finished: 5,583 series,
7,948 survivors, 3,195 screen hits (3,181 with usable settlements, 831
events, 325 series), all recorded under
`run_id=backtest-2026-08-25-insider-fullcov` (tier A, run row recorded)
with deterministic gate tags on every row and every raw payload/candle
banked in the history cache as fetched. Then scored it, updated idea 14
with the replication result, and launched the tier-B judged sample
(batches 1-2 of 8 dispatched to Sonnet subagents; save-before-spend
artifacts committed first in cfed04a).

**Learned:** (1) *The gate discriminates, at scale and in the right
direction*: gate-plausible +0.71pts net (n=1,561) vs gated-out -2.18
(n=1,620) — a ~2.9pt gap. But (2) *what the gate keeps is roughly
fair-priced, not profitable*: the +0.71 is nominally p=0.04 by rows but
event-clustered t is -0.25 (1,561 rows on only 456 events), and the
84-row sample's +4.40 headline does not survive — same lesson as
mention's +5.48: small samples of this screen are confidently wrong.
So screen+gate alone earns nothing; the theory's remaining case rests
entirely on judgment adding selection within the plausible pool, which
is precisely what the judged sample measures. (3) The no-side-premium
asymmetry partially echoes on this disjoint population (YES 0.80-0.90
significantly overpriced; NO beats YES below \$0.90) but the mention
run's NO>=0.90 cell does not strongly replicate (+1.04, p=0.09) and the
band structure moves — durable claim downgraded to side-level, recorded
on idea 14. (4) Curiosity, not a claim: the gated "future price:
compute/collectible" family scored +4.56 (n=152, p=0.038, but t_ev
+0.12) — GPU/collectible price ladders; post-hoc, cluster-weak, noted
only so a future session knows it was seen.

**Next:** Ingest and commit each judged batch as it lands; score bucket
calibration + interpretation value vs the screen+gate baseline; then the
final write-up. Backfill of pre-cache raw data is running in parallel.

## 2026-08-26 — Tier-B judged sample complete: judgment orders outcomes; strong-NO and the rules-divergence flag are the standouts

**Did:** All 8 batches of the judged-s200 replay ran to completion under
the save-as-you-spend protocol — every batch's payload committed before
dispatch, every verdicts file written by the judging subagent itself,
ingested to the ledger and committed before the next dispatch (commits
df97b9b..1a4c490). 200 events / 704 market rows judged by
claude-sonnet-5 (web search off, blind payloads, per-batch as-of dates,
committed mechanism sheet in lieu of search). Run row recorded tier B.
Scored against the same-sample screen+gate baseline.

**Learned:** Bucket totals 24 strong / 66 moderate / 110 weak. The
buckets order outcomes exactly as the thesis predicts: strong +5.09pts
net (n=111 rows, p_fair=0.044), moderate +0.85, weak -0.79, over a
baseline of +0.67 — the first time any judgment layer in this repo has
produced its predicted ordering on settled data. Event-level means are
monotone too (+2.88 / -0.56 / -2.26). The concentrated cells: strong-NO
+8.59 net (n=83, p=0.006) against strong-YES -5.30 — the optimism-tax
asymmetry's third independent appearance today — and events flagged
rules_diverge_from_title scored +1.97 with t_ev=+2.90 (26 events), the
strongest event-clustered statistic of the session: reading rules
against titles measurably pays. Limits stated plainly: 24 strong events,
bucket-ordering clustered support weak (t_ev +0.66), sharp cells are
post-hoc slices. The judges also produced qualitative value the code
path cannot: e.g. catching that the Emmy winner markets close on
NOMINATION day (before final voting concludes), gutting the
"tabulators already know" logic for that family.

**Next:** Pre-registered live plan for insider_judgment (status stays
testing): track strong — and strong-NO as its own view — plus the
divergence flag on every live row; promotion requires the ordering to
repeat on live settlements. The judged-run bucket rates are usable as
bootstraps with the in-sample caveat attached. Backfill continues in
background (~9.6k candle windows cached so far); when done, the entire
reachable window's raw data is durable and every variant re-test is
offline.

## 2026-08-26 — Strong-YES autopsy: the bleed was sealed-tabulation award markets; excluding them repairs YES to breakeven, NO-rule strengthens

User challenged the methodology on strong-YES's -7c. Autopsy: the losses
cluster in Emmy-nomination/BET/award strikes — events where the judge is
arguably RIGHT that a small body already knows (tabulators), but the
knowledge is SEALED and never leaks into price before close, so buying
the public's favorite at the ask pays the crowd's guess plus spread. The
thesis needs leakable knowledge, not just knowledge — prompt-refinement
candidate for a future version ("does the group's knowledge plausibly
escape before close?"), which would be a version bump. Excluding the
award family (KXEMMY*/KXESPYS/KXBET/KXFIELDS pattern; 135 rows / 40
events, own net +1.6) symmetrically from all cells: strong-YES -7.0 →
+0.6 (n=24, breakeven, not negative); strong-NO +6.8 → +11.0 (luck
0.2%, but only 16 events); moderate-YES worsens to -6.9 (the YES
problem is not award-specific); bet rule (str+mod NO) +5.1 → +5.9,
luck-odds ~0 either way. Post-hoc caveat recorded: exclusion chosen
after seeing the losers; legitimate path is pre-registering a
sealed-small-body-decision NO-rule for the gate (version bump) and
letting live rows decide. Contamination note: strong-YES losing at all
is itself evidence the blinding held — a leaky judge wins its confident
bucket, never loses it.

## 2026-08-26 — Uniform "enter 3-2 days before close" repriced from the candle cache: waiting KILLS the moderate edge, only strong-NO survives late entry

User-directed focus: what if we only bet 3-2 days before close?
`reprice_entry_window.py` replays a UNIFORM late-entry strategy from the
durable candle cache (fixed snapshot nearest close-2.5d, unmodified
screen conditions, favorite at that snapshot's ask) over all 1,081
judged rows — distinguishing "chose to enter late" from the earlier,
confounded "first qualified late" filter. Result: only 444 rows are
even biddable at 3-2d (414 fail the price band there, 100 lack a candle
in the window, 69 spread, 37 volume, 17 awaiting cache backfill).
The bet rule (str+mod NO) at uniform late entry: +1.81pts, p=0.18 —
versus +5.13 at first-qualifying entry. The culprit is convergence:
moderate-NO's mean ask at 3-2d is 0.895 vs 0.861 at first
qualification, and its edge collapses to +0.29. **The moderate edge is
substantially an early-entry edge — catch the favorite when it first
crosses the screen, not after the market has drifted toward
certainty.** The exception: strong-NO holds +8.29 late (n=32/19ev,
p=0.10), consistent with the first-qualifying-entry late slice (+12.2).
The earlier "late entries did well" table was selection, not a timing
rule — the confound the mention_family docstring flagged as untested is
now tested, and delaying hurts everywhere except strong-NO. (Ignore the
repriced weak-YES +5.9 — no mechanism, third noise-shaped YES cell.)
Practical rule that survives: enter moderate-NO at first qualification;
strong-NO may be entered any time including late.

## 2026-08-26 — FULL POPULATION JUDGED: the pre-registered NO-side rule REPLICATED out of sample

**Did:** Completed judgment coverage of the entire gate-plausible
population from the tier-A walk: s200 (200 events) + s200b (200) + s57
(57) = 457 events / 1,561 market rows, every batch payload committed
before dispatch, every verdicts file ingested and committed as it
landed (through bbadf13), one batch recovered intact from a usage-cutoff
orphan. Also repriced the uniform 3-2-days-before-close entry over the
full set from the candle cache, and the backfill finished its walk
(~17k candle windows / ~18k payloads durable).

**Learned — the headline:** The bet rule pre-registered from s200
(strong-or-moderate judgment, NO side, first-qualifying entry)
**replicated on the 257 events judged after pre-registration: +4.92pts
net, p_fair=0.0008 (312 rows / 85 events), vs +5.34, p=0.0018 on the
original round.** Pooled: +5.10pts, p<0.0001, n=551 rows / 162 events,
win rate 0.922 at mean ask 0.863; excluding the award family: +5.45.
Sub-cells: moderate-NO replicated STRONGER (+3.61 -> +5.13, p=0.003);
strong-NO replicated in direction but weaker (+8.59 -> +4.29, p=0.096
-- partial regression toward the mean, as expected for the flashiest
cell). The rules-divergence flag repeated its direction (+1.97 ->
+2.17) without reaching significance. Full-population bucket x side:
NO ladder monotone and significant (strong +6.50 p=0.0017 / moderate
+4.52 p=0.0006 / weak -1.96), YES side flat-to-negative everywhere
(strong -4.98, moderate -3.19, weak +0.36) -- the optimism-tax
asymmetry held through every expansion. Timing at full coverage:
uniform 3-2d late entry still underperforms first-qualifying entry
(+2.32 p=0.06 vs +5.10), confirming the moderate edge is an
early-entry edge; strong-NO alone tolerates late entry.

**Next:** This is the strongest evidence any theory in this repo has
produced: tier B, pre-registered, out-of-sample replicated, mechanism-
backed (optimism tax + insider-NO), n=162 events. Still backtest, still
one summer, still sibling-correlated within events — the promotion bar
remains live settlements. Proposed live procedure for the user to
ratify (a v4 version bump): judge as today; bet only strong/moderate
NO favorites at first qualification; record dtc and the divergence
flag on every row; sealed-tabulation award families as a new gate
NO-rule candidate. Bucket rates for pricing: use the pooled judged-run
rates with the in-sample caveat until live rows accumulate.
