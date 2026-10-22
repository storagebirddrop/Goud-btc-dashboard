# BTC-02: Bitcoin market history and a defensible monthly BTC/EUR research series

Status: **research only, PROPOSED.** Not a decision, not legal advice. Nothing is approved or published; Bitcoin and satoshi stay `withheld`. ADR-004 (BTC part), ADR-007, ADR-008 and ADR-010 remain `PROPOSED`. No existing file, public data, ETL code, frontend, JSON or ADR status is changed. Extends `BTC_01_METHODOLOGY.md` (does not repeat it). Measured 2026-10-21 on GitHub-hosted runners (the sandbox has no network).

Labels: **CONFIRMED** = primary text or measurement in a CI run; **PROPOSED**; **INFERRED**; **UNRESOLVED**. Provenance for every measured series (URL, retrieval time, sha256 of the raw bytes, rows, first/last day) is printed in the workflow logs of `.github/workflows/btc-02-history.yml` (`tools/btc_02_probe.py`); raw bytes and daily prices are never committed or uploaded (only aggregate logs, 14 days). Runs: [39584598332](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39584598332) (first measurement; Bitstamp archive), [39594261672](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594261672) (exchanges, aggregators, Yahoo), [39594396610](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594396610) (terms), [39595505061](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39595505061) (trade archives via Internet Archive).

## 1. Verdict

| Question | Finding |
|---|---|
| Bitcoin created | 2009-01 (genesis block). No market price exists then. INFERRED from general knowledge, not measured here. |
| Earliest recorded exchange trade | **Mt. Gox BTC/USD, 2010-07-17T23:09:17Z** (CONFIRMED in the bitcoincharts `mtgoxUSD` trade file as archived by the Internet Archive on 2016-12-29: 8,295,809 trades, 1,314 trading days to 2014-02-25). Coin Metrics Community `PriceUSD` starts 2010-07-18 (5,939 daily rows, no gap); Blockchain.com `market-price` 2010-08-18 (592 earlier zero points skipped). |
| Earliest gap-free live exchange series | **Bitstamp BTC/USD 2011-08-18** (complete months from **2011-09**, 181 to 2026-09, zero missing days). Mt. Gox USD gives 41 complete months 2010-08..2014-01 (2011-06 lacks 6 days; 2014-02 is partial because Mt. Gox stopped on 2014-02-25) but only through a third-party archive copy (4.2) and with large deviations from Bitstamp (mean 3.8%, max 14.3%). |
| Continuous credible market price | Mt. Gox notional >= 1e5 USD/day sustained from **2011-05** and >= 1e6 from **2013-02**; Bitstamp >= 1e5 from 2013-02 and >= 1e6 from 2013-07. So a credible (not thin) USD market exists from about **2013-02/2013-07**; before that everything is thin (Q3, research only). Proposed measure, parameter 1e6 USD/day. |
| Earliest reliable BTC/EUR-derived valuation | **2013-04** (USD-derived V1 from Bitstamp, Q2; 2013-06 Q3 by the threshold). EUR-native: **Kraken EUR 2014-02** (trade archive, notional >= 1e6 EUR/day from 2015-10; agrees with Bitstamp EUR within 0.73% max), **Bitstamp EUR 2016-05** (live API, Q1), Coinbase EUR 2015-05 (thin, <= 3e5 EUR/day until 2016-04). |
| Gaps stay null | Yes. No splice, no interpolation, no forward fill anywhere. Months before 2011-09 have no value in the Bitstamp-based reconstruction; Mt. Gox-based values 2010-08..2011-08 exist only as a separate Q3 research series. |
| Empirical cross-source tolerance | Per-month relative deviation of monthly means between independent venues/sources: p50 0.01-0.1%, p99 about 1.5%, max 4.1% (Coinbase vs Bitstamp EUR, 2017-12). Table in 5. The BTC-01 5% default is never exceeded among liquid exchange venues (2014+); Mt. Gox vs Bitstamp (2011-2014) and early aggregators reach 8-14%. |
| Readiness | Ready for owner review of method and quality levels. **Not ready for publication**: rights (6.4), fixing definition, start month and Mt. Gox/early-market scope are open owner decisions. |

## 2. Distinctions the report keeps apart

1. **Creation** (2009-01): protocol exists, no price discovery.
2. **Earliest recorded exchange trades**: 2010-07-ish (CM PriceUSD begins 2010-07-18; Mt. Gox trades are INFERRED earlier/equal, raw trades UNRESOLVED).
3. **Continuous credible market price**: a monthly mean that a 24/7 market with enough volume supports. Measured by daily notional on Bitstamp: 199 USD/day mean in 2011, 1.6e4 in 2012, 4.3e6 in 2013, 7.3e6 in 2014 (BTC volume/day: 59, 1,552, 13,780, 13,760).
4. **EUR-derived valuation**: USD price divided by ECB USD per EUR (V1/V2) works for any BTC date from 1999 on, but is a derived value, not a EUR market.
5. **EUR-native valuation**: only from a EUR order book (Coinbase 2015-04-23, Bitstamp 2016-04-16, Kraken first EUR trade 2013-09-10 per its `Trades` API but only 720 daily candles retrievable, Bitfinex 2017-05-19, Binance BTCEUR 2020-01-03).

## 3. Source matrix (measured)

All HTTP 200 on 2026-10-21 from GitHub runners unless stated. "Complete months" = every calendar day present.

| Source / series | Earliest | Last | Rows | Missing days in span | Complete months (first) | Notes |
|---|---|---|---|---|---|---|
| Bitstamp `btcusd` OHLC 1d | 2011-08-18 | 2026-10-20 | 5,543 | 0 | 181 (2011-09) | UTC-midnight timestamps only (0 non-aligned), 0 duplicates; today's partial candle dropped |
| Bitstamp `btceur` OHLC 1d | 2016-04-16 | 2026-10-20 | 3,840 | 0 | 125 (2016-05) | same checks |
| Coinbase Exchange `BTC-USD` | 2015-07-20 | 2026-10-20 | 4,111 | 0 | 134 (2015-08) | |
| Coinbase Exchange `BTC-EUR` | 2015-04-23 | 2026-10-20 | 4,196 | 3 (2015-04-25..26, 2016-07-12) | 136 (2015-05) | |
| Bitfinex `tBTCUSD` 1D | 2013-03-31 | 2026-10-20 | 4,945 | 7 (2016-08-03..09) | 161 (2013-04) | |
| Bitfinex `tBTCEUR` 1D | 2017-05-19 | 2026-10-20 | 3,432 | 10 (2017) | 109 (2017-06) | |
| Binance `BTCEUR` 1d | 2020-01-03 | 2026-10-20 | 2,483 | 0 | 80 (2020-02) | `api.binance.com` returned HTTP 451 (restricted location) from the runner; `data-api.binance.vision` worked |
| Kraken `XBTUSD` / `XBTEUR` REST OHLC 1440 | 2024-10-31 | 2026-10-20 | 720 each | 0 | 23 (2024-11) | REST returns only the latest 720 candles. First trade in the `Trades` API (since=0): XBTUSD 2013-10-06, XBTEUR 2013-09-10. Full-history ZIP (support article) not fetched |
| Coin Metrics Community `PriceUSD` 1d | 2010-07-18 | 2026-10-20 | 5,939 | 0 | 194 (2010-08) | free, no key, one page of 10,000; `ReferenceRateUSD/EUR` only last 7 days (BTC-01 section 12) |
| Blockchain.com `market-price` | 2010-08-18 | 2026-10-15 | 5,903 | 0 | 193 (2010-09) | 592 zero-price points skipped; last point 5 days old |
| Trading repo (ADR-010) Yahoo `BTC-USD` 1d | 2014-09-17 | 2026-10-12 | 4,409 | 0 | 144 (2014-10) | file `history.csv`, 46,911,298 bytes, sha256 `9433e1f2...b2c` (full value in log) |
| ECB `EXR.D.USD.EUR.SP00.A` | 1999-01-04 | 2026-10-20 | 7,118 | 3,034 calendar days | n/a | see 4.1 |
| CryptoCompare `histoday` (BTC/USD, BTC/EUR, e=Bitstamp, e=mtgox) | n/a | n/a | n/a | n/a | n/a | **HTTP 401, API key required** (now under CoinDesk Data). Blocker for free use |
| CoinDesk BPI legacy `api.coindesk.com/v1/bpi/historical` | n/a | n/a | n/a | n/a | n/a | connection error (host unreachable): UNRESOLVED/likely discontinued |
| CoinGecko public `market_chart` | 2025-10-22 | 2026-10-21 | 366 | n/a | n/a | `days=max` refused (HTTP 401, error 10012: beyond 365 days needs a plan) |
| bitcoincharts trade CSV `mtgoxUSD` via Internet Archive capture 2016-12-29 | 2010-07-17 | 2014-02-25 | 8,295,809 trades; 1,314 days | 6 (2011-06-20..25) | 41 (2010-08) | 57 pages, 59,585,679 bytes, sha256 `1a880feeadfe3c535c54aec4e66912fa6f277b3fb14f00829f05a345ab4b91eb`; 0 unordered/bad rows |
| bitcoincharts `mtgoxEUR` (capture 2016-12-28) | 2011-08-27 | 2014-02-25 | 953,470 trades; 909 days | 5 | 28 (2011-10) | 7,275,281 bytes, sha256 `cec2724d78c4d5fe18bb4edb69571304a36692a137b68ee849d2d4323f692ec5` |
| bitcoincharts `krakenEUR` (capture 2021-05-07) | 2014-01-08 | 2021-05-06 | 54,129,722 trades; 2,627 days | 49 (2016-01-19..2016-03-04, 2017-10-21, 2018-01-12, 2018-09-21) | 81 (2014-02) | 387,008,192 bytes, sha256 `58f56ddbe260e459b6be4353ad64922d9693143daad6676c1f580f90b4e05a51` |
| bitcoincharts `krakenUSD` (capture 2016-12-28) | 2014-01-07 | 2016-12-28 | 508,558 trades; 1,039 days | 48 | 26 (2014-02) | 3,845,164 bytes, sha256 `cafb53ad5bc623a776ad5de7e67ccdfd7c6b752cfd388f54148d7330842fd668` |
| bitcoincharts `bitstampUSD` (capture 2023-07-26; run 39584598332) | 2011-09-13 | 2023-07-26 | 67,472,737 trades; 4,314 days | 21 (2011-09..11) | 137 (2012-01) | 526,476,882 bytes, sha256 `bdef499e489896a302822796e82b3c7562027cfedd1f44e72d74b1427bd2867c`; monthly means equal the Bitstamp API to 0.000% in all 137 months (archive fidelity check); 9 negative-amount rows dropped |
| bitcoincharts live host `api.bitcoincharts.com` | n/a | n/a | n/a | n/a | n/a | connection failure on https and http (every file); `bitstampEUR` has no Internet Archive capture |
| TradingView `INDEX:BTCUSD` | n/a | n/a | n/a | n/a | n/a | no export API; terms in 7 |

Provenance values are in the logs. Example (Bitstamp, run 39584598332): `btcusd` 6 pages, 730,921 bytes, sha256 `ada5f22e7b89b52e55933d2100e266a6825ab7e80b7ca67230e7bbe39dbe7462`; `btceur` 8 pages, 512,683 bytes, sha256 `80bbbd138de8464fba98d88fb4fc8c3f1c75d4472c7530c8431afc0ed25eb959`. The sha256 differs per retrieval because the newest candle changes; that is expected and shows why pinning needs a stored copy (storage class B, DATA_01B) before any publication.

## 4. Structural issues (measured where possible)

### 4.1 ECB USD per EUR coverage (CONFIRMED)

Series key `EXR.D.USD.EUR.SP00.A`, 7,118 observations 1999-01-04..2026-10-20. No weekend rate exists (weekend_days_with_rate = 0); 3,034 calendar days are absent, of which 134 are weekdays (TARGET holidays). Months have 18-23 valid days (minimum 14 only in the incomplete 2026-10). So USD to EUR conversion is **possible for every BTC month since 1999** but **never daily-matched for weekends/holidays** without a carry-forward that is forbidden here. Consequences:
- V1 (monthly mean of USD closes / monthly mean of valid ECB days): needs no matching; ADR-004 parallel.
- V2 (mean of daily usd/fx on matched days only): is a weekday-only mean; never "complete" for a 24/7 asset.

### 4.2 Mt. Gox and other trade archives (CONFIRMED measurement, provenance caveat)

- The live bitcoincharts host is unreachable from GitHub runners. The Internet Archive holds captures of the CSV files (CDX API: `mtgoxUSD` 6 captures 2014-03-30..2016-12-29, `krakenEUR` 7 captures to 2021-05-07, `bitstampEUR` none). The probe fetched the raw capture (`.../web/<timestamp>id_/...`), streamed and aggregated it in memory (no bytes stored), and hashed it (hashes in section 3).
- **These are third-party copies of a third-party aggregation**: bitcoincharts' own collection of exchange trade feeds, then archived. Integrity relative to the exchange cannot be proven from the file. Evidence for fidelity: the `bitstampUSD` capture reproduces the Bitstamp API monthly means exactly (0.000%, 137 months), and `krakenEUR` agrees with Bitstamp EUR within 0.73% (57 months). Mt. Gox has no live comparison source after 2014.
- Mt. Gox USD facts (CONFIRMED from the capture): first trade 2010-07-17T23:09:17Z; trades per year 2010 8,757; 2011 1,279,900; 2012 1,970,995; 2013 4,286,846; 2014 749,311 (to 2014-02-25); BTC volume per year 2.67e6 (2010), 1.35e7, 2.02e7, 1.79e7, 1.28e6; gap 2011-06-20..2011-06-25 (6 days, no trades in the file; consistent with the 2011-06 hack/outage period, INFERRED); the series ends 2014-02-25, around the Mt. Gox suspension (INFERRED from general knowledge). Largest day-over-day moves: +129% on 2014-02-22 (collapse days), +73% on 2010-07-18 (first days), +57% 2014-02-20, +53% 2011-05-10.
- Mt. Gox vs Bitstamp USD, monthly means (n=29 complete months in both): mean 3.76%, p50 2.07%, p90 9.59%, max 14.26% (2014-01); by year 2011 mean 6.4% (max 8.2%), 2012 1.07% (max 2.4%), 2013 4.7% (max 10.7%). The premium/discount in 2013-2014 is consistent with the withdrawal problems alleged for Mt. Gox (INFERRED, not tested); Mt. Gox months are therefore not a market average after 2013.
- Mt. Gox EUR (`mtgoxEUR`) is thin: notional >= 1e5 EUR/day only from 2013-03 and >= 1e6 only from 2014-02; vs V1(Bitstamp USD) mean 3.3%, max 12.5% (2014-01).
- Not covered: the Mt. Gox leak (about 7 million trades 2011-04..2013-11, WEIS 2019, search summary), wash-trading allegations, flash-event reconstruction, Kaggle/academic dumps (need login). Internet Archive search for Mt. Gox datasets returned no relevant item.

### 4.3 Kraken as a EUR-native archive (CONFIRMED)

`krakenEUR` trades 2014-01-08..2021-05-06 aggregate to 2,627 trading days and 81 complete months from 2014-02 (months 2016-01..2016-03, 2017-10, 2018-01, 2018-09 are incomplete and therefore null). Notional >= 1e5 EUR/day sustained from 2014-01 and >= 1e6 EUR/day from 2015-10. Against Bitstamp EUR (2016-2021, 57 months): mean 0.089%, p50 0.054%, p90 0.211%, max 0.731% (2017-06). Against V1(Bitstamp USD) 2014-2021 (81 months): mean 0.262%, p50 0.169%, p90 0.617%, max 1.116% (2015-08). The archive stops at 2021-05, so it is a historical EUR-native alternative, not a live source (live Kraken REST has only 720 candles). `krakenUSD` (2014-01..2016-12, 26 complete months) deviates from Bitstamp USD by mean 0.41%, max 1.42%.

### 4.4 Early-market thinness (CONFIRMED, Bitstamp)

| Year | BTC volume/day (mean) | USD notional/day (mean) |
|---|---|---|
| 2011 | 59 | 199 |
| 2012 | 1,552 | 1.58e4 |
| 2013 | 13,780 | 4.29e6 |
| 2014 | 13,760 | 7.28e6 |
| 2015 | 15,140 | 4.21e6 |
| 2016 | 5,443 | 3.05e6 |
| 2017 | 12,870 | 5.98e7 |
| 2018 | 10,770 | 8.50e7 |
| 2020 | 8,400 | 9.11e7 |
| 2021 | 4,940 | 2.20e8 |
| 2024 | 2,207 | 1.48e8 |

Sustained notional (every later month above the level): >= 1e5 USD/day from 2013-02; >= 1e6 from 2013-07; >= 1e7 from 2017-05. EUR pair: >= 1e5 EUR/day from 2016-05; >= 1e6 from 2017-05. Largest day-over-day moves on Bitstamp USD: +56% (2011-10-28), +49% (2013-04-11), +43% (2011-10-20); on EUR: +38% (2020-03-12). Single-exchange concentration: before 2013 the only measured exchange is Bitstamp, whose own volume is tiny in 2011-2012, so a Bitstamp month then is not a market price (Q3 at best).

### 4.5 UTC cutoffs and conventions (CONFIRMED / INFERRED)

Bitstamp: every candle timestamp is exactly UTC midnight (0 non-aligned of 9,383), close = last trade of that UTC day. Coin Metrics `PriceUSD` and CryptoCompare label a day by its start but carry an end-of-day value (INFERRED from vendor docs, BTC-01). Yahoo's cutoff is unverified. Different cutoffs explain the early-year deviations between sources (not errors).

### 4.6 Month-end vs mean (CONFIRMED)

Month-end close deviates from the monthly mean of daily closes by mean 7.8% (EUR, p50 6.0%, p90 17.9%, max 31.3% 2020-12) and 9.5% (USD, p50 6.4%, p99 66.7%, max 105.0% 2013-11). The mean-of-daily-closes definition is retained; month-end is not a usable proxy.

## 5. Cross-source tolerance (CONFIRMED measurement; relative deviation of complete-month means)

Deviation = |a - b| / b with b the reference. n = months compared.

| Comparison | n | mean | p50 | p90 | p99 | max (month) | >1% | >5% |
|---|---|---|---|---|---|---|---|---|
| V1 (Bitstamp USD / ECB) vs Bitstamp EUR-native | 125 | 0.129% | 0.079% | 0.288% | 0.748% | 0.916% (2017-09) | 0 | 0 |
| V2 (matched weekdays) vs Bitstamp EUR-native | 125 | 0.444% | 0.317% | 0.936% | 2.224% | 2.694% (2017-12) | 9 | 0 |
| V1 vs V2 (Bitstamp USD) | 181 | 0.478% | 0.323% | 1.014% | 2.634% | 2.927% (2013-12) | 20 | 0 |
| Coinbase USD vs Bitstamp USD | 134 | 0.096% | 0.008% | 0.338% | 1.448% | 1.847% (2017-12) | 2 | 0 |
| Coinbase EUR vs Bitstamp EUR | 124 | 0.142% | 0.021% | 0.292% | 1.522% | 4.113% (2017-12) | 4 | 0 |
| Coinbase EUR vs V1(Bitstamp USD) incl. 2015-05..2016-04 | 136 | 0.248% | 0.107% | 0.692% | 1.582% | 3.341% (2017-12) | 6 | 0 |
| Bitfinex USD vs Bitstamp USD | 161 | 0.276% | 0.083% | 0.572% | 3.063% | 4.063% (2017-04) | 11 | 0 |
| Bitfinex EUR vs Bitstamp EUR | 109 | 0.233% | 0.063% | 0.409% | 2.513% | 2.741% (2018-12) | 9 | 0 |
| Binance EUR vs Bitstamp EUR | 80 | 0.150% | 0.063% | 0.401% | 1.096% | 1.096% (2021-08) | 1 | 0 |
| Kraken USD vs Bitstamp USD (23 recent months) | 23 | 0.005% | 0.005% | 0.012% | 0.012% | 0.012% (2025-01) | 0 | 0 |
| Kraken EUR vs Bitstamp EUR (23 recent months) | 23 | 0.008% | 0.006% | 0.017% | 0.029% | 0.029% (2024-12) | 0 | 0 |
| Kraken EUR (trade archive) vs Bitstamp EUR | 57 | 0.089% | 0.054% | 0.211% | 0.731% | 0.731% (2017-06) | 0 | 0 |
| Kraken EUR (trade archive) vs V1(Bitstamp USD) | 81 | 0.262% | 0.169% | 0.617% | 1.116% | 1.116% (2015-08) | 1 | 0 |
| Kraken USD (trade archive) vs Bitstamp USD | 26 | 0.411% | 0.304% | 1.087% | 1.424% | 1.424% (2014-03) | 3 | 0 |
| Mt. Gox USD (trade archive) vs Bitstamp USD, 2011-09..2014-01 | 29 | 3.756% | 2.065% | 9.586% | 14.259% | 14.259% (2014-01) | 20 | 10 |
| Mt. Gox EUR vs V1(Bitstamp USD) | 28 | 3.316% | 1.551% | 8.454% | 12.523% | 12.523% (2014-01) | 20 | 9 |
| Bitcoincharts `bitstampUSD` archive vs Bitstamp API (fidelity) | 137 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0 | 0 |
| Yahoo `BTC-USD` (ADR-010) vs Bitstamp USD | 144 | 0.214% | 0.052% | 0.536% | 1.542% | 2.000% (2017-12) | 9 | 0 |
| Coin Metrics `PriceUSD` vs Bitstamp USD | 181 | 0.307% | 0.052% | 0.624% | 7.262% | 8.120% (2011-11) | 11 | 3 |
| Blockchain.com vs Bitstamp USD | 181 | 0.833% | 0.516% | 1.739% | 5.217% | 5.499% (2013-11) | 46 | 3 |
| V1(Coin Metrics `PriceUSD`) vs Bitstamp EUR-native | 125 | 0.139% | 0.085% | 0.243% | 0.914% | 2.090% (2017-12) | 1 | 0 |
| V1(Blockchain.com) vs Bitstamp EUR-native | 125 | 0.539% | 0.417% | 1.119% | 1.767% | 2.481% (2018-11) | 17 | 0 |

Yahoo daily closes vs Bitstamp: n=4,409, p50 0.103%, p90 0.848%, p99 2.364%, max 7.830% (cutoff differences). Yahoo monthly deviation is 0.006-0.04% from 2022 on and 0.6-2.0% in 2017-2019.

Reading (PROPOSED): among exchange venues and V1, 92-100% of months agree within 1% (Bitfinex lowest: 11 of 161 USD months and 9 of 109 EUR months above 1%), the maximum is 4.1% (Coinbase EUR 2017-12, Bitfinex USD 2017-04 and Coinbase EUR) and no exchange comparison exceeds 5%. The bull-run months 2017-04 and 2017-12 are the worst. An empirical typical tolerance of about 2% (p99 across exchanges 1.1-3.1%) with the BTC-01 5% as hard fail is supported for 2014 on. For 2011-2013 the aggregator comparison shows up to 8.1% (Coin Metrics 2011-11) and 5.5% (Blockchain.com 2013-11) and Mt. Gox deviates from Bitstamp by up to 10.7% in 2013 (14.3% in 2014-01), so any pre-2014 month must be Q3 and cannot claim the 5% tolerance. The supported empirical tolerance is period-dependent: <= 1.5% typical (p99) and <= 4.1% max from 2014 on; no defensible tolerance below about 10% before 2014.

## 6. Reconstructions, quality levels and recommendation

### 6.1 Variants (all Decimal, unrounded; `tools/btc_02_history.py`)

- **V3 EUR-native**: mean of daily EUR closes of one venue in a complete month. Preferred where a liquid EUR book exists.
- **V1**: monthly mean of USD closes / monthly mean of valid ECB days; needs 100% BTC day coverage of the month.
- **V2**: matched-day mean of usd/fx; research sensitivity only (weekday bias: V2 differs from EUR-native by up to 2.7%).

### 6.2 Quality levels (PROPOSED)

| Level | Definition | Measured start (Bitstamp-based) |
|---|---|---|
| **Q1** | EUR-native complete month (V3) and mean daily USD-equivalent notional >= 1e6 | **2016-05** (125 months to 2026-09) |
| **Q2** | USD-derived (V1) complete month, liquid (>= 1e6 USD/day), single venue | **2013-04** (36 months: 2013-04..05, 2013-07..2016-04) |
| **Q3** | Complete month but thin (< 1e6 USD/day) or notional unknown: **research only, never published** | **2011-09** (20 months: 2011-09..2013-03 and 2013-06) |
| **Q0** | No complete month: value `null` with reason (`PARTIAL_MONTH`, `NO_DATA`, `NO_FX`) | 2011-08 and every month before 2011-09; the current month |

The 1e6 threshold is a parameter, not a decision (sensitivity: 1e5 from 2013-02; 1e7 would move Q1 to 2017-05 and Q2 out to 2017-05). 2013-06 flickers to Q3 because its mean notional dipped below 1e6; the level is a function of the month, it is not smoothed. Counts for 2011-08..2026-10: Q1 125, Q2 36, Q3 20, Q0 2. The Bitstamp-only candidate (canonical Decimal JSON incl. house join) has sha256 `83ffa9003cb8afc1cf89b0e0eaa5749ddd5796ac2935d438b1bb1b2375728c09`.

### 6.3 House join (CONFIRMED)

`btc_per_house = house_eur / btc_eur`, `sat_per_house = btc_per_house * 100000000` exact in Decimal. `data/cbs-housing.csv` `nl_house_avg_eur` exists 2000-01..2026-08; BTC and house price coexist for **180 months, 2011-09..2026-08**. Months before 2011-09 have a house price but no BTC value (null, reason `NO_BTC_PRICE`); 2026-09/10 have BTC data but no house price (`NO_HOUSE_PRICE`, the house series is not extended). Samples (unrounded in the log): 2011-09 Q3 4.65 EUR/BTC, 5.30e12 sat per house; 2014-10 Q2 287.23 EUR, 7.83e10 sat; 2016-05 Q1 407.68 EUR, 5.81e10 sat; 2020-01 Q1 7,544.90 EUR, 4.37e9 sat; 2024-01 Q1 39,378.55 EUR, 1.10e9 sat; 2026-08 Q1 59,929.24 EUR, 8.40e8 sat.

### 6.4 Rights and terms (see 7 for quoted text; none grants republication of derived monthly values)

Findings so far (search summaries NOT VERIFIED unless the terms job quote in 7 says otherwise):
- Bitstamp API page: commercial use of exchange data requires a signed Data License Agreement (partners@bitstamp.net); redistribution allowed only under that agreement (search summary).
- Kraken: "any non-personal commercial use of data from publicly accessible endpoints, such as market data" needs prior permission (marketdata@kraken.com) (legacy docs, search summary).
- Coinbase: separate "Market Data Terms of Use" (https://www.coinbase.com/legal/market_data), text in 7.
- Coin Metrics Community: Creative Commons, non-commercial (BTC-01, unverified licence version); commercial via sales.
- CryptoCompare/CoinDesk Data: API key now required (HTTP 401 CONFIRMED).
- TradingView: INDEX:BTCUSD cannot be extracted programmatically; see 7.
- Yahoo: terms unresolved (BTC-01).
- Reconstructability: `btc_eur = house_eur * 1e8 / sat_per_house` (BTC-01 6). Publishing sats equals publishing the monthly price, so the licence of the price source applies to sats.

### 6.5 Recommendation (PROPOSED, owner decides)

| Period | Preferred | Fallback / check | Level |
|---|---|---|---|
| 2016-05 onward | Bitstamp `btceur` mean of daily closes (V3) | Coinbase EUR (V3), Bitfinex/Binance/Kraken EUR; V1(Bitstamp USD) deviates <= 0.92% | Q1 |
| 2013-04..2016-04 | V1 from Bitstamp `btcusd` + ECB | Coinbase EUR from 2015-05 (thin), Bitfinex USD V1, CM `PriceUSD` V1 | Q2 (2013-06 Q3) |
| 2011-09..2013-03 | V1 Bitstamp (single thin venue) or CM `PriceUSD` V1 | Blockchain.com V1 | Q3, research only |
| 2010-08..2011-08 | Mt. Gox USD trade archive, V1 (41 complete Mt. Gox months 2010-08..2014-01, 2011-06 null) | CM `PriceUSD` V1, Blockchain.com V1 (aggregators) | Q3, research only; archive copy not publishable |
| 2014-02..2016-04 (EUR-native alternative) | Kraken EUR trade archive V3 (notional >= 1e6 EUR/day from 2015-10; 2016-01..03 null) | Coinbase EUR, V1 Bitstamp | Q3 until 2015-10, Q1 candidate afterwards; owner decision on archive provenance |

Preference follows: a EUR order book avoids FX; Bitstamp is the longest gap-free free source; the order book is single venue, which is the weakest point (concentration). Agreement with independent venues is shown in 5. No automatic splice: the Q1/Q2 break at 2016-04/05 is a visible basis change (V3 vs V1) whose size is bounded by the V1-vs-EUR-native deviation in 2016-2017 (mean 0.37%, max 0.70% in 2016; max 0.92% 2017-09).

Earliest defensible month per level (PROPOSED): Q1 2016-05; Q2 2013-04; Q3 2011-09 (research only). Defensible publication candidate, if the owner accepts a single-venue fixing and rights allow: **2013-07 onward** (Q2 from the first sustained 1e6 USD/day month, with 2013-06 excluded) or the conservative **2016-05**.

## 7. Terms and index documentation (CI-read primary text)

Read on 2026-10-21 by the `terms` job (run 39594396610). Quotes are the only sentences the keyword filter returned (sorted for redistribution/commercial wording); pages rendered by JavaScript may hide more. Page hashes (first 16 hex) are in the log. None of these quotes is a licence for republishing monthly values derived from the data.

| Source | Page | Quoted text (CONFIRMED text) | Reading |
|---|---|---|---|
| Bitstamp | bitstamp.net/api/ | "Companies seeking to utilize Bitstamp's exchange data for their own commercial purposes are directed to contact [partners address] ..." and "Bitstamp allows the incorporation and redistribution of our exchange data for commercial purposes." | Redistribution is expressly contemplated but through a data licence contact; free public API use for a public derived dashboard is UNRESOLVED |
| Kraken | docs-legacy.kraken.com global-intro | "This includes, but is not limited to, any non-personal commercial use of data from publicly accessible endpoints, such as market data, exchange status, and any other data." (context: prior permission) | Permission needed for non-personal commercial use; the current docs page returned no matching text |
| Kraken | support OHLCVT article (updated 2026-10-12) | Daily files are "direct file links"; no licence sentence found | Terms for the ZIP are UNRESOLVED |
| Coinbase | coinbase.com/legal/market_data | "...grants you a nonexclusive, nontransferable, non-sublicensable, revocable, limited license, solely for you and/or the officers and employees of you..." | Internal-use licence; not a redistribution grant |
| Coin Metrics | docs Community Data page | "Available to the community under the Creative Commons license." | Licence variant not stated on the page (BY-NC? UNRESOLVED) |
| CoinGecko | coingecko.com/en/api_terms | "you are not allowed to duplicate, reproduce, copy, store, derive from or translate any Data ... or any information expressed by the Data" except as permitted; "The scope of use ... will be dependent on the usage plan" | Derived data restricted by plan |
| Yahoo | legal.yahoo.com terms | "access or collect data ... using any automated means ... scrapers ..."; "Unless otherwise expressly stated, you may not access or reuse the Services ... for any commercial purpose."; no reproduction or derivative works for commercial purposes without written permission | Weakest basis for the ADR-010 source; rights NOT granted |
| TradingView | support article "How is the BTC Index being calculated?" | "The BTC Index is a spread chart that tracks the average BTC/USD exchange rate since Bitcoin was born." (page text 2,994 chars; the composition sentences were not returned by the filter) | Documents an average index; the composition is from the search summary only (Bitstamp, Coinbase, Bitfinex, Kraken average for recent data; early history including Mt. Gox): INFERRED, not confirmed on the primary page |
| TradingView | tradingview.com/policies | "...you shall not, without the prior expressed written consent of TradingView and the relevant Data Providers, make copies of any of the software or documentation ..." (26 filter hits; data-redistribution clauses not isolated) | No export/redistribution right for chart data is evident; chart extraction is not assumed allowed |
| ECB | ecb.europa.eu disclaimer | "users of this website may make free use of the information obtained directly from it subject to the following conditions: When such information is distributed or reproduced, it must appear accurately and the ECB must be cited as..." | FX leg is free to reuse with citation (matches GOLD-01) |
| Blockchain.com, CoinDesk Data, Bitcoincharts, Bitfinex, Binance | charts_api page (0 hits), CoinDesk legacy docs (JS page, 1 char), bitcoincharts (host unreachable), Bitfinex (404), Binance (HTTP 202 empty) | no text obtained | UNRESOLVED |

Conclusion: no primary text read grants the right to publish BTC prices or values from which the price can be recovered. TradingView `INDEX:BTCUSD` is not extractable by an API and its terms point to data-provider consent; it is treated as a visual cross-check only, never as a data source.

## 8. Blockers

1. **Rights**: no source grants republication of derived monthly values; exchange data licences are commercial (Bitstamp DLA, Kraken permission), Coin Metrics Community is non-commercial.
2. **Mt. Gox and pre-2011-09 trades**: only a third-party archive copy (Internet Archive capture of bitcoincharts files) is retrievable; no exchange-originated archive, no licence text for bitcoincharts (host and terms page unreachable), Mt. Gox stopped 2014-02-25 and deviates up to 14% from Bitstamp; pinned bytes are not stored (blocker 5).
3. **CryptoCompare/CoinDesk**: API key required; CoinDesk BPI legacy unreachable; CoinGecko history beyond 365 days refused.
4. **Kraken full history**: only the 720-candle REST window was measured; the OHLCVT ZIP is a manual download.
5. **Pinning**: retrieved bytes are not stored (storage class B not configured), so the sha256 values prove one retrieval, not reproducibility.
6. **Binance** blocks the main API host from US runners (HTTP 451); the data mirror worked.

## 9. Reproduction

Run `btc-02-history.yml` (pull_request on its own paths, or workflow_dispatch). Jobs: `offline-tests`, `exchanges` (Bitstamp/Coinbase/Bitfinex/Binance/Kraken/ECB, V1/V2/V3, quality levels, house join, candidate hash), `aggregators` (Blockchain.com, Coin Metrics, CryptoCompare, CoinDesk BPI, CoinGecko), `archives` (Internet Archive captures of bitcoincharts trade files; about 0.45 GB read, about 7 minutes), `yahoo` (ADR-010 file vs Bitstamp), `terms` (primary text keyword extraction).

## 10. Open owner decisions

- D1 rights path (which source, written request); D2 method (V3 where native, V1 otherwise; V2 sensitivity only); D3 start month and the 2016-04/05 basis break (2016-05 or 2013-07); D4 fields (sats only vs price); D5 tolerance (proposal 2% typical / 5% hard fail, supported 2014+); D6 liquidity threshold for Q2/Q3 (parameter 1e6 USD/day); D7 whether Q3 may ever be published.

## 11. Implementation

`tools/btc_02_history.py` (pure functions: `parse_daily`, `v1_ratio_of_means`, `v2_matched_day`, `v3_native_eur`, `classify_quality`, `build_monthly`, `assemble` (explicit plan only), `compare_monthly`, `house_join`, `sat_per_house`, `sha256_canonical`, `request_publication` always refuses), `tools/btc_02_probe.py` (CI probes), `tests/test_btc_02_history.py` (negative tests: duplicate/unordered, missing days stay missing, no forward fill, no automatic splice, non-positive, float refused, sat exactness, USD/EUR confusion, hash mismatch, partial month, publication refused), `.github/workflows/btc-02-history.yml` (permissions `contents: read`, artifacts aggregate logs only, 14 days).
