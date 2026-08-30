# mention_family — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design; nothing was migrated into it.

- **`THEORY.md` Status** — `under_review` as of 2026-08-25, with a
  standing retirement proposal filed the same day and still awaiting
  the user's ruling. The tier A full-coverage backtest
  (`backtest-2026-08-25-mention-fullcov`: every mention-family
  survivor in the API-reachable window, n=3,441 settled, vs the n=116
  sample the bins were fit on) found no edge —
  `calibration_edge=-0.49` gross, `calibration_edge_net=-1.53`,
  `roi_all=-1.9%` — superseding the audit below.
- **`THEORY.md` Learnings** — the distilled record, in chronological
  order: (1) the 2026-08-25 skeptical audit of the original backtest
  edge — mechanics came back clean (no lookahead, fees included,
  negligible event clustering, stable pre-event favorites) but the
  statistical case was already much weaker than the headline read —
  pooled p=0.0395 gross, p=0.070 after fees, before any correction for
  this family having been *selected* as the standout slice of a
  200-row backtest; (2) the full-coverage rerun that followed and
  killed the edge outright, driving the status change above; (3) a
  same-day pattern-mining pass over the full-coverage rows that found
  timing and price-level effects dead, but a side asymmetry (NO
  favorites at ask ≥0.90) that survived every stress test — recorded
  as backlog idea `no-side-premium`, not a revival of this theory.
- **`RESEARCH_LOG.md`** — the session narratives, in order: the
  2026-08-24 split from `insider_judgment` into a separate theory; the
  2026-08-25 audit in full; "Full-coverage rerun: mention_family has
  no edge; under_review, retirement proposed"; and the same day's
  "Pattern-mining the fullcov rows" follow-up.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.

## 2026-08-29 — a shared-module correction changed this theory's arithmetic (retired; no version bump)

`tools/buckets.edge_for` was corrected on 2026-08-29: a confidence bucket
now contributes its own realized **edge** (`win_rate − mean entry price of
the rows that measured it`) instead of being repriced against each
candidate's own ask. See `theories/insider_bias/insider_judgment/
THEORY.md` "Version 4" for the full argument.

**This theory used that function, so its arithmetic moved under it.** On
the characterization fixture the ranking changes materially:

| | top pick | ask | net edge |
|---|---|---|---|
| before | `KXEARNINGSMENTIONURBN` (a cheaper strike) | 0.85 | +14.11 |
| after | `KXEARNINGSMENTIONURBN-26AUG26-TARI` | 0.97 | +8.21 |

The old formula was sorting this theory **by cheapness**: every candidate
in a price bin was repriced against that bin's win rate, so the cheapest
member of the bin always looked best. Price binning was the workaround
that kept this survivable — inside a narrow bin the flat rate is nearly
right — which is why the defect was never visible here as it was on
`insider_judgment`'s single 0.65–0.97 band. It was still a defect.

**No version bump.** This theory is `retired` (user ruling, 2026-08-27)
and records no further rows, so there is no track record for a version
number to keep separable; the fact is recorded here and in `THEORY.md`
instead. Anyone reviving it must read the v1 rows as priced by the old
formula, and re-derive, not reuse, any ranking from that era. The
pre-correction output is preserved unmodified in
`tests/characterization/goldens/mention_rank_wide.json`.

## 2026-08-24 — Two follow-ups from user questions: a corrected Big Brother bet, and a new mechanical path for the MENTION-family edge (migrated from RESEARCH_LOG.md)

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

## 2026-08-25 — mention_family edge audited on user suspicion: mechanics clean, inference weak, live slate mismatched (migrated from RESEARCH_LOG.md)

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

## 2026-08-25 — Full-coverage rerun: mention_family has no edge; under_review, retirement proposed (migrated from RESEARCH_LOG.md)

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

## 2026-08-24 — mention_family becomes a real, separate theory; insider_bias renamed insider_judgment and folded into a shared parent folder (migrated from RESEARCH_LOG.md)

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
