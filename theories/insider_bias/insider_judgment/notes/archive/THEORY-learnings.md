## Learnings

- 2026-08-29 — **The bet rule is registered as slice
  `strong-moderate-no`** (`theory_slices`; `cli slices report
  insider_judgment --version 3`), so ranking reads this theory per
  segment: candidates matching strong-or-moderate NO rank on the
  slice's out-of-sample record (+4.30 net row-weighted / +8.10 ± 1.88
  day-weighted, 88 clusters / 42 days — the OOS cell survives day
  clustering, which the judged runs as a whole did not), and everything
  else ranks on the complement (−2.54 net, 809 clusters), not the
  aggregate. `s200b`/`s57` are the designated out-of-sample runs; `s200`
  stays in-sample. Slice evidence is per-version: v4's segments are
  empty until its rows settle, and any v4 recommendation citing the v3
  segment must say so. No version bump — a slice is ranking-layer data.
  Full numbers and caveats: `NOTES.md` 2026-08-29 (cont.).
- 2026-08-26 — **The campaign's authoritative summary lives in
  `backtests/RESULTS.md`** — read it before quoting any number from the
  entries below. It carries the corrected statistics (Holm over the
  pre-registered family: the bet rule and moderate-NO survive,
  strong-NO alone and the divergence flag do not; event-clustered
  significance ≈ p=0.01, not the row-level p<0.0001), the attribution
  ladder, the timing verdict, the gate validation (99/100 weak), and
  the contamination audit (clean; the batch-as-of wrinkle bounded, rule
  holds at +4.65 on the clean subset).
- 2026-08-26 — **Full-population judgment coverage; the pre-registered
  NO-side rule replicated out of sample.** All 457 gate-plausible events
  from the tier-A walk are now judged (runs `...judged-s200`, `-s200b`,
  `-s57`; 1,561 market rows). The bet rule pre-registered after s200 —
  strong-or-moderate verdict, NO-side favorite, first-qualifying entry —
  scored **+4.92pts net (p=0.0008, 312 rows / 85 events) on the 257
  events judged after pre-registration**, vs +5.34 (p=0.0018) on the
  round that generated it; pooled +5.10, p<0.0001, win rate 0.922 at
  mean ask 0.863. Moderate-NO replicated stronger (+5.13, p=0.003);
  strong-NO in direction but weaker (+4.29, p=0.096). The NO bucket
  ladder is monotone and significant on the full population (+6.50 /
  +4.52 / −1.96); every YES cell stays flat-to-negative — judgment adds
  selection only on the NO side, consistent with the optimism-tax
  mechanism and with strong-YES's bleed tracing to sealed-tabulation
  award families (see 2026-08-26 log). Timing: uniform 3-2d late entry
  underperforms first-qualifying entry on the full set (+2.32 vs
  +5.10); only strong-NO tolerates late entry. Promotion still requires
  live settlements; the proposed v4 procedure (NO-side-only betting
  rule, dtc + divergence flag recorded per row, award families gated)
  awaits the user's ratification.
- 2026-08-25/26 — **Two backtests at scale: screen+gate is breakeven,
  and judgment shows its first predicted ordering.** Tier A
  (`backtest-2026-08-25-insider-fullcov`): every non-mention survivor in
  the API-reachable window (n=3,181 settled, 831 events) — the gate
  discriminates (+0.71pts net kept vs −2.18 gated, ~2.9pt gap in the
  predicted direction), but the kept slice is fair-priced once event
  clustering is respected (t_ev −0.25); the old 84-row sample's +4.40
  was small-sample noise, exactly like the sibling theory's +5.48. So
  the thesis rests entirely on stage-2/3 selection. Tier B
  (`backtest-2026-08-26-insider-judged-s200`): 200 seeded gate-plausible
  events judged by claude-sonnet-5 through the committed analysis
  prompt, web search off, blind payloads, per-batch as-of dates, with a
  committed mechanism context sheet substituting for search (all
  artifacts under `backtests/judged-s200/`). Result: **buckets order
  outcomes as the thesis predicts** — strong +5.09pts net (n=111 rows /
  24 events, row-level p=0.044), moderate +0.85, weak −0.79; event-level
  means +2.88 / −0.56 / −2.26. Two sharper cells, both post-hoc and both
  echoing the session's optimism-tax finding: strong-NO +8.59 (n=83,
  p=0.006) vs strong-YES −5.30; and events flagged
  `rules_diverge_from_title` scored +1.97 with the strongest clustered
  stat of the day (t_ev +2.90, 26 events) — the "read the rules, not
  the title" claim finally has a measurement. Honest limits: 24 strong
  events is thin, clustered support for the bucket ordering itself is
  weak (t_ev +0.66), and the sharp cells came from slicing. Status
  stays `testing`; what this earns is a pre-registered live tracking
  plan — strong (and strong-NO specifically) as the buckets that must
  repeat live before any promotion, with the divergence flag recorded
  on every live row.
- 2026-08-23 — Ported from `kalshi_trader`. The reality-TV weighting is
  recorded here as a stage-2 heuristic rather than encoded, because it has not
  yet been measured against the endorsed/rejected split. Migrate it into
  stage 1 only once there is evidence.
- 2026-08-23 — The imported history's `edge_basis='prior'` rows are not "it
  felt about right" placeholders — every field on this repo's convention
  says a missing basis means that, but these rows are the exception. They
  are LLM-introspected `q` values from `kalshi_trader`'s OpenAI gpt-5 **pick
  stage** (not the classifier/gate, which was gpt-5-mini and never produced a
  `q` at all), kept because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge. See each row's
  `extra_json.model_prob_source` for the exact provenance.
- 2026-08-23 — **First live run.** Complete board (96,084 markets) → 765
  candidates / 274 events. Classified against this theory's own gate rules,
  **242 of 274 events (88%) are categories the gate is written to reject** —
  crypto/commodity/compute strike ladders, weather, live sport that leaked
  past `EXCLUDED_PREFIXES`, scheduled indicators, and aggregates of many
  independent people. Stage 1 has no thesis term in it; it selects tradeable
  favorites, not markets an insider could know. Strong candidate explanation
  for the flat imported record.
- 2026-08-23 — **19 of 32 judged events (59%) had resolution rules that
  diverge from the title.** This section already lists that as a warning
  sign; at 59% it is the modal property of the candidate class, not an
  occasional trap. Reading rules may be a larger share of the available edge
  than identifying informed groups.
- 2026-08-23 — **The pre-taped-TV heuristic above is wrong as written.**
  Applied to `KXAGTELIMINATION`, deep analysis correctly refused it: AGT's
  live quarterfinals are not pre-taped and elimination is decided by public
  vote — the aggregate-of-many-people case the thesis excludes. The
  heuristic needs the qualifier *pre-taped **and** taping already completed*;
  on a live-vote show it inverts. `KXBIGBROTHERELIMINATION` is the version
  that does work: 24/7 live feeds give a concrete group the nominations,
  veto result and vote plan days before broadcast.
- 2026-08-23 — **Most rules divergences cut against the side the screen
  picks.** 543 of 765 candidates are NO-side favourites, and a rule broader
  than its title makes YES *easier* — so the divergence damages exactly the
  leg the screen selected. Seen live on `KXCLAUDE-NXTMYTH` (an unexcluded
  Mythos 5 already satisfies it), `KXNEWDEAL` (Trump already posted "we have
  a DEAL"), `KXTRYFIRECOOK` (removal already attempted in 2025), and the
  rolling-BLA markets (arguably already submitted). This is mechanically
  checkable and is the strongest stage-1 candidate for v3.
- 2026-08-23 — **v2 recorded**: 44 opportunities, 3 endorsed / 41 rejected,
  all `judged_blind=True`, all `edge_basis='prior'`, all carrying
  `final_recommendation.decided_by`. The gap between what the mechanical rule
  would have endorsed (25) and what the main model recommends (3) is the
  entire reason Stage 3 exists. They settle Aug 24–Sep 5, which makes
  `interpretation_value` computable for the first time.
- 2026-08-24 — **First tier A backtest: the stage-1 screen alone is
  net-positive, but the number is a mix of two very different signals.**
  90-day window, `run_id=backtest-2026-08-24-stage1-90d`, n=200 real screen
  hits (see "How to backtest" for the fetch methodology). Overall:
  `win_rate=85.0%`, `price_implied_rate=82.7%`, `calibration_edge_net=
  +1.38pts`. That headline number undersells what's actually there — three
  slices tell three different stories:
  - **n=47, series `gate.py` already classifies as "aggregate of many
    independent people"** (Rotten Tomatoes scores, Netflix rankings, album
    equivalent sales, YouTube view counts, shipping-lane traffic counts,
    press-briefing/launch counts): `calibration_edge_net = -11.12pts`. This
    is **direct mechanical confirmation that gate.py's existing exclusion of
    this family is correct** — buying these "favorites" loses money against
    their own price, not just against the thesis. Previously this was a
    design argument from first principles; now it is measured, tier A, n=47.
  - **n=116, series with a "MENTION"/"SAY"/"ACT" suffix that `gate.py`'s
    current regex does NOT catch** (`KXWCMENTION`, `KXTRUMPMENTION`,
    `KXFIGHTMENTION`, `KXLATENIGHTMENTION`, `KXHEARINGMENTION`,
    `KXFEDMENTION`, `KXFOXNEWSMENTION`, ...): `calibration_edge_net =
    +5.48pts`. Structurally this reads like the same aggregate-of-many
    pattern (a mention is decided by whether a public figure happens to say
    something, not by a small informed group), but it backtests
    **positive**, unlike the family above. Two live possibilities, not yet
    distinguished: either this is a base-rate-calibration edge unrelated to
    the insider thesis (still worth a mechanical rule, but a different
    theory), or "will X mention Y" markets really do have an informed
    minority (a press office, a campaign, a network that knows what's
    scheduled to air) the way `KXBIGBROTHERELIMINATION`'s live-feed viewers
    do. `gate.py`'s classification of this whole family as `PLAUSIBLE` is
    presently just an accident of which specific series got named in its
    regex, not a decision — see Status item 3.
  - **n=37, everything else (not mention-family, not gate-rejected)** — the
    slice that most resembles what actually reaches judgment in the live
    pipeline: `calibration_edge_net = +4.40pts`. Named series in this slice
    include `KXBIGBROTHERELIMINATION` (the same series as a live v2
    endorsed opportunity), `KXGABBARDOUT`, `KXEPSTEIN`, `KXFDAAPPROVE`,
    `KXTRUMPMEET`, `KXSTARMERCABLEAVE`, `KXLIUKELIMINATION`/
    `KXLOVEISLANDUSARANK` (reality-TV elimination, the theory's own
    strongest sub-case), `KXSUMMERHOUSECAST`, `KXESPYS`,
    `KXTAYLORSWIFTWEDDINGATTEND`. This is the cleanest tier A evidence yet
    that the screen, restricted to genuinely thesis-eligible families, beats
    its own price.

  Methodology note: this backtest used a **category-narrowed slice of
  settled markets** (Kalshi series `category` not in `backtest.py`'s
  `NO_CATEGORIES`, recency ≤ 60 days), not literally every settled market —
  see `backtest.py`'s module docstring point 2. That scoping choice is why
  n=200 is a *sample* of 18,430 raw survivors, not the full count, and
  should be named alongside this result, not left implicit.

  **How much to trust each slice, not just the point estimate.** A rough
  z ≈ (win_rate − price_implied_rate) / sqrt(win_rate·(1−win_rate)/n) per
  slice — an approximation, since it treats each slice's price-implied rate
  as one fixed benchmark rather than testing each contract against its own
  price, so read it as "roughly how many standard errors from zero," not a
  real p-value: aggregate-of-many z≈-1.6, MENTION-family z≈+2.1, clean
  thesis-eligible z≈+1.1. Only the MENTION slice clears a conventional
  2-SE bar on its own; none of the others individually would survive a
  strict significance filter. What makes the *pattern* more trustworthy than
  any single slice's precision is that all three land exactly where the
  theory's own structure predicts — strongly negative on the family it
  already excludes, positive on families with a plausible informed minority.
  Do not read any one slice's exact point estimate (`+4.40`, `-11.12`,
  `+5.48`) as a number that will hold at this precision going forward; read
  the *direction and rough size* as the evidence, and let more data narrow
  it. This detail exists here rather than only in conversation because a
  headline number without its confidence is a number that gets over-trusted
  the next time someone reads it.
- 2026-08-24 — **Stage 3 endorsed `KXBIGBROTHERELIMINATION-26AUG27-DRE`
  without verifying the resolution mechanism, and the user caught it, not the
  process.** The recorded rationale said "no rules divergence... resolution
  lands before close" and treated the outcome as effectively already known
  via 24/7 live feeds. That is half right: nominations and the veto result
  really were known days in advance. What it missed is that this season
  resolves eviction through "BB Block Buster" — the three nominees compete
  in a genuinely live, live-that-day competition, the winner is safe, and
  only *then* does the house vote out one of the other two. The competition
  itself is live sport, exactly the category this theory's own gate says no
  to; a subagent correctly reporting the pre-known facts (nominees, veto)
  does not mean the *thing the market actually resolves on* is one of them.
  On checking (web search, since this was live research on an open
  opportunity, not a backtest — see Backtest tiers on why that distinction
  matters), the NO bet still holds up, but for a narrower and more specific
  reason than originally recorded: the house's stated plan (Gold Derby, Big
  Brother Network, live-feed coverage, Aug 22-23) covers every branch of the
  live competition — Drew is protected whether Mallory, Taylor, or Drew
  himself wins it. That is house consensus robust across a live event, not
  an outcome already decided before the event. Corrected the opportunity's
  recorded interpretation (id 192) rather than leave the overstated version
  standing. The general lesson, folded into Stage 3's checklist above:
  verifying the facts a subagent reports is not the same as verifying that
  those facts are what the market actually resolves on.
- 2026-08-24 — **Built, ran, debugged, and then split out the mechanical
  MENTION-family path — now `mention_family`, its own theory.** For a few
  hours this lived here as v3's `mention_bucket.py`. In that window: first
  live run correctly found 0 candidates (checked why — a board-state fact
  about days-to-close, not a bug); a user math-check corrected a
  points-vs-ROI confusion (`calibration_edge_net` is not a percentage
  return — the real `roi_all` for this slice is 6.7%); a real bug was found
  and fixed (one flat win rate for the whole price band, when win rate
  actually rises sharply with price — caught because the user's own trading
  experience didn't match the model's ranking, and the backtest data agreed
  with the user); and an entry-timing analysis found most candidates only
  become eligible in the final days before close, structurally, not by
  choice. All of that detail now lives in `mention_family/THEORY.md`,
  `mention_family/RUNBOOK.md`, and `mention_bucket.py`'s own module
  docstring — not duplicated here to avoid two documents drifting on the
  same facts. The evidence (116 backtest rows, both live preview runs)
  migrated with the split rather than resetting to zero; see that theory's
  own Learnings for what's specific to its life as an independent theory
  going forward.
