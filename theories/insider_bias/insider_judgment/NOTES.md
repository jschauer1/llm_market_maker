# insider_judgment — notes

Lab notebook: raw, dated, append-only. The format and the distillation rule
are in `theories/_TEMPLATE/NOTES.md`. Nothing here is private — any session
may read any theory's notes.

## 2026-08-25 — Notebook opened; where this theory's history lives

This file starts empty by design. Everything written before today stayed
where it was written, and none of it was migrated:

- **`THEORY.md` Learnings** — the distilled record: the reality-TV stage-2
  heuristic deliberately left unencoded until it is measured against the
  endorsed/rejected split, the `edge_basis='prior'` imported-history
  exception (LLM-introspected `q` values from `kalshi_trader`'s pick stage,
  kept precisely because they are the only dataset that can answer whether
  introspected probabilities realize their claimed edge), and the Big
  Brother correction.
- **`RESEARCH_LOG.md`** — the session narratives: the 2026-08-24 tier A
  backtest of the stage-1 screen, including the 47-minute false start that
  preceded it, and the 2026-08-24 Big Brother / mention-family follow-ups.
- **`theories/insider_bias/replay.py`'s module docstring** (this was
  `insider_judgment/backtest.py` until 2026-08-25; do not confuse it with
  the `backtest_fullcov.py` / `backtest_judged.py` drivers still in this
  folder) — the three constraints that shape
  the replay: combinatorial-series fetch scoping, the category pre-filter's
  status as a fetch-scoping decision rather than a change to the screen
  under test, and per-day versus cumulative candle volume.

From here on, raw findings about this theory land in this file, and
`THEORY.md` changes only when the claim, the procedure, or the status
changes.

## 2026-08-27 — v3's first score (+11.85 net, n=17) measures the screen, on one day

`score report insider_judgment` now shows v3 at `n=17`, win rate 0.941,
`calibration_edge_net = +11.85`. Two things about that number before anyone
banks it.

**1. It is not the theory's product.** All 17 settled rows carry
`disposition='screened'` — raw stage-1 screen output from
`live-2026-08-26-noscan`, recorded but never gated and never judged. 15 of
the 17 are sports (KXARGNACB, KXBOLPDIV, KXCPLMATCH, KXUSLSPREAD/TOTAL,
KXT20MATCH, KXKBOSPREAD, KXFIBAGAME, KXEGYPLGAME), all bought on the **NO**
side. The theory's actual recommendations — `endorsed`, n=8 outstanding —
have **0 settled**, so `interpretation_value` is still `None` and nothing
here says anything about whether the judgment stage adds or destroys value.

**2. All 17 settled on 2026-08-27, and that day flattered everything.**
Whole-population control over the same screen, priced from the
2026-08-27T01:06:07Z snapshot before any of it settled
(`studies/2026-08-27-settlement-day-clustering/`, n=99 settled of 109):
favorites beat implied by +5.40 net that day; 52/52 favorites priced
0.90–0.98 won.

The honest comparison for these rows is the day's **NO-favorite** baseline,
since that is what they are: n=44, **−3.05** net. Against that, 16/17 at
+11.85 is roughly +15 pts of outperformance — the one genuinely interesting
number here, and it is drawn from one settlement day with `n_days=1`, so no
standard error exists for it. Under the naive row-level SE it would look
like ~2σ; it is not.

Worth noting rather than acting on: on 08-25 the population's NO favorites
ran **+7.98** net and its YES favorites −1.42, i.e. the side split reverses
day to day. Whatever these 17 rows show, one day cannot distinguish "the
screen picks good NO favorites" from "NO favorites had a day".

**Nothing changes about the theory.** Status stays `testing`, v3, no
version bump, no claim added or withdrawn — this is a note about how to
read a score, not about the procedure. The lifecycle trigger (n=20 with
net ≤ 0) is not close and would not fire on this anyway.

**What to watch:** the 8 endorsed rows are the ones that matter, and the
GTA video-length ladder (4 legs) plus both Big Brother legs settle tonight —
that is the first real read on the endorsed tier. Track it with
`score report insider_judgment | jq .settlement_days.endorsed` and wait for
`n_days`, not `n`, to grow.

## 2026-08-27 (later) — the tier-B judged backtests do not survive day clustering

Follow-on from the settlement-day clustering study. Historical backtests
previously could not be day-clustered at all — the replays recorded
settlements with no `resolved_at`. Recovered from `extra_json`
(`entry_day_iso + days_to_close_at_entry`) with no API call; see
`studies/2026-08-27-settlement-day-clustering/backfill_resolved_at.py`.

| run | n | days | row net | day net | row SE | day SE |
|---|---|---|---|---|---|---|
| insider fullcov (screen only) | 3,195 | 66 | −1.15 | −1.16 | 0.63 | 1.12 |
| judged s200 | 704 | 58 | **+0.67** | **−0.35** | 1.27 | 2.50 |
| judged s200b | 644 | 63 | −0.02 | +0.35 | 1.37 | 2.33 |
| judged s57 | 216 | 30 | **+1.90** | **−1.36** | 2.02 | 4.78 |

**The judged runs flip sign purely on how days are weighted**, and their
clustered SEs swamp either estimate. Row-weighting over-counts busy
settlement days, so a handful of good heavy days lifts the row-weighted
figure — precisely the confound the study documents, appearing in the very
runs that were meant to validate v3's buckets (the s-series completed 100%
judgment coverage of the gate-plausible population and carried
pre-registered cells: strong-NO positive, moderate-NO positive, bucket
ordering).

An estimate that changes sign under reweighting is not evidence in either
direction. It does not say the buckets are wrong; it says these runs
cannot tell us.

**What changes, and what does not.** Status stays `testing` — which
already means "running, claims not demonstrated", so nothing about the
theory's standing moves. No version bump: the procedure is untouched.
What changes is the promotion bar: **v3 must not go `active` on the
s-series**, because day-clustered they show nothing. The stage-1 screen's
own number (−1.16 ± 1.12) is likewise not distinguishable from zero,
though it was never the theory's claim — the claim is that stage-2
judgment adds edge on top of it, and `interpretation_value` is still
`None` because the endorsed tier has no settled rows.

**So the live endorsed tier now carries the weight the backtests cannot.**
First settlements are due tonight/2026-08-28: the GTA video-length ladder
has converged in-market to the endorsed [15,30) view (all four endorsed
legs 187, 188, 9238, 9239 quoted at 1.00), and both Big Brother legs
resolve tonight (TAY looks a win, NO at 0.91; DRE looks a loss, NO down to
0.44 from the 0.82 entry). That would be roughly 5 wins and 1 loss.

**Read it with `settlement_days`, not `n`.** All six settle the same
night, so it will come back `n_days=1` with no computable SE — a first
data point, not a verdict, and the temptation to call a 5-1 start
"validation" is exactly what this whole day's work exists to prevent.
