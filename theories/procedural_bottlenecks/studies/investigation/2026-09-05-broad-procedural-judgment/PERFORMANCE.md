# Broad procedural judgment: performance assessment

**September 5, 2026. Collection stopped at the user's request.**

The broad process finds research candidates, including two credible leads.
It has **not demonstrated profitable prediction or added value over a cheap
disclosure baseline**. The first classifier also has substantial rule-reading
errors. Keep the hypothesis open; do not promote these labels into calibrated
probabilities or continue expanding this live sample to answer profitability.

## What was actually measured

The 115,840-contract board passed 3,563 contracts in 1,037 events through
symmetric price/liquidity and procedural-mechanics gates. We stopped three
workers after 48 of 73 batches: **2,296 contracts / 697 events** received
research judgments. The remaining **1,267 contracts are unjudged**, not negative
findings. Actual requested model: `gpt-5.6-sol`, high, web enabled; resolved
snapshot unknown. Judges never supplied prices or probabilities.

| First classification | Contracts | Meaning for this experiment |
|---|---:|---|
| Not applicable | 1,646 | No necessary-step mechanism identified |
| Insufficient evidence | 430 | Status too weak or incomplete |
| Plausible path | 143 | Supported route; not a YES prediction |
| Substantive barrier | 56 | Predicted direction NO, not quantified |
| Formalities only | 21 | Predicted direction YES, not quantified |

Thus 71.7% of judged survivors were classified not applicable; 77/2,296
(3.35%) received a directional label. This is discovery yield, not win rate.
Repeated deadlines and counterparties are not independent trials. The stopped
sample does not establish coverage of every family in the frozen universe.

Four original batches generated 173 automatic abstentions without evaluating
the fetched search pages. Those are quarantined method failures. Their first
valid, separately preserved research replacements count once in the table.

## Classification quality

Review covered **all 21 formalities labels**, representing 13 event groups:

| Review disposition | Contracts | Main reason |
|---|---:|---|
| Failed category definition or exact rule | 14 | LandSpace and Senate reconciliation events predated issuance; ABC source was a promo; Waymo access remained restricted; SAVE votes concerned excluded amendments; UK writs still require a discretionary motion/vote |
| Material evidence gap | 2 | ML2's original public-release condition unproven; NYC rent freeze has an active legal challenge omitted by the judge |
| Future implementation still unresolved | 4 | Fed SEP publication, CMS rule effectiveness, California ballot administration, Ontario wage commencement |
| Qualifying event supported | 1 | FDA camizestrant approval matches the contract's indication and permitted approval type |

This is a source/rule audit, **not 14 losing bets**. Reviewed cases may still
resolve YES through later events. Reviews knew prices and are not independent
calibration evidence. The four future cases have plausible procedural grounds;
their success probabilities and profitability remain unmeasured.

Barrier review was not exhaustive. It also found stale status presented as
current obstacles, mere pending steps treated as barriers, announcement versus
effective-date confusion, and Missouri's pre-September-3 nominations used to
judge an explicitly post-September-3 process. Preserve all first labels and
review sidecars; do not silently improve apparent performance by relabeling.

## Payable economics, not hypothetical win rates

Books were captured after judgment with actual timestamps, depth and series
fees. Corrected curves use the exact retained raw prices and hashes; original
captures remain unchanged. There were 53 barrier contracts with a complete
100-contract NO fill: **median all-in cost 97.21 cents**, so a bet at that cost
needs success above 97.21% to have positive expectation. Across all 53 at equal
100-contract size, mean cost was 91.66 cents, which is the pooled break-even
win rate before opportunity cost. This average includes flagged bad labels.

Twenty formalities contracts had a complete 100-contract YES fill; median
all-in cost was 91.03 cents. The apparently cheapest cases include clear
interpretation failures, so that price distribution is not evidence of value.
One formalities and three barrier contracts lacked sufficient quoted depth.

Two specific leads survived a bounded source/rule check:

| Contract / direction | Captured cost for 100, including fees | Profit if that side wins | Evidence and limit |
|---|---:|---:|---|
| `KXFDAAPPROVE-CAM-26OCT01` / YES | $97.21 | $2.79 | FDA announced qualifying accelerated approval September 4, after May issuance. It is a settlement-lag lead; the contract was still active at capture. |
| `KXSPCELAUNCH-COMM-27FEB01` / NO | $45.51 | $54.49 | Virgin Galactic's August update moved commercial Delta service to February 2027; contract asks for launch before February 1. A target date is not a guarantee or measured probability. |

These are observations at saved prices, not live quotes or realized profits.
Neither case establishes that an LLM beats a source/disclosure baseline.

## What can be concluded about edge

**No valid realized-return estimate exists for this broad run yet.** At the
first quote captures, 2,292 contracts were active. Four were already finalized
before the common judgment cutoff, so they cannot become post-judgment wins.
No historical outcome analysis was performed. The separate 271-contract /
110-event historical frame is only a frozen membership list: it lacks frozen
as-of research packets and judgments. Calling it a completed backtest would
be false.

The useful next experiment is a bounded historical evaluation with an as-of
disclosure baseline, all first classifications, actual entry prices/fees and
subject-level analysis. Stop live expansion. It may find a large effect; a
small sample cannot reliably rule out a modest edge. Do not retire the broad
idea based on these diagnostics, and do not infer profitability from the
number of classifications collected.

## Evidence and reproduction

- [Frozen stop manifest](data/analysis-stop-manifest.json), [aggregate data](data/analysis/summary.json), [all 21 review dispositions](data/analysis/formalities-review.json).
- First outputs, source supplements and review sidecars: `data/judgments/batch-*` and the four `data/repair-judgments/batch-*`; [method exclusions](data/judgments/quality-exclusions.json).
- Original rules, prices, depth and fee receipts: each selected batch's `input.json` and `book-capture.json`. `summarize.py` recomputes arithmetic from retained raw books without new requests or outcome inspection.
- [FDA approval](https://www.fda.gov/drugs/resources-information-approved-drugs/fda-grants-accelerated-approval-camizestrant-cdk46-inhibitor-esr1-mutated-hr-positive-her2-negative), [Virgin Galactic schedule](https://investors.virgingalactic.com/news/news-details/2026/Virgin-Galactic-Announces-Second-Quarter-2026-Financial-Results-and-Provides-Business-Update/default.aspx), [writ discretion](https://commonslibrary.parliament.uk/research-briefings/sn06609/), [SAVE amendment vote](https://www.dailypress.senate.gov/thursday-june-4-2026/).
- Future status: [Fed calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm), [final CMS rule](https://www.govinfo.gov/content/pkg/FR-2026-08-13/pdf/2026-16508.pdf), [Ontario rate](https://www.ontario.ca/document/your-guide-employment-standards-act-0/minimum-wage), [rent-freeze litigation](https://legalaidnyc.org/wp-content/uploads/2026/09/LAS-LSNYC-Motion-to-Intervene-Statement.pdf).

Validation: 50 focused study tests; 1,847 repository tests passed, four network
tests deselected. No ledger opportunities, calibration updates or bets written.
