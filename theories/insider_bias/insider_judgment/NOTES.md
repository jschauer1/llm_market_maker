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
