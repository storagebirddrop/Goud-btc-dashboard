# BTC-03 methodology decision memo for Project Control (research decisions recorded 2026-10-22)

**Scope: RESEARCH ONLY; NO BTC OR SATOSHI PUBLICATION.** Project Control accepted the research choices in the decision record below. This does **not** accept or amend ADR-004 (BTC part) or ADR-007..010, change a public dataset, authorize PR merge, or establish third-party redistribution rights. The original option matrix follows for audit provenance; its "Needed" column documents questions at the time of proposal, not the present status. Evidence: `BTC_03_HOUSING_BTC_SAT.md`.

## Project Control research decision record — 2026-10-22

| Item | Decision | Status |
|---|---|---|
| 1 — A1 | Arithmetic mean of daily UTC closes **only for complete calendar months**; absent days/months stay null. Month-end close is not the primary price. | ACCEPTED — BTC-03 research only |
| 2 — C1 | For USD-derived EUR prices, ratio of complete-month mean BTC/USD to valid-day monthly-mean ECB USD/EUR; do not forward-fill weekends or holidays. | ACCEPTED — BTC-03 research only |
| 3 — Q1 | Bitstamp EUR-native from 2016-05; separate primary-quality research segment, not automatically publishable. | ACCEPTED — BTC-03 research only |
| 3 — Q2 | Bitstamp USD-derived EUR from **2013-07** under the proposed sustained >= USD 1 million average daily notional rule; 2013-04..2013-06 remain Q3 pending any future reassessment. | ACCEPTED AS A RESEARCH CLASSIFICATION; USD 1m liquidity threshold remains a provisional heuristic, not a validated general market-liquidity standard |
| 3/4 — Q3 | Earlier Mt. Gox and Bitstamp months stay individually identified Q3 research segments; archive provenance, gaps and venue effects visible; never splice. | ACCEPTED — BTC-03 research only |
| 5 — NVM | No NVM/BTC or NVM/satoshi series: NVM ends in 2000-H2, BTC price begins in 2010. Half-year BTC aggregation remains **DEFERRED**, not adopted as policy. | ACCEPTED scope boundary |
| 6 — tolerances | 1% investigation / 5% failure and venue-transition policy require further review; no blanket automated cross-venue failure rule adopted. | PROPOSED |
| 7 — storage | Retain source-window pins and derived hash as research evidence. Raw-vintage private storage and long-term reproducibility remain unresolved; hashes are not archives. | PINNING IMPLEMENTED; storage decision DEFERRED |
| 8 — rights | No additional rights or raw-byte retention authorized. Evaluate source-specific terms before any public release. | UNRESOLVED |
| 9 — publication | No public Bitcoin/satoshi series or frontend changes; existing publication allowlist remains empty. | WITHHELD — no authorization |

## Original proposal matrix (preserved for traceability)

| # | Decision | Options | Quantified impact | Recommendation | Needed |
|---|---|---|---|---|---|
| 1 | Monthly BTC price (A1) | A1 mean of daily UTC closes of a complete month; month-end close; trade-based A3/A3V/A4 | month-end differs by mean 7.85% (EUR) / 9.48% (USD), max 31.3% / 105%; satoshi per house mean 7.68%, max 34.1%; A4 time-weighted differs from A1 by mean 0.29-0.76% (max 4.6%); A3/A3V 1.3-3.1% (max 26%) | A1 on complete months, nulls otherwise; month-end rejected | Accept or reject A1 |
| 2 | USD to EUR (C1) | C1 ratio of monthly means; C2/C3 matched-day | vs Bitstamp EUR native: C1 mean 0.129%, max 0.92%; C2 0.444%, max 2.69%; C3 0.451%, max 2.66%; satoshi per house C1 mean 0.129% | C1; matched-day is weekday-biased | Accept or reject C1 |
| 3 | Source hierarchy and earliest month by quality | Q1 Bitstamp EUR native 2016-05; Q2 Bitstamp USD x ECB; Q3 thin/early/archive (Mt. Gox 2010-08, Bitstamp USD from 2011-09) | Q1 125 months from 2016-05; Q2 159 months from 2013-07 under the sustained-liquidity rule; Q3 22 Bitstamp USD months 2011-09..2013-06 and 41 Mt. Gox months | Q1 from 2016-05 as primary; Q2 from the sustained start; Q3 research only | **Decide the Q2 start: 2013-07 (sustained, June 2013 notional $0.87M is below $1M) or 2013-04 (first liquid month)** and the liquidity threshold |
| 4 | Early Mt. Gox / Bitstamp treatment | research-only segments with flags; or exclude | Mt. Gox vs Bitstamp USD (29 shared months) mean 3.76%, max 14.26%; 19 months 2011-09..2013-03 below the liquidity threshold; Mt. Gox 2011-06 missing days | keep as Q3 research series, labelled, never spliced, no claim of representativeness | Confirm |
| 5 | Half-year BTC aggregation for NVM | mean of six monthly A1; day-weighted; end/start of period; median | no NVM overlap exists (NVM ends 2000-H2, BTC from 2010-08); day-weighted vs M1 mean 0.06-0.08%, max 0.47%; end/start/median 8-38% mean | none needed now; if ever needed use M1 (do not reuse the gold rule unchecked) | Defer; confirm that no NVM/BTC series is wanted |
| 6 | Cross-source tolerances and transition boundaries | investigate above 1%, fail above 5% (HIST-08 proposal) | in-venue C1 max 0.92%; cross-venue 0.73-1.10%; Q2 vs Kraken EUR max 1.10%; venue effect Mt. Gox vs Bitstamp up to 14.3% | keep 1% / 5% for same-venue conversion; treat cross-venue differences as a measured break, not a tolerance | Accept thresholds |
| 7 | Vintage pinning and archival limits | window hashes in Git (done) vs private raw store | pins detect revisions (`MATCH` for all five sources); raw bytes are not recoverable; Internet Archive captures are third-party | pins as the standing control; a private store only after the rights assessment; a hash is not an archive | Decide on a private store |
| 8 | Rights and retention | Bitstamp API terms, Internet Archive copies of bitcoincharts files, ECB reuse: all UNVERIFIED | no raw exchange data is committed or uploaded; artifacts hold aggregates | no raw retention in public Git; per-source rights review before any publication | Authorize a rights review |
| 9 | Future publication eligibility | none; or Q1 Bitstamp EUR native from 2016-05 only | 124 CBS months in BTC and satoshis would be eligible | not eligible now; Q1 only after decisions 1-3 and 8 and the BTC ADRs; no splice with other segments; ROOD item | Decide separately; not requested now |

Provisional assumptions used (research only): FX coverage threshold 50% of calendar days and complete final month (HIST-10 decision 7); liquidity threshold USD 1,000,000 per day from BTC-02; Mt. Gox always Q3. Unresolved: rights of all sources; no Bitstamp EUR trade archive; ECB fixing time versus the UTC close; the timing basis of the CBS house price.
