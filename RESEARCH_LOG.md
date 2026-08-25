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
