# Mention Family

<!-- research-memory-route -->
> [Find scoped lessons and avoided mistakes](learnings/README.md). Read this specification
> for the claim/procedure relevant to your task; historical learning narratives
> are source evidence, not an accumulating current-memory summary.
<!-- /research-memory-route -->


## Hypothesis

Kalshi runs a recurring family of "will X mention/say/do Y" markets
(`KXTRUMPMENTION`, `KXWCMENTION`, `KXFIGHTMENTION`, `KXFEDMENTION`, and
others sharing a `MENTION`/`SAY`/`ACT`-suffixed series ticker). As a *ticker
family*, restricted to the same tradeable-favorite screen its sibling
theory `insider_judgment` uses, it beats its own price — measured, tier A,
no model in the loop.

This is **not** a claim about an informed minority. It does not test whether
a specific group already knows the outcome the way `insider_judgment` does;
it tests whether a mechanical filter (a real favorite, priced by its own
measured historical win rate) is enough on its own. Two live possibilities
for *why* the edge exists, not yet distinguished: it could be a genuine
informational asymmetry (a press office, a campaign, a network that knows
what is scheduled to be said before the public does — the same mechanism
`insider_judgment` targets), or it could be a base-rate-calibration effect
unrelated to insider knowledge (the market underestimates how often a
public figure repeats predictable behavior). This theory does not need to
resolve that question to capture the edge; see idea
`insider-bias-mention-family` for the open research thread on which it is.

## Origin — split out of `insider_bias` (now `insider_judgment`), 2026-08-24

This theory was discovered as a side effect of backtesting the sibling
theory's stage-1 screen, back when that theory was still named
`insider_bias` (`run_id=backtest-2026-08-24-stage1-90d`): of 200 real
screen hits, 116 were this ticker family, and it behaved completely
differently from the rest of the screen's output (see that backtest's full
breakdown in `theories/insider_bias/insider_judgment/THEORY.md` Learnings,
2026-08-24). It lived inside that theory as a "v3" mechanical sub-path for
a few hours before being split into its own theory, once it was clear the
two were answering different questions and one version number could not
honestly describe both. The evidence moved with it — this theory's `n=116`
did not start at zero, because that would have discarded a real
measurement rather than correcting where it lives.
`theories/insider_bias/` then became a shared *parent* folder for both
theories (this one, and the renamed `insider_judgment`) rather than either
theory's own name — see `theories/insider_bias/insider_judgment/THEORY.md`
for that sibling's own hypothesis and the fuller discovery history; this
document does not repeat it.

## Data sources

Kalshi only, via the same client the sibling theory uses
(`tools/kalshi/markets.py`). No Polymarket dependency.

## Status

`under_review` — set 2026-08-25 (`authorized_by=claude`), with a
**standing retirement proposal** filed the same day. The tier A
full-coverage backtest (`backtest-2026-08-25-mention-fullcov`: every
mention-family survivor in the API-reachable window, n=3,441 settled,
vs the n=116 sample the bins were fit on) measures
`calibration_edge=-0.49` gross, `calibration_edge_net=-1.53`,
`roi_all=-1.9%`. Every price bin is at or below zero net; every
sub-family is ~zero or negative on fresh rows. The bootstrap's +5.48pts
was sampling luck in a ~3% systematic sample of the same window. Do not
recommend bets from this theory; the user rules on retirement.

The paragraph below records what Status said before that run, for the
history of how the evidence developed:

`testing` — set 2026-08-24 (`authorized_by=claude`). The backtest evidence
technically clears the letter of "testing → active needs a tier A/B
backtest with positive calibration_edge_net" (n=116, `calibration_edge_net=
+5.48pts`, and — more precisely, see Confidence buckets — every one of the
three price bins is individually positive). Held at `testing` rather than
`active` anyway: this mechanism had a real bug (a flat probability applied
across the whole price band) caught and fixed the same day it was built,
and has zero live settlements of its own yet — the backtest is real
evidence, but "just fixed a bug hours ago" is not the same footing as
"has actually worked live." Promote to `active` once live rows settle and
confirm the price-binned model, not on the backtest alone.

## Version

**No version bump — 2026-08-29 shared-module correction, and read this
before reviving the theory.** `tools/buckets.edge_for` was corrected so a
confidence bucket contributes its own realized *edge* rather than being
repriced against each candidate's ask (see
`theories/insider_bias/insider_judgment/THEORY.md` "Version 4"). This
theory called that function, so **its arithmetic changed under it**: on
the characterization fixture the top pick moves from a $0.85 candidate at
+14.11 net to a $0.97 one at +8.21. The old formula ranked this theory by
*cheapness*; price binning masked how badly, because inside a narrow bin
a flat rate is nearly right.

No bump because the theory is `retired` and records no further rows —
there is no track record for a version number to keep separable. The v1
rows in the ledger were priced by the old formula and stay that way.
Anyone reviving this must re-derive any ranking from that era rather than
reuse it; `NOTES.md` 2026-08-29 has the full account.

**No version bump — 2026-08-25 module move.** The tier A replay of the
shared stage-1 screen moved from `insider_judgment/backtest.py` to
`theories/insider_bias/replay.py`, and the `is_mention_family` ticker
classifier from `mention_family/mention_bucket.py` to
`theories/insider_bias/families.py` — both into the shared parent, beside
the `screen.py` they serve. No decision logic changed and neither theory's
version bumps: both call the same functions with the same arguments and
get the same results. The move restores the rule that a theory folder
never imports a sibling theory's folder, now enforced by
`tests/test_conventions.py::test_no_theory_imports_a_sibling_theory`.

**1** (2026-08-24) — initial split, `theory_id='mention_family'`. Procedure:
`theories.insider_bias.screen.screen()` (shared with `insider_judgment`) →
`is_mention_family` narrows to this ticker family → each candidate is
priced against its own price bin's measured historical win rate
(`PRICE_BINS`, `bucket_for_price`) → `tools.buckets.edge_for` computes
mechanical edge → ranked by `(edge_pts_net, volume)`, volume breaking ties
only. No LLM anywhere in this procedure; `uses_llm_judgment=False`.

**Not part of this version's history, but worth knowing:** the price-bin
fix and the volume-as-tiebreaker decision both happened on 2026-08-24,
*before* this theory had its own separate identity (while the code still
lived inside the theory now named `insider_judgment`). They are not
separate version bumps here because version 1 of *this* theory already
reflects the corrected, final design — see `mention_bucket.py`'s module
docstring for the full account of how the bug was found and fixed, since
that history is genuinely useful context for trusting (or not trusting)
this theory's numbers.

## Stage 1 — mechanical screen (shared with `insider_judgment`)

`theories.insider_bias.screen.screen(markets)` — clear favorite (ask in
[0.65, 0.97]), spread ≤ 0.07, volume ≥ 500, closing within 14 days, minus a
coarse ticker-family exclusion list (`EXCLUDED_PREFIXES`: sports leagues
and `KXMVECROSSCATEGORY`, whose 400,000+ markets/day would flood any
settled-history walk — see that module's docstring). This is not this
theory's own screen; it is the shared parent's stage 1 (`theories/
insider_bias/screen.py`), imported and narrowed further, on purpose — both
sibling theories should get the exact same candidate pool up to this point,
or the shared evidence (`EXCLUDED_PREFIXES`, the favorite-band thresholds)
stops meaning the same thing in both places.

## Stage 2 — the mention-family filter and price-binned edge

`is_mention_family(series_ticker)` — defined in the shared parent's
`families.py`, imported by `mention_bucket` — narrows stage-1 hits to
series whose ticker contains `MENTION` or ends in `SAY`/`ACT`. Everything
past this point is mechanical — see `mention_bucket.py`'s module docstring
for the full reasoning behind every design choice below; this section is
the short version.

**Price-binned, not one flat rate.** A candidate's edge comes from its own
bin's measured win rate, not the family average — the family average
(0.871) was tried first and was a real bug: win rate rises sharply with
price, so one flat rate overstated the cheap end's edge and understated the
strong end's. See Confidence buckets below for the three bins.

**Volume is reported and breaks ties, not part of the edge.** Checked
directly against the backtest data: volume is not predictive of win rate
here the way price is (no clean trend across volume bins, and the
highest-volume bin is n=4 — too small to mean anything). It matters for a
different, real reason — confidence the displayed price is fillable — so
`rank`/`rank_preview` sort by `(edge_pts_net, volume)` descending.

**Entry timing is structural, not a free choice.** 36% of the 116 backtest
hits only became screen-eligible on the literal last day before close, and
most of the rest in the final 1-2 days; only 12 of 116 were sitting as a
favorite 10+ days out. This theory's screen therefore needs to run close to
individual markets' close dates — a recurring check, not a one-off scan —
or it will miss most of what it is built to find. See `mention_bucket.py`'s
module docstring for the binned edge-by-timing table and its confound
(these are different markets selected by when each crossed into favorite
territory, not the same market resampled at different entry times — what
was NOT tested is whether *delaying* entry on an early-qualifying candidate
would help or hurt).

**No probability estimate beyond the measured rate — nothing to judge.**
Unlike `insider_judgment`, there is no Stage 3: `edge_basis='measured'`
(or `'model'` for the wider-window preview path, `rank_preview`) candidates
arrive with an edge already attached and are recommendable without a
research pass, per CLAUDE.md's "pipelines propose, judgment disposes."
`disposition` stays the default `'screened'` for exactly this reason — see
`ledger.record_opportunity`'s default and CLAUDE.md's note that
`'screened'` on a mechanical theory means "needed no interpretation," not
"not yet assessed."

## Confidence buckets

**INVALIDATED 2026-08-25 — do not price candidates from this table.** The
full-coverage rerun (see Status and Learnings) measured these same bins at
n=1,132/1,003/1,190 on fresh rows: win rates 0.678/0.785/0.913 against
mean prices 0.694/0.796/0.909 — every bin at or below zero net edge. The
rates below came from a ~3% sample of the same window and were sampling
luck. The table is kept so the record of what was believed, and why, stays
legible:

Not LLM-judged confidence labels (`strong`/`moderate`/`weak`, as in
`insider_judgment`) — these are price bins, and their rates are measured
directly from the 2026-08-24 backtest, not asserted priors:

| bucket | price range | n | win rate | mean price | edge (net) |
|---|---|---|---|---|---|
| `mention_family_lt75` | $0.65–$0.75 | 37 | 0.730 | 0.696 | +1.87pts |
| `mention_family_75_85` | $0.75–$0.85 | 38 | 0.868 | 0.793 | +6.38pts |
| `mention_family_85plus` | $0.85–$0.98 | 41 | 1.000 | 0.916 | +7.88pts |

**Treat `mention_family_85plus`'s 1.000 with real skepticism.** Zero losses
in 41 tries is strong evidence of a high win rate, not proof of certainty.
`buckets.edge_for` takes it at face value (no shrinkage beyond
`buckets.MIN_BUCKET_N=10`, the one consistent convention this repo uses
rather than bespoke per-bucket smoothing) — the true rate is very likely
below 100%, so a `+7.88pts` headline on this bin deserves more hedging than
the other two when reported.

These rates will be recomputed from this theory's own live settlements once
it has enough (`score.bucket_rates(conn, "mention_family", 1, run_mode="live")`)
— the table above is the *bootstrap*, from `insider_judgment`'s original
backtest (recorded under its old name, `insider_bias`), not this theory's
own accumulated history. Say so every time it is quoted; see
`mention_bucket.py`'s `MEASURED_RATE_RUN_ID`.

## How to backtest

**Tier A** — no LLM anywhere in the decision path. Rerunning the original
90-day backtest (`theories/insider_bias/replay.py`, which lives in the
shared parent since it replays the stage-1 screen both theories share —
this theory's evidence rode along as a byproduct) over a
longer window, or a more recent one, would extend this theory's own
evidence directly. That infrastructure (the `KXMVECROSSCATEGORY` volume
trap, the series-scoped fetch, `candidate_series()`) is documented in that
module's docstring and `insider_judgment/RUNBOOK.md` — reuse it rather than
rebuild it; this theory has no reason to duplicate that machinery for a
different ticker family.

## Learnings

[Choose an actionable lesson](learnings/README.md). The cards preserve only
scoped conclusions that change a later decision or avoid expensive repetition.
The original [learning narrative](notes/archive/THEORY-learnings.md) remains
available for a specific evidence question; it is not current startup context.

<!-- research-memory-archive: notes/archive/THEORY-learnings.md -->
