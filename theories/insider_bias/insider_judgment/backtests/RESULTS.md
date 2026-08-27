# Judged-backtest campaign results — 2026-08-25/26

The authoritative summary of the tier-B judgment backtests over
`insider_judgment`'s population. Everything here is reproducible from
the ledger (run ids below), the committed batch artifacts in this
folder's subdirectories, and `db/history_cache.db`; the session
narrative lives in RESEARCH_LOG.md (2026-08-25/26 entries).

## What was run

| run id | population | events / rows | role |
|---|---|---|---|
| `backtest-2026-08-25-insider-fullcov` | every non-mention screen survivor, reachable window | 831 / 3,181 | tier A base: screen + code gate, no LLM |
| `backtest-2026-08-26-insider-judged-s200` | random 200 of 457 gate-plausible events | 200 / 704 | tier B round 1 — generated the hypotheses |
| `backtest-2026-08-26-insider-judged-s200b` | 200 of the remaining 257 | 200 / 641 | tier B round 2 — replication (pre-registered) |
| `backtest-2026-08-26-insider-judged-s57` | the final 57 | 57 / 216 | completes 100% population coverage |
| `exp/2026-08-26-insider-judged-gated100` | 100 of 377 gated-OUT events | 100 / 480 | gate validation experiment (excluded from track record) |

Protocol, identical in every judged run: claude-sonnet-5 subagents via
the committed `prompts/analysis.md`, 25 events per batch, **web search
off**, blind payloads (`pipeline.build_blind_payload` whitelist +
`assert_blind`), one pinned as-of date per batch, a committed
series-family mechanism sheet in lieu of search (`context_sheet.md` in
each run folder), every artifact committed before dispatch and every
verdicts file ingested and committed before the next dispatch. One
batch (s200b/4) was recovered intact from a mid-run usage cutoff —
the protocol's design case.

## Headline result

**The pre-registered bet rule — buy the NO-side favorite at its first
screen-qualifying day when the judge says `strong` or `moderate` —
replicated out of sample.**

| | rows / events | win rate | mean ask | net edge/bet | row-level p_fair |
|---|---|---|---|---|---|
| round 1 (rule declared after this) | 239 / 77 | 0.921 | $0.86 | +5.34 | 0.0018 |
| **replication (judged after declaration)** | 312 / 85 | 0.923 | $0.87 | **+4.92** | **0.0008** |
| pooled | 551 / 162 | 0.922 | $0.86 | +5.10 | <0.0001 |
| pooled, award families excluded | 453 / 123 | 0.932 | $0.87 | +5.45 | <0.0001 |

**Corrected significance (the numbers to quote):** Holm-Bonferroni over
the pre-registered family of four, on replication data only: the bet
rule (p=0.0008 vs 0.0125) and moderate-NO (p=0.0030 vs 0.0167)
**survive**; strong-NO alone (p=0.096) and the rules-divergence flag
(p=0.23) do not. Event-clustered one-sided t (one observation per
event, removing sibling-strike inflation): **+5.21/event, t=2.26,
p≈0.012** on the 85 replication events; +3.87, t=2.29, p≈0.011 pooled.
The defensible claim is "significant at ~p=0.01 clustered," not the
row-level p<0.0001.

## Full-population bucket × side (457 events, 1,561 rows)

| verdict × side | rows / events | win | net | note |
|---|---|---|---|---|
| strong NO | 162 / 39 | 0.938 | +6.50 | real inside the rule; not Holm-significant alone |
| moderate NO | 389 / 123 | 0.915 | +4.52 | the workhorse; Holm-survives |
| weak NO | 471 / 181 | 0.854 | −1.96 | correctly identified as nothing |
| strong YES | 67 / 32 | 0.776 | −4.98 | bleed traced to sealed-tabulation award votes |
| moderate YES | 173 / 81 | 0.809 | −3.19 | fade |
| weak YES | 299 / 158 | 0.866 | +0.36 | noise |

The ladder exists only on the NO side. Mechanism: the optimism tax —
retail hope keeps NO favorites cheap; whatever insiders know on the
YES side is already in the ask (and sealed award knowledge never
reaches the price at all).

## Attribution ladder (what each layer earns)

| strategy | rows / events | net/bet |
|---|---|---|
| NO favorite on everything screened (mention + non-mention) | 3,807 / 978 | −0.16 |
| NO favorite on gate-plausible only (screen+gate, no judge) | 1,022 / 343 | +1.85 |
| NO favorite on strong/moderate verdicts (the rule) | 551 / 162 | +5.10 |

Blanket NO is worth nothing (fees eat the raw asymmetry); the gate
adds ~+2; the judge adds ~+3 more by removing weak-NO.

## Timing (user question; measured two ways)

Uniform "enter 3-2 days before close" repriced from the candle cache
(`reprice_entry_window.py`): the rule earns +2.32 (p=0.06) versus +5.10
at first-qualifying entry — **the moderate edge is an early-entry
edge**; its ask converges from $0.86 to $0.90 by 2.5 days out. Only
strong-NO tolerates late entry (+8.3 repriced late; +12.2 in the
late-first-qualifier slice — texture, not Holm-proven). Late entries on
weak verdicts were the worst cells measured (−19.9 within 2 days).

## Gate validation

100 gated-out events judged under the identical protocol: **99 weak,
1 moderate, 0 strong.** The regex gate and the judge agree essentially
perfectly on what carries no insider thesis; the gate discards no
judgable opportunity. (The tier-A +4.56 in the gated GPU-ladder family
is price-band luck, not missed insider signal.)

## Contamination audit (all clean; one wrinkle bounded)

Zero WebSearch/WebFetch invocations across all 23 judge transcripts
(grepped, not self-reported). Payloads: whitelist-only fields on all
2,044 markets; zero price/outcome keys; 'settle' hits are rules
boilerplate. Wrinkle: batch-level as-of pinning left 618 markets whose
close_time preceded the pinned "today" — a judge could infer those had
concluded, never how. Shape check: those rows scored WORSE (leakage
inflates confident buckets; this deflated them), and **the rule on the
clean still-open subset holds at +4.65, win 0.910, n=409.** Behavioral
fingerprint is anti-leakage: strong-YES lost money, and three judge
instances independently rediscovered the Emmy nomination-day trap.

## Standing caveats

One summer (June–Aug 2026), one regime. Entries assume the daily
candle's closing ask was fillable in thin books (volume floor is 500
contracts lifetime). 551 rows are ~162 independent events. Backtest
edges historically land below their paper numbers live.

## Proposed v4 live procedure (awaiting user ratification)

Judge as today, plus: bet only strong/moderate NO favorites at first
qualification; record days-to-close and the divergence flag on every
row; pin judgment as-of per event, not per batch; add a leakability
question to the prompt ("can this group's knowledge escape before
close?"); candidate gate NO-rule for sealed-tabulation award families.
Promotion to `active` requires the rule repeating on live settlements.
