# BTC-03: Dutch housing prices in BTC and satoshis (research only, nothing published)

Status: **RESEARCH ONLY, PROPOSED methods. NOT AUTHORIZED FOR PUBLICATION.** No Bitcoin or satoshi value is public, no BTC selector exists in the frontend, `frontend/public/data/monthly.json`, `data/cbs-housing.csv`, GOLD-03/04, ADR-004 and every BTC ADR are untouched, `ALLOWLIST` of `etl/hist_model.py` stays empty. The methodology choices are in `BTC_03_DECISION_MEMO.md` and are all PROPOSED.

Code: `tools/btc_03_housing.py`; model additions in `etl/hist_model.py` (`btc_per_house`, median-aware `sats_per_house`, median/mean separation also for BTC); tests `tests/test_btc_03_housing.py` (32, synthetic: they prove code, not data); workflow `.github/workflows/btc-03-housing.yml` (read-only). Real-data evidence: runs 39769016414 (`bfe85c5`) and 39770032765 (`8da4a4a`), both `COMPLETE_RESEARCH`, `missing_sources` empty, bundles valid, rebuilds identical, vintage `MATCH` (second run). The numbers below were read from the summary lines of those runs; the artifact file (aggregates only) was not downloaded. No raw exchange data was committed or uploaded.

## 1. Methods (PROPOSED, not accepted)

* **A1:** monthly BTC price = arithmetic mean of all daily UTC closes of a COMPLETE calendar month (every day present). Incomplete months, interior gaps and partial final months are explicit nulls (`INSUFFICIENT_DAILY_COVERAGE`); nothing is carried forward or interpolated.
* **C1:** `BTC_EUR = mean(BTC_USD daily closes) / mean(ECB USD-per-EUR over valid days)` of the same month. ECB has no weekend or holiday rate; those days are simply absent from the FX mean (never filled). The ECB monthly mean uses the HIST-10 rule (at least 50% of calendar days, complete final month).
* `btc_per_house = house_eur / btc_eur`; `sat_per_house = btc_per_house x 100,000,000` (exact Decimal, 34 digits). Housing: CBS monthly mean price only (committed series 2000-01..2026-08).
* Quote direction and units are part of the series (`USD_per_BTC`, `EUR_per_BTC`, `USD_per_EUR`); a USD price cannot enter the EUR housing formula and an EUR price cannot be "converted" to EUR (tests).

## 2. Source coverage and quality matrix (run `8da4a4a`)

| Source (segment) | Daily coverage obtained | Complete months | Quality (PROPOSED) |
|---|---|---|---|
| Mt. Gox USD (Internet Archive copy of the bitcoincharts file, capture 20161229014309) | 2010-07-17..2014-02-25 (1,314 days, 6 calendar gaps in 2011-06) | 2010-08..2014-01: 41 months (2011-06 null) | Q3 always (early, thin, archive copy) |
| Bitstamp USD (API daily candles) | 2011-08-18..2026-10-21 (5,544 days, 0 gaps, 0 non-midnight timestamps, 0 duplicates) | 2011-09..2026-09: 181 | Q3 2011-09..2013-06 (22 months), Q2 from 2013-07 (159 months) |
| Bitstamp EUR (API daily candles) | 2016-04-16..2026-10-21 (3,841 days, 0 gaps) | 2016-05..2026-09: 125 | Q1 all 125 months (liquid) |
| Kraken EUR (archive capture 20210507020401), cross-validation only | 2014-01-08..2021-05-06 (2,627 days, 49 gaps) | 2014-02..2021-04: 81 with 8 nulls | not a housing segment |
| ECB EXR.D.USD.EUR.SP00.A | 1999-01-04..2026-10-21 (7,119 days; 3,034 calendar gaps = weekends and 134 weekday holidays) | monthly mean 1999-01..2026-09; 2026-10 null (partial month) | reference, equal to the HIST-10 pin |

**Liquidity finding (new, UNRESOLVED as a decision):** the BTC-02 rule "mean daily USD notional (close x volume) at least 1,000,000, sustained" gives `liquid_start = 2013-07`. The first month above the threshold is 2013-04 ($1.74M/day) and 2013-05 is above too ($1.11M), but 2013-06 is below ($0.87M), so the sustained start is 2013-07. Months 2013-04..2013-06 are therefore labelled Q3 here. The earlier candidate start 2013-04 is the first liquid month, not the sustained start; which one defines Q2 is a Project Control decision. The 19 months 2011-09..2013-03 are all below the threshold ($226 per day in 2011-09, $339k in 2013-03).

## 3. BTC/EUR research series (separate segments, never spliced)

| Series | Months |
|---|---|
| `mtgox_usd_derived_eur_c1` | 2010-08..2014-01 (41 values, 2011-06 null) |
| `bitstamp_usd_derived_eur_c1` | 2011-09..2026-09 (181) |
| `bitstamp_eur_monthly_a1` (EUR-native) | 2016-05..2026-09 (125) |
| `kraken_eur_monthly_a1` (cross-check) | 2014-02..2021-04 (81 values, 8 nulls) |

The three housing segments overlap in time (the USD-derived segment also covers 2016-05 onward); they are alternative constructions, not a continuation of one series.

## 4. CBS in BTC and satoshis (separate series per segment)

| Series | Months | n | Gaps |
|---|---|---|---|
| `cbs_btc_per_house_mtgox_usd_derived` / `cbs_sats_per_house_mtgox_usd_derived` | 2010-08..2014-01 | 41 | 2011-06 null (missing source days) |
| `..._bitstamp_usd_derived` | 2011-09..2026-08 | 180 | none |
| `..._bitstamp_eur_native` | 2016-05..2026-08 | 124 | none |

Representative values, independently recomputed with exact Fractions from the raw daily closes (relative difference to the model at most 3.1e-34):

| Month | Segment | BTC/EUR | House (EUR) | BTC per house | Satoshi per house |
|---|---|---|---|---|---|
| 2010-08 | Mt. Gox derived (Q3) | 0.0501 | 242,259 | 4,837,019.5051 | 483,701,950,507,840.69 |
| 2013-04 | Bitstamp USD derived (Q3 under the sustained rule) | 98.0306 | 214,969 | 2,192.8764 | 219,287,638,794.62 |
| 2016-05 | Bitstamp EUR native (Q1) | 407.6771 | 236,730 | 580.6802 | 58,068,015,562.60 |
| 2016-05 | Bitstamp USD derived (Q2) | 407.3875 | 236,730 | 581.0930 | 58,109,297,426.27 |
| 2026-08 | Bitstamp EUR native (Q1) | 59,929.2384 | 503,523 | 8.4020 | 840,195,893.61 |
| 2026-08 | Bitstamp USD derived (Q2) | 59,939.3770 | 503,523 | 8.4005 | 840,053,775.88 |

## 5. NVM median: no supported overlap

NVM runs 1975-H1..2000-H2 (52 half-years); the first complete BTC month is 2010-08. Overlapping half-years with six complete BTC months: **0** for every segment (`nvm_overlap`). No NVM/BTC or NVM/satoshi series is produced, nothing is spread to months, and the model refuses the combination (a semiannual house against a monthly price raises `FrequencyError`; the gold half-year rule is rejected for BTC with `DefinitionMismatch`). Bundle D of the assignment is therefore intentionally empty, with this reason recorded.

## 6. Methodology sensitivity (percent, versus the reference)

* **Month-end close vs A1** (Bitstamp EUR, 125 months): mean 7.85%, p99 27.53%, max 31.30% (2020-12). Bitstamp USD (181): mean 9.48%, max 105.0% (2013-11). Effect on satoshi per house (124 months): mean 7.68%, max 34.06% (2018-11). Month-end is not usable.
* **Trade-based definitions vs A1:** time-weighted average A4: Mt. Gox mean 0.76%, max 4.62% (2011-04); Kraken EUR mean 0.29%, max 0.85% (2020-03). Trade mean A3 and VWAP A3V: Mt. Gox mean 3.10% / 2.48% (max 26.2% / 20.2%), Kraken EUR mean 1.35% / 1.59% (max 7.7% / 12.5%). A1 is a close proxy of the true time-weighted price; no Bitstamp EUR trade archive exists, so its A4 was not measured.
* **USD to EUR vs the Bitstamp EUR native A1** (125 months): C1 mean 0.129%, p99 0.748%, max 0.916% (2017-09); C2 matched-day mean 0.444%, max 2.694%; C3 mean 0.451%, max 2.657%. Satoshi per house, C1 vs native: mean 0.129%, max 0.924%.
* **Transitions:** 2016-05..2017-04 C1 vs native: mean 0.333%, max 0.702% (2016-12). Q2 cross-check C1 vs Kraken EUR 2014-02..2016-04 (24 months): mean 0.370%, max 1.104% (2015-08). Cross-venue Kraken EUR vs Bitstamp EUR native 2016-05..2021-04 (57): mean 0.089%, max 0.731%. Mt. Gox vs Bitstamp USD, 29 shared months 2011-09..2014-01: mean 3.76%, max 14.26% (2014-01): a venue effect, so the two are never spliced.
* **Half-year BTC aggregation** (sensitivity only, no NVM overlap exists): versus the mean of the six monthly A1 (M1), the day-weighted mean of all daily closes (D) differs by mean 0.064% / max 0.212% (Bitstamp EUR, 20 half-years) and mean 0.078% / max 0.470% (Bitstamp USD, 29); the median of the months by 7.8% / 8.9% mean; the last month by 32.5% / 34.5% mean (max 130.9% / 162.7%); the first month by 21.0% / 24.5% mean; the last-day close by 36.6% / 37.7% mean. For BTC the gold rule M1 is only acceptable if it is checked (it is within 0.5% of the day-weighted mean); end-of-period rules are not.

## 7. Source versions, hashes and pins

Raw hashes identify the bytes downloaded in a run, not an archive of them: Bitstamp USD `ed370eed4f6dac7b692411c464b3df97e6dba8457376bc9a4a672960ef660511` (6 pages, 731,058 bytes), Bitstamp EUR `9fdd282e7dfeec7a97172eb460c20ea6259230912ae5e84ccf3de1b53a2d8361` (8 pages, 512,817 bytes), ECB `c9fad3ef319672f9e86a15221e9432ac676138b70173d13342a1ef4c581f89f0`, Mt. Gox archive `1a880feeadfe3c535c54aec4e66912fa6f277b3fb14f00829f05a345ab4b91eb` (59,585,679 bytes), Kraken EUR archive `58f56ddbe260e459b6be4353ad64922d9693143daad6676c1f580f90b4e05a51` (387,008,192 bytes). The Bitstamp API hashes differ between the two runs only through the responses' own content; the pinned windows below are the stable identity.

Window pins (`data/fixtures/btc03/source_pins.json`, method `BTC03_A1_C1_V1`; hashes only): Bitstamp USD 2011-08-18..2026-08-31 (5,493, `3c5f7ab0...4c3b`), Bitstamp EUR 2016-04-16..2026-08-31 (3,790, `2384c18d...fefe`), ECB 1999-01-04..2026-08-31 (7,082, `0daadfe8...f294`, equal to the HIST-10 pin), Kraken EUR 2014-01-08..2021-04-30 (2,621, `5ec73906...969a`), Mt. Gox 2010-07-17..2014-02-25 (1,314, `216e10c5...672d`); derived monthly values hash (cutoff 2026-08) `abb46e902ec24ef507e5b56270927249239e242b266734c52464ca8a327c6a29`. Each run reports `vintage_check` (`MATCH`, `SOURCE_REVISED`, `DEFECT_DERIVED_DRIFT`, `METHOD_CHANGED`, `UNPINNED`); the second run reports `MATCH` for all five sources.

Bundles (hist-model/1, 0 validation violations, full rebuild from the same bytes identical; they contain the acquisition timestamp and so differ between runs, `8da4a4a` run): A `8abfad30e82b4239d77d1859096a6acb1096a96f3b7147d01263cd85356e0c34`, B `89f4d4345bc129bd0a550d86407de2ad77eb894420fc8547790a6b1dba233bbf`, C `eeccd9d168213085137b9406055a795045000084b128705381019f942b5a9e83`. The bundles hold raw daily prices of third parties and were therefore not uploaded or committed.

## 8. Limits (UNRESOLVED)

Rights and terms of Bitstamp, the Internet Archive copies of bitcoincharts files and ECB reuse are UNVERIFIED; Bitstamp EUR has no trade archive (A4 not measured); the Mt. Gox and Kraken files are third-party archive copies, not pinned bytes; Mt. Gox 2011-06 has missing days; the ECB fixing time is not the UTC close; the timing basis of the CBS house price is the Kadaster registration, not a market date. Bitcoin and satoshi stay `withheld` under ADR-004 (BTC part), ADR-007, ADR-008, ADR-009 and ADR-010 (all PROPOSED).
