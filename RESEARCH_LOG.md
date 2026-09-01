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

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-23 — `insider_bias` is `active` but already past its review trigger (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

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

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-23 — First live run: the screen has almost no thesis alignment (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

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

## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false start that took 47 minutes to fail

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-24 — First tier A backtest of the stage-1 screen, after a false start that took 47 minutes to fail (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother bet, and a new mechanical path for the MENTION-family edge

Moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md` under the heading `## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother bet, and a new mechanical path for the MENTION-family edge (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-24 — mention_family becomes a real, separate theory; insider_bias renamed insider_judgment and folded into a shared parent folder

On 2026-08-24, mention_family split out of insider_bias to become its
own theory at the user's direction: `theories/insider_bias/` became a
shared parent folder, the LLM-judged theory was renamed
`insider_judgment` (since `insider_bias` was no longer its name once it
stopped being a leaf folder), `mention_family` became a sibling
subfolder, and the shared favorite screen moved to
`theories/insider_bias/screen.py` rather than generic `tools/` — the
architecture CLAUDE.md now documents. `theory_id='insider_bias'` was
renamed to `'insider_judgment'` across every referencing table (128
opportunities, 4 judgment_runs, 1 backtest_runs row) with its version
number (3) carried over unchanged, since it was the same decision
procedure under a corrected name; `mention_family` kept its own
`theory_id` throughout. Splitting the evidence apart changed what
insider_judgment's own remaining tier-A backtest said: the original
+1.38pts headline (n=200) was mostly mention_family's positive edge
canceling insider_judgment's own negative slice, and with
mention_family's 116 rows properly attributed elsewhere,
insider_judgment's own remaining 84 non-mention rows scored
`calibration_edge_net=-4.28pts` — a blend of the family `gate.py`
already excludes (-11.12pts, n=47) and the gate-plausible slice that
reaches judgment in the live pipeline (+4.40pts, n=37).

Narrative moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md`
under `## 2026-08-24 — mention_family becomes a real, separate theory;
insider_bias renamed insider_judgment and folded into a shared parent folder
(migrated from RESEARCH_LOG.md)` (spec §6.8).

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

Moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md` under the heading `## 2026-08-25 — mention_family edge audited on user suspicion: mechanics clean, inference weak, live slate mismatched (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-25 — Kalshi archives settled markets after ~60 days; backward extension impossible; full-coverage rerun launched instead

Attempting to extend mention_family's tier-A evidence backward (closes
2025-08-25..2026-05-26) with a new family-scoped driver returned zero
survivors; systematic probing (bisected windows, every status value,
unstatused listings, nested-event markets, reconstructed tickers against
known old events) established that Kalshi's public API archives settled
markets out of existence roughly 60 days after close — the markets
listing serves only never-traded husks beyond the floor, events keep
shells with no markets attached, and candlesticks for archived tickers
return empty. This is the ~60-day archive constraint CLAUDE.md's data
conventions now cite (`list_settled`'s docstring was corrected in
place); a corollary is that the theory's original "90-day" backtest was
effectively a ~60-day one, and the floor advances daily, so historical
evidence only survives if captured before it ages out. Since backward
extension was dead, this entry launched full coverage of the reachable
window instead (`run_id=backtest-2026-08-25-mention-fullcov`, tier A):
every mention-family survivor, 11,084 rows across 379 series, replacing
the original 600-of-18,430 systematic sample.

Narrative moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md`
under `## 2026-08-25 — Kalshi archives settled markets after ~60 days;
backward extension impossible; full-coverage rerun launched instead
(migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-25 — Full-coverage rerun: mention_family has no edge; under_review, retirement proposed

Moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md` under the heading `## 2026-08-25 — Full-coverage rerun: mention_family has no edge; under_review, retirement proposed (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-25 — Pattern-mining the fullcov rows: timing and price-level dead, but a side asymmetry survives every stress and feeds no-side-premium

A structured slicing pass over the 3,441 settled fullcov rows (366
events, 135 series) found the 0-4d timing marker and 80+ price level
both dead at scale (timing -0.95 net n=2,418; price 0.80+ -0.51 net
n=1,767), no series-level skill (z-variance 1.19 vs 1.0 binomial across
96 series), and one real survivor: side x price. YES favorites were
overpriced in every band (-1.7 to -4.2 net), while NO favorites at
ask>=0.90 were underpriced at +2.25pts net after fees (n=450, 213
events, p_fair=0.0084), positive across all four sub-families, both
window halves, and both dtc slices — the synthetic mirror trade (fading
YES favorites via NO longshots) was negative at every band because the
spread eats the mispricing, so the asymmetry is only harvestable on the
NO-favorite side near certainty. Found in a ~50-cell post-hoc scan
(event-clustered t +1.4) — a hypothesis to pre-register, not a measured
edge — this became `no-side-premium`'s (idea 14) founding evidence and
moved it to status `investigating`; mention_family's own retirement
proposal stood unchanged, since its both-sides price-bin procedure is
what was measured dead.

Narrative moved 2026-08-29 to `theories/insider_bias/mention_family/NOTES.md`
under `## 2026-08-25 — Pattern-mining the fullcov rows: timing and price-level
dead, but a side asymmetry survives every stress and feeds no-side-premium
(migrated from RESEARCH_LOG.md)` (spec §6.8).

---

## 2026-08-25 — Theory locality: backtests and notes live in the theory, and reads stay open

Spec: `docs/superpowers/specs/2026-08-25-theory-locality-design.md`.
Plan: `docs/superpowers/plans/2026-08-25-theory-locality.md`.

**Did:** Wrote down what lives in a theory and what gets elevated, in the
places a future session actually reads: `CLAUDE.md` gained a "What lives in
a theory, and what gets elevated" section, `tools/README.md` two
conventions, `theories/_TEMPLATE/` a `NOTES.md` and a rewritten Learnings
section, and three skills (`backtest-theory`, `go`, `score-theories`) the
corrections that stop them teaching the old behavior. `insider_judgment`
and `mention_family` each got a seeded `NOTES.md`; no existing note was
migrated. Then made the one rule that is mechanically checkable actually
mechanical: the shared replay moved from `insider_judgment/backtest.py` to
`theories/insider_bias/replay.py` and the `is_mention_family` classifier
from `mention_family/mention_bucket.py` to
`theories/insider_bias/families.py`, both into the family's shared parent,
with every importer repointed, no logic changed and no version bump on
either theory — guarded now by
`tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`.

**Learned:** Two of the three headline decisions were already argued from
evidence in this repo rather than from taste. The case against a shared
backtest engine is that replay itself (`insider_judgment/backtest.py`
then, `theories/insider_bias/replay.py` now): most of its
design budget went to quirks — a combinatorial series settling 400,000
markets a day, per-day candle volume needing a warm-up sum, a fetch-scoping
category filter that must not leak into the screen under test — that
belong to replaying *this* screen over Kalshi's settled-market API, not to
backtesting in general, so a generic engine would either anticipate all of
them or paper over them silently. A review pass also caught that two skills
still instructed the behavior the spec replaces, which would have broken
the convention on the very next `go` session in good faith; documents that
steer future sessions are load-bearing, and a spec that changes conventions
has to grep for every place the old one is taught.

The sharpest lesson came from testing the rule instead of asserting it. A
probe of the proposed guard test found the repo crossing the theory-folder
boundary in *both* directions, and both crossings were deliberate and
well-argued: `mention_family/backtest.py` reused `insider_judgment`'s
replay byte-for-byte because two windows are only comparable if the
population rules and the replay are identical, and
`insider_judgment/backtest_fullcov.py` reused `is_mention_family` to
define its own complement population ("every NON-mention survivor"). So
the rule was never really "stop sharing" — it is "share through the
parent, not sideways", and the code was one refactor short of it, not
wrong in spirit. The classifier is the interesting case: it *originally*
lived in `screen.py` and was moved into `mention_family` by the
2026-08-24 split, guarded by a test asserting `screen` does not carry it.
That made the obvious destination the wrong one, so it went to a new
`families.py` in the parent instead — shared ancestry without becoming a
stage of the screen again. A rule nobody has run against real code is a
hypothesis; running it found the design.

**Next:** The convention is forward-only, so the first real test is the next
session that researches inside one theory — its findings belong in that
theory's `NOTES.md`, with a pointer from here, not a copy. Nothing about
theory standing, ranking, or the live board changed.


## 2026-08-25 — insider_judgment tier-A full coverage: the gate separates, but what it keeps is only breakeven; judged sample launched

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-25 — insider_judgment tier-A full coverage: the gate separates, but what it keeps is only breakeven; judged sample launched (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — Tier-B judged sample complete: judgment orders outcomes; strong-NO and the rules-divergence flag are the standouts

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-26 — Tier-B judged sample complete: judgment orders outcomes; strong-NO and the rules-divergence flag are the standouts (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — Strong-YES autopsy: the bleed was sealed-tabulation award markets; excluding them repairs YES to breakeven, NO-rule strengthens

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-26 — Strong-YES autopsy: the bleed was sealed-tabulation award markets; excluding them repairs YES to breakeven, NO-rule strengthens (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — Uniform "enter 3-2 days before close" repriced from the candle cache: waiting KILLS the moderate edge, only strong-NO survives late entry

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-26 — Uniform "enter 3-2 days before close" repriced from the candle cache: waiting KILLS the moderate edge, only strong-NO survives late entry (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — FULL POPULATION JUDGED: the pre-registered NO-side rule REPLICATED out of sample

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-26 — FULL POPULATION JUDGED: the pre-registered NO-side rule REPLICATED out of sample (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — Gate validation: 100 gated-out events judged, 99 weak / 1 moderate / 0 strong; the session's autonomous arc is complete

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-26 — Gate validation: 100 gated-out events judged, 99 weak / 1 moderate / 0 strong; the session's autonomous arc is complete (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 — Formal multiplicity pass (user-prompted): Holm + event clustering

Holm-Bonferroni correction was applied over the pre-registered family
(m=4, replication data only): the bet rule (p=0.0008 vs 0.0125) and
moderate-NO (p=0.0030 vs 0.0167) survived; strong-NO (p=0.0961) and the
divergence flag did not. The sterner event-clustered one-sided t-test
(one observation per event, removing sibling-strike inflation) held the
bet rule up independently: +5.21/event, t=2.26, p≈0.012 on 85
replication events, and +3.87, t=2.29, p≈0.011 pooled over 162. Report
language was downgraded accordingly, from the uncorrected p<0.0001 to
~p=0.01 clustered — this established the Holm-plus-event-clustering
precedent that CLAUDE.md's mining discipline now cites for any
exploratory-scan claim.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-26 —
Formal multiplicity pass (user-prompted): Holm + event clustering
(migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-26 — Contamination audit of the judged runs (user-prompted): no hints found; one timing wrinkle bounded

A four-channel contamination audit of the judged runs found no leakage:
zero WebSearch/WebFetch calls across the 23 judge subagent transcripts,
zero price/outcome/status fields in the 557 events / 2,044 markets
carried by the four runs (the 11 "settle" substring hits were ordinary
Kalshi rules boilerplate), and no outcome-tracking behavior in
verdicts — strong-YES lost money, and three judge instances
independently rediscovered the Emmy nomination-day trap on mechanism
grounds, not outcome grounds. One real wrinkle was found and bounded:
batch-level as_of pinning (max of the batch's entry days) left
618/2,044 markets with a close_time before the pinned "today"; those
rows scored WORSE, not better (-0.74 vs +1.16 net), the opposite of
what leakage would produce, and the bet rule held on the clean
still-open-at-as_of subset alone (+4.65 net, win 0.910, n=409). The fix
— pin as_of per event, or at the min of the batch rather than the max —
was noted for the v4 procedure. This established the contamination-probe
method used on subsequent judged runs.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-26 —
Contamination audit of the judged runs (user-prompted): no hints found;
one timing wrinkle bounded (migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-26 — First live scan under the campaign rule: 8 endorsed NO bets; board-cache identity bug found and fixed on the way

The first live scan under the campaign rule ran the full pipeline
(fresh 110,590-market board → screen 844 → gate 100 events → 76
NO-favorite events → two live Sonnet judgment batches, payloads blind
to price) and recorded all 125 NO-favorite rows under
run_id=live-2026-08-26-noscan with buckets, campaign-measured edges,
and provenance, endorsing 8 NO bets (4 strong, 4 moderate) as the first
live rows of the pre-registered forward test. En route, a real defect
was found and fixed (commit 01e6792): a board rebuilt from cache lost
`series_ticker`, because event-envelope enrichment is not part of the
market's raw payload, which silently disabled the gate on cached
boards — 349/349 events passed the gate on a cached board vs 100/349 on
a freshly fetched one; a regression test was added to catch a
recurrence.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-26 —
First live scan under the campaign rule: 8 endorsed NO bets; board-cache
identity bug found and fixed on the way (migrated from RESEARCH_LOG.md)`
(spec §6.8).

## 2026-08-26 — User bets placed and tracked; stage-3 research made a mandatory, attributed step

User placed $25 NO on KXGTATRAILER-26SEP (id 9186) and $25 NO on
KXGROK-GROK47-26SEP04 (id 9184), both tracked via mark-taken. Stage-3
research (user-prompted) validated the Grok bet independently (4.7
publicly slipped to early September vs the Sep 3 deadline) and found
real resolution risk on the trailer bet (the Aug 27 "Extended Look"
airs inside the window; media call it a trailer; Rockstar does not) —
flag recorded on the row; hold-don't-add advice given at $25 size.
Process change ratified by the user and written into RESULTS.md's v4
section: the operating model's independent research pass is a
mandatory stage-3 step; endorsements/rejections in the ledger ARE the
model's tracked suggestions (8 endorsed / 9 rejected this scan, 11
endorsed live rows all-time), attributed via final_review provenance
(claude-fable-5 recorded for this scan) so interpretation_value can
score the model's suggestion quality against the raw screen over time.

## 2026-08-26 — structural_arb implemented from backlog; first live riskless find recorded

Moved 2026-08-29 to `theories/structural_arb/NOTES.md` under the heading `## 2026-08-26 — structural_arb implemented from backlog; first live riskless find recorded (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-26 (cont.) — no_side_premium forward test implemented and running; polymarket whale filter fixed

This entry built and launched `no_side_premium` v1 (idea 14) as the
pre-registered forward test of the optimism-tax finding: cell A
(mention-family NO favorites, ask>=0.85, prior +2.0 net) screened, and
cell B (non-mention YES favorites, 0.80-0.90) recorded REJECTED as a
free avoid-list control, both drawn from `insider_bias.screen`'s
population and pinned by test; the first run recorded 60 rows (8 A + 59
B) at fresh asks under `run_id=live-2026-08-26-nsp`, all
`edge_basis='prior'` until settlements measure the cells. En route it
fixed a repo-tooling defect in `tools/polymarket/trades.py`:
Polymarket's `filterAmount` without `filterType=CASH` filters on share
count, not dollars, caught by a live-contract test — the fix is the
durable fact, since any future Polymarket dollar-threshold query depends
on it.

Narrative moved 2026-08-29 to `theories/no_side_premium/NOTES.md` under
`## 2026-08-26 (cont.) — no_side_premium forward test implemented and
running; polymarket whale filter fixed (migrated from RESEARCH_LOG.md)`
(spec §6.8).

## 2026-08-27 — structural_arb v2: depth gate mechanical; queue re-quoted, mostly decayed

Moved 2026-08-29 to `theories/structural_arb/NOTES.md` under the heading `## 2026-08-27 — structural_arb v2: depth gate mechanical; queue re-quoted, mostly decayed (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-27 (later) — ledger defect: position identity, not a theory finding

Not a research session. User asked whether duplicate suggestions are handled
correctly for performance measurement. They are not, and the diagnosis is
in **docs/DEDUP_PLAN.md** (full handoff: findings, design, next steps).

**Learned:** `opportunities` carries `run_id` in its UNIQUE key, so it
enforces one row per market per *run* where `ledger.py`'s own docstring says
one position per market per *theory version*. Every run gets a fresh dated
run_id, so re-recordings insert instead of collide. 1,686 duplicate positions
repo-wide. Pooled `compute_score` counts each as an independent observation:
insider_judgment v3 backtest reads n=4,759 / -0.59 net where the fullcov run
alone is n=3,195 / -1.15 — the judged sub-runs were drawn *from* fullcov, so
pooling re-counts them and pulls the headline up. A duplicate improved
measured performance.

> **Corrected 2026-08-28.** This figure pooled duplicate rows: `run_id` was
> in the `opportunities` UNIQUE key, so the judged sub-runs re-counted
> markets the full-coverage run had already recorded. The honest figure for
> v3 backtest is the full-coverage run alone: `n=3,195, calibration_edge_net
> -1.15` — and after the migration, pooled and fullcov now report the
> identical number, because the merge collapsed the duplicates. See
> `docs/superpowers/specs/2026-08-27-position-identity-design.md` and
> `docs/superpowers/plans/2026-08-27-migration-report.md`.

The same defect destroyed the persistence signal: `times_seen` exists to count
re-proposal and reads **1 on all 9,153 rows** — every repetition became a new
row instead of incrementing the counter. The double-count and the lost signal
are one defect seen from two sides; fixing the key fixes both.

`extra_json.entry_day_iso` already holds the decision day (8,880/9,153), so
decision identity needs no heuristic. All 1,564 insider_judgment duplicate
groups share it — every duplicate in the repo is a same-day re-recording, and
there are currently **zero** genuine multi-day re-decisions. (An earlier read
of 19 live cross-run positions as multi-day was wrong — they are v2 vs v3.)

Design agreed with the user: two levels. **Proposals** keyed
(theory, version, run_mode, lane, ticker, outcome) with `run_id` demoted to an
attribute and an `opportunity_attempts` child table carrying the date list —
scored for calibration, theory_id stays in the key so per-theory track records
survive. **Bets** keyed (ticker, outcome) with no theory — scored for money, so
one bet proposed by three theories and taken once counts once.

**Built:** the handoff doc and `tests/test_position_dedup.py` (15 tests,
failing by design). No implementation yet.

**Next:** schema + migration + ledger + score per docs/DEDUP_PLAN.md section 5,
then level 2. Note the caveat in section 7 — deduping fixes the pooled
number's arithmetic, not its meaning; insider_judgment v3's honest reading
stays the fullcov run alone at -1.15.

## 2026-08-27 (evening) — settlement-day clustering confounds both live theories; calibration_harvest built; calendar-arb killed

On 2026-08-27, this entry established settlement-day clustering as a
first-order confound in this ledger: many settlements sharing one
close-day are one effective observation, not N independent ones. The
day-level favorite edge on the shared screen moved +4.26 / -7.29 / +5.40
net over three consecutive close-days, with the YES/NO split reversing
between them, and both live theories' headline scores that day sat
inside that single day's swing — insider_judgment v3's +11.85 net (n=17,
all NO favorites) and no_side_premium's cell B +14.59 net (n=12, all YES
favorites), recorded under their own 2026-08-27 entries in
`theories/insider_bias/insider_judgment/NOTES.md` and
`theories/no_side_premium/NOTES.md`. `score.settlement_day_clusters()`
(n_days as effective sample size, between-day clustered SE) was shipped
in response, and this entry is where `calibration_harvest` (backlog #1)
was founded, registered `proposed` with nothing yet measured. The same
session killed `calendar-arb` before building it (idea 21, status `dead`
in the idea registry: zero cross-event violations across 295 near-dated
date-ladder pairs, since Kalshi prices near-dated ladders as siblings
inside one event). A same-session addendum (00:20Z) day-clustered the
repo's existing settled evidence and found the tier-B judged runs flip
sign under day weighting (s200 +0.67 → -0.35; s57 +1.90 → -1.36) —
insider_judgment v3 must not be promoted to `active` on those
pre-registered bucket-validation runs.

Narrative moved 2026-08-29 to `theories/calibration_harvest/NOTES.md`
under `## 2026-08-27 (evening) — settlement-day clustering confounds
both live theories; calibration_harvest built; calendar-arb killed
(migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-28 — position identity + attempt fidelity: the migration ran

Not a research session. Closes out the ledger defect diagnosed 2026-08-27
(`docs/DEDUP_PLAN.md`, above). Both specs
(`docs/superpowers/specs/2026-08-27-position-identity-design.md`,
`docs/superpowers/specs/2026-08-27-attempt-fidelity-design.md`) implemented
and merged to `master` (`12a898b`), then `db/market_edge.db` migrated once,
for real: **9,948 rows -> 8,183 positions**, every row surviving as an
attempt, 0 legs orphaned, 0 attempts orphaned, `times_seen` finally moving
off 1 (1,764 positions now show it). Full figures, independently
re-verified against the live database rather than copied from the
migration's own report, and the 26 superseded research verdicts named in
full (money-holding ones called out): `docs/superpowers/plans/
2026-08-27-migration-report.md`.

**The corrected headline:** `insider_judgment` v3 backtest pooled scoring,
previously `n=4,759, calibration_edge_net -0.588` (duplicated rows —
judged sub-runs re-counting markets the fullcov run already recorded),
now reads `n=3,195, calibration_edge_net -1.1486` — identical to the
fullcov-only figure, which is what pooled should always have meant. Same
correction annotated in place above (2026-08-27 entry) rather than edited
out; no other theory write-up quoted the stale number.

The migration also made something computable for the first time:
confidence-bucket win rates over the *merged* judged backtest (labels and
settlements previously lived on different rows). Monotone in the claimed
direction (weak -0.29, moderate +2.51, strong +3.95 pts gross, n=1,564) —
but it's post-hoc on the data that suggested it, so it's pre-registered as
a hypothesis in the idea registry (`confidence-bucket-gradient`, id 27,
`ideas status` carries the revisit angle: needs an out-of-sample walk, net
of fees, and checked inside single settlement-day clusters), not acted on.

`score_campaign.py` — the script that regenerates `insider_judgment`'s
`RESULTS.md` — was repointed to read `opportunity_attempts` directly
(spec attempt-fidelity §9, done on-branch as Task 10a) rather than the
position rollup, because a merged position's `run_id` is now the
*earliest* run's and the old query would have silently returned nothing.
Re-ran it against the migrated database: `load()` returns the same 1,561
rows it returned before the migration, and every printed number (bucket ×
side, the Holm-Bonferroni family, the event-clustered t) matches
`RESULTS.md` exactly. Nothing in that file needed correction.

No theory version bumped — this changed how the ledger counts, not any
theory's decision procedure. Suite green (848) after.

## 2026-08-29 — all three theories current; six endorsed bets settled (all won, one day); the bucket defect survives a 4x bigger sample

The bucket defect diagnosed on 2026-08-28 was confirmed to survive a 4×
larger sample: `insider_judgment`'s `weak` bucket grew from n=17 to
n=67 and its flat win rate merely moved from 0.941 to 0.776, so a rate
applied across a 0.65–0.97 band kept minting "positive edge" on
everything priced below it — 16 such rows this run (Taça de Portugal
football, T20 cricket, Hulu app downloads, South Africa GDP, a Creed
Aventus retail price); bigger n does not fix a miscalibrated shape. Six
of the nine queued endorsed bets settled the same night and all six
won, an early, unvalidated data point (`interpretation_value` +34.4,
`n_days=1`, no computable SE). `no_side_premium`'s same-session status
(cell A/B counts, the cell B sign flip) is recorded in its own
`NOTES.md` under 2026-08-29; `structural_arb`'s (three nested-pair
finds, all rejected by the v2 depth gate) is recorded in its own
`NOTES.md` under 2026-08-29 as well.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-29 — all
three theories current; six endorsed bets settled (all won, one day); the
bucket defect survives a 4x bigger sample (migrated from RESEARCH_LOG.md)`
(spec §6.8).

## 2026-08-29 (cont.) — the bucket layer was differencing against the wrong price; insider_judgment v4

`tools/buckets.edge_for` computed `(bucket_win_rate − this candidate's
price)`, reading a bucket's pooled win rate as this candidate's
probability, which made claimed edge move 1:1 with price and disagreed
with `score.compute_score`'s own `win_rate − price_implied_rate`
formula — undetected for a month. On `insider_judgment`'s own live
`weak` bucket (win 0.7761 at a mean entry of 0.8446, i.e. −6.85 points
of real edge) it claimed +10.04 at an ask of 0.66 and −19.59 at 0.97.
The fix rewrote the formula to `(win_rate − mean entry price of the
rows that measured it)`, with only the fee depending on the
candidate's own ask, and shipped `MIN_BUCKET_DAYS = 5` (a bucket must
span five distinct settlement days before replacing its prior, and an
unsupplied day count fails closed). This bumped `insider_judgment` to
**v4**, recorded in its own `THEORY.md`. The same bug had a second,
invisible victim: it had been silently ranking the retired
`mention_family`'s candidates by cheapness rather than edge.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-29
(cont.) — the bucket layer was differencing against the wrong price;
insider_judgment v4 (migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-29 (cont.) — gate.py reads resolution rules; 130 survivors → 18

Moved 2026-08-29 to `theories/insider_bias/insider_judgment/NOTES.md` under the heading `## 2026-08-29 (cont.) — gate.py reads resolution rules; 130 survivors → 18 (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — deadline-drift's classifier audited three times; the spec is missing its biggest exclusion

Moved 2026-08-29 to `theories/deadline_drift/NOTES.md` under the heading `## 2026-08-29 (cont.) — deadline-drift's classifier audited three times; the spec is missing its biggest exclusion (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — structural_arb: six violations in 11 snapshots, and all three kinds are sterile

Moved 2026-08-29 to `theories/structural_arb/NOTES.md` under the heading `## 2026-08-29 (cont.) — structural_arb: six violations in 11 snapshots, and all three kinds are sterile (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — structural_arb v3: the sterile classes screened at stage 1

Moved 2026-08-29 to `theories/structural_arb/NOTES.md` under the heading `## 2026-08-29 (cont.) — structural_arb v3: the sterile classes screened at stage 1 (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — two ledger defects found while taking stock, one urgent

**Did:** Closing out the session's state check surfaced two real bugs, both
in code that runs every session.

**1. The `go` skill over-reported the endorsed queue, every session.** Its
snippet filtered `opportunities list` output on `r.get("settled_at")` — a
key that listing has never returned, because settlements live in their own
table keyed by ticker. `not r.get(...)` was therefore always true, so
settled positions were counted as outstanding. It reported **8 open bets
when 2 were open**. Replaced with `ledger.list_opportunities(...,
unsettled_only=True)`, which also handles baskets correctly (a basket is
settled only when every leg is). Skill fixed in place.

**2. A re-judged position silently rewrites its own history — and this one
is about to bite.** `compute_score` groups by the POSITION's disposition,
but a position seen again by a later run gets re-interpreted, and
`ledger.interpret` overwrote the position row *without touching the
attempt*. So the record of what each run actually decided was lost the
moment a later run disagreed.

Measured: 222 of 630 live positions have a current disposition differing
from their first attempt. Most are the benign `screened -> rejected`. But
**three went `endorsed -> rejected`** — 9184 (`KXGROK-GROK47`), 9186
(`KXGTATRAILER`), 9203 (`KXNEWDRUGAPPLICATIONCMPS-360`) — all endorsed on
2026-08-27, all declined by today's stage-3 review, **and all settling
Sept 1–4**. None has settled yet, so no score is wrong *yet*; when they
settle they will land in the rejected control pool, which is exactly the
comparison `interpretation_value` exists to make.

`interpret` now stamps the current attempt as well as the position (TDD,
suite **893** green). That is a *fidelity* fix, not a semantics one: it
makes both readings computable instead of losing the earlier verdict.

**Learned:** both bugs were invisible because they fail silently in the
safe-looking direction — one inflates a count nobody cross-checks, the
other quietly moves rows between the two pools the repo exists to compare.
Neither would ever surface as an error; the queue one had been wrong for
every session since the skill was written.

**Next (user decision):** which disposition should a re-judged position be
scored under? Two defensible answers — "a recommendation, once made,
happened, so ever-endorsed scores as endorsed", or "the latest view wins,
because a withdrawn recommendation was never acted on". The history now
supports either. Three positions settle within days, so it is worth
deciding before then.

## 2026-08-29 (session 3) — the version-bump gap, and what v4's clean gate revealed

The `go` skill's freshness check groups by `theory_id` and date but not
by `theory_version`, so a theory that version-bumps after its daily run
reads as current for the rest of that day even though its new procedure
never touched a board: `insider_judgment` v3→v4 and `structural_arb`
v2→v3 both landed at ~00:34Z, after that morning's 00:21/00:44 runs,
and neither had actually run under its current version until this
session forced both. This is the same silent-merge failure the
versioning rule exists to prevent, arriving through the freshness check
instead of the ledger, and it is the finding behind §2 ("Version bumps
outrun settlements") of
`docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md`.
Re-running `insider_judgment` under v4's now-clean gate (23 events, 0
recommended) surfaced a further result: the screen and its best signal
point in opposite directions — the screen picked NO on 30 of 35 legs,
while 15 of 23 events carry a rules divergence broader than their
title, which favors YES, five of them confirmed by research rather
than inferred.

Narrative moved 2026-08-29 to
`theories/insider_bias/insider_judgment/NOTES.md` under `## 2026-08-29
(session 3) — the version-bump gap, and what v4's clean gate revealed
(migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-29 (session 3, item 2) — no_side_premium: a sharper estimator, and a contaminated control caught

Moved 2026-08-29 to `theories/no_side_premium/NOTES.md` under the heading `## 2026-08-29 (session 3, item 2) — no_side_premium: a sharper estimator, and a contaminated control caught (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — calibration_harvest's first population lands; weather is fairly priced; two defects fixed

Moved 2026-08-29 to `theories/calibration_harvest/NOTES.md` under the heading `## 2026-08-29 (cont.) — calibration_harvest's first population lands; weather is fairly priced; two defects fixed (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (session 3, item 3) — TWO SESSIONS ARE RUNNING CONCURRENTLY

**Did:** Went to pick up `calibration_harvest` (the #1-ranked spec, then
`proposed`) and found another session had just taken it to `testing` v2.

**Learned — this is a process problem, not a research finding:**

1. **A concurrent session is live on this repo and database.** Commit
   `a7bddcb` ("calibration_harvest: first population complete; two defects
   fixed; -> testing v2") landed at 08:13:10, **three seconds** before this
   session's `7555bc8` at 08:13:13. It has since written
   `backtests/politics.json` and a `backtest-2026-08-29-calharvest-politics`
   run. `calibration_harvest` now has two live runs today (10,269 rows at v1
   under `live-2026-08-29-calharvest`, 10,269 at v2 under
   `...-calharvest-v2`).
2. **This session's `git add -A` swept that session's in-progress work into
   commit `edba7f7`.** `theories/calibration_harvest/{THEORY.md,NOTES.md,
   theory.py,backtests/weather.json}` and two test files were staged and
   committed under a message about `insider_judgment` and `structural_arb`.
   Nothing is broken — tree is coherent and the suite is **900** green — but
   one logical change is now split across two commits and the first
   attributes it wrongly.
3. **`git add -A` is unsafe in this repo.** Stage explicit paths. Recorded
   here rather than only in a report because the next session will otherwise
   repeat it.

**Consequence for the standing obligation:** `calibration_harvest` became a
running theory mid-session and was already run today by the other session, so
§2 is satisfied for it without this session touching it.

**Next:** paused for a user ruling on how the two sessions should divide work
— continuing in parallel risks duplicated effort and further tangled commits.

## 2026-08-29 (session 3, item 4) — smile-smoothing killed at step one; tools/ladders.py survives it

This entry killed `smile-smoothing` (backlog #11) at measurement, before
registering it as a theory: at any tradeable liquidity floor the
isotonic fit across Kalshi strike ladders was a no-op (97.6% of 959
rungs sat exactly on the fit, zero candidates cleared a 3-point buffer),
because Kalshi lists and quotes ladder siblings together inside one
event, so the ladder is internally consistent by construction — the same
structural cause the 2026-08-27 calendar-arb study found from the other
direction. The one durable output of the dead theory was
`tools/ladders.py` (`YesSet`, `yes_set`, `underlying_key`,
`strike_value`, `is_upper_tail`), elevated out of `structural_arb` under
the caller-count rule once it had three real callers (`structural_arb`,
this study, and the violation-liquidity probe); `structural_arb`
re-exports the names and its funnel stayed byte-identical before and
after, so the elevation carried no version bump. Full write-up:
`studies/2026-08-29-smile-smoothing-ladder-flatness/STUDY.md`.

Narrative moved 2026-08-29 to
`studies/2026-08-29-smile-smoothing-ladder-flatness/STUDY.md` under `##
2026-08-29 (session 3, item 4) — smile-smoothing killed at step one;
tools/ladders.py survives it (migrated from RESEARCH_LOG.md)` (spec
§6.8).

## 2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable

Moved 2026-08-29 to `theories/calibration_harvest/NOTES.md` under the heading `## 2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

Note: this entry is retracted by `## 2026-08-29 (CORRECTION) — the
politics headline was wrong; the pre-registered test failed` (below in
this log); the correction's narrative sits adjacent to this entry's in
the notebook.

## 2026-08-29 (CORRECTION) — the politics headline was wrong; the pre-registered test failed

This entry retracts `## 2026-08-29 (cont.) — politics: the horizon gradient is REAL, and nothing is bettable` above: the politics horizon-gradient headline was wrong. The test pre-registered in `4a01f9a` (ordering `1mo+` > `1w-1mo` > `2d-1w` > `<=2d`) failed at its first step, and the long-vs-short contrast published in its place, and described there as the pre-registered contrast, was in fact the best of three split points (t 0.11, 3.50, 2.23), chosen after seeing where the sign flipped and reported as if fixed in advance. This is the multiple-comparisons instance the enforcing-surfaces spec §1 cites as its motivating case: a result selected from several candidate splits, reported as pre-registered when it was not.

Narrative moved 2026-08-29 to `theories/calibration_harvest/NOTES.md` under `## 2026-08-29 (CORRECTION) — the politics headline was wrong; the pre-registered test failed (migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-29 (session 3, item 5) — series-bias-mining: not measured, and my own bar was the defect

This entry found series-bias-mining (backlog #4) "not measured", not
negative: of 17 series tested, 0 flagged and the largest |t| was 1.43,
but the median minimum detectable effect was 13.5pts against a
theory-grade edge of 3-6pts, so only 2 of 17 series could even resolve a
5-point effect, and 10 of the 17 were the mention_family negative
control (only 7 real series were tested). The methodological correction:
my own pre-registered bar was defective, because it used series COUNT as
its power proxy, and count says nothing about whether a series can
resolve a given effect size — the same defect class as the politics read
hours earlier, which used an unstated "≥3-bins-per-day" rule; here the
unstated substitute was "count as power". Naming the contrast is not
enough — the power floor and inclusion rules are themselves part of the
bar, and this is recorded as a methodological correction rather than
re-bucketing the result. The fixture universe also caught a related
design bug before any real data ran: the statistic was net of fees, and
fees are a near-constant offset, so a perfectly calibrated series scored
negative in both split halves and would have been waved through by the
very split-sample guard meant to catch bias — fixed to score gross, with
net reported alongside. Full write-up:
`studies/2026-08-29-series-bias-mining/STUDY.md`.

Narrative moved 2026-08-29 to
`studies/2026-08-29-series-bias-mining/STUDY.md` under `## 2026-08-29
(session 3, item 5) — series-bias-mining: not measured, and my own bar
was the defect (migrated from RESEARCH_LOG.md)` (spec §6.8).

## 2026-08-29 (cont.) — the ledger is confirmed paper: 8 endorsed, 8 skipped, 0 taken

**Did:** The user confirmed they have **never placed a bet** from this
system. All eight endorsed positions still sitting at
`user_action='untouched'` are now marked `skipped` with that reason:

| id | market | side | ask | recommended | outcome |
|---|---|---|---|---|---|
| 187 | `KXVIDEOLENGTH-26AUG27-GTA-10` | yes | 0.93 | 08-24 | won |
| 188 | `KXVIDEOLENGTH-26AUG27-GTA-15` | yes | 0.87 | 08-24 | won |
| 192 | `KXBIGBROTHERELIMINATION-26AUG27-DRE` | no | 0.82 | 08-24 | won |
| 9134 | `KXBIGBROTHERELIMINATION-26AUG27-TAY` | no | 0.65 | 08-27 | won |
| 9140 | `KXCANUSDEAL-26-26SEP01` | no | 0.97 | 08-27 | open |
| 9204 | `KXNEWDRUGAPPNTLA-LONV-26SEP01` | no | 0.88 | 08-27 | open |
| 9238 | `KXVIDEOLENGTH-26AUG27-GTA-30` | no | 0.85 | 08-27 | won |
| 9239 | `KXVIDEOLENGTH-26AUG27-GTA-45` | no | 0.94 | 08-27 | won |

**Learned:**

1. **`roi_taken: null` now means something different, and the difference
   matters.** Until today it meant *unknown* — nobody had told the system
   either way. It now means **confirmed zero**: the user has placed no
   bets, ever. The `user_action='skipped'` on all eight rows is what
   carries that distinction; a future session must not read the null as a
   missing-data problem to chase.
2. **Every performance number in this repo is hypothetical, without
   exception.** `roi_all` assumes every suggestion was taken. Six
   endorsed positions settled as winners this session and **none of them
   was money**. That was always true and is now recorded rather than
   implied.
3. **The endorsed-vs-taken divergence signal `compare-theories` mines is
   uniform and therefore empty**: 8 endorsed, 8 skipped, 0 taken. There
   is no divergence to learn from yet, and there will not be until a bet
   is actually placed. Worth knowing before anyone builds analysis on top
   of that channel.
4. **Stop asking for `mark-taken` on a settled backlog.** The standing
   ask in every report was addressed to a queue that no longer exists.
   The right ask from here is narrower: *when a new position is endorsed,
   say whether you took it* — not a recurring request to reconcile
   history.

Note also that `score report insider_judgment` now returns `n=0`: the
registry is at v4 (bumped today) and every settled row is v2 or v3. That
is version segmentation working as designed, not data loss — v2 holds 15
settled rows, v3 holds 96. Score a specific version explicitly with
`score.compute_score(conn, 'insider_judgment', 3, run_mode='live')`.

## 2026-08-29 — the event envelope was being fetched and discarded on every board pull

> Contributed verbatim by the parallel session `llm-market-identifier-78`.
> Appended by `llm-market-identifier-18`, which owns this file for the day.

`tools/kalshi/markets.py::list_open` walked `/events?with_nested_markets=true`, iterated `event["markets"]`, and dropped the event object — keeping only `event_ticker`, `series_ticker`, `title`, and only as fallbacks. Kalshi sends `mutually_exclusive`, `category`, `strike_period`, `settlement_sources`, `collateral_return_type` on every event. A full pull downloaded ~14k envelopes and discarded all of them, breaking the guarantee in `Market.raw`'s docstring that a cached board is identical to a fetched one. `board.py:93`'s series_ticker re-derivation is an older scar from the same cause (2026-08-26, gate.py 349/349 cached vs 100/349 fetched).

Cost, before the fix: `structural_arb` fetched `mutually_exclusive` one event at a time under a 150-per-screen budget, accumulating 2,042 cached flags over the repo's whole history; `calibration_harvest` carried an injected series->category map for the same reason.

Fixed in `09a66f7` (tools/ only — re-sourcing a theory's data bumps its version, left to the owning sessions). `Market.event` defaults to `{}` and `market_snapshots.event_json` is additive/nullable, so pre-fix captures read UNKNOWN rather than false, following the `bucket_rates.n_days` convention. Verified: 961 passed; structural_arb's funnel byte-identical; live pull carries envelopes on all 110,628 markets with 0 fetched-vs-cached mismatches; 8/8 positive-class agreement against the old per-event path.

Two findings fell out, both cross-session:

- **structural_arb's 1,445 flag candidates -> 0 confirmed is the guard working, not budget exhaustion.** Kalshi calls 0 of those 1,445 mutually_exclusive (1,436 false, 9 unknown) against a board that is 46% true — conditioning on "the NO-basket arithmetic cleared" selects against genuine partitions, because real ones are priced to sum correctly. The guard should become free rather than be cut.
- **`deadline-drift` gains a fourth option.** Its screen plateaued at ~15% misclassification over four disjoint 50-market audits because the residue (multi-destination "which branch" markets) is semantic. `mutually_exclusive` answers that mechanically and keeps the theory tier A. On the current board the flag agrees with 98% of the regex's 2,687 hand-derived exclusions and catches 336 survivors it missed; paired with a price-partition test (>=3 siblings sharing one deadline summing <=1.05, with a date-ladder exemption) the union removes 665 and catches 4 of the 5 named round-4 misses. Projected ~8% — but that is IN-SAMPLE on the markets that motivated it and needs a fresh disjoint round 5. User decision still open; this changes the choice rather than settling it.

## 2026-08-29 (cont.) — structural_arb v4: the guard is free, and now complete

Moved 2026-08-29 to `theories/structural_arb/NOTES.md` under the heading `## 2026-08-29 (cont.) — structural_arb v4: the guard is free, and now complete (migrated from RESEARCH_LOG.md)`, per the enforcing-surfaces migration (spec §6.8).

## 2026-08-29 (cont.) — the tier rule changed under three of my artifacts

**Did:** The user amended the backtest tier rule (`0f06265`, CLAUDE.md +
the `backtest-theory` skill). Tier A moved from "no LLM in the decision
path" to "no **outcome** judgment in the decision path": a stage that
only asks a *structural* question keeps tier A, subject to four
conditions, all required — answerable from the market's text as written
at open; payload of rules and title only; decides eligibility never
direction; and passes the contamination probe.

I verified the commit and read the rule rather than taking the summary on
trust, because CLAUDE.md is the governing document and a peer report of a
user decision is still a report.

**The peer relaying it said "nothing to do on your side". That was
wrong**, and it is worth recording why: three of my own artifacts assert
the trade-off the amendment removes, and all three are load-bearing for a
decision the user is holding *right now*.

- `studies/2026-08-29-deadline-drift-classifier-audit/STUDY.md` — "Costs
  the live path its **tier-A status**"
- `docs/superpowers/specs/theories/2026-08-24-theory-deadline-drift-design.md`
  — "a cheap LLM gate (clears the bar, loses tier A)"
- idea 3's `revisit_angle` — the same, in the field a future session reads
  *instead of* the study

All three corrected in place, marked as amendments rather than silently
rewritten.

**Learned:**

1. **A rule change dates every artifact that reasoned about the rule.**
   The tier amendment touched no code, so nothing failed and no test went
   red — and three documents quietly became misleading. The blast radius
   of a *docs* change is the set of claims that depended on it, and
   nothing computes that set for you. `grep` for the claim, not for the
   file.
2. **The decision I put to the user got simpler, not just different.** It
   was "three options, each sacrificing something". It is now: **take the
   data.** `mutually_exclusive` answers the multi-destination question
   outright, free and exact, and CLAUDE.md now names that exact field as
   its worked example with the instruction that no prompt should be
   written to re-derive it. The LLM gate is third in the stated
   preference order (data → code → structural gate → outcome judgment),
   and only *plausibly* tier A: the contamination probe is **unrun**, and
   an unrun probe counts as outcome judgment.
3. **The amendment's own guard is the interesting part.** "Structural" is
   the one label a theory could award itself, so the rule makes it
   derived and never self-reported, treats an unrun probe as outcome
   judgment, and rules that any stage assigning a bucket is outcome
   judgment whatever its prompt is called. It moves the tier, not the
   paper trail — provenance, prompts-on-disk and version bumps are all
   untouched.

## 2026-08-29 (cont.) — a fourth stale artifact, and my third overstatement of the day

**Did:** Two corrections, both from peer pushback, both mine.

**1. My sweep for tier-rule-dated artifacts missed one, and the miss was
instructive.** I grepped `"loses tier A\|forfeits tier A\|tier-A status"`
and found three. Session 78 applied my own generalisation back to me with
a wider pattern and found a fourth: the backlog index's step 3, *"backtest
tier A means **no LLM anywhere in the decision path**"* (`b1e2e7d`).

It survived because it states the claim as a **contract** rather than as a
**consequence** — no "loses", no "forfeits", no "status". And it was the
worst one to leave standing: it sits in the index's how-to-implement
checklist, read at the start of any work on any of the 22 backlog entries,
so it would have re-taught the old rule to sessions that never went near
`deadline-drift`.

So the rule needs one more turn: **grep the claim, not the file — and
grep more than one phrasing of the claim.** Two phrasings found three
artifacts; a third phrasing found the fourth. I re-ran a wider sweep
across `*.md` and `*.py` and confirmed the remainder are legitimate: the
new rule itself, three hits in `plans/2026-08-23-theory-harness.md` (a
historical plan, correctly left as audit trail), and per-spec headers that
are still true of theories using no model at all.

**2. I overstated the deadline-drift conclusion — the third time today.**
I told the user the decision had "collapsed" to *take the data*. It has
not. `mutually_exclusive` **alone catches 2 of the 5** named round-4
misses; it takes the flag *plus* a price-partition test to reach 4 of 5,
and the resulting ~8% is **in-sample on the very markets that motivated
the rule**. Data is the right first instrument and the evidence for it is
strong — 98% agreement with 2,687 hand-derived exclusions, and it reaches
the residue the regex structurally could not — but *clears the 10% bar* is
unmeasured out of sample, and round 5 is that measurement.

Re-reading my own text I found a second overstatement in the same
paragraph: I had written that a structural LLM gate **"would clear 10%"**.
No such gate has been built or run against any sample. Both corrected.

**Learned:** three overstatements in one day — the politics headline, "the
decision collapsed", "would clear 10%" — is a pattern, not three
accidents. Each was the same move: taking a real, directional result and
reporting it one notch stronger than the measurement supported. The
symmetry is worth recording, because session 78 made the mirror-image
error in the same exchange (telling the user the structural gate route was
"available" when its probe is unrun) and we caught each other's within
minutes. **Neither of us should be writing the conclusion before the
audit** — and the reason this repo keeps catching it is that the numbers
are always reproducible and someone always re-derives them.

## 2026-08-29 (correction) — I misattributed a peer's work, and committed another peer's file

Two process failures of mine, both caught by `llm-market-identifier-4f`,
both verified against `git log` rather than memory before being recorded
here.

**1. I credited the fourth-artifact catch to the wrong session.** It was
`llm-market-identifier-78` (`b1e2e7d`), not `4f`. I sent `4f` a detailed
acceptance of a critique they never made. `10f7932` and `9f7193e` are
mine.

**Cause worth naming, because it will recur:** every session commits as
`jschauer1`, so `git log --author` cannot separate us — and I compounded
that by tracking who-said-what from conversational memory across a long
session with three peers. The fix is not better recall; it is not needing
it. **Quote the commit before crediting the work.**

**2. I committed a file out of another session's working tree.**
`classifier_r5.py` — 78's round-5 classifier for `deadline-drift` —
entered the repo in **my** commit `9f7193e`, swept up by
`git add -A studies/`. The content is untouched; only the commit it
landed under is wrong. I then told `4f` "round 5 is yours", so for a
while **two sessions were deliberately avoiding one file and none owned
it**. Both told; round 5 is 78's, stated explicitly.

This is exactly what `4f` did to my in-progress `calibration_harvest`
work this morning (`edba7f7`), apologised for, and stopped doing. I read
that, agreed with it, and then did the same thing to a third session
hours later. **Stopped using `git add -A`; explicit paths only.**

**3. `4f` corrected my analysis of the day's overstatements, and their
version is better.** I had filed their "strictly better than the three
options" alongside my three as mirror-image errors. They aren't the same
failure:

- **Mine happened at the point of writing** — taking my own directional
  result one notch past what the measurement supports. Three times: the
  politics gradient headline, "the decision collapsed", "would clear
  10%".
- **Theirs happened at the point of quoting** — relaying 78's measurement
  without re-deriving it, *because* 78 had been reliable all day.

Different fixes. I need a habit before writing a conclusion; they need
one before repeating someone else's number. Filing them together would
have hidden both. Recording them apart.

**Note on `classifier_r5.py`, since it is now in the repo under my
name:** it is 78's work and it is good practice — the classifier is
frozen *before* the sample is drawn, with the reason stated (its two
structural rules were designed against round 4's misses, so re-tuning
against round 5 would reproduce the in-sample flattery the round exists
to detect). If round 5 lands near the projected ~8%, that agreement is
**unsurprising rather than confirmatory**: the projection was fitted on
those same misses. Only a disjoint sample carries information.

## 2026-08-29 (cont.) — supervisor session: three reviews, two standing proposals for the user

Session 09 ran as a review-only supervisor at the user's direction;
peers sent three items. All three closed the same day.

**1. 4f's payload-version study (`0b5b25e`) — thesis right, exhibits
wrong.** Independent re-run reproduced every count (331/541/39), but
three of four examples were quoted direction-reversed — the headline
"strike moved 12000→12500" was actually a title typo corrected *toward*
rules that said 12K throughout, on a market whose outcome does not exist
yet — and the 39 "number moves" decomposed to 38 template artifacts plus
that typo. Root cause in 4f's extraction: `sorted(set)` presented as
chronology. 4f verified all of it and revised (`0ecd8f2`); the
hand-classification the review asked for found **one** genuine
resolution-criteria change in the 5-day window (`KXDATACENTERMORATORIUM`),
now the study's entire empirical basis, labelled as such. The review
also caught that the proposed fix's exclusion clause would have voided
structural gating over all pre-2026-08-24 history — repealing the
amendment it patched. Replaced by a two-part form (mandatory
point-in-time payload where a capture exists; disclosed, drift-bounded
current text where none does).

**2. 78's deadline-drift round 5 — reviewed after the fact, holds.**
Design-stage request was overtaken; reviewed execution instead: sample
disjointness verified against all four prior rounds (zero overlap),
arithmetic checked, two-reader protocol sound. Review adds recorded in
`3dcc2d5`: the 6/50 CI contains the bar (verdict rests on burden +
mechanism, stated now), the shared-frame limitation, and a real bug in
the price-partition rule — no lower bound on the sum — which 78 then
measured: **281 of 318 exclusions were wrong** (true population ~4,416,
not 4,135). No conclusion moved; the frozen classifier stayed frozen.

**3. structural_arb v4 (`117a258`) — sound; rationale inverted; fixed in
`3475d26`.** Requested by session 18, which ended before delivery;
fixes applied directly. The tri-state's stated reason ("absence-as-False
would let a replay accept an unverified partition") is backwards —
False and None both exclude; the split protects the *record* against
re-manufacturing the all-false illusion. "1,449 false arbitrage claims"
tempered to unverifiable: round 5 proved the flag reads False on
semantically exclusive events, and 78 measured the gap (53 partition-
priced events, 10 unflagged, 0 clearing) — real, currently empty, kept
as a standing check in the theory's NOTES. Read-only cache now has a
pin test; flag-stability-across-life flagged as assumed-not-measured,
now measurable from cross-capture envelopes. Ideas #28
(`unflagged-partition-arbs`) files the lead. Suite 965.

**Standing proposals awaiting the user — surfaced here so orient sees
them; CLAUDE.md deliberately untouched (tier rule is a user decision):**

1. **Fifth structural-gate condition, two-part form** — payload built
   from a point-in-time capture where one exists; where none exists
   (all history before 2026-08-24), today's text may be used but the
   run's notes must say so and carry a snapshot-era drift bound, with
   tier-A acceptability of that half explicitly the user's call.
   Proposal text and evidence: `studies/2026-08-29-structural-gate-
   payload-version/STUDY.md` (revised, `0ecd8f2`).
2. **A sharper contamination probe** for the backtest-theory skill, as
   its own item, not bundled with #1: compare a gate's *pass rate* on
   structure-matched pre- vs post-cutoff markets; a gap is leakage the
   current "can you state the outcome?" probe cannot see. Origin: 4f's
   study, observation 2; endorsed on review.

## 2026-08-29 (cont.) — decision authority delegated to the supervisor session

The user delegated adjudication of research-governance decisions to the
supervisor session (09): standing proposals, pre-registration amendments,
resource sequencing, and the like now route there, and reach the user
only when they genuinely need them (money, retirement of theories, and
anything a session's permissions block). Recorded so future sessions
route correctly.

Ruled under that authority, same hour:

- **Fifth structural-gate condition ADOPTED** (`4266413`) — two-part
  form; part (b) keeps tier A with mandatory disclosure + drift bound.
  Supersedes the "standing proposal" status in the entry above. The
  SKILL.md mirror edit is blocked by session 09's permissions and
  pending; CLAUDE.md is authoritative.
- **4f's decision-point amendment ruled legitimate** (24h → 25% of span,
  infeasibility-driven, pre-observation, now frozen), with instructions
  to price both decision points from the already-fetched candles and to
  separate hazard-style families from date-certain ones — a decision
  point derived from observed span is outcome data under early
  settlement, a bias both the original and amended rule share.
- **Candles-endpoint sequencing:** 4f's bounded phase-2 run finishes;
  78's deadline_drift hazard bins next (theory-critical); then the
  phase-2 remainder (~10h, authorized, resumable). One long job at a
  time.

## 2026-08-29 (cont.) — supervisor rulings: attempt-level scoring; the anchor rule at scale

**Disposition scoring ruled ATTEMPT-LEVEL** (supervisor, under delegated
authority). Each attempt scores in the pool of its own disposition at
its own decision_date and entry price; position-level disposition is
display-only (latest attempt), never a scoring key. Rejects both
"latest view wins" (a later run could erase an earlier run's published
decision — the disposition-form of the silent merge the versioning rule
prevents) and "ever-endorsed" (pins the maximal claim, starves the
control pool). The three flipped positions (9184, 9186, 9203, settling
Sept 1–4) therefore feed both pools — endorsed as of their August
attempts, rejected as of 2026-08-27. 4f implements in
`tools/score.py::compute_score` before Sept 1, flip case tested,
semantics documented; unstamped-attempt backfill cases come back to the
supervisor rather than being chosen silently.

**The early-settlement anchor hazard is two-thirds broad, not an edge
case.** 4f measured 66.8% of 173,632 eligible settled markets closing
early (median 3h, max 490 days); 28.4% close on schedule. 78's
deadline_drift sign-flip was the visible instance. Kalshi's
`expected_expiration_time` preserves the schedule (the measurement is
only possible because it does), making it the valid anchor where rules
parsing is impractical. 4f's phase-2 hardening: anchor on
`expected_expiration_time`, exclude-and-count when absent (114 rows),
never fall back to observed close; both the 25%-of-span and original
24h decision points now computed inside the same fetch, so the
pre-registration amendment gets measured, not argued.

**Pending skill edits, blocked by session 09's permissions** (queued for
the user or a permitted session; CLAUDE.md is authoritative meanwhile):
`.claude/skills/backtest-theory/SKILL.md` — (1) "four conditions" →
five; (2) point-in-time payload paragraph mirroring the adopted fifth
condition; (3) the pass-rate probe recommendation; (4) new bullet under
"Enforce the rules": never derive a decision point from observed close
or span — on a "by D" market actual close is the outcome variable
(66.8% measurement; deadline_drift sign-flip as the worked example).

## 2026-08-29 (cont.) — scoring ruling completed: dedupe, non-decisions, clustering

Three refinements to the attempt-level ruling, from cases 4f and 78
surfaced before implementation (the surfacing discipline working as
intended):

1. **Consecutive-run dedupe.** Same-disposition re-affirmations collapse
   to the first attempt of the run — a disposition *change* is the
   decision boundary. Handles 2,204 positions with duplicate-disposition
   attempts (worst case: one market screened daily for its whole window
   would otherwise score ~21× against one settlement), while still
   scoring genuine flip-backs as separate decisions at their own prices.
2. **Post-interpretation `screened` rows are non-decisions.** A screened
   attempt on a position with any prior interpreted attempt records the
   scan re-seeing, not a judgment: retained in the ledger, skipped by
   scoring. Pre-interpretation screened rows DO score (they are the
   stage-1 baseline; dropping them would bias the screened pool toward
   never-interpreted positions). No-op for mechanical theories. The
   three flipped positions land in two pools, not three.
3. **Event-clustered uncertainty, cluster-count n.** Point estimates
   stay attempt-level post-dedupe; all SE/z/intervals are clustered at
   the event level (ticker fallback); and the n feeding credibility is
   the cluster count, raw rows reported beside it. 78's hazard estimate
   is the exhibit: 2,805 daily rows → 48 clustered, z≈9 naive → 1.34
   honest. Correlated rows must not manufacture precision or ranking
   credibility. CLAUDE.md's formula text unchanged; n's definition is
   documented at compute_score.

4f implements all of it before Sept 1. Verified independently this hour:
`python -m theories.deadline_drift.hazard` reproduces the corrected
deadline_drift table from disk (1eaa918), and the standing capture job
for its perishing population is committed (766d469). Pending skill-edit
item 4 adopts 78's conditional wording: anchor on scheduled close
always; families with a long right tail in closed_early_days (median
210d for "by D" families vs 3h population-wide) are where the
actual-close anchor inverts signs rather than adding noise.

## 2026-08-29 (cont.) — attempt-level scoring landed; schema ruling for cluster-n

`f6a1047` (suite 982) lands the attempt-level ruling ahead of the Sept 1
settlements: consecutive-run dedupe (flip-backs score twice, proven by
test), post-interpretation screened rows retained-but-unscored, three-
position two-pool fixture. First concrete payoff: position-level
grouping had been ERASING stage-1 baselines wherever stage 2 later
engaged — no_side_premium cell A went n=0 → n=8 (+1.375 net), and 4f
corrected its own morning statement to the user ("cell A has 0 settled
rows") which was an artifact of the defect.

Schema ruling for the clustering extension (supervisor): `n_clusters`
is ADDED as a nullable column — the stored `n` keeps its row-count
meaning everywhere, historical rows stay NULL, nothing is rewritten in
place. `rank.py` switches to cluster-n in the same commit, with two
mandatory disclosures: the full before/after ranked-edge table for
every theory, and explicit callout of probation flips (n<10 now binds
on clusters). Additive ALTER only; characterization tests cover both
row generations. `bucket_rates` shares the correlated-sibling issue in
principle but is explicitly OUT of this scope — separate ruling when
filed.

## 2026-08-29 (cont.) — tier B is a different evidence profile, not a worse one

User ruling on the narrative around judgment theories. The docs had been
saying two incompatible things: "the ladder ranks instruments for a given
*question*, not theories" alongside "pure code is often the better theory"
and "the most expensive and least verifiable" instrument. The portfolio
shows which half was winning — 1 of 6 theories uses judgment, and that one
(`insider_judgment`) was ported in rather than chosen; the open backlog is
~1 interpretive idea in 22.

Six edits to CLAUDE.md, two to `theories/_TEMPLATE/THEORY.md`, one to
`propose-theory`. Substance, not tone:

- Tier B's cost is reframed as **operational** (slower accrual, tokens per
  replay) rather than epistemic. That is a reason to iterate faster on
  mechanical theories, never to propose fewer interpretive ones.
- **Counterweight recorded for the first time:** tier B's window is recent
  *by construction*, so its sample sits closer to current market conditions
  than years of tier A history.
- **Double-counting forbidden.** Sample size is already in the t-statistic
  and in `credibility`; discounting a tier B result again "for being tier B"
  charges twice for the same fact. The doubt that *is* unpriced is named
  explicitly: residual leakage (a cutoff is a ragged boundary) and
  non-reproducibility (verdicts move with model version).
- "Reaching for a model is the second choice" now scoped in its topic
  sentence to *structural* questions, which is what the rest of the passage
  already meant.

Historical specs under `docs/superpowers/` keep the old wording on purpose:
they are the audit trail of what was decided when, not live guidance.

Not addressed, still open: nothing in code reads `backtest_runs.tier`, so
"tier C is excluded from credibility" is a procedural rule rather than an
enforced one. No tier C runs exist today, so it does not yet bite.

## 2026-08-29 (cont.) — subset edges: registered slices, and the ranking partition

User directive: a theory whose aggregate shows no edge can contain a
subset with a demonstrated one (insider_judgment's strong/moderate-NO
rule), and bets inside the proven subset must be weighted differently
from the rest — built into the repo as an expectation for every agent
composing bets.

Shipped `tools/slices.py` + `theory_slices` + `cli slices
register|list|report|match|retire` (spec:
`docs/superpowers/specs/2026-08-29-theory-slices-design.md`; tests:
`tests/test_slices.py`; CLAUDE.md "Subset edges" under How ranking
works; find-edge and score-theories updated). The short version: a
slice is an immutable, pre-registered, mechanical predicate over
recorded fields; its credibility counts only out-of-sample evidence
(settled after registration, or runs designated at registration —
designation matches any run that proposed the position, since the
first seer is usually the mechanical screen); past ≥10 OOS clusters
and ≥5 settlement days it partitions ranking into slice vs complement.
`rank.py`'s formula is untouched — slices choose which row feeds it.
`score.py` grew the seam (`observations()`/`aggregate()`, enriched
observation dicts); `compute_score` arithmetic unchanged, suite green
(1,005).

First registration: `insider_judgment/strong-moderate-no`, backdated to
its documented 2026-08-26 pre-registration, s200b/s57 designated OOS.
Result on real data (v3): slice OOS +4.30 net row-weighted / **+8.10 ±
1.88 day-weighted over 42 days** — the bet-rule cell survives day
clustering even though the judged runs as a whole flip sign under it —
against a complement of **−2.54 net (809 clusters)**. Details:
insider_judgment `NOTES.md` 2026-08-29 (cont.).

Two standing notes. (1) The 2026-08-29 "nothing reads
backtest_runs.tier" gap is now partially closed: slice segments exclude
tier-C-touched rows in code; whole-theory `compute_score` still does
not read tiers. (2) A segment whose rows recorded near-zero claimed
edges saturates `realization` at the 1.5 clamp (insider's OOS segment
does: mean_claimed_edge ≈ 0.09), so credibility there is effectively
sample-weight × 1.5 — reports built on such a segment must show the
clustered/day SEs alongside, which `slices report` emits.

## 2026-08-29 (cont.) — slice sweep: the subset-edge mechanism applied across the portfolio

User directive: make sure registered slices apply to all theories, not
just insider_judgment. Reviewed all six; per-theory outcomes:

- **insider_judgment** — `strong-moderate-no` already registered
  (earlier today). The second documented candidate (rules-diverge, from
  the 2026-08-26 live tracking plan) is **blocked**: all 35 v4 live
  rows have extra_json NULL, so the flag the plan says is recorded per
  row is not being recorded. That is a v4 recording gap for the next
  session that runs the theory; the slice registers the day the field
  exists. See its NOTES.md 2026-08-29 (cont.).
- **no_side_premium** — both pre-registered cells registered as slices
  (`cell-a-no-favorite`, `cell-b-yes-avoid`), backdated to the
  documented 2026-08-26 pre-registration. Validation: the slice
  machinery independently reproduces the theory's hand-computed status
  (cell B forward n=46 / 3 days / −10.44, day SE 12.7 — unmeasured;
  cell A 0 settled). The theory's own stricter bars still govern
  confirmation; note in its THEORY.md that a ready-and-negative cell B
  is the avoid claim CONFIRMING.
- **calibration_harvest** — deliberately none: its cell grid is the
  native subset mechanism with stricter bars, and no cell is
  measurable-positive. Standing rule recorded in its NOTES.md: register
  a cell as a slice in the same session it first clears its bars
  (`{"extra": {"cell": ...}}`; v2 records the cell per row). Tooling
  gap noted for cross-cell predicates (extra clause is exact-equality;
  extend to lists only when a real slice needs it).
- **deadline_drift** — `proposed`, does not run; its hazard bins are
  native subset machinery. Nothing to register until rows exist.
- **structural_arb** — not applicable by design: its positions are
  baskets, and slice predicates never match baskets (single-leg
  vocabulary).
- **mention_family** — retired; produces no rows to partition. Its
  surviving subset claim already lives on as no_side_premium's cell A.

No code changes; registrations are DB rows plus notes. Coverage rule
now in effect via find-edge: any theory with a `slices list` result is
ranked per segment.

---

## 2026-08-29 — Enforcing-surfaces spec reviewed and corrected; user ruled: migrate the log, adopt the bar

**Did:** Reviewed `docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md`
against the live repo and DB. Every measured claim reproduced exactly
(opportunity counts, per-version settled rows, snapshot rows, CLAUDE.md line
anchors, companion-table structure). Fixed what didn't hold: §2.4's carry
equivalence field list (now checks decision outputs incl. `confidence` and
slice-predicated `extra_json` keys; `outcome` joins from the parent position;
`entry_price` is input, not proof), §5.2 phase 2's batch-semantics gap
(`board_info` under dedup; three tests allowed to change, four frozen), §5.2
phase 3's nonexistent "accessor" (readers enumerated; decode helper +
studies stance specified), §1.4/§1.7 question double-count (`slices register`
is sole writer for slice-origin questions), §7.5-vs-§0 doctrine-count
contradiction, §3.1 stale log measurements, `ledger.`→`score.
record_backtest_run`, §2.6 backfill's version-history source, and a
`theory_versions` CHECK making unproven carries uninsertable. Added §6.8: a
nine-step executable migration procedure.

**Learned / RULINGS (user, direct, this session — backfill into `rulings`
when §3.3 ships):** (1) Theory-locality plan §22 is **reversed** — migrate
theory-local `RESEARCH_LOG.md` content into the owning theory's `NOTES.md`
"when possible" (T wholesale, M split one at a time, X stays). (2) The
promotion bar is **adopted**: this log carries only what is very useful
generally — mechanisms, rulings, precedents, constraints, breakthroughs,
corrections; theory-local results are a headline plus a pointer. Both
outrank the pending supervisor packet. Sequencing still holds: nothing moves
before `state`, `rulings`, and the citation sweep exist (§9 phases 1–3).

**Next:** Implement §9 phase 0 (ledger backup — the only total-loss risk),
then phase 1 (`state`, `--ticker`, hygiene). The migration itself follows
§6.8 in order.

---

## 2026-08-29 — Three more user rulings on the enforcing-surfaces spec

**RULINGS (user, direct — backfill into `rulings` when §3.3 ships):**
(1) §4.3 paper lane: **no** — deleted per its own terms; divergence input
comes from the raise lane's raised-but-never-taken population instead.
(2) §5.2 phase 1: get `db/` out of OneDrive by **relocation + junction**
(default `%LOCALAPPDATA%\market_edge\db\`), with the junction-sync
verification and no-open-sessions caution now written into the phase.
(3) §5.3: **adopt** the ~30-minute floor on `get_board(force=True)` —
comparability across concurrent sessions is the point.

Spec updated in place; the only question still open in it is §7.7's
prefer-mechanical consolidation (explanation delivered to the user, ruling
pending).

---

## 2026-08-29 — RULING: the prefer-mechanical rule reframed as a division of labour, consolidation performed

**RULING (user, direct — backfill into `rulings` when §3.3 ships):** The
user rejected the "prefer statistics / mechanical-first" framing and
recentred the rule: **a model categorizes; measurement quantifies.** An LLM
may only classify (bucket, side, in/out, better/worse) — it can never emit
an edge number — and any edge an LLM-judged theory claims must trace to
backtesting or settled history, never the model guessing. Interpretive
theories (`insider_judgment`-style) remain explicitly first-class.

**Did:** Performed the §7.7 consolidation under that framing. The canonical
statement (with the four hedges kept as numbered riders) now lives in
`CLAUDE.md` under "Never state a probability you introspected"; the
question/thesis passage and the backtest-tiers ladder passage were trimmed
to their local substance plus pointers; the gates paragraph is untouched as
rider 4's operational home. `edge_basis='prior'` is explicitly bound: a
prior comes from a stated structural assumption, never a felt sense. No rule
removed, no hedge dropped; enforcement already existed in code (Verdict has
no numeric field; `buckets.py`; `edge_basis`). Spec updated; no open
questions remain in it.

---

## 2026-08-29 — RULING: task-time rules get one home — their skill, not CLAUDE.md

**RULING (user, direct — backfill into `rulings` when §3.3 ships):** The
enforcing-surfaces spec's §7 changes from duplicate-and-test to
**single-home relocation**: the ten owned task-time rules (web-search-off,
structural-gate conditions, tier-claim recording; judge-blind,
buckets-from-deep-stage, batch-and-dedupe; facts-are-data,
search-the-registry, revisit-angle; notes/theory/log split) **move** out of
`CLAUDE.md` into the skills that own their activities, so `CLAUDE.md` reads
as a non-diluted cardinal core plus a skill map. Constitutional and
enforced tiers stay in full; the three unowned rules stay (nowhere to go);
rule 18's tier definitions stay constitutional with only a reading
explainer in score-theories. Safety mechanics are part of the ruling: every
move is atomic (removal and skill-landing in one commit, content-neutral by
diff) and a manifest conventions test holds each moved rule in exactly its
owning skill. Approval is scoped to exactly these ten; anything further
needs fresh approval. Spec §0/§7/§9/§10/§11 rewritten accordingly.

---

## 2026-08-29 — RULING: the expert-agent architecture — theory-level context and skills

**RULING (user, direct — backfill into `rulings` when §3.3 ships):** The
repo's overarching architecture is now stated, not latent: **design
everything so a strong agent can be initialized inside one theory — the
cardinal `CLAUDE.md`, the skills, and the theory's folder — and operate as
that theory's expert**, while a supervisor at the abstract level supervises
experts reading only shared structures (`state`, `THEORY.md`, the DB, this
log). Mechanisms, both native to the harness: `theories/<slug>/CLAUDE.md`
as auto-loaded theory-level cardinal context (a distillate, never a second
notebook), and directory-scoped theory-level skills that elevate to the
global set only at 2+ theory callers, as a migration — the same elevation
rule code follows into `tools/`. The two existing laws (repo-level facts
surface in shared structures; theory folders are self-sufficient) are this
architecture's two interfaces, unchanged. Recorded in the
enforcing-surfaces spec as §7.9 with phase C; the §6 migration is the
architecture's backfill.

---

## 2026-08-29 — Expert-agent architecture written into CLAUDE.md; the two locality rules renamed as its contracts

**Did (user-instructed):** Performed §7.9's CLAUDE.md rewrite. The "shape
also supports — without requiring" paragraph is now the stated overarching
architecture: a supervisor over theory experts, an expert initializable
from the cardinal file + skills + theory folder. The two existing rules are
rephrased in the architecture's vocabulary — **the supervisor's contract**
(every fact the supervisor needs in order to supervise surfaces in a shared
structure; distillation upward, never a supervisor reading notebooks) and
**the expert's contract** (a theory folder contains everything its expert
needs to run; no sibling imports; shared ancestry via parent module or
tools/; test-enforced). Substance unchanged, names new. Spec §3.1/§7.9/§9
updated to quote the new wording.

---

## 2026-08-29 — Foundation plan shipped: backup, hygiene, --ticker, force floor, state, rulings; db/ relocated out of OneDrive

**Did:** Executed `docs/superpowers/plans/2026-08-29-enforcing-surfaces-foundation.md`
(spec phases 0, 1, 1b, 2) via subagent-driven development — every task
reviewed, all findings fixed or ruled, suite 1,022 green. Shipped: `db
backup` (ledger dump excluding snapshots, source attached SQLite-enforced
read-only; real backup taken and restore-verified at
%LOCALAPPDATA%\market_edge\backups\market_edge_ledger_20260829T233205.db.gz,
4.2 MB); §5.1 hygiene + `test_every_repo_path_named_in_docs_resolves`
(migration artifacts retired to `attic/kalshi_trader_migration/`);
`mark-taken --ticker`; the 30-minute force floor on `get_board`;
`python -m tools.cli state` (orientation now renders from the DB —
`CLAUDE.md` and the go skill point at it); the `rulings` table with all
twelve standing rulings backfilled. **`db/` was then relocated** to
`%LOCALAPPDATA%\market_edge\db\` behind an NTFS junction at `db/`
(WAL-checkpointed first; `state`, git tracking of `db/schema.sql`, and the
full suite verified through the junction). OneDrive was not running during
the move; watch its first restart for any attempt to sync the junction —
fallback is pointing `tools/db.py::DEFAULT_DB_PATH` at the new home.
Rulings 4 (relocation), 5 (force floor) and 6 (division of labour, from the
earlier consolidation) marked implemented.

**Next:** Plan 2 of the spec — §9 phases 3–5, the log migration (§6.8's
procedure), now unblocked: `state` exists, `rulings` exists, the citation
sweep is the first step.

**Addendum, same session — final-review fix wave.** The whole-branch Opus
review returned no Criticals and six Importants; one fix wave closed all of
them (commit f16642a, suite 1,022 → 1,038). Substantive: `resolve_ticker`
now matches only `run_mode='live', lane='main'` rows and refuses outcome
ambiguity — it could previously land a fill on a backtest or experiment row
(reproduced in review); `state` renders "scores never written" honestly and
stops truncating rulings without notice; the backup's read-only ATTACH is
now guarded by a test that fails on revert; `tools/README.md` maps the
three new modules. **Carried to the next plan:** nothing writes `scores`
(`save_score` has no production caller — EVIDENCE/rank/compare all read an
empty table), and the docs-path test skips nested family THEORY.md files
until spans resolve doc-relative.

---

## 2026-08-29 — Storage design gate measured: byte-exact dedup is 38.8%, and the "jitter" is mostly real data

**Did:** Ran the enforcing-surfaces spec §5.2 design gate against the live
snapshot store (1,390,328 rows): full-payload (raw_json + event_json)
byte-exact comparison finds **539,827 unchanged repeats (38.8%)** vs the
56.5% measured on the five material columns. Sampling 4,000 of the
materially-unchanged-but-byte-different pairs, the divergence is:
`previous_yes_ask_dollars` 40%, event envelope 32%, `yes_ask_size_fp` 26%,
`previous_yes_bid_dollars` 20%, `yes_bid_size_fp` 13%, `volume_24h_fp` 6%,
`updated_time` 1%.

**Learned / design ruling for the storage plan:** top-of-book depth
(`*_size_fp`) is load-bearing data — structural_arb's depth gate reads it —
and the `previous_*` / `volume_24h` fields are real rolling references, so
**dedup stays byte-exact with no field exclusions**. 38.8% (~2 GB) is the
dedup contribution; compression (phase 3, ~8× on remaining JSON) carries
the rest of the 5.3 GB → ~0.5 GB projection. Zero information loss holds.

**Next:** Write the storage plan (spec §5.2 phases 2–4) or the log
migration plan (§6.8) — both unblocked; user to pick order.

---

## 2026-08-29 — Carry chains shipped (spec phase 6); rule delivery nine-tenths done (phases A/B)

**Did (session llm-market-identifier-c0 and predecessors, via SDD):**
Phase 6 complete — commits e376c83, 96d250e, 9a70a7a, 0109f38, c36a60a,
bb33577, 9a77861, 2644d01, b1c96e0. Version bumps now declare
`breaking`/`carry` (`theory_versions`; DB CHECK makes an unproven carry
uninsertable); `prove_carry` replays a theory-supplied `decide` over the
predecessor's stored attempts and compares decision outputs field-exactly
(slice-predicated `extra_json` keys included); evidence pools across proven
chains behind `pool="chain"` in `compute_score`, `settlement_day_clusters`,
and `slices.segment_report`, all defaulting to today's per-version
behaviour (characterization-locked); `score report --pool chain` is the
adoption surface, documented in find-edge/score-theories. All 13 historical
bumps backfilled `breaking`; disclosure table confirms **zero ranked-edge
movement today, structurally** — the machinery arms only when a real
`prove_carry` passes (first candidate: `insider_judgment` v3→v4, expected
`breaking` per its own record).

Phases A/B (rule delivery): nine of ten task-time rules moved atomically
into their owning skills (backtest-theory 13/19/20, find-edge 10/11/12,
propose-theory 17/35/36) with the single-home manifest test holding each;
score-theories carries the rule-18 reading explainer. Remaining: rule 32 →
go (gated on the migration's §6.7 rewrite) + closeout — parked resumable in
the rule-delivery SDD ledger; session -91 inherits after its Task 15.

**Research note surfaced by the phase-6 disclosure:** `no_side_premium`
live evidence at v1 reads n=38 clusters, `calibration_edge_net` −10.44 vs
mean claimed −3.9 (credibility 0.655). Worth a `score-theories` diagnosis
pass by a research session — recorded here so it is not lost in a ledger.

---

## 2026-08-30 — RESEARCH_LOG migration complete: the canon left the journal (spec 6.8)

**Did (session -91, Task 15 — the migration's own reconciliation, spec §6.8
steps 8–9):** Closed out the enforcing-surfaces log migration begun at
`0e3d89a` (design: `docs/superpowers/specs/2026-08-29-enforcing-surfaces-
design.md` §6.8; classification: `docs/superpowers/specs/2026-08-29-
enforcing-surfaces-log-classification.md`). Against that pinned table, **22
theory-local entries (9,484 words)** moved verbatim to their owners'
notebooks under migrated headings, and **14 repo-fact-bearing entries
(5,958 words)** split — the fact extracted upward, the narrative moved the
same way — one theory or one split per commit across `0e3d89a..HEAD`. The
28 cross-cutting entries (9,370 words) stayed in place untouched, per the
procedure's step 7. 15,442 of the pinned table's 24,812 words (62%) left
this file; every departure left a one-paragraph stub at its original date
and heading, so a dated citation into this file still resolves.

**Reconciled (step 8):** stub count equals moved-row count — **36** (22 T +
14 M), cross-checked against the companion file's main table and its
M-split record. First count came back 32, not because four stubs were
missing but because four of the M-split sentences had their ordinary
line-wrap fall exactly inside the stub's fixed anchor phrase, splitting it
across two lines and hiding it from the single-line grep the convention
depends on. Rewrapped those four — content unchanged, only the break point
moved — and the count now matches. Fixed in the same pass, whitespace-only:
10 of the phase-4 T-stubs were missing the blank line every other stub in
this file carries before its following `## ` heading. Both fixes, and the
full words-per-class accounting above, are recorded in the companion
file's new "Reconciliation" section. `python -m tools.cli state` renders
clean; the full suite is green.

**Stood down, not notified:** the two peer sessions coordinating around
this migration — `llm-market-identifier-21` (parked on this rewrite to
make its go-skill rule-32 move) and `llm-market-identifier-c0`
(rule-delivery, which left rule 32 and its own closeout open pending this
commit) — both stood down before it landed. Nothing live to notify; the
controller carries forward whatever either left open.

**Ruled:** the §6.5 promotion bar is written into `CLAUDE.md`'s "What
lives in a theory, and what gets elevated" (§6.7) as of this commit and
**binds from here forward**, per the user's 2026-08-29 ruling — a log
entry is earned by a fact that would change how a session that never
touched this theory would act; a result inside one theory is a headline
and a pointer into its `NOTES.md`, never a copy. See
`docs/superpowers/specs/2026-08-29-enforcing-surfaces-log-classification.md`
for the full row-by-row accounting this entry summarizes.

---

## 2026-08-30 — rule delivery complete: ten task-time rules live in their skills (spec 7, phases A+B)

**Did:** Moved the tenth and final task-time rule — `notes-theory-log-split`,
the `NOTES.md`/`RESEARCH_LOG.md` split — into `go`'s §4 "Log it", closing
phases A and B of the rule-delivery plan
(`.superpowers/sdd/2026-08-29-enforcing-surfaces-rule-delivery/`). All ten
rules named in ruling 7 (task-time rules get one home — their skill, not
CLAUDE.md) now live inside a `<!-- rule: slug (moved from CLAUDE.md § ...,
2026-08-29) -->` marked block in the skill that owns the activity:

- `backtest-web-search-off`, `structural-gate-conditions`,
  `record-the-tier-claim` → `backtest-theory`
- `judge-blind`, `batch-and-dedupe`, `buckets-from-deep-stage` → `find-edge`
- `facts-are-data`, `search-the-registry`, `revisit-angle` → `propose-theory`
- `notes-theory-log-split` → `go`

`tests/test_conventions.py::test_every_moved_rule_lives_in_its_owning_skill`
is the guard: it walks all ten manifest entries and fails at the commit
that drops a marked block or lets CLAUDE.md's skill map stop naming the
owner, so a rule losing its single home breaks the suite rather than
sitting undetected. Full suite green: 1095 passed, `test_conventions.py`
15 passed. Ruling 7 flipped `binding` → `implemented`.

**Learned:** `wc -w CLAUDE.md` now reads 6,414 words, against the
6,671-word post-consolidation baseline the spec's §0 names — a net
**-257** words, even though every move left a one-line pointer sentence
behind. The ten rules' bodies (prose, code fences, worked-example
reasoning) outweighed the section furniture and full paragraphs they
replaced.

**Next:** Nothing outstanding on this spec. `backtest-theory`, `find-edge`,
`propose-theory` and `go` each now carry their moved rules alongside their
existing task guidance; a future session extending one of those skills
should keep its marked block(s) intact rather than editing around them.

This entry is a repo-level mechanism, not a theory result, so it passes the
§6.5 promotion bar on its own terms: the manifest test and the single-home
ruling change how any future session editing CLAUDE.md or a skill would
act. See this file's 2026-08-29 "Carry chains shipped (spec phase 6); rule
delivery nine-tenths done (phases A/B)" entry for the mid-flight status
this completes, and
`.superpowers/sdd/2026-08-29-enforcing-surfaces-rule-delivery/` for the
full task-by-task plan.

---

## 2026-08-30 — snapshot store overhauled: dedup intervals, zlib payloads, own database file (spec 5.2 complete)

**Did:** Shipped spec 5.2's remaining phases (2-4) end to end against the
live ledger, per the plan at
`docs/superpowers/plans/2026-08-30-snapshot-store-overhaul.md` (`5771590`):
write-path dedup (`72b1964`, review fix `be3c219`), the retro-dedup command
(`fe351d0`), zlib compression (`1e2f7f0`), and the split into its own
attached file (`42eb40c`, rerun-safety fix `db1efbd`). Spec
`docs/superpowers/specs/2026-08-29-enforcing-surfaces-design.md` §5.2 now
carries a done-marker naming this entry as its live-run record.

**Measured (live run against `db/market_edge.db`, before/after):**

- **Baseline, pre-work:** 1,390,328 rows across 13 batches; file
  5,539,033,088 B, grown to 5,623,709,696 B by split time; payload text
  3,047,953,692 B raw_json + 68,859,034 B event_json; a fresh ledger backup
  taken first, gzipped to 4,242,630 B.
- **Retro-dedup:** deleted 539,827 rows (38.83% of the pre-work total) —
  matching the design gate's predicted byte-exact-duplicate rate to two
  decimal places, not just in the right neighborhood. Kept 850,501 rows
  across 202,690 distinct markets.
- **Compression:** all 850,501 surviving rows converted; payload bytes
  1,942,666,499 -> 834,288,422, ~2.33x. **Honest miss:** the spec projected
  ~8x; that estimate assumed bulk compression over the whole corpus.
  Per-row zlib against ~2 KB JSON documents, already stripped of
  duplicates by the retro-dedup pass, tops out around 2.3x — a small
  document compresses worse per-document than a large concatenated blob
  would. Zero information loss either way; the ratio is a
  resource-planning number, not a correctness one.
- **Split:** the same 850,501 rows moved into `db/snapshots.db`. Main file
  5,623,709,696 -> 66,539,520 B (66.5 MB); `db/snapshots.db` 1,292,386,304 B
  (1.29 GB). Net 5.62 GB -> 1.36 GB total (76% smaller), and the file that
  actually matters for disaster recovery — the ledger — is now 66 MB and
  backs up in seconds instead of being inseparable from a 5+ GB blob.
- **End state:** `db stats` renders both files; `state` renders clean; the
  board rebuilds correctly (110,628 markets at `2026-08-29T13:14:32Z`);
  full suite green at 1,125.

**New invariants a future session must know:**

- A `market_snapshots` row is a validity interval, `[captured_at,
  last_seen_at]`, not a point-in-time snapshot — a market present but
  unchanged extends the existing row's `last_seen_at` rather than writing
  a new row.
- "Unchanged" is decided by byte-exact comparison of the **full** payload
  (`raw_json` + `event_json` concatenated) — the design gate ruled this
  explicitly rather than the five material columns, so an edit to rules
  text or `close_time` alone still forces a new row.
- **Every** read of `raw_json`/`event_json` must go through
  `tools.snapshot.payload_text` — the cell's SQLite storage class (`TEXT`
  for legacy plain rows, `BLOB` for zlib-compressed ones) is now the codec
  discriminator, and a direct `json.loads(row["raw_json"])` breaks the
  moment it hits a compressed row.
- The store lives in `db/snapshots.db`, `ATTACH`ed as `snapdb` by
  `tools.db.connect()`; unqualified queries against `market_snapshots` keep
  resolving there unchanged, because main no longer has a table by that
  name.
- `db split-snapshots`, `db dedup-snapshots`, and `db compress-snapshots`
  are all idempotent and rerun-safe — each was proven so by a dedicated
  test (`db1efbd`'s fix closed the one real gap found: a second
  `split-snapshots` call, or a process that died between the `DROP TABLE`
  and the `VACUUM`, used to crash rather than no-op).
- Backup cadence is per `tools/README.md`'s "Backup cadence" section: the
  ledger backs up before any schema migration or destructive command and
  at the start of a session that will settle or migrate; `snapshots.db`
  gets no automatic backup, copied by hand only if a study needs a
  specific historical window preserved.

**Pointers:** the full task-by-task plan is
`docs/superpowers/plans/2026-08-30-snapshot-store-overhaul.md`; the four
study write-ups repointed to read through `payload_text` are
`studies/2026-08-27-calendar-arb-firing-rate/STUDY.md`,
`studies/2026-08-29-side-asymmetry-extension/STUDY.md`,
`studies/2026-08-29-structural-arb-violation-liquidity/STUDY.md`, and
`studies/2026-08-29-structural-gate-payload-version/STUDY.md`.

This entry is a repo-level mechanism plus a data-source constraint change
(every `raw_json`/`event_json` reader's contract changed, and the store's
physical location changed under `ATTACH`), so it passes the §6.5 promotion
bar on its own terms — a session that never worked on this overhaul still
needs the interval semantics and the `payload_text` rule the moment it
touches a snapshot row.

---

## 2026-08-30 — first forward settlements land; two scoring rulings; four sessions collide

**Did:** Ran the `go` floor against the shared 104,304-market board (pulled
19:22Z by peer session `ec`; nobody re-forced). Settled **10,460** awaiting
tickers → **1,541 new settlements**, the first forward evidence three
theories have ever had. Recomputed scores, bucket rates and slice segments.
Ran `no_side_premium` v1 (63 candidates), `structural_arb` v4 (**ran clean,
0 candidates** — 1,411 flag candidates all removed as
`not_mutually_exclusive`), `calibration_harvest` v2 (9,777), and
`insider_judgment` v4 stages 1-4 (700 screened → 309 events → 21 survivors).

**Learned:**

1. **Two settlement days is not a measurement, and this repo's headline
   surface cannot tell you that.** `calibration_harvest` v2 went to n=1,521
   settled with `calibration_edge_net` −4.76 and `clustered_se` 1.31 —
   t ≈ −3.6, which reads as decisive. The entire corpus is **two settlement
   days**. At 1 df the 95% critical value is **12.71**, so the honest p is
   ≈ 0.19. `score.settlement_day_clusters` already computes `n_days` and
   the CLI already emits it; nothing was broken except the reading. Ruling
   **14** now binds: under 3 settlement days, report "not yet measurable"
   and take no lifecycle action.

2. **Observation rows are not predictions** (ruling **13**). Every settled
   `calibration_harvest` row has claimed edge ≤ 0 — 1,478 at exactly 0.0
   carrying the rationale *"Recorded so the cell accrues settlements; not a
   recommendation"*. Its aggregate calibration edge measures the **board**,
   not a decision procedure, and the n=20 `under_review` rule would
   otherwise have flagged a theory that has never made a prediction. Its
   pre-registered kill criterion is **not** met either: zero of 18 cells
   clear `n>=30` **and** `n_days>=8`, so the bar has not been tested, let
   alone failed. Theory stays `testing`.

3. **`opportunities.run_id` is "first sighted", never "which run decided
   this".** A position's run id freezes at first sighting, so a re-run's
   rows are invisible to any query keyed on it. `collect.cell_rates`
   documented this trap for collection runs; it bit
   `theories/calibration_harvest/forward_cells.py` (written wrong, fixed
   same day, now reads `opportunity_attempts`) and a peer session hit it
   independently on `insider_judgment`'s judged run ids the same afternoon.
   Third occurrence — treat it as a standing hazard of the position rollup,
   not a one-off.

4. **The repo's best-evidenced result is real, and it is not on any running
   theory.** `insider_judgment` **v3**'s registered slice
   `strong-moderate-no` is READY out-of-sample: n=321, 89 event clusters,
   43 settlement days, win 0.916 vs implied 0.865. Verified independently
   from the ledger. Report it as a **pair**, because the two available
   statistics are weighted differently and mixing them flatters it:
   row-weighted **+4.31 net** with event-clustered t **1.79**, or
   day-weighted **+8.06** with day-clustered t **4.38**. Quoting "+4.31,
   t=4.38" pairs a row-weighted estimate with a day-weighted error bar. The
   gap between the two also says heavy days did *worse* than light days,
   which is a caveat and not a bonus. It is invisible by default: `score
   report` and `slices report` scope to the current version (v4, n=2), and
   v4 is a `breaking` bump, so v4 is not entitled to this evidence and has
   not adopted the NO-side rule.

**Next:** (a) `insider_judgment` v2→v3 is recorded `breaking` with
justification *"pre-dates the carry ruling; not adjudicated"*, while its own
RUNBOOK says stages 1-6 never changed between them — a `carry` candidate
that would pool the v2 live cohort, needing a replay as proof, not the
assertion. (b) `calibration_harvest`'s binding constraint is settlement
days, which only calendar time buys. (c) A defective run of mine
(`run_id='live'`, 9,777 attempts / 2,018 positions recorded with no
categories and no cell_rates) is quarantined by id in
`forward_cells.EXCLUDED_RUNS`; a ledger DELETE was refused by the
permission layer and needs the user's call.

Theory-level detail is in `theories/calibration_harvest/NOTES.md`
(2026-08-30). This entry is here rather than there because rulings 13 and
14, and the run_id hazard, change how a session that never opens that
theory would read any score in this repo.

## 2026-08-30 (item 3) — entry timing: a committed bar produced a false confirmation

**Did:** Asked whether entry timing has a general direction, on 8,268
paired rows already sitting in `series-bias-mining`'s `collect.db` (both
entry prices stored, so zero marginal fetches). Pre-registered and
committed the bar first (`fc52527`), ran it second (`33dbdd4`). Study:
`studies/2026-08-30-entry-timing/`. Also resumed that study's stalled
phase-2 collection in the background — 228 of 840 series were priced, both
sessions that owned it had exited, and Kalshi archives settled markets out
of reach ~60 days after close.

**Learned:**

1. **A pre-registered bar returned a clean confirmation that was an
   artifact, and only the exploratory breakdown caught it.** The primary
   statistic differenced two entry points defined by *different kinds of
   rule* — one relative (25% of scheduled lifetime before close), one
   absolute (24h before close). Which is *later* therefore depends on the
   market's lifetime, and it inverts below 4 days: **5,156 of 8,268 rows,
   62.4%**. As written the test read **−2.41 pts, t = −3.85** and scored
   itself CONFIRMATORY in the predicted direction. Re-oriented so every
   difference reads later-minus-earlier, it is **+2.97, t = +4.79** —
   powered, significant, opposite sign. **Reported as a FAILED
   PREDICTION**, which is the whole reason the sign was fixed in advance.

   **The generalizable rule, and it is new:** *when two measurement points
   are defined by different kinds of rule — one relative, one absolute —
   verify their ordering is constant across the population before
   differencing them.* Pre-registration does not protect against this;
   the bar was committed, honest, and wrong. What caught it was reporting
   the exploratory buckets next to the primary test.

2. **Entry timing on a fixed side is worth about half a point, which is
   nothing.** On the 92% of rows where the same side is bought at both
   points, later-minus-earlier is **+0.56 (t = 1.86, MDE 0.85)** — below
   the 2.0-pt floor the bar declared actionable. Waiting does not buy a
   better price on the bet you were already making, so **entry should
   follow liquidity and spread, not a timing rule** — in this population.
   That is the genuinely useful half of the study and it is the
   *secondary* statistic, not the headline.

3. **The entire pooled effect is the 8% of rows whose favorite side
   flipped (+31.43, t = 4.56).** There the later entry simply buys
   whatever the market now favours, and the later favorite wins far more
   often. That is price informativeness, not a harvestable edge — nobody
   knows in advance which markets will flip. A first, buggy pass had this
   backwards and looked like an overreaction signal; it is the opposite.

4. **This does not contradict `insider_judgment`'s late-entry penalty**
   (+5.10 first-qualifying vs +2.32 late) and must not be read as doing
   so: that is LLM-selected NO favorites at mean ask 0.863; this is a
   sports-dominated small-series tail. Two populations disagreeing about a
   half-point effect is a reason not to generalize either.

**Next:** the phase-2 collection is running and will add 612 series
including politics and weather — a genuinely fresh population for any
follow-up, and the one this study's own limits section names. Two
independent populations measured favorites as overpriced today
(`calibration_harvest` forward −3.88 gross; both entry points here −5.19 /
−7.60), but **neither was collected to answer that question and neither may
be cited as evidence for it** — a powered, pre-registered test belongs in
its own study, and `no_side_premium` already holds the side-level version.

This entry is here rather than in a theory's notes because rule 1 changes
how any session in this repo should write a pre-registration, and because
rule 2 is an execution finding that applies to every theory's entry rule,
not to one.

## 2026-08-30 (cont.) — parlays: a real +7 pt markup nobody here can trade, and the cross-event arb channel closes

**Did:** Took the theory-backlog lane (session `8e` ran the §2 floor; we
collided on ownership four times before settling it). Ran the mandatory
rule-0 measurement on backlog spec #8 `parlay-fade`, which turned into a
full study: `studies/2026-08-30-parlay-markup/`.

**Learned — three things a session that never touches parlays still needs:**

**1. The cross-event combo-vs-leg channel is measured and flat.** Rule 0
of the backlog index told every session that cross-*event* relative value
"remains open". One channel of it is now closed by the strongest test
available. Kalshi's 92 listed `*COMBO` markets are 2x2 partitions whose
legs sit in *separate* events, so `{DD, DR}` is an **exact synthetic** of
the standalone leg — an arbitrage identity holding whatever the
correlation, unlike a product-of-legs test. 34 constructions at executable
prices with real fees: **1 profitable at zero buffer (+0.05 pts), 0 at a
1c/leg buffer**, and the most liquid case had the *smallest* gap. Rule 0
updated (`93de418`) to narrow the open claim rather than erase it: what
remains open is cross-event *forecast* disagreement, where no identity
exists — a weaker claim than a violated identity.

**2. A large, unknown-to-this-repo data source exists, and it is
perishable.** `/multivariate_event_collections` is **public and
unauthenticated**. Settled parlays carry `mve_selected_legs` (exact leg
tickers **and sides**), `last_price_dollars`, `open_interest_fp` and
`result` — a complete tier-A input with no model in the path. 1.7M+
settled cross-game rows collected before the sweep was stopped. Kalshi
ages settled markets out at ~60 days, so this window cannot be recovered
later.

**3. The finding, and why it is not a theory.** Cross-game parlays trade
**+7.06 pts above the product of their legs** (day-clustered over 4
creation slates, t=+17.47, MDE 1.13 against a 3pt floor, all four days
positive at 6.01–7.85). It survives the artifact most likely to have
manufactured it — leg spreads compound multiplicatively — at **+6.64 pts**
when every leg is priced at the side actually payable. But `active_quoters`
is **0 across all 2,134 associated events in all three open collections**:
capturing a markup means *selling* parlays into RFQs answered in seconds,
which a manual bettor cannot do. The spec's own kill criterion #7 called
this. **A real mispricing this user probably cannot trade** — worth
knowing, poor basis for a theory.

**Two methodological facts that generalize beyond this study:**

- **A row count can be one cluster wearing a crowd's clothes, and the
  arithmetic can prove a design is hopeless before you run it.** Phase 1
  (calibration against realized outcomes) put 395,692 rows into **18
  day-clusters** — every parlay on a slate shares legs, so they win
  together. Between-day SD 17.35 pts ⇒ the 3pt floor needs **262
  settlement days**; Kalshi retains ~60, capping the achievable MDE at
  **6.3 pts**. Outcome-based calibration of parlays is *structurally*
  underpowered here and no further collection fixes it. The fix was to
  switch to an **outcome-free** statistic (price vs product-of-legs),
  which the day-level common shock cannot enter at all. Worth asking of
  any new design: *is there an outcome-free form of this question?*
- **Report a failed secondary as failed, and do not switch units.** The
  bar predicted markup magnitude **grows** with leg count. In points it
  shrinks hard (`corr = −0.920`: +10.50 at 2 legs, +1.75 at 12). In
  *ratio* terms it grows (+0.682) — but that framing was not
  pre-registered and is a hypothesis for a separate test, not a rescue.
  Switching metrics after seeing the sign is what `calibration_harvest`
  was retracted for the day before. The points reading is also the
  economically relevant one for a fader, so the usable form **inverts**
  both the spec and its source paper: the largest absolute edge is in
  **short 2–5 leg parlays**, not long lottery tickets.

**Next:** the study's open items are listed in its own `STUDY.md` (the
`last_price`-vs-`created_time` timing gap, ~10% unpriceable-leg
exclusions, an unrun `same_game` control that would be weak anyway since
correlated legs *should* show a positive gap that is correlation not
markup). `parlay-fade` is `investigating` in the registry with all of it
recorded. The question that decides whether it ever becomes a theory is
**execution, not measurement**: whether any resting-order path exists to
sell parlays without answering an RFQ.

## 2026-08-30 — go restructured: the promotion key decides what the user is told

**Did (user-directed):** Implemented
`docs/superpowers/specs/2026-08-30-go-session-structure-design.md` end to
end. The organizing principle: anything two sessions should decide the
same way now has a structural surface the session cites, never a
per-session judgment call.

- **`docs/promotion-key.md` (v1) + `tools/promotion.py` + `cli promote`**:
  six named rungs (R1 RECOMMENDED, R2 RISKLESS, R3 PROVISIONAL, R4
  ACCRUING, R5 MEASURED-AGAINST, R6 CONTROL) decide report-worthiness
  mechanically, on the same `slices.ranking_segment` row ranking already
  uses (chain pool, no hand-mixed score rows). R1/R3 recompute at today's
  ask and check executability; rulings 13 and 14 are encoded as rungs.
  Sessions cite rungs; disagreement is a dissent in the report, never an
  override. `promotion.orphaned_evidence` surfaces ready slices with no
  bet path at the current version — verified live: it finds
  insider_judgment v3 `strong-moderate-no` (89 clusters, 43 days, +4.31
  net) orphaned under the breaking v4 bump, so the repo's best-evidenced
  result is now a standing escalation instead of invisible-by-default.
- **The go skill is rewritten** around six phases: 0 peers (one
  authorized orientation message dividing floor ownership — carve-out to
  the no-unprompted-messaging rule, user 2026-08-30), 1 orient, 2 the
  floor (settle with `score report --save`, then every running theory by
  its RUNBOOK through every stage, recording everything), 3 promote, 4
  the value menu, 5 log & a five-section report contract (Floor / Bets /
  Activity / For your ruling / Queue). Phases 0-3 complete and are
  reported before any menu work. §7 binds: **never ask — escalate into
  "For your ruling" and keep working**; the only exits are an empty menu
  or everything-user-blocked.
- **RUNBOOK.md is now a required, standardized surface** (Stages / Run /
  Record / Report / Skip): written for `no_side_premium` and
  `structural_arb`, retrofitted onto the other four, conventions-tested
  (`tests/test_db_discipline.py`) so a theory cannot sit in a scannable
  status without a written run procedure.
- **DB discipline is enforced by tests, not memory**: AST-based guards —
  no direct `list_open()`, no `get_board(force=True)` outside board.py,
  every snapshot payload read through `payload_text`. The payload guard
  caught four live offenders on its first run (all four study scripts
  reading `market_snapshots` with direct `json.loads` — latent breakage
  on zlib rows since the 5.2 overhaul); fixed in the same commit.
- **`score report --save`** persists per-version scores (`save_score`
  finally has a production caller), closing the carried gap where `state`
  EVIDENCE rendered "scores never written" against numbers every session
  computed by hand. find-edge adopts the evaluator and rung vocabulary,
  so go and find-edge can no longer rank or report the same candidate
  differently.

**Learned:** the guard-tests-find-real-bugs pattern held immediately —
the payload_text convention was two days old, already documented, already
violated in four places nothing would have caught until a study rerun
crashed months after the archive window closed.

**Next:** first go session under the new floor exercises the whole path
(peers -> runbooks -> promote -> report contract); the deferred
`session_claims` table triggers only if sessions collide under the
phase-0 protocol.


## 2026-08-31 - go floor: 850 settlements, all four theories run, 0 promotable bets, slice orphan escalated again

**Did:** Full go floor. Two live peer sessions found at start; orientation
sent per the go phase-0 protocol, no claims returned, all floor items run
here. Settled 850 (559 no / 279 yes / 12 scalar); first score save for
all four running theories (scores table was empty before today).
structural_arb v4 ran clean (0 recorded; see its NOTES). no_side_premium
v1 recorded 66 (cell A 10 -> R4, cell B 56 -> R6). calibration_harvest v2
recorded 9,269 observation rows -> R6. insider_judgment v4 ran all six
stages (24 events judged by opus subagents, 35 markets, endorsed 0; see
its NOTES). Promotion key v1 over all runs: zero R1/R2/R3 - an honestly
empty bets table.

**Learned:** no_side_premium cell B (avoid-YES-favorites) is accruing in
the pre-registered direction: OOS n=64, -8.0 net (the avoid claim wants
negative), 54 clusters, but only 4/5 settlement days toward its gate.
Cell A is nearly empty (n=2). insider_judgment's orphaned-evidence
escalation fired mechanically for the second day: strong-moderate-no
proven at v3 (+4.31 net OOS, n=321/43 days) with no bet path at v4 -
user ruling needed on adoption. calibration_harvest settled rows sit at
-2.6 net day-clustered over 3 days (SE 2.0) - below ruling-14's
measurability floor, not yet a verdict on the cells.

**Next:** user rulings on the slice orphan; deadline_drift is the top
unbuilt spec (classifier at 12% vs 10% bar, round 5); cell-A drought in
no_side_premium worth a look (population screen finds few 0.85+ mention
NO favorites).

## 2026-08-31 - bug-window residue: pre-fix attempts keep 'screened' under non-screened positions; two theories repaired, one escalated

**Did:** Reconciling no_side_premium's screened pool against its cell-a
slice exposed 112 attempts recorded 2026-08-28T23:45Z..2026-08-29T02:30Z
(between the attempt-table migration and 37f0f2a's interpret-stamps-
attempt fix) whose disposition never got stamped: rejected positions,
screened attempts. Repaired the two deterministic cases with the intended
value written in the row itself: no_side_premium 106 (avoid-cell marker)
and structural_arb 6 (dust rejects, the theory's only non-screened
disposition). Re-saved both theories' scores. insider_judgment's 280
same-window attempts are NOT repaired - mapping each to that day's
final-review verdict needs per-day reconstruction, and its pools feed
interpretation_value - escalated for a ruling instead.

**Learned:** disposition pools for rows recorded before 2026-08-29T02:30Z
can misstate what a run decided; slice segments (predicate-based) were
never affected. When a score pool and a slice pool disagree, the slice is
the one reading recorded facts.

**Next:** ruling on the insider_judgment attempt repair rule (stamp
pre-fix screened attempts with their position's same-day interpretation;
never touch attempts whose position was re-judged later).

## 2026-08-31 - backtested evidence counts as forward evidence (user ruling 15)

**Did:** Implemented the user's ruling that a backtested edge is evidence
exactly as a forward-settled one is -- for a registered slice as much as
for a whole theory. Before this, `tools/slices.py` filed every replay of
already-settled history as `in_sample` "by default, however recently it
ran", so a sub-theory could carry a clean tier-A/B backtested edge and
still promote as R4 ACCRUING, invisible to the user. Now a tier A/B
replay feeds a slice's out-of-sample score and its readiness gates with
no designation required. Promotion key v1 -> v2; `mined_from_run_ids`
added to `theory_slices`; `n_backtest` added to every segment score and
disclosed on every R1/R3 promotion.

**Learned:**

1. **Flipping that default silently hands a slice back the rows that
   suggested it.** The date test was doing double duty -- "is this
   forward evidence" *and* "is this the data the hypothesis was fitted
   to" -- and only the first was intended. `strong-moderate-no` proved
   it live: with the new default and nothing declared, its out-of-sample
   pool jumped from n=321 to **n=560** (166 clusters, 52 days) because
   `backtest-2026-08-26-insider-judged-s200`, the run its own `origin`
   names as having *generated the rule*, started vouching for it. The
   guard had to become explicit at exactly the moment the default was
   removed, not later.
2. **The declaration can only ever restrict, which is what makes a
   post-registration write safe on an immutable row.**
   `slices.declare_mined_from` is additive and refuses withdrawal, so a
   slice may give up more of its own evidence and never reclaim any.
   That invariant is the whole argument for touching a registered slice
   at all; without it this would be an edit to a pre-registration.
   Declaring s200 restored `strong-moderate-no` to exactly the n=321 /
   89 clusters / 43 days / +4.31 net this log has been citing all along
   -- the registration now means in data what it always said in prose.
3. **An untiered replay vouches for nothing.** Only a run recorded in
   `backtest_runs` at tier A or B counts; unknown provenance resolves
   against the slice, exactly as a settlement on the registration day
   does. Without that, any row written with `run_mode='backtest'` and no
   tier record would have become evidence for free.

**Next:** `go` is being restructured into two phases (floor, then
research) and phase 1's report contract is drafted; the ruling above is
what makes a sub-theory's backtested edge reportable at all, which that
draft depends on. `insider_judgment`'s orphaned-evidence escalation is
unchanged and still needs a user call on adoption at v4.

## 2026-08-31 - evidence carries across versions; sub-theories versioned with parents (user ruling 16)

**Did:** Implemented three linked user rulings. (a) Settled outcomes and
tier A/B replays are the same kind of evidence and pool -- for theories
and sub-theories alike. (b) A version bump no longer invalidates evidence
by itself: `continues` is the new default bump kind and pools forward;
only an explicit `breaking` resets. (c) Sub-theories are versioned with
their parent -- `save_segment_scores` pools the version chain, and every
score records its span in `pooled_versions` and its replay share in
`n_backtest`.

**Learned:**

1. **The old default had discarded every theory's history, and nobody
   had adjudicated any of it.** All seven multi-version rows in this repo
   read `breaking` with the justification *"pre-dates the carry ruling;
   not adjudicated"* -- the absence of a finding, frozen into the schema
   because `breaking` was what you got for saying nothing. Reclassifying
   exactly those rows (`theories.reclassify_bump`, which appends its
   reason and never erases the original wording) relinked
   insider_judgment to [1,2,3,4] and structural_arb to [1,2,3,4].
2. **That resolved the repo's longest-standing escalation mechanically.**
   `strong-moderate-no` had been proven at v3 and orphaned at v4 for
   three sessions running, reported to the user every time. It is now
   READY at the current version: n=325, 89 event clusters, +4.37 net,
   with the complement separately at -2.51 -- the partition doing exactly
   what it exists for. `promotion.orphaned_evidence` returns empty.
3. **Widening what MAY be recorded is not rewriting what WAS.** The
   `theory_versions` CHECK migration accepts `continues` but carries every
   legacy row across unchanged; the reclassification was a separate,
   explicit, per-row act with its own audit trail. Worth keeping distinct
   -- a migration that silently reinterpreted old governance rows would
   be indistinguishable from tampering.

**Next:** phase 2 of the `go` restructure is still undefined. The
sub-theory partition is now visible in `state`, so a session can see
strong-moderate-no without asking -- worth watching whether it produces
an R1 on the next floor.

## 2026-09-01 - series-bias pass 3: the breadth problem is solved, and the negative control caught the next one

**Lane:** new-theory, focus `series-bias-mining`. Chosen over the
`insider_judgment` v5 adoption ticket on one argument: the adoption
decision is worth exactly as much next week, while this study's input
*perishes* — Kalshi archives settled markets out of its API ~60 days
after close, and the broad sweep was 76% done and stalled since 08-30.

**Did:** Resumed the phase-2 price sweep (658 -> 664 of 840 series,
~71k observations). Pre-registered pass 3's analysis bar in `STUDY.md`
and committed it **before** computing any per-series number, then built
`pass3.py` with 10 fixture tests and ran it once against a frozen
snapshot. Verdict by its own bar: **NOT MEASURED** — 347 series tested
against a floor of 30, but median MDE 12.16 against a bar of 8.0.
Diagnosed the nine flags, found the cause, fixed the collector, filed
two tickets and pre-registered pass 4.

**Learned:**

1. **347 series tested, against pass 1's seven and pass 2's one — and
   it still is not measured.** The breadth problem this study has
   carried since 08-25 is genuinely solved; the collector works and is
   resumable. What breadth did *not* fix is power: median MDE 12.16
   says the median recurring series cannot resolve a 3-6pt effect from
   60 days of history, and **more series will never fix that — only
   longer per-series history will.** That reframes the study's real
   output as a *standing capture* rather than another one-shot sweep,
   which is the shape `deadline_drift`'s RUNBOOK already uses.

2. **The negative control did its job for the first time, and that is
   the session's most valuable result.** Nine series cleared all four
   gates at -10 to -45 points. None is reported as a finding, because
   5 of 11 mention_family control series tripped the gates too — the
   same ten-series control pass 1 ran on the screened population with
   *all ten* non-significant. Same series, same statistic, different
   population, so what moved is the population. Pass 1 wrote that a
   flag among the control means the guard is too loose; this is the
   first pass that had to cash that sentence, and it is why a -45pt
   "bias" got written up as an artifact instead of a discovery.

3. **A population without a liquidity filter cannot be mined for
   bias.** The gap grows monotonically with the ask: -2.6pts at
   0.50-0.70 rising to **-18.6 at 0.980-0.995, where 23% of the
   population sits**, priced 0.987 and realizing 0.801. That is an
   absent offer, not a mispricing. Passes 1-2 never saw it because
   their population came through `insider_bias/screen.py`
   (spread <= 0.07, volume >= 500); pass 3 widened the population and
   threw the liquidity filter out along with the screen. Capping the
   ask moves the control from 5/11 to 2/9 — so extreme asks are about
   *half* of it, and the residue was undiagnosable from what had been
   stored.

4. **The root cause was a data-conventions failure, and it is the
   worked example of why that rule exists.** `candlesticks` returns
   `yes_bid_close`, `volume` and `open_interest`. `collect.py` fetched
   all three, used the bid to pick the favorite side, and persisted
   only the derived ask — distilling at write time and discarding
   exactly the fields that later decided whether the distillate meant
   anything. CLAUDE.md's "raw payloads over distillates" is aimed at
   precisely this, and the cost is not recoverable at leisure: the
   fields can only be re-derived from candles inside the archive
   window. **Stopped the running sweep mid-flight to land the fix**,
   because every further series priced without them would have been
   another to re-fetch against a closing window.

5. **An SE-based power floor is not outcome-neutral, and pass 3
   reversed pass 2 on it.** For binomial data variance is p(1-p), so an
   MDE floor preferentially admits extreme-win-rate series — exactly
   where a large gap can sit. Pass 2 found this itself: its one flag
   was the most extreme-win-rate series in its population *and* had
   the lowest MDE. Pass 3 admits on counts alone and *reports* the
   win-rate composition by stratum (0.796 at MDE<=8 vs 0.732 above)
   rather than filtering on it. Cost: Holm over 347 series. Checked
   before running that this does not exclude an effect of the size
   being looked for — pass 2's KXLOWTLV at p<1e-5 would still clear a
   family that size.

6. **Carried candidates, both signs fixed before looking.** `KXRT`
   predicted negative: -2.76, t -0.76, p 0.47 — right sign, nowhere
   near significant, **not confirmed**, still a hypothesis. `KXLOWTLV`
   predicted positive: did not clear the count floors here, so
   **untested, not refuted**. Neither is re-read in light of the
   result.

**Next:** Pass 4 is pre-registered in `STUDY.md` — the pass-3 bar plus a
tradeable-book requirement at passes 1-2's own thresholds
(spread <= 0.07, volume >= 500), with the negative control as the
**acceptance test** rather than commentary: if mention_family still
trips under the filter, the population is still wrong. Two ticketed
prerequisites, and the second is the more urgent of the two because it
is work already done that expires: `2026-09-01-series-bias-sweep-finish`
(~180 series left, all large) and
`2026-09-01-series-bias-backfill-liquidity` (the 660 series priced
before the fix read NULL for spread/volume; pass 4 cannot run on them
until backfilled, and the candles expire).

**Untouched, for whoever takes the theory lane:** the
`insider_judgment` ticket to adopt `strong-moderate-no` at v5 is still
open and is the best-evidenced unclaimed work in the repo (+4.37 net,
89 event clusters, 43 settlement days, READY at v4).

## 2026-09-01 — floor (session `llm-market-identifier-cc`, claim 1)

**Did.** First floor ever completed (`floor status` had "no floor has
ever completed"). Board pulled 105,104 markets. Settlement pass re-quoted
10,715 awaiting tickers in 107 chunks and landed **775 new settlements**
(ledger now 14,043). Scored and saved every segment for all four running
theories. Ran all four per their RUNBOOKs, every stage:
`insider_judgment` v4 all six stages including the opus analysis subagent
and a stage-6 final review; `no_side_premium` v1 all four;
`calibration_harvest` v2 stage 3 twice; `structural_arb` v4 all five.
18,558 rows recorded. Report at `user_reports/2026-09-01/README.md`.

**Learned.**

1. **No bets today, and the near-miss is instructive.**
   `KXPRESSSECANNOUNCE-26AUG-SEP08` NO matched `strong-moderate-no`, the
   repo's best-evidenced segment (90 clusters, +3.757 net, chain 1–4),
   and the final review recommended it — but `promote` returned **R4**,
   not R1, because the position was first seen at 0.85 on 2026-08-29 and
   today's ask is 0.92, recomputing the claim to −4.62 pts. That is now
   the *third* distinct way a slice-matching NO candidate has failed to
   reach the user (gate removed it / final review declined it / price
   moved first). Worth someone asking whether the screen systematically
   finds these after the move.

2. **The orphaned-evidence escalation is over.** `promote` ranked a v4
   candidate directly on `slice:strong-moderate-no` with
   `chain_versions=[1,2,3,4]` — the 2026-08-31 relinking ruling took
   effect. `insider_judgment`'s RUNBOOK still says the opposite and still
   mandates escalating it every session; ticketed, not fixed (theory
   lane).

3. **`calibration_harvest` double-counts every market, every floor.**
   Its runbook says the two stage-3 runs cover distinct complete
   populations; `screen()` has no population filter — `categories` is
   only a cell-key *label* map. Measured: 9,247 attempts per run, **100%
   overlap**, 6,944 with an identical cell key. `politics|*` and
   `weather|*` cells are clean; the `other|*` cells (which hold nearly
   all the data) get the same market twice plus each run labelling the
   other's population as `other`. Same failure `EXCLUDED_RUNS` quarantines
   the 2026-08-30 run for. Present since 2026-08-31. Ticketed with both
   candidate fixes; quarantine decision left to the user.

4. **`tickets new --theory` writes to a phantom folder for any
   family-nested theory.** `ticket_dir` hardcodes
   `theories/<slug>/tickets`, ignoring the registry `path`, so
   insider_judgment's tickets land in `theories/insider_judgment/` — a
   directory containing nothing but `tickets/` — while the theory itself
   lives at `theories/insider_bias/insider_judgment/`. Invisible from the
   supervisor side because `tickets list` globs; breaks the expert
   contract exactly. Ticketed.

5. **The pre-taped-TV sub-case got talked down for the first time.** The
   subagent graded Big Brother 28 `strong`; final review lowered it to
   `moderate` and declined, because BB feed spoilers are republished
   same-day by Parade/GoldDerby/TVInsider and this market's traders are
   those readers — the thesis is asymmetry, not expertise. Verification
   also broke the subagent's stated block (nominees were LaTrice, Taylor
   and **Yash**, with Yash winning the veto). If that reasoning is right
   it applies to every live-feed reality show, which is a meaningful
   narrowing of the theory's flagship family.

6. `no_side_premium` moved hard on settlements: aggregate −7.54 → −0.16
   (n 66 → 129). `cell-b-yes-avoid` is READY at −0.98 — still confirming
   its avoid claim, but far weaker than the −3.9 it was written against.
   `calibration_harvest` cells: **0 of 21 measurable**, best is 4
   settlement days against a bar of 8.

**Next.**

- Fix the `calibration_harvest` double-run (maintenance ticket) — it is
  corrupting the cell grid every day it runs, so it compounds.
- Fix `ticket_dir` and move the two stranded insider_judgment tickets.
- The `adopt-strong-moderate-no` question now has a concrete argument
  behind it: today the slice matched, the review endorsed, and the bet
  still died on price because the *procedure* has no NO-side entry rule.
- Nobody has run a replay for `structural_arb` (n=0 at v4, tier A, all
  history fetchable) — that remains the cheapest evidence on the board.

**Correction to the commit above (same session).** Commit `9302b82`
carries more than the floor run. I staged with `git add -A` while four
peer sessions were live, so it also swept in a concurrent session's
in-progress work: `tools/cli.py`, `tools/score.py`, `tools/tickets.py`,
`tests/test_cli.py`, `tests/test_score.py`, `tests/test_tickets.py`, a
`CLAUDE.md` edit, the tickets reorganization into `open/` subdirectories,
and two `series-bias` tickets this session did not file. None of that is
floor work and the commit message does not describe it.

Nothing was lost and the commit was never pushed. It was left standing
rather than rewritten because that peer was still editing `tools/
tickets.py` at the time, and a soft reset would have restaged their
partial work under whichever session committed next — swapping one
misattribution for the same one in the other direction. The floor's own
changes in that commit are `RESEARCH_LOG.md`, the `insider_judgment`
`NOTES.md` entry, and the three tickets named above; `user_reports/` is
gitignored, so the report itself is untracked by design.

Lesson for later floors: stage explicit paths. A floor session shares a
working tree with every other lane, so `git add -A` cannot mean "my
work".

## 2026-09-01 -- insider_judgment v5 and promotion key v3: the endorsement gate comes out

**User-directed refactor.** Removed `insider_judgment`'s stage 6, the main
session's price-aware final review, and with it the endorsement gate that
was the only path from a bucketed candidate to a bet.

**Why it matters beyond one theory.** Two things had drifted apart without
anyone putting them side by side:

1. **The live procedure was not the measured procedure.** All 3,759 of this
   theory's backtest rows -- including the 314 out-of-sample rows behind
   `strong-moderate-no` at +3.76 net, the best-evidenced result in the repo
   -- were generated with no final review. The live path ran six stages
   while every number justifying it described five. That is the silent
   merge the versioning rules exist to prevent, arriving as two *stage
   counts* under one track record rather than two prompts under one version.
2. **The promotion key's R4 gate contradicted its own rationale.** It
   required `disposition='endorsed'`, while its stated reason was that the
   rung holds candidates whose *stage 2 has not run*. A bucketed row has had
   stage 2 run. Consequence: 72 of the 79 live rows the proven slice
   entitled were rejected by stage 6 and landed on R6 CONTROL --
   unbettable forever. The sub-theory routing machinery worked exactly as
   designed and a second, unmeasured veto downstream cancelled it.

**Key v3** re-expresses the R4 gate as "no confidence bucket recorded".
Rungs, their order and every other criterion are unchanged;
`insider_judgment` is the only `uses_llm_judgment` theory, so nothing else
moved. Rows already recorded `rejected` stay R6 -- this governs what is
judged from here and rewrites no history.

**Verified on a copy of the real DB** (real ledger untouched): unsettled
live rows went R1 3 -> 57, R5 0 -> 67, R6 308 -> 187. The proven subset
gets a bet path; the complement is suppressed at R5 on its own -2.39.

**Bumped `continues`**, and worth noting why the label is easy here: since
every backtest row came from a five-stage procedure, v5 sits *closer* to
the measured evidence than v4 did. A bump that removes a stage is not
automatically a sever.

**What was NOT established, stated plainly.** Stage 6 was not measured and
found harmful. Its endorsed cohort settled 6/6 at +14.81 net against -8.06
for its 109 settled rejections -- which points the other way. n=6 over 2
event clusters clears no gate here, so it is unconfirmed, and the argument
for removal is structural: the stage sat outside the measured procedure and
was vetoing the measured result. The 456 interpreted live rows are frozen
at v2-v4 so the question stays askable; ticket
`insider_judgment/2026-09-01-did-stage-6-add-value` carries it, including
the instruction that a confirmed finding would be mechanized as a field or
gate rule, never reinstated as a session veto.

**Filed separately:** `cli theories bump` still offers only breaking/carry
and advertises breaking as the default, so it cannot record the kind the
2026-08-31 ruling made default. The v5 bump went through the Python API.
Maintenance ticket `2026-09-01-bump-cli-missing-continues`.

## 2026-09-01 (session llm-market-identifier-57, theory lane / no_side_premium) — a snapshot reader that silently returns the wrong board; and pairing measured as the wrong estimator

**Did:** Took the theory lane on `no_side_premium` (maintenance and
new-theory were held; `insider_judgment` was another session's). Extended
the within-day side-asymmetry series from 5 close-days to its
pre-registered `n_days >= 8` bar, then mined it. Detail in
`theories/no_side_premium/NOTES.md` 2026-09-01 and
`studies/2026-08-29-side-asymmetry-extension/` "Pass 2". Suite 1,287 green.

**Learned:**

1. **`WHERE captured_at = ?` on `market_snapshots` stopped returning the
   board on 2026-08-30 and nothing failed.** Dedup-on-write (spec 5.2
   phase 2) writes no row for a market whose payload did not change, so an
   exact-stamp filter returns *the markets that moved at that pull* — a
   liquidity-correlated subset. It costs **46% of the 2026-08-31 board**
   (53,613 rows against 99,064 markets) and 24% of 2026-09-01's. Any
   session replaying a post-2026-08-30 snapshot has been measuring a
   biased sample without an error to warn it. Fixed by
   **`tools.snapshot.board_as_of(conn, platform, at)`** (the row per market
   whose `[captured_at, last_seen_at]` interval contains the instant;
   6 tests). It returns exactly 105,104 for the 09-01 capture — the board
   size that floor reported pulling. Two study probes still carry the old
   query and are ticketed (`snapshot-exact-stamp-readers`); **their
   published results stand**, having run against pre-dedup captures.

2. **A variance-cancelling estimator can import variance instead, and this
   one did.** `no_side_premium` has been read since 2026-08-29 on a paired
   within-day `NO - YES` statistic, adopted because "the day effect is a
   common shock to both sides, so it cancels". Eight days let the premise
   be tested: between-day SD is **15.59** paired, versus **6.90** for the
   NO side alone and 5.64 for NO at 0.90+. The paired estimator is the
   worst of the four — the sides are different markets on different
   subjects, not two sides of one contract, so there is no shared shock to
   cancel. In days-to-detect-2.0-points: **477 paired, 62 single-side.**
   Generalisable: pairing only cancels a shock the two arms actually
   share; check that rather than assuming it.

3. **The bar was reached and the claim is null** — `NO - YES` = +2.91,
   day-clustered SE 5.51, t=0.53, 95% CI [-7.89, +13.72], 5/8 days
   positive. Pass 1's +8.25 at 5 days, and both its per-side estimates,
   moved toward zero as days were added. **Unconfirmed, not disproven**;
   the CI still contains +2. Leave-one-out: drop 08-28 and the mean goes
   negative, so the 8-day paired mean is one day.

4. **A pre-registration bar can be reached honestly or dishonestly, and
   the difference is a decision made before a number.** The >=90%-settled
   inclusion rule left 7 days against a bar of 8, and admitting the 18%-
   settled 2026-09-01 would have reached it. Instead an unused *complete*
   day (2026-08-24, 155/156 settled) was added, and the decision was
   written down before its value was computed. It then turned out to
   flatter the thesis — dropping it moves the result further toward null
   (+2.91 -> +1.31) — which is the check worth running whenever a day is
   added to reach a bar.

5. **"The inclusion rule is the result", caught a second time.** The one
   cell that looks alive (`NO 0.90-0.97`, +1.70 +/- 1.99, 7/8 days
   positive) reads **+3.59 with t=4.93** under a >=10-rows-per-day floor —
   because that floor drops exactly one day, the only negative one, which
   had 6 rows and one loss. Recorded as a trap, not a finding, and the fix
   is a rows-per-day rule fixed *before* collection. Same failure the
   calibration_harvest gradient review caught on 2026-08-29; it is
   evidently a repeating shape rather than a one-off.

6. **A theory can be starved by its own population restriction while its
   mechanism is fine.** `no_side_premium`'s cell A is mention-family NO
   favorites — **15 rows on 2 of 8 close-days**. The same band across the
   whole screen is 275 rows over 8 days at a comparable point estimate.
   The band carries what signal there is; the family restriction starves
   it. Cell A was **not** widened — that is the move a pre-registration
   exists to prevent — and the wide version is filed as its own theory
   (idea 33 / ticket `no-favorite-high-band`), the way `no_side_premium`
   itself came off `mention_family`.

**Next:** `no-favorite-high-band` is the live question, not
`no_side_premium`; it is reachable (62 settlement days, or a tier-A replay)
where the parent's paired claim is not (477). Read `no_side_premium` on the
single-side NO 0.90+ figure from now on. Re-run `measure.py` each session;
2026-09-01 enters the series by itself once it clears 90% settled. No
retirement proposed — neither cell is killable by its own pre-registered
rule.

## 2026-09-01 — find-theories: five theses filed, and Kalshi turns out to publish per-trade taker side

Session `llm-market-identifier-0e`, find-theories lane (claim 5). The
user asked for a session that avoided the insider_bias family. First and
second choices (`theory`/no_side_premium, then `maintenance`) were both
claimed by peers within the two minutes it took to explore, so this took
the open lane.

**Did.** Filed five new-theory theses (tickets + idea registry, 30–32,
34–35) and three theory tickets. Worked two of the skill's sources: the
board, and outside literature. Every board claim below was measured on
the 2026-09-01 board before filing.

**Learned — the one that outranks the theses.** `GET /trade-api/v2/
markets/trades` is **unauthenticated and returns the aggressor side of
every trade** (`taker_side`, `taker_outcome_side`, `taker_book_side`,
`count_fp`, `is_block_trade`). The repo has no client for it and no
theory reads it. Verified live: ticker filtering, `min_ts` and cursor
paging all work, and **12 of 12 archived-settled markets (close
2026-06-30) still return full trade history** — so it survives
settlement and replays at tier A for free.

CLAUDE.md's "Polymarket … exposes per-trade wallet identity and holder
positions that Kalshi does not" is true about *wallet identity* and is
easy to over-read into "Kalshi exposes no flow data". It does. Nothing
in the flow thesis needs a wallet.

One loose end worth someone's time: the trade span on an open market
reached 2026-06-25, **8 days older than the ~60-day settled-market
archive floor**. If trades generally predate that floor, this is a route
to history the repo currently treats as permanently lost.

**Learned — the rest.**

1. **`rules_secondary` is on 95.4% of markets and almost nothing reads
   it.** `grep -rn rules_secondary --include=*.py .` returns two hits,
   both inside `insider_judgment`, both reaching into `.raw`; it is not
   on the typed `Market` object at all. 12,806 markets (12.2%) carry a
   timing/revision clause there. `deadline_drift` parses its stated
   deadline from `rules_primary` alone, and that anchor is its whole
   theory — flagged in the ticket, unverified against its allowlist.
2. **Cross-event aggregation identities are unscanned.** `structural_arb`
   groups strictly by `event_ticker`, so anything spanning events is
   invisible to it by construction. Two measured instances, same sign:
   NFL win totals imply 274.25 wins against a hard ceiling of 272 (not
   significant — the bid/ask band [264.0, 284.5] straddles it); and over
   the five states with complete district coverage, summed district
   P(Dem) exceeds the state seat market's E[seats] by +0.320 at mid,
   5/5 positive, **+0.073 with districts at bid and state E at ask, 4/5
   positive**. This is the cross-event successor idea 8 explicitly asked
   for in its revisit angle.
3. **Seven of series-bias pass 3's nine flagged series are niche or
   foreign leagues** (NPB, KBO, ATP Challenger, CPL, T20, Europa League).
   Pass 3 rightly declined to call them, since its negative control
   fired 5/11 on a contaminated population — but contaminated is not
   disproven. Filed as **one** pre-registered grouping rather than 347
   mined series, which is the whole statistical point: no Holm divisor,
   and it pools rows that per-series tests waste.
4. **An outside paper independently confirms `no_side_premium`.**
   "Adverse Selection in Prediction Markets: Evidence from Kalshi"
   (Stanford Law, 2026-04-21, 41.6M trades) finds traders "systematically
   overbet YES in markets that predominantly settle NO" — arrived at from
   microstructure, not behavioural priors. That theory currently cites
   Becker and Reichenbach & Walther; this is worth adding, and it
   materially raises the prior on a theory sitting at n_days=5.
5. **`settlement_sources` is a populated published field on every event
   envelope** (ESPN 46,440; Fox Sports 20,208; …) that no cell axis uses.

**Ranking, since a list of five gets triaged by whoever reads it:**
`kalshi-taker-flow-toxicity` is the best — it is the only one carrying an
independent 41.6M-trade empirical basis, its data is confirmed reachable
*and* backtestable at tier A, and it opens a data source rather than a
single thesis. `fine-print-divergence` is second on evidence-per-effort.
`aggregation-gap` is the most rigorously measured but most likely
fee-eaten.

**Next.**

- Nobody has run the `structural_arb` replay (n=0 at v4, tier A) — still
  the cheapest evidence on the board, and untouched since the 2026-09-01
  floor named it.
- The `calibration_harvest` double-run defect compounds daily and was
  claimed this session by `llm-market-identifier-df`; check it landed.
- `no_side_premium` is calendar-blocked at n_days=5 against its own bar
  of 8, while ~60 settlement days of settled history sit unused in
  `studies/2026-08-29-series-bias-mining/data/collect.db` — never split
  by side, which is that theory's entire hypothesis. Ticketed into its
  folder.
- Sources NOT worked this session, for whoever takes this lane next:
  Polymarket-side structure, Kalshi's newly listed series as a cohort
  (KXTRUMPSAYMONTH and KXNETFLIXRANKMOVIE are both <30 days old with real
  volume), and resolution-source behaviour beyond noting the field exists.

## 2026-09-01 — maintenance: two surfaces that were lying (session llm-market-identifier-df)

Lane: `maintenance`. Floor was already done (0.3h before), `new-theory`
held by a peer on series-bias, and the user ruled `insider_bias` off
limits (another session).

**Chose maintenance over the theory lane** after comparing four options.
`structural_arb`'s replay — the last floor's "cheapest evidence on the
board" — was rejected as runner-up because
`studies/2026-08-29-structural-arb-violation-liquidity/` already replayed
its geometry over 11 boards and found 6 violations in 5 days, *all six*
rejected by the v3/v4 thresholds; a fuller replay confirms an absence.
`deadline_drift` is calendar-bound, not replay-bound: its 112 settled
markets are already the entire fetchable history (~60 closes/month
forward), and its capture marker was fresh at 1.1 days against a 14-day
bar. `no_side_premium` is calendar-bound too. The calharvest defect won
because it **compounds** — ~9,200 doubled attempt rows per floor.

**Did.**

1. **`calibration_harvest` v3 (`continues`) — the domain axis had been
   collapsing since the theory started recording.** Ticket asked about a
   double-run; the root cause was wider and is a *vocabulary* bug.
   `domain_for` returned `other` both for a category the grid does not
   bin and for a series the run's map never covered. The RUNBOOK claimed
   two runs per floor covering "one complete population" each;
   `screen()` has no population filter, so both screened the whole board
   and each labelled the other's population `other`. Measured
   2026-09-01: 9,247 attempts per run, **100% overlap**, and 99.4% of the
   weather run in one `other` bucket.

   The fix cost nothing and always could have: `/series` returns all
   13,687 series in one response with no cursor, so
   `all_series_categories()` — the complete map — costs exactly what the
   partial one cost. Nobody was paying for the collapse. Today's board
   now bins into **11 real domains** with `other` at 102 (1.1%) instead
   of 9,123 (99.4%). `unmapped` is now a separate domain, so a partial
   map produces a conspicuous cell instead of a plausible one.

   Quarantine is **per cell, not per run**: `other|*` below v3, plus the
   exact-duplicate run `live-2026-08-29-calharvest-v2` by id. Per-cell
   because `weather|*` on the weather run and `politics|*` on the
   politics run were always correct — a run-level exclusion would have
   discarded 2,704 clean politics rows to punish the `other` rows beside
   them. Corpus 6,960 → 100 rows, 21 → 6 cells, and it **costs no
   conclusion**: 0 of 21 cells were measurable before, 0 of 6 now.

2. **`state` reported zero evidence for every theory after a `continues`
   bump.** Found by watching my own bump blank the panel. The 2026-08-31
   ruling flipped the default from `breaking` to `continues`; three
   panels in `tools/state.py` still counted at `theory_version =
   <current>` exactly, which was correct only while a bump severed.
   Live at the time: `calibration_harvest` (chain [1,2,3], 28,909 rows)
   and `insider_judgment` (chain [1,2,3,4,5], 4,275 rows) both rendered
   `rows 0` / `no live score`, and **`strong-moderate-no` — +3.76 net
   over 90 clusters, the best-evidenced result in this repo —
   disappeared from EVIDENCE entirely**, on the one surface CLAUDE.md
   tells every session to orient with. All three panels now count over
   `carry_chain` (which stops at `breaking`, so severing still works —
   pinned by a test), and an aggregate borrowed from a predecessor is
   labelled `[scored at vN]`.

3. Closed `state-md-stale` as **not a bug**: STATE.md is gitignored, has
   never been tracked, and does not exist. The spec says why — "a
   tracked generated file drifts the moment someone edits it" — which is
   the exact drift the ticket feared.

4. Grouped `lanes.py` and `tickets.py` under "starting a session" in the
   toolkit surface; they are two of the four cheap reads `go`'s Orient
   mandates and were in the ungrouped fallback.

**Learned.**

- **CLAUDE.md's "when a default changes, check what reads it" is not
  hypothetical, and the reader can be the orientation surface itself.**
  The `breaking`→`continues` flip was recorded as a ruling and applied
  in `carry_chain` and `score.py`, but `state.py` was never swept. I
  swept the rest of the repo afterwards and it is clean — `score.py` is
  already parameterized (`pool="chain"`), `theories.py`'s carry-proof
  replay must read exactly one version, and `ledger.py`/`provenance.py`
  use the version as part of a row-identity key. `state.py` was the only
  stale reader, but it was the highest-traffic one.
- **A vocabulary that means two things fails silently and takes three
  incidents to notice.** `other` meaning both "unbinned category" and
  "map missed it" is why the collapse survived the 2026-08-30 `live`
  quarantine — that run was caught only because it was *total*. Two
  partial versions of the same bug then ran for three days looking
  legitimate. The split is cheap and makes the next one loud.
- **Checked before reporting: `no_side_premium`'s complement showing
  identical numbers to `cell-a-no-favorite` is correct, not a bug.**
  The complement is of the *ready* slices; `cell-a` is not ready (2
  clusters against a bar of 10), so its rows are the complement.

**Note on `ecb07b6`.** A peer's insider_judgment v5 commit swept in my
`tests/test_registry.py` edit via `git add -A` — the same failure the
2026-09-01 floor logged a lesson about, now recurring. Left standing for
the same reason: rewriting a shared commit while seven sessions are live
swaps one misattribution for another. Nothing lost; my own two commits
stage explicit paths.

**Next.**

- `calharvest-recover-quarantined-other-rows` (theory lane, filed in
  the theory's own folder): the 6,860 quarantined rows are
  **recoverable** — every attempt carries `series_ticker` in
  `extra_json` and the complete map re-derives the true domain. That is
  ~69x the current corpus and the only forward rows the nine
  never-labelled domains have. It needs a dedup rule decided, which is
  why maintenance did not just do it.
- `structural_arb` shows **5 rows**, not 0 — the old panel was hiding
  those too. Worth someone checking what they were before treating the
  theory as never having fired.
- The maintenance backlog is now **empty**.

### 2026-09-01 (same session, second half) — a side gap that replicated on every axis and was still composition

A peer (`llm-market-identifier-0e`) filed a ticket mid-session pointing at
`studies/2026-08-29-series-bias-mining/data/collect.db`: **72,010 priced
settled markets over 61 close days**, with a `side` column nobody had split.
That is `no_side_premium`'s hypothesis on 61 days where its own series has 8.
Write-up: `studies/2026-09-01-side-split-60day-obs/`.

**7. A result can survive every robustness view you own and still be an
artifact, if none of them is the right control.** The pooled NO−YES gap in
band 0.90–0.97 came in at **+3.95, t=3.03, 41/61 days** — and then held at
+3.94 out-of-sample over 51 clean days, went *stronger* in the on-time
settling stratum (+8.62 vs +1.34), got *larger* at an independent 24h
decision point (+11.02), and was positive in every band but the cheapest.
Five independent-looking confirmations. **All of it was composition:** NO
favorites outnumber YES 5:2 there and the two sides are largely different
series, so the gap measured *which markets happen to be NO-favorite*.
Differencing within (series, close day) gives **−1.85 (t=−1.40)**, stable
across weightings and leave-one-series-out, with 61/138 series leaning
positive — a coin flip. The lesson is not "check robustness"; it is that
robustness views drawn from the same confound all inherit it, and only a
control that *removes the confound* is worth anything. `calibration_harvest`
met the same thing at 38% on 2026-08-29; here it was more than 100%.

**8. So: a within-series (or within-family) control is now mandatory for
any side or category comparison in this repo.** A pooled A-vs-B number over
a mixed board is a statement about which markets are A, until proven
otherwise. Cheap to run, and it is the difference between a finding and an
embarrassment.

**9. The same control on the narrower screen population does NOT reverse**
(+7.69, t=1.75 in the same band — but 30 series over 7 days, unreadable as
a magnitude). The populations disagree; `insider_bias.screen` filters
`spread ≤ 0.07` / `volume ≥ 500` and the board-wide sweep filters neither,
which is also why every level in the sweep runs −3.7 to −40 (quotes nobody
would fill, not mispricings). **This makes the series-bias liquidity
backfill the deciding experiment for a proposed theory, not a chore** —
filter the sweep to the screen's bar, re-run the control, and
`no-favorite-high-band` is either built or abandoned on 61 days of evidence.

**Next (revised):** `no-favorite-high-band` is **blocked pending that
backfill**, and its ticket says so. Nothing about it should be
pre-registered until the control has been run on liquidity-filtered sweep
data.

---

## 2026-09-01 — a snapshot-reading defect that outlived its correctness, and structural_arb's two standing checks

Session `llm-market-identifier-af`, theory lane, focus `structural_arb`.
Theory-level detail stays in `theories/structural_arb/NOTES.md`
(2026-09-01) and the study's own amendment; what follows is only what a
session that never touches this theory needs.

**Did.** Ran the two standing checks `structural_arb`'s notebook leaves
open, extended its violation study from 11 captures to all 17, and
measured flag stability for the first time. No procedure changed and no
version was bumped — every finding was about an instrument, not a
decision.

### 1. A study that was correct when it ran can be wrong when re-run — snapshot reads are the case (cross-cutting)

**`WHERE captured_at = <stamp>` stopped meaning "the board" on
2026-08-30**, when dedup-on-write landed: a pull writes no row for a
market whose payload did not change, so the filter now returns *the
markets that moved at that pull*. `snapshot.board_as_of` exists for this
and its docstring names the trap.

The failure is quiet and it is **biased, not random** — markets that move
are the liquid ones, so any study measuring liquidity, price or side
gets a subset correlated with its own dependent variable. Measured on
`structural_arb`'s probe, same 17 captures both ways:

```
2026-08-27T11:47:05Z   exact:  3,254 markets   as_of: 107,656 markets
2026-08-30T19:22:32Z   exact: 55,433 markets   as_of: 104,304 markets
raw violations found   exact:     24 total     as_of:      36 total
```

**A third of the findings were invisible.** Both probes carrying this
were correct on the day they ran; the defect bites only on re-runs, which
is exactly what a "Reproduce" section invites.

**The constraint, for anyone writing or re-running a study:** read a
stored board through `snapshot.board_as_of`, never by exact stamp, and
route payloads through `payload_text`. A number produced by an
exact-stamp read after 2026-08-30 is not comparable to the same number
produced before it.

Swept the repo. One other live instance:
`studies/2026-08-27-calendar-arb-firing-rate/probe.py:108` — ticketed,
and it matters because that study's zero-violation result is what
falsified calendar-arb's premise, and the open
`calendar-arb-soft-relative-value` ticket sends a future session straight
back into it.
`studies/2026-08-29-side-asymmetry-extension/measure.py:69` is already
correct and carries a comment naming the trap — the counter-example to
copy.

### 2. `mutually_exclusive` does not drift (constraint, useful to any snapshot replay)

Four envelope-bearing captures now exist, so the stability that
`structural_arb`'s `theory_facts` fallback had only *assumed* is now
measured: **12,000 events seen in two or more captures, zero flag
changes, zero within-capture inconsistencies.** A replay may lean on a
cached flag. The window is four days — this says the flag does not drift
week to week, not that it never changes over a market's life.

### 3. A rejected position that could not be filled is not the same counterfactual as one you declined (precedent, for scoring)

`score report structural_arb` reads **+55% `riskless_roi`**, and every
row behind it was rejected as unfillable — the two contributing findings'
own rationales say `~0.01 baskets fillable, ~$0.00 floor profit`. Not a
ranking bug: `riskless_roi` never reaches `ranked_edge` and
`promotion.py` does not read it.

The distinction worth having in the vocabulary: rejections counting
toward `roi_all` is deliberate and right for a **judgment** theory, where
a rejected winner means the screen was right and the judgment cost you.
Where the rejection reason is *not fillable at any size*, the
counterfactual is **impossible rather than merely untaken** — there was
no position. Filed with three options rather than patched, because
`disposition` and the riskless bucket are load-bearing vocabulary and
redefining a recorded field rewrites every row already written under the
old meaning.

**Learned.** `structural_arb` is idle and correct, not broken: 16
distinct violations in 8 days, 14 of them removed by `MIN_LEG_VOLUME`,
and **none of those 14 has a leg carrying open interest above 6.0** — so
the threshold, fit on six violations back in August, is well placed on an
axis it was never fit on. Twelve of the sixteen are one series
(`KXWTAGTOTAL`, WTA match totals) at zero open interest: the theory's
daily "violations found, none survive" is **nominal ladders on markets
nobody has ever traded**, not opportunities an arb bot beat us to.

Also learned, and worth flagging because the floor's Next line said the
opposite: **a replay is not this theory's missing evidence.** Kalshi
archives no historical order books, and depth is what killed all five
live findings and the single liquid violation in the dataset. A replay
can measure violation *existence* — now done over the full history — but
must not record `backtest-*` ledger rows, which would be phantom riskless
positions carrying nothing that says the book was a hundredth of a
contract deep.

**Next.**

- Neither standing check should be repeated as recorded: the
  partition-gap recipe over-triggers ~15x and does not reproduce session
  78's numbers (ticketed, with the fix — group by
  `scan.underlying_key`, not by "asks sum near 1").
- `structural_arb` needs nothing else right now. Against its own kill
  criteria it is on day 6 of 60 and they say leave it running; it is
  **not** a retirement candidate, and no retirement is proposed.
- The `calendar-arb-firing-rate` probe should be fixed before anyone
  works `calendar-arb-soft-relative-value` off its dataset.
