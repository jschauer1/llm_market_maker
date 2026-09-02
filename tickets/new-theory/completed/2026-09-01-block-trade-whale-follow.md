---
title: is_block_trade is a published negotiated-size flag: whale-follow with no Polymarket wallet needed
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-70
author_lane: new-theory
author_focus: taker_flow
author_context: Spun off while building tools/kalshi/trades.py; the flag is already normalized onto the Trade dataclass but nothing reads it.
status: done
closed: 2026-09-01
resolution: KILLED on population, 2026-09-01 by fleet-w2-g2, on the cheapest decisive first step this ticket itself named. Full measurement and the three reusable capability facts: tickets/new-theory/evidence/2026-09-01-block-trade-probe/RESULT.md; pre-registration in that folder's PREREG.md, written before any per-ticker count. HEADLINE: 5 block trades in 498,918 trades (1 per ~118,000), across three strata including 205 markets whose ENTIRE reachable trade history was walked. Pre-registered bar was >=30 markets carrying a block; observed 5, of which 3 are a single decision (LSU football, three events, all YES, 53 seconds apart). ~3 independent block events per 67 days = ~16/year board-wide, which cannot clear >=10 event clusters / >=5 settlement days in any useful horizon. Robust to the open fixed-vs-rolling retention question: a full year of history still yields ~16. WHAT THE TICKET GOT RIGHT: both of its named kill tests came back FAVOURABLE -- the flag is genuine and is not a size proxy (1,342 of 15,000 trades were >=500 contracts, one was 272,727, none flagged; every real block was 500k-3M and the largest print in its market's history), and blocks are directional baskets rather than maker inventory transfers. The thesis was sound; there is just no population. Idea 37 recorded dead with a revisit angle that redirects the finding at a zero-gate alert and at a correlated-flow detector that needs no block flag.
---
CLAUDE.md says Polymarket is a first-class research tool because it exposes per-trade wallet identity that Kalshi does not. True about IDENTITY -- but Kalshi publishes is_block_trade, a flag on negotiated large-size trades, and idea 10 (whale-follow) currently assumes cross-venue matching is required. It may not be.

WHAT EXISTS ALREADY. tools/kalshi/trades.py normalizes is_block_trade onto the Trade dataclass. Nothing reads it. The client also carries the feed's measured quirks (retention floor 2026-06-26, newest-first ordering, per-ticker collection only), so a study can start immediately.

FIRST STEP, cheap and decisive: MEASURE THE BASE RATE BEFORE DESIGNING ANYTHING. taker_flow sampled 93,399 trades across the 40 highest-volume markets and the one market inspected in detail had ZERO block trades. If block trades are vanishingly rare on the liquid board, there is no population and the idea dies for one afternoon's work. If they are common enough, the thesis is: a negotiated block is size that could not be worked into the book, which is what an informed large trader looks like -- so follow the block's direction.

WHAT WOULD KILL IT, beyond an empty population:
  - Blocks are market-maker inventory transfers rather than directional bets, in which case direction is meaningless. Check whether blocks cluster at the touch or away from it.
  - The same residual test taker_flow's thesis failed: does block direction predict settlement BEYOND what the contemporaneous price implies? A naive test rediscovers that favourites win.
  - Fees and a >=24h decision buffer, which is the rhythm this repo trades at. taker_flow's buffer sweep found signal DECAYS toward the close rather than growing, so do not assume a fast signal is available.

RELATION TO taker_flow: distinct signal on the same feed. taker_flow aggregates ALL flow into an imbalance; this keys on individual negotiated prints. taker_flow's aggregate failed its pre-registered rule (+0.70 pts, t=+0.62) while its extreme tail survived as an unproven registered slice -- so the feed is not established as predictive, and this ticket should carry its own pre-registration rather than borrowing taker_flow's optimism.

Mechanical, tier A, replays over the same ~67-day window.
