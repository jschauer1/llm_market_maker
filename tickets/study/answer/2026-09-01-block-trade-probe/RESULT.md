# `is_block_trade` is real, and it fires ~3 times per 67 days board-wide

**Verdict: DO NOT BUILD `block-trade-whale-follow`.** Reached on the rule
pre-registered in `PREREG.md` before any per-ticker number existed.

Session `fleet-w2-g2`, new-theory lane, 2026-09-01. Spec:
`git show 6e7d920:tickets/new-theory/completed/2026-09-01-block-trade-whale-follow.md`.
Registry idea `block-trade-whale-follow` (spun off idea 32,
`kalshi-taker-flow-toxicity`).

## The number

| pass | population | trades | blocks | markets w/ block |
|---|---|---|---|---|
| A | board-wide feed, 15 consecutive pages (23:43:45–23:45:48Z) | 15,000 | **0** | 0 |
| B | 300 highest-OI liquid markets (`OI>=500, vol>=1000, spread<=0.05`), 3 pages each | 473,191 | **5** | **5** |
| C | 300 random open markets, no liquidity filter, 2 pages each | 10,727 | **0** | 0 |
| — | **total this session** | **498,918** | **5** | **5** |

Add `taker_flow`'s earlier 93,399-trade sample (0 blocks) and the repo has
now seen **~592,000 Kalshi trades and 5 block prints** — 1 per ~118,000.

Pre-registered bar was **>= 30 markets carrying a block**. Observed: 5.

## Coverage — why this is not a thin sample

Pass B walked **205 of 300 markets to exhaustion** (fewer than 3,000
trades exist for them at all), and the median market's oldest reached
trade is `2026-06-26T20:46Z` — the feed's retention floor itself. So for
most of the sample this is not a sample: it is **the market's entire
reachable trade history**. The 5 blocks are 5 events in ~67 days of
complete history over the liquid board.

## The flag is genuine, and it is not a size proxy

Every block is 4–5 orders of magnitude above its own market's median
trade, and every one is the largest print in that market's history:

| ticker | time (UTC) | side | count | price | market median size |
|---|---|---|---|---|---|
| `KXFLYCANCJFK-JFK-ALL-26OCT21-T50` | 2026-07-27 20:14:32 | yes | 3,000,000 | 0.004 | 13.5 |
| `KXNCAAFPLAYOFF-26-LSU` | 2026-08-13 19:05:35 | yes | 837,500 | 0.41 | 11.8 |
| `KXNCAAFFINALIST-27-LSU` | 2026-08-13 19:06:16 | yes | 537,500 | 0.12 | 25.0 |
| `KXNCAAF-27-LSU` | 2026-08-13 19:06:28 | yes | 787,500 | 0.08 | 91.1 |
| `KXCAGOAT-26SEP30` | 2026-08-04 19:37:00 | no | 500,000 | 0.90 (yes) | 23.3 |

**Two facts the ticket wanted, both answered.**

1. *Is the population empty?* No — the facility exists and is used for
   exactly what the thesis describes. It is simply almost never used.
2. *Are blocks maker inventory transfers rather than directional bets?*
   These are not inventory transfers. **Three of the five are one trade**:
   LSU football across three different events (season wins, playoff,
   finalist), all YES, all inside **53 seconds**. That is one participant
   putting on a correlated directional basket by negotiation — precisely
   the whale the ticket hypothesised.

So the honest count of independent decisions is **3, not 5**.

## Why 3 events kills it, robustly

At 3 independent block events per 67 days the board produces **~16 per
year** (~27/yr if each print is counted separately). This repo's evidence
gates are >= 10 event clusters and >= 5 settlement days. A theory firing
16 times a year, on single markets, in unrelated families, would take
**years** to clear its own gates — and would then be resting on a sample
assembled across wholly different regimes.

**This conclusion does not depend on the retention floor.** The open
`taker_flow` ticket asks whether the feed's 2026-06-26 floor is fixed (so
the window grows) or rolling (so it does not). It does not matter here:
even a *fixed* floor giving a full year of history yields ~16 events. The
rate is the kill, not the window.

## What this does NOT establish

Whether Kalshi runs a larger negotiated-block business that is not
surfaced on the public trade feed. If it does, it is invisible here — and
a signal you cannot read is not a theory either, so the verdict stands
regardless.

## Reusable capability facts (they cost a session to learn)

- **`is_block_trade` is present on every trade payload** (10/10 keys on
  all 15,000 pass-A rows) and is a measured `false`, not a missing field.
  A future reader does not need to re-establish that.
- **A liquid Kalshi market's ENTIRE reachable trade history is usually
  under 3,000 trades** — 205 of 300 of the highest-OI markets on the board
  exhausted inside 3 pages. Any flow theory can plan `max_pages=3` as
  full coverage rather than as a sample, which is a much cheaper collection
  budget than the module docstring's "max_pages is a real budget" implies
  for *liquid* names.
- **Very large prints happen constantly without the flag**: 1,342 of
  15,000 board-wide trades were >= 500 contracts, one was 272,727, and
  none was flagged. `is_block_trade` means *negotiated*, not *big*.

## Reproducing

```bash
python pass_a.py board_trades.jsonl 15     # board-wide feed
python pass_b.py pass_b.jsonl 300 3        # liquid stratum
python pass_c.py pass_c.jsonl 300 2        # random stratum (seed 20260901)
```

`pass_b.jsonl` / `pass_c.jsonl` are kept — one row per market with counts,
open interest, spread, walk depth and oldest trade reached, which is the
part with reuse value. `board_trades.jsonl` (4.9 MB of raw pass-A payloads,
zero blocks in it) was **not** kept: its content is fully summarised by the
size distribution above, and the per-market files carry everything a later
question would need. Re-running pass A costs two minutes.
