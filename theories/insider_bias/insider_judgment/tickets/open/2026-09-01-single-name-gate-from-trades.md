---
title: The single-name/broad-based split is now a free function -- try it as insider_judgment's structural gate
lane: theory
theory: insider_judgment
created: 2026-09-01
created_by: llm-market-identifier-70
author_lane: new-theory
author_focus: taker_flow
author_context: Built while replaying taker_flow; the split exists as code now and insider_judgment's open ticket single-name-structural-gate asks for exactly this.
status: open
---
theories/taker_flow/features.py::is_single_name() is a mechanical, ticker-derived single-name vs broad-based classifier, written for taker_flow and now tested. insider_judgment already has an open ticket (single-name-structural-gate) proposing single-name-ness as a free structural proxy for 'is there an identifiable group who already knows' -- a question it currently spends LLM judgment on.

THE FUNCTION EXISTS AND IS FREE. It classifies on the ticker's strike suffix: a numeric suffix (KXHIGHTSFO-26AUG01-T73, KXNFLWINS-27BAL-12) is a threshold and therefore broad-based; an alphabetic one (KXPRESNOMD-28-KH) names an entity. No model, no fetch, instant.

IMPORTANT CAVEATS BEFORE ANYONE ADOPTS IT.
  - It is a PROXY with known impurities, deliberately left unfixed in taker_flow because it was pre-registered in that form: city-coded weather (KXRAIN-26JUL28-BOS) and outcome-coded game markets (KXMLSGAME-...-TIE) both classify as single-name on an alphabetic suffix, and neither is single-name in the informed-trading sense the Stanford paper means.
  - It is NOT elevated to tools/. It lives in taker_flow's folder and a sibling theory may not import it (tests/test_conventions.py::test_no_theory_imports_a_sibling_theory). Adopting it means either copying it into insider_judgment or elevating it to tools/ under the normal caller-count rule -- it would then have two real callers, which is exactly the bar.
  - taker_flow measured NO predictive difference across this split (+0.71 single-name vs +0.69 broad-based, its pre-registered test, which failed). That is evidence against the split mattering for FLOW toxicity. It says nothing either way about insider_judgment's question, which is a different claim -- but whoever picks this up should know the one measurement that exists came back null.

Per CLAUDE.md's division of labour, a structural question answered by a script beats one answered by a prompt, and a structural gate no longer costs tier A. If it reproduces insider_judgment's gate decisions closely enough, it removes a judging stage.
