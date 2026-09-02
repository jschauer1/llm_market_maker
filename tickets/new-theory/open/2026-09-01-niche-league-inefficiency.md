---
title: Niche and foreign leagues on a US exchange: one pre-registered grouping, not 347 mined series
lane: new-theory
created: 2026-09-01
created_by: llm-market-identifier-0e
author_lane: find-theories
author_context: Found by connecting an outside sports-microstructure claim to series-bias pass 3's flagged list; no new measurement run.
status: open
---
MECHANISM. Sports-betting microstructure research is consistent on one
point: major markets (NFL, Premier League) correct fast because volume
is enormous, while lower-tier and foreign leagues correct slowly because
fewer informed participants are watching, and margins there are wider.
Kalshi is a US exchange whose liquidity is overwhelmingly US-sport and
US-politics. So its FOREIGN and LOWER-TIER league contracts are exactly
the "fewer eyes" case, listed on a venue whose informed flow is
elsewhere.

Who is on the other side: US retail treating a Korean baseball line like
an MLB line. Why it persists: the people who actually know KBO are not
on Kalshi, and the people on Kalshi have no reason to specialise in it.

THE IN-REPO OBSERVATION THAT MOTIVATES IT -- and this is the whole
reason to file it. series-bias-mining pass 3 flagged NINE series through
all four of its gates. SEVEN OF THE NINE ARE NICHE OR FOREIGN LEAGUES:

    KXNPBRFI                  -40.85   Nippon Professional Baseball
    KXCPLTEAMTOTAL            -44.97   Caribbean Premier League
    KXT20TEAMTOTAL            -33.54   T20 cricket
    KXATPCHALLENGERDOUBLES    -26.09   ATP Challenger (2nd-tier tennis)
    KXKBORFI                  -25.47   Korea Baseball Organization
    KXUELFTTS                 -24.74   Europa League
    KXATP                      +5.91   ATP tennis
    (the two others: KXNFL4Q -10.18, KXNFL2H -9.69)

Pass 3 correctly declined to call any of these findings, because its
mention_family negative control fired on 5 of 11 and the whole
population turned out to be contaminated by placeholder asks (23% of
observations at 0.980-0.995 realizing 0.801). That verdict is right and
this ticket does not dispute it.

BUT "the population was contaminated" does not establish "there is
nothing in the niche-league signal" -- CLAUDE.md's own rule is that a
pattern failing a contaminated or underpowered pass is UNCONFIRMED, not
disproven. Both things can be true at once: the artifact is real, AND
niche leagues are genuinely softer. Pass 4's liquidity filter
(spread<=0.07, volume>=500 at the decision point) is precisely the
instrument that separates them.

WHY THIS IS NOT JUST series-bias-mining (idea 5), and this is the
statistical point. That study mines EVERY series separately and pays a
Holm divisor over 347 tests -- which is why its median MDE is 12.16
points and why it has been "not measured" three passes running. This is
ONE PRE-REGISTERED GROUPING: niche/foreign vs major, a single
comparison, motivated by outside literature BEFORE looking at the split,
with the league classification fixed in advance. One test needs no
multiple-comparisons correction and pools every series in the group, so
it has vastly more power than 347 underpowered per-series tests over the
same rows. Same data, far better estimator, because the hypothesis is
declared rather than searched.

KALSHI POPULATION, 2026-09-01 board. Foreign/lower-tier series carrying
real volume: KXITFMATCH (308 markets, ITF -- the lowest professional
tennis tier), KXCPLMATCH (Caribbean Premier League),
KXARGPREMDIVGAME (51, Argentine Primera), KXCHLLDPGAME (36, Chilean
Primera), KXLALIGAGAME (72), KXLEAGUESCUP (36), KXATPCHALLENGERDOUBLES,
KXDPWORLDTOUR (89), plus the NPB/KBO/T20 families above. Comparison
group: KXNFLGAME, KXNFLSPREAD, KXMLBGAME, KXMLBTOTAL, KXNCAAFGAME.
Settled history for all of it already sits in
theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/data/collect.db (981,451 settled
markets, 2026-06-30..2026-08-29) -- so this needs NO new collection.

WHAT WOULD KILL IT.
  - The gap vanishes under the liquidity filter. This is the primary
    test and the likely outcome: if niche-league softness is entirely
    the placeholder-ask artifact, filtering on spread AND open_interest
    removes it. Run that first; it is the cheapest possible kill.
  - It is a LIQUIDITY effect, not a league effect. Niche leagues are
    thin, so any league grouping is partly a volume grouping. Control
    for volume/open_interest WITHIN the comparison -- match a thin major
    -league market against a thin niche one -- or the finding is just
    "thin books are mispriced", which is already known and not
    tradeable.
  - The direction is unusable. Every flagged niche series above is
    NEGATIVE (favorites overpriced), which means the trade is buying
    NO/underdogs in thin foreign markets -- and thin is exactly where
    execution fails. A real edge you cannot fill is not an edge; the
    depth check must come before any claim.
  - Settlement-day clustering. Sport settles in daily blocks and this
    repo has measured day-level swings of +/-7 points on a favorite
    screen. Cluster by settlement day and report the day-clustered SE,
    or the sample will look far more significant than it is.

MECHANICAL, tier A. League classification is a fixed map from
series_ticker -- write it down BEFORE computing anything, and commit it,
because a classification adjusted after seeing results is the whole
game. edge_basis="model". Replays for free over data already on disk.

PRE-REGISTRATION DISCIPLINE. Because this is motivated by a pattern
someone already saw in pass 3's output, it is a HYPOTHESIS TO
PRE-REGISTER, never an edge to bet on the data that suggested it. The
honest form: fix the league map and the analysis bar, then test on the
liquidity-filtered population (which pass 3 did NOT have and pass 4 will
-- so pass 4's rows are genuinely out of sample with respect to the
contaminated pass-3 view that suggested this). Coordinate with whoever
holds series-bias-mining; the backfill this depends on is running under
ticket 2026-09-01-series-bias-backfill-liquidity.

SOURCE: sports-betting efficiency literature on lower-league slow
correction (Winkelmann et al. 2024, Management Science; "Beating the
House", arXiv:1910.08858; ECU "Weak Form Efficiency in Sports Betting
Markets"), cross-read against
theories/insider_bias/mention_family/studies/investigation/2026-08-29-series-bias-mining/STUDY.md pass 3's flagged list.
