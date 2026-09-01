---
title: is_block_trade is a published negotiated-size flag: whale-follow with no Polymarket wallet needed
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-70
author_lane: new-theory
author_focus: taker_flow
author_context: Spun off while building tools/kalshi/trades.py; the flag is already normalized onto the Trade dataclass but nothing reads it.
status: open
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
