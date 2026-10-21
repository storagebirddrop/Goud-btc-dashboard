# HIST-08: BTC monthly price definition, USD to EUR construction and transition treatment

Status: **research only, PROPOSED.** Nothing here is a decision. **Nothing in this document, the tool, the tests or the workflow authorizes Bitcoin publication**: Bitcoin and satoshi stay `withheld`, ADR-004 (BTC part), ADR-007, ADR-008, ADR-009 and ADR-010 stay `PROPOSED`. No file under `data/`, `frontend/`, no existing `etl/` file, no existing `tools/`, `docs/` or ADR file is changed. Extends `BTC_02_HISTORY.md` and `BTC_01_METHODOLOGY.md` (does not repeat them). Measured 2026-10-21 on GitHub-hosted runners (the sandbox has no network).

Labels: **CONFIRMED** = measured in a CI run; **PROPOSED**; **INFERRED**; **UNRESOLVED**. Raw third-party bytes and daily prices were never written to disk, committed or uploaded; the workflow artifacts hold aggregate logs only (14 days). Provenance (URL, retrieval time, sha256 of the raw bytes, rows) is printed in the logs. Runs of `.github/workflows/hist-08-btc-definition.yml`: [39603563520](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39603563520) (reported here) and [39602798866](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39602798866) (first run; its Bitstamp archive request got HTTP 502 for the newest capture and silently fell back to an older capture ending 2017-12, which is why the tool now retries the same capture; all numbers below are from the second run).

## 1. Scope and method

Segments kept separate (no automatic splice, quality levels as in BTC-02): **Mt. Gox USD** (2010-07 onward, third-party archive copy), **Bitstamp USD** (complete months from 2011-09), **USD-derived BTC/EUR** (candidate from 2013-04), **Bitstamp EUR** (candidate from 2016-05). A month is complete only if every UTC calendar day has an observation; otherwise the value is `null` with a reason. All arithmetic is Decimal, nothing is interpolated, forward-filled or backfilled.

Monthly price definitions compared per complete month (reference **A1**):

| Id | Definition | Data needed |
|---|---|---|
| A1 | arithmetic mean of daily UTC closes (last trade of each UTC day) | daily candles |
| A2 | monthly close (last trade / close of the last calendar day) | daily candles |
| A3 | intraday trade average (simple mean of all trade prices) | trades |
| A3V | volume-weighted trade average (VWAP) | trades |
| A4 | time-weighted average price: each trade price is held until the next trade over the whole month (hold-last-trade is the definition of a TWAP inside a month where every day has trades; it never fills a missing day; the first and last month of a file have no TWAP) | trades |

USD to EUR constructions (ECB `EXR.D.USD.EUR.SP00.A`, USD per EUR, no rate on weekends or TARGET holidays; 18-23 valid days per month in the shared windows):

| Id | Construction |
|---|---|
| C1 | ratio of monthly means: mean of all USD closes of the complete month / mean of the valid ECB days (the BTC-02 `V1`) |
| C2 | matched day: mean over days with both a USD close and an ECB rate of usd/ecb (the BTC-02 `V2`; weekday-only) |
| C3 | matched-day ratio of means: mean(USD on matched days) / mean(ECB on matched days) |

No FX carry-forward variant was computed. Trade data come from the Internet Archive captures of the bitcoincharts files already registered in BTC-02 (`mtgoxUSD` capture 2016-12-29, `bitstampUSD` capture 2023-07-26, `krakenEUR` capture 2021-05-07, `krakenUSD` capture 2016-12-28), daily data from the live Bitstamp, Coinbase and Bitfinex APIs and the ECB API. `tools/hist_02_acquire.py` has a fixed source registry (World Bank, FRED) and was not used; the BTC-02 probe helpers (`tools/btc_02_probe.py`) were reused read-only. Deviation = |a - b| / b with b the reference.

## 2. Price definition (CONFIRMED measurement)

Trade-based definitions against A1, all complete months:

| Series (months) | A2 month close | A3 trade mean | A3V VWAP | A4 TWAP |
|---|---|---|---|---|
| Bitstamp USD archive 2012-01..2023-06 (137) mean / p99 / max | 10.39% / 66.7% / 105.0% (2013-11) | 1.19% / 7.9% / 8.5% (2018-11) | 1.58% / 9.4% / 12.2% (2018-11) | **0.34% / 1.14% / 3.31% (2013-11)** |
| Kraken EUR archive 2014-02..2021-04 (81) | 9.16% / 31.1% / 31.1% (2020-12) | 1.35% / 7.7% / 7.7% | 1.59% / 12.5% / 12.5% (2018-11) | **0.29% / 0.85% / 0.85% (2020-03)** |
| Mt. Gox USD archive 2010-08..2014-01 (41) | 22.15% / 184% / 184% (2011-04) | 3.10% / 26.2% / 26.2% (2011-04) | 2.48% / 20.2% / 20.2% (2011-04) | 0.76% / 4.62% / 4.62% (2011-04) |

By year, Bitstamp archive A4 vs A1 mean / max: 2012 0.30/0.87, 2013 0.78/3.31, 2014 0.21/0.75, 2015 0.21/0.61, 2016 0.23/0.61, 2017 0.45/1.14, 2018 0.28/0.78, 2019 0.20/0.78, 2020 0.45/0.86, 2021 0.40/1.12, 2022 0.31/0.53, 2023 (6 months) 0.20/0.60 percent. A3 vs A1 mean / max: 2012 0.51/1.27, 2013 1.81/5.60, 2014 1.71/4.63, 2015 1.50/4.58, 2016 0.75/2.79, 2017 1.18/4.11, 2018 1.47/8.51, 2019 1.61/7.88, 2020 1.34/5.64, 2021 0.94/2.74, 2022 0.62/2.69, 2023 0.49/0.94 percent. A2 vs A1 by year: mean 6.1-13.4% except 2013 (28.7%, max 105.0%); A3V is worse than A3 in 2013-2014 and 2018-2020 (volume clusters in volatile days).

Daily-candle sources (A2 vs A1 only): Bitstamp USD 181 months mean 9.48%, p50 6.37%, max 105.0% (2013-11); Bitstamp EUR 125 months mean 7.85%, p99 27.5%, max 31.3% (2020-12); Coinbase USD 134 months mean 7.87%, max 31.9%; Coinbase EUR 136 months mean 7.83%, max 33.8% (2017-11). Signed mean of A2 - A1 is +1.9% to +2.9% (month close is biased by the trend and by one day's noise).

Other CONFIRMED facts:
- The Bitstamp trade archive reproduces the Bitstamp API A1 exactly (137 months, max deviation 0.000%, 9 negative-amount rows dropped, 0 unordered rows). The Mt. Gox and Kraken archives have 0 unordered rows and 0 bad prices.
- Trades per day (mean): Mt. Gox 2010 54, 2011 3,368, 2012 5,392, 2013 11,751; Bitstamp 2012 199, 2013 5,856, 2017 22,113, 2023 17,648; Kraken EUR 2014 2,509, 2017 26,725, 2021 69,004. Longest inter-trade gap inside a complete month: Mt. Gox 24.1 h (2010-09), Bitstamp 29.3 h (2012-01), Kraken EUR 23.0 h (2014-11).
- Mt. Gox early months, ratio to A1: A4 0.981-0.998 (2010-08..2011-02), A3 0.907-1.044, A2 0.80-1.77 (2010-10: 1.766).
- Bitstamp trade archive complete months start 2012-01 (2011-09..2011-11 have missing days in the archive); Bitstamp API daily candles are complete from 2011-09. Bitstamp EUR has no trade archive (BTC-02), so a true TWAP for the Q1 segment 2016-05+ was **not measured**; the evidence is Kraken EUR (same currency, 81 months) and Bitstamp USD (same venue, other pair).

Reading: A1 is within about 0.3% on average and 1.14% at p99 (max 3.3% only in the thin 2013 market) of the true time-weighted price, so the daily-close mean is a faithful and reproducible proxy that needs only daily candles. Month close (A2) is not usable. Trade-count and volume weighting (A3, A3V) over-weight busy days and deviate 1-2% on average and up to 12%.

## 3. USD to EUR constructions (CONFIRMED measurement)

Against the EUR-native A1 of the same venue (shared complete months):

| Venue (months) | C1 mean / p99 / max rel | C2 mean / p99 / max rel | C3 mean / p99 / max rel | C1 signed mean |
|---|---|---|---|---|
| Bitstamp 2016-05..2026-09 (125) | **0.129% / 0.75% / 0.92% (2017-09)** | 0.444% / 2.22% / 2.69% (2017-12) | 0.451% / 2.41% / 2.66% (2017-12) | -0.051% |
| Coinbase 2015-08..2026-09 (133) | 0.167% / 1.45% / 1.58% (2018-01) | 0.443% / 1.60% / 3.26% | 0.450% / 1.59% / 3.45% | -0.098% |
| Bitfinex 2017-06..2026-09 (109) | 0.094% / 0.39% / 0.44% (2025-08) | 0.424% / 2.02% / 2.26% | 0.426% / 2.21% / 2.22% | +0.036% |
| Kraken same venue 2014-02..2016-11 (26) | 0.342% / 0.77% / 0.77% (2015-11) | 0.555% / 2.08% / 2.08% (2014-03) | 0.564% / 2.09% / 2.09% | +0.116% |

Absolute EUR per BTC, Bitstamp, by year (mean abs / max abs): C1 2016 2.32/5.52, 2017 14.04/94.03, 2018 9.74/45.97, 2019 5.10/7.81, 2020 9.97/24.93, 2021 31.46/123.35, 2022 15.17/29.75, 2023 20.55/48.41, 2024 33.62/104.32, 2025 91.54/241.77, 2026 (9 months) 45.01/86.38. C2: 2016 3.17/7.20, 2017 43.21/338.78, 2018 47.73/236.72, 2019 26.70/91.19, 2020 44.19/114.98, 2021 171.78/358.30, 2022 72.46/216.34, 2023 60.25/157.45, 2024 185.94/598.69, 2025 261.49/798.92, 2026 238.07/574.87. Relative C1 mean / max by year (%): 2016 0.373/0.702, 2017 0.310/0.916, 2018 0.149/0.432, 2019 0.098/0.209, 2020 0.098/0.165, 2021 0.080/0.258, 2022 0.062/0.141, 2023 0.085/0.258, 2024 0.055/0.170, 2025 0.103/0.268, 2026 0.071/0.157. C2 mean / max: 2016 0.538/0.915, 2017 0.808/2.694, 2018 0.701/2.224, 2019 0.432/1.399, 2020 0.491/1.415, 2021 0.448/0.978, 2022 0.272/0.568, 2023 0.228/0.575, 2024 0.312/1.015, 2025 0.294/0.872, 2026 0.376/0.911.

Cross-checks against independent EUR-native venues where Bitstamp EUR does not exist (2014-02..2016-04, different venue, so the venue effect is included):

| Comparison | n | mean | p50 | p99 / max |
|---|---|---|---|---|
| Bitstamp C1 vs Kraken EUR A1 (2014-02..2016-04) | 24 | 0.370% | 0.286% | 1.10% (2015-08) |
| Bitstamp C2 vs Kraken EUR A1 | 24 | 0.568% | 0.356% | 2.50% (2014-02) |
| Bitstamp C3 vs Kraken EUR A1 | 24 | 0.578% | 0.320% | 2.58% (2014-02) |
| Bitstamp C1 vs Coinbase EUR A1 (2015-05..2016-04, thin book) | 12 | 0.456% | 0.379% | 1.40% (2015-08) |
| Kraken EUR A1 vs Bitstamp EUR A1 (2016-05..2021-05) | 57 | 0.089% | 0.054% | 0.73% (2017-06) |

C2 and C3 are practically identical (Bitstamp 181 months: mean 0.039%, max 0.35%); the difference between C1 and C2/C3 is the **weekday bias** of matched-day means (a weekday-only mean of a 24/7 asset), not the FX averaging. C1 is the only construction that uses all calendar days of the USD side, and it also needs no matched-day rule. Its residual (about 0.13% on average) is the genuine venue and fixing-time difference between the two Bitstamp books. C1 vs C2 over the full USD history (181 months): mean 0.478%, max 2.93% (2013-12), signed mean -0.113%.

## 4. Source transitions (CONFIRMED measurement, no splice)

- **Mt. Gox to Bitstamp** (archive copies, 25 shared complete months 2012-01..2014-01): A1 mean 3.34%, p50 1.36%, p90 9.59%, max 14.26% (2014-01); 2012 mean 1.07% (max 2.45%), 2013 mean 4.70% (max 10.69%). The size is the same for every definition (mean 3.2-4.3% for A1, A2, A3, A3V, A4), so the gap is a **venue effect, not a definition effect**. Signed mean +2.9% (Mt. Gox above Bitstamp). BTC-02 reported 29 months with the API (mean 3.76%, max 14.26%).
- **Q2 to Q1 basis break at 2016-05** (C1 on Bitstamp USD vs Bitstamp EUR A1, 2016-05..2017-04, 12 months): mean 0.333%, max 0.702% (2016-12), signed mean -0.241% (2016: -0.373%, 2017: +0.023%). C2: mean 0.531%, max 1.246%; C3: mean 0.548%, max 1.161%.
- **USD-derived vs EUR-native before 2016-05**: 0.37% mean / 1.10% max against Kraken EUR (2014-02..2016-04); 0.46% / 1.40% against Coinbase EUR (2015-05..2016-04).
- Segments before 2014-02 have no EUR-native cross-check in the registered sources; Mt. Gox EUR (thin until 2014-02) deviates up to 12.5% from V1 (BTC-02).

## 5. BTC and satoshi per house (CONFIRMED arithmetic, INFERRED interpretation)

`btc_per_house = house_eur / btc_eur`; `sat_per_house = btc_per_house * 1e8`, exact in Decimal. The number of satoshi is a unit conversion of the EUR price: it contains no information beyond the pair (house price, BTC price), and the relative change of `sat_per_house` equals |b - a| / a when price definition a replaces b. Measured on Bitstamp EUR with CBS house prices (124 months 2016-05..2026-08):

| Choice | mean change in sat/house | max |
|---|---|---|
| A2 month close instead of A1 | 7.68% | 34.06% (2018-11) |
| C1 (USD + ECB) instead of EUR-native A1 | 0.129% | 0.924% (2017-09) |
| Kraken EUR archive: A4 / A3 / A3V instead of A1 (81 months) | 0.29% / 1.35% / 1.62% | 0.84% / 8.31% / 14.23% |

Samples (A1, Bitstamp EUR; unrounded values are in the log): 2016-05 house 236,730 EUR, 407.68 EUR/BTC, 580.7 BTC, 5.807e10 sat per house; 2020-12 333,199 EUR, 18,041 EUR/BTC, 18.47 BTC, 1.847e9 sat (A2/A1 ratio 0.762); 2026-08 503,523 EUR, 59,929 EUR/BTC, 8.402 BTC, 8.402e8 sat. Interpretation (PROPOSED): sat/house is the house price in the BTC unit of account; it falls when BTC appreciates faster than the CBS average price, and it is dominated by the BTC price (house price moved from 237 to 504 thousand EUR while sat/house fell by a factor 69). Integer-sat rounding is irrelevant (9 significant digits at the end of the range); the uncertainty is the price definition (up to 34% for month close), the venue (below 1% from 2014, up to 14% earlier) and the time basis. The time basis of the CBS average (month of registration vs. month of the transaction) is **UNRESOLVED** here, as is the intra-month timing mismatch between the ECB reference rate (fixing around 14:15 CET) and 00:00 UTC BTC closes (not tested).

## 6. Recommendations (PROPOSED, owner decides; nothing is ACCEPTED)

1. **Preferred monthly price definition: A1, mean of daily UTC closes of one named venue over a complete calendar month** (the BTC-02 definition). Evidence: within 0.34% mean / 1.14% p99 of the time-weighted price (137 and 81 months), needs only daily candles available live, reproducible and exactly equal between API and trade archive. Reject A2 (month close: mean 8-10%, max 105%). Do not use A3/A3V (1-2% mean, up to 12% bias from trade clustering, and trade-level data are not available live). Keep A4 as a research cross-check only.
2. **USD to EUR: C1 (ratio of monthly means)**, with the ECB monthly mean over valid days; C2/C3 only as sensitivities. C1 beats C2/C3 by a factor 3-4 in mean and max on every venue tested (Bitstamp, Coinbase, Bitfinex, Kraken same-venue) and across the 2014-2016 cross-venue window. Missing ECB days stay missing; no carry-forward.
3. **Earliest reliable BTC/EUR-equivalent month.** Keep BTC-02 as is: Q2 (USD-derived C1, liquid) from **2013-04** and Q1 (EUR-native A1, Bitstamp) from **2016-05**. Refinement (PROPOSED, INFERRED): split Q2 into **2014-02..2016-04** (cross-validated: C1 within 0.37% mean / 1.10% max of Kraken EUR and 1.40% of Coinbase EUR) and **2013-04..2014-01** (single-currency USD evidence only; Mt. Gox vs Bitstamp up to 10.7% in 2013; no EUR-native check). The conservative start for any later publication discussion is 2016-05; 2014-02 is the earliest start with an independent EUR-native confirmation. This is not a publication recommendation.
4. **Earlier research-only observations** (Q3, never published): Bitstamp USD 2011-09..2013-03 (thin, C1), Mt. Gox 2010-08..2011-08 (41 complete Mt. Gox months in total to 2014-01). For Mt. Gox the choice between A1 and A4 changes the month by at most 1.9% in 2010 and 4.6% in 2011 (A2: up to 184%), but the venue itself differs from Bitstamp by 3.3% mean and 14.3% max; Mt. Gox months are a separate research series with archive-copy provenance, not a market mean.
5. **Source-transition treatment.** Keep segments in separate columns or series with explicit `source`, `basis` (A1 native / A1 + C1) and `quality` fields. No splice, no level adjustment or back-casting at 2016-04/05; show the break and its measured size (mean 0.33%, max 0.70% in the first twelve months, signed -0.24%) rather than hiding it. A change of venue within a segment is a source revision that needs owner approval (as for CBS).
6. **Empirical tolerances (PROPOSED parameters, supported by the measurements above, not decisions):** (a) USD-derived C1 vs EUR-native same venue: investigate above **1%** (observed max 0.92%, p99 0.75%); (b) cross-venue EUR-native A1 from 2014: investigate above **1%** (Kraken vs Bitstamp max 0.73%), hard fail above **5%** (BTC-02 proposal); (c) A1 vs time-weighted price: **1.5%** from 2014 (observed max 1.14%), 5% before 2014 (observed max 3.31%); (d) segments before 2014-02: no tolerance claim beyond the observed Mt. Gox-Bitstamp range (max 14.3%).
7. **BTC and sats per house:** if ever published, derive from the A1/C1 price of the stated segment and carry the segment's quality level; `sat_per_house` must not be presented as more precise than the price (relative error equal to the price error, 0.1-1% for Q1/Q2-validated, several percent before 2014). Publishing sats reveals the price (BTC-01), so source rights apply (BTC-02 section 6.4).

## 7. Not verified

- No true TWAP for Bitstamp EUR (no trade archive) and no Bitstamp intraday data after 2023-07-26; the trade archives are third-party copies (Internet Archive captures of bitcoincharts files), fidelity proven only for Bitstamp USD (exact) and indirectly for Kraken.
- TWAP uses hold-last-trade; alternatives (midpoints, order-book data) not tested. Mt. Gox months are not a market mean after 2013.
- ECB fixing time vs UTC close timing, CBS house price time basis, rights and licences for any source, and the owner decisions D1-D7 of BTC-02 remain open.
- Retrieved bytes are not pinned (hashes prove one retrieval; Bitstamp API hashes change daily). Single measurement day; no multi-day reproducibility check.
- Venues beyond Bitstamp, Coinbase, Bitfinex, Kraken, Mt. Gox were not re-measured; the aggregator and Yahoo series of BTC-02 were not reused.

## 8. Implementation

`tools/hist_08_btc_definition.py` (pure functions `TradeMonthAggregator`, `aggregate_trades_monthly`, `daily_definitions`, `convert_usd_to_eur` (C1/C2/C3), `diff_stats`, `diff_by_year`, `sat_effect`; CI jobs `daily`, `usd-archives`, `eur-archives` print aggregates only; no publication path), `tests/test_hist_08_btc_definition.py` (offline, no network: UTC day and month boundaries incl. leap February, month completeness, each aggregation incl. exact TWAP and month-boundary splitting, conversion alternatives incl. weekday bias, missing and duplicate days, corrupted trades and FX rows, USD/EUR confusion, publication refusal), `.github/workflows/hist-08-btc-definition.yml` (`contents: read`, aggregate-only artifacts, 14 days; triggers: `workflow_dispatch`, push to the research branch, pull_request on its own paths). Reproduce with `python -m pytest -q tests/test_hist_08_btc_definition.py` and the workflow jobs.
