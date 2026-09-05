## Learnings

- 2026-08-25 — **Pattern-mining the dead aggregate found one survivor:
  the NO side at high prices (user-prompted: "don't give up on a pattern
  because of initial bad results").** Full slicing of the 3,441
  full-coverage rows — timing, fine price bins, side x price, volume,
  spread, sub-family, per-series z — answered the open questions
  directly: the bootstrap's 0-4d timing edge is dead at scale (-0.95
  net, n=2,418; every timing bin negative, the 10-14d bin's +10.2
  re-measures at -3.1); price 0.80+ as such is dead (-0.51, n=1,767);
  the old 85plus bin is *perfectly calibrated* at scale (+0.11 net,
  n=1,231); no single series is distinguishable from luck (z-variance
  1.19 across 96 series). What survived every stress: **NO favorites at
  ask ≥0.90** — +2.25pts net (n=450, 213 events, p_fair=0.0084),
  positive in all four sub-families, both window halves, both timing
  slices, and still +1.86 excluding the ended World Cup series — while
  YES favorites are overpriced in every band (-1.7 to -4.2 net). The
  spread makes the mirror trade (fading YES with NO longshots)
  negative, so the bias is only harvestable on the NO-favorite side.
  Found post-hoc in a ~50-cell scan (event-clustered t only +1.4), so
  it is a pre-registerable hypothesis, not a demonstrated edge; it is
  recorded on backlog idea `no-side-premium` (whose Becker-based
  mechanism predicted exactly this asymmetry) rather than as a revival
  of this theory, whose both-sides price-bin procedure stays dead as
  measured. The retirement proposal stands unchanged.
- 2026-08-25 — **Full-coverage rerun killed the edge; retirement
  proposed.** `backtest-2026-08-25-mention-fullcov` (tier A) replayed
  every mention-family survivor in the API-reachable close window —
  11,084 survivors across 379 series, 3,441 screen hits, all settled —
  where the original evidence was a 600-of-18,430 systematic sample that
  yielded this family's 116 rows. Result: win rate 0.797 vs mean price
  0.802, `calibration_edge_net=-1.53pts`, gross calibration edge already
  negative (-0.49), ROI -1.9%. Fresh rows only (excluding the original
  116): -1.78 net. The 85plus bin at full coverage is n=1,190,
  win rate 0.913 vs price 0.909 — *perfectly calibrated*, confirming the
  audit's suspicion that 41/41 was luck; the lt75 and 75_85 bins are
  negative outright. All four sub-families land at ~zero or negative on
  fresh rows (worldcup -0.94, earnings -3.82, trump +0.05, other -1.48),
  so the bootstrap's positive sub-families (worldcup +8.3, earnings
  +6.1) were also luck, not structure. Per-series means at n≤25 scatter
  from +22 to -45pts — mean-zero noise, and no positive slice was
  pre-registered. Conclusion: the family is priced essentially fairly
  and a favorite-buyer loses the fee. Status moved to `under_review`
  and a retirement proposal filed for the user to rule on. The first
  live out-of-sample settlement (KXTRUMPMENTION-26AUG24B-IRAN, no
  @0.89, resolved yes) also lost. Separately: the window the rerun
  *wanted* (back to 2025) is unreachable — Kalshi archives settled
  markets out of its public API ~60 days after close (2,103 of the
  11,084 survivors already returned no candles) — so full coverage of
  the reachable window was the strongest evidence obtainable, and any
  future series-level follow-up must snapshot settled markets before
  they age out.
- 2026-08-25 — **Skeptical audit of the backtest edge (user-prompted):
  the mechanics are clean, but the statistical case is much weaker than
  the headline reads.** Full detail in RESEARCH_LOG.md (2026-08-25).
  What was checked and came back clean: the replay has no lookahead
  (entry at the daily candle's closing ask with eligibility evaluated at
  that same timestamp; `no_ask = 1 - yes_bid` is exact on Kalshi's
  complementary book), fees are included, event clustering is negligible
  (113 distinct events across 116 rows), and sampled candle traces show
  stable pre-event favorites, not post-news stale quotes. What did not
  hold up: (1) tested against "the price was already fair," the bins are
  individually weak — lt75 p=0.40, 75_85 p=0.17, 85plus p=0.026 — and
  the pooled family is p=0.0395 gross, **p=0.070 after fees**, before
  any correction for this family having been *selected* as the standout
  slice of a 200-row backtest (115 series families in that run) with bin
  boundaries then fit on the same rows. (2) The family is not
  homogeneous: the positive edge is carried by World Cup sponsor-mention
  markets (+8.3pts net, n=28 — tournament over), earnings-call mentions
  (+6.1, n=38 — episodic), and a long tail of n=1 series (+12.7, n=24),
  while the one persistent political sub-family (`KXTRUMPMENTION`/
  `KXTRUMPSAY`/`KXTRUMPACT`) measured **-5.2pts net (n=26)**. (3) The
  live preview slate (`...preview30-v2`) is 100% political-speech
  series (TRUMPMENTION, WARSHMENTION, FEDMENTION, SECPRESSMENTION) —
  the bootstrapped rates are being applied to precisely the
  sub-population that measured negative. Practical upshot: do not treat
  the bucket table as measured edge for political-speech candidates;
  the 40 unsettled preview rows (none taken) are a free out-of-sample
  test settling Aug 28–Sep 15, and any promotion should wait on them
  plus a longer-window tier-A rerun with the sub-family split
  pre-registered.
- 2026-08-24 — **Split from `insider_bias` (renamed `insider_judgment`)
  v3.** See Origin, above, and `insider_judgment/THEORY.md` Learnings
  (2026-08-24 entries) for the full discovery history: the backtest that
  found this family, the flat-rate bug and its fix, the volume check, and
  the entry-timing analysis. Not duplicated here to avoid two documents
  drifting on the same facts — `mention_bucket.py`'s module docstring is
  this theory's own authoritative summary of all of it.
- 2026-08-24 — **First live runs, both under the sibling theory's old
  `insider_bias` identity, migrated here with the theory.** `run_id=
  live-2026-08-24-mention-preview30` used the pre-fix flat-rate model and
  is marked `skipped` in the ledger with a correction note — do not treat
  those 20 rows as a live recommendation. `run_id=
  live-2026-08-24-mention-preview30-v2` used the corrected price-binned
  model and is a real, if unsettled, live run.
- 2026-08-24 — **Folder restructure: `theories/insider_bias/` became a
  shared parent for this theory and `insider_judgment`, both nested inside
  it.** Requested directly: the user wanted the inheritance relationship
  (both theories screen the same board through the same shared filter)
  visible in the directory structure rather than implied by an import into
  an unrelated-looking `tools/` module. `theory_id` stayed `mention_family`
  through the move; only the package path changed
  (`theories.mention_family` → `theories.insider_bias.mention_family`).
