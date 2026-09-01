---
title: Widen the population past the allowlist, bump the version, and start recording
lane: theory
theory: deadline_drift
created: 2026-09-01
created_by: llm-market-identifier-9e
author_lane: theory
author_focus: deadline_drift
author_context: Filed at the end of the 2026-09-01 session that found the allowlist, not the thesis, is what makes this theory unmeasurable.
status: open
---
WHY. Measured 2026-09-01 over the full fetchable by-deadline history (~1,400 settled markets), at the price a NO buyer actually pays, event-clustered and bootstrapped:

  allowlist (what ships)   -1.7 pts   95% CI [-10.7, +5.1]   21 events
  wide hazard stratum      +6.3 pts   95% CI [ +2.1, +10.3]  64 events

The allowlist row is not evidence against the thesis, it is NO EVIDENCE -- 70 series is too thin a slice of the board to measure anything inside a 60-day archive window. The wide row is a real signal and it survives every cut (grows to +7.3 under a <=2pt spread filter, survives removing one-winner partition families, survives an open-interest floor). See NOTES.md 2026-09-01 and THEORY.md's Status section.

THE BLOCKER IS GONE AND NOBODY NOTICED. The allowlist was adopted on 2026-08-29 with this reasoning, still in NOTES.md: 'a cheap LLM gate -- clears the bar, forfeits TIER A, which was this theory's defining property'. CLAUDE.md's 'Structural gates keep tier A' and backtest-theory's five structural-gate conditions removed that price on the same day. 'Does this market condition on which branch the event takes?' is answerable from the market's text as written at open, carries no outcome-bearing data, decides eligibility rather than direction -- it is structural, and it costs the tier nothing.

WHAT TO DO.
1. Build the gate. Judge at the SERIES level, not per market: round 5b established this is a series-level property (70/70 exhaustive) and it is ~960 calls rather than ~4,800. Send title + rules_primary + sibling yes_sub_titles from the same event; siblings are the single most informative structural signal ('different subject' vs 'different branch') and carry no outcome information. NEVER send close_time -- on this population actual close IS the outcome (a YES market closes a median of ~100 days early), which is correction 1 in hazard.py.
2. Run the contamination probe against the gate's own sample and record the result in the judgment_runs notes. Treat an unrun probe as outcome judgment. Do not claim tier A without it.
3. Validate the gate for free against settled outcomes rather than by hand-audit: hazard.partition_families() finds families whose events pay exactly one winner, and it catches KXBIGBROTHERELIMINATION, which five rounds of rules-text regex missed. That replaces the audit's 50-market hand samples with an exhaustive check and no sampling error.
4. Bump the version -- kind 'continues' (the theory has recorded no rows, so nothing pools either way, but continues is the default and this is not a sever).
5. Promote to testing and start recording. Given DD-1 is pre-registered and unconfirmed, record OBSERVATION ROWS under the 2026-08-30 ruling -- claimed edge <= 0, rationale saying it is not a recommendation -- so cells accrue settlements without the theory claiming an edge it has not earned out of sample. Do NOT write hazard_bins.json until DD-1 clears.

DO NOT SKIP THE PRE-REGISTRATION. DD-1 is in THEORY.md with its out-of-sample set (markets settling after 2026-09-01), its power estimate (~60 days), and its kill criterion. Today's capture is in-sample and vouches for nothing. The standing capture obligation in RUNBOOK.md is now the experiment rather than housekeeping, so run it.

DATA IS ALREADY THERE. data/ now holds every settled by-deadline market in the archive window with BOTH sides of the book, volume and open interest per candle -- collect_settled --wide walks all 960 series and applies no exclusions, because capture is not classification and only capture is perishable.
