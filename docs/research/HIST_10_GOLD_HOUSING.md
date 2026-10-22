# HIST-10: Dutch housing prices in grams of gold from 1975 (research only, nothing published)

Status: **RESEARCH ONLY. NOT AUTHORIZED FOR PUBLICATION.** No change to `frontend/public/data/monthly.json`, `data/cbs-housing.csv`, GOLD-03/04 results, ADR-004 or any ADR. `ALLOWLIST` of `etl/hist_model.py` stays empty. Methodology choices are listed separately in `HIST_10_DECISION_MEMO.md` (all PROPOSED).

Code: `tools/hist_10_gold_housing.py`; model additions in `etl/hist_model.py` (quote-direction FX conversion, half-year aggregation rules, median-based grams per house, median/mean definitions cannot be mixed); tests `tests/test_hist_10_gold_housing.py` (26, synthetic: they prove code, not data); workflow `.github/workflows/hist-10-gold-housing.yml` (read-only). Real-data evidence: workflow runs 39758759214 (`1d4fd80`) and 39759345752 (`83560ef`), both `COMPLETE_RESEARCH`, 0 defects, no missing source, no flags. The numbers below were read from the summary lines the runs print from their `summary.json`; the artifact file itself (aggregates and a derived half-year CSV, 14-day retention) was not downloaded.

## 1. Formulas (checked)

`gold_price_per_gram_local = gold_price_per_troy_ounce_local / 31.1034768`; `grams_gold_per_house = housing_price_local / gold_price_per_gram_local`. Local gold: NLG era `USD/oz x (NLG per USD)`; EUR era `USD/oz / (USD per EUR)`. `NVM_EUR = NVM_NLG / 2.20371` is a denomination, not an inflation adjustment. FX direction is part of the series unit (`NLG_per_USD`, `USD_per_EUR`) and an inverted quote is rejected (tests). Half-year gold under the research rule M1 is the arithmetic mean of the six monthly local prices; all decimal arithmetic is 34-digit `Decimal`.

## 2. Source coverage and provenance matrix (run `1d4fd80`; identical in `83560ef`)

| Source | Series | Coverage actually obtained | sha256 of the obtained bytes |
|---|---|---|---|
| World Bank Pink Sheet workbook | gold USD/oz, monthly, whole USD | 1975-01..2026-09 (621) | `ea1c350827878ea3bbe30e3cda16a13fd3bd5b409b8458940dc94a36b5a33154` |
| Fed H.10 (two files) | NLG per USD, daily | 1971-01-04..1998-12-31 (7,021 obs; monthly mean 1971-01..1998-12, 336 months) | combined `56ac7e0fae00a2c5b6c4f5666601b2be29f0d7f6d71c7ceb3c50cc828260dd6d` |
| ECB reference rates | USD per EUR, daily | 1999-01-04..2026-10-21 (7,119 obs; monthly 1999-01..2026-09 = 333, 2026-10 null: partial month) | `c9fad3ef319672f9e86a15221e9432ac676138b70173d13342a1ef4c581f89f0` (changes daily) |
| CBS 85773NED export (HIST-09) | monthly mean price, count, value, 1995-01..2000-12 | 72 months each | zip `01d2aea00c19026e41b18ccd3a17b6beb004cd1b914a8a4a3f6683e15700584f` |
| NVM/OTB 2001 Table B3.8 (HIST-09) | nominal median, NLG, half-year | 1975-H1..2000-H2 (52) | csv `099489a42548f81c009607d464756871d11b8a646bfc54d0a28e687e3d5dffda` |
| CBS committed fixture / csv | monthly mean price | 1995-01..1999-12 (retro EUR), 2000-01..2026-08 | existing pins |

Missing sources: none (`missing_sources` empty). Not obtained: a guilder-native gold price (C2). Rights for all new sources remain `UNVERIFIED`.

## 3. Research datasets (separate, never spliced)

| Dataset | Periods | n | Note |
|---|---|---|---|
| NVM median in grams, NLG route | 1975-H1..1998-H2 | 48 | NVM NLG over gold NLG |
| NVM median in grams, retrospective EUR route | 1975-H1..1998-H2 | 48 | identical to the NLG route (max relative difference 8.3e-34) |
| NVM median in grams, observed EUR | 1999-H1..2000-H2 | 4 | NVM_EUR over ECB-based gold |
| CBS mean in grams, half-year (transaction-weighted mean price) | 1995-H1..1998-H2 retro EUR; 1999-H1..2000-H2 EUR | 8 + 4 | |
| CBS mean in grams, monthly | 1995-01..1998-12 retro; 1999-01..1999-12; 2000-01..2026-08 | 48, 12, 320 | no nulls |

Bundles (hist-model/1, 0 validation violations): A gold original (1 series, 257,096 B, `b06ac3dd...3422`), B gold local (`8d0e7b5e648b31cd2d86611c7042f9b3e04c4d3faf8cbf16f84e134954cbdb41`), C NVM grams (`7f607a3550de272b1d97342396b2166a2500f2fc07dee4ab5dc2a13e63511eec`), D CBS grams (`fe4243ea48f69b60f2b20493e1b90e5d8232413e83ad17c240e0d9fd580c801c`). These hashes belong to this source vintage (they change with the ECB bytes). Determinism on real data: a full rebuild from the same in-memory source bytes gives identical hashes for all four bundles (`rebuild_identical` true, run `83560ef`); offline, two clean rebuilds are byte-identical (tests).

Grams of gold per house, aggregation M1 (derived values, 2 decimals):

NVM median, NLG route: 1975-H1 6645.71, H2 7884.94; 1976 10004.70, 13158.26; 1977 14161.20, 14836.99; 1978 14576.99, 12806.52; 1979 10820.40, 7291.44; 1980 4385.17, 3787.39; 1981 3831.07, 3839.28; 1982 4381.10, 3560.25; 1983 3329.67, 3393.14; 1984 3422.09, 3506.34; 1985 3570.40, 4069.06; 1986 4694.11, 4702.56; 1987 4982.28, 4766.91; 1988 5287.65, 5335.66; 1989 5866.69, 6151.73; 1990 6824.73, 7386.80; 1991 7499.29, 7629.84; 1992 8713.97, 9751.44; 1993 9515.26, 8925.84; 1994 9193.15, 9991.20; 1995 11069.50, 11517.79; 1996 11336.11, 12067.65; 1997 12529.00, 13353.86; 1998 14588.20, 16648.38. Observed EUR: 1999-H1 18017.01, H2 18690.00; 2000-H1 18135.86, H2 18082.03.

CBS mean, retro EUR: 1995-H1 10095.81, H2 10680.67; 1996 10256.93, 11217.02; 1997 11383.32, 12599.52; 1998 13640.88, 15597.58. Observed EUR: 1999-H1 16463.67, H2 17776.37; 2000-H1 17154.50, H2 18098.04.

Same gold denominator means the NVM/CBS gap in grams equals the price gap (tested): 1995-H1 +9.64%, 2000-H2 -0.09%. NVM median and CBS mean are different statistics; no joined series.

## 4. Verification

* Representative half-years recomputed with exact Fractions straight from the raw dictionaries (1975-H1, 1980-H2, 1995-H1, 1998-H2, 1999-H1, 2000-H2): model and exact values agree to a relative difference of at most 6e-34. 1975-H1 NVM 6645.713418 g; 1995-H1 NVM 11069.501148 g and CBS 10095.812403 g; 2000-H2 NVM 18082.026050 g and CBS 18098.044778 g.
* The CBS monthly grams 2000-01..2026-08 (320 months) equal the published `gold_grams_per_house` of production within 9.75e-17 (floating point), so the model reproduces the accepted ADR-004 chain; no production value was changed.
* The model's monthly mean of the ECB daily rates equals the ECB monthly series within 5.3e-14 (333 months).
* Offline tests: direction and units, troy-ounce constant, half-year boundaries, aggregation rules, incomplete half-years (explicit null), missing months, bad inputs, currency transition (no overlap or splice between NLG and EUR eras), NVM/CBS separation (median-based and mean-based grams cannot be combined), lineage tamper, deterministic bundles, empty allowlist, unchanged production hashes.

## 5. Half-year aggregation alternatives (NVM grams vs M1, 52 half-years)

M1 mean of the six monthly local prices (reference); M2 mean(USD gold) x mean(monthly FX); M2d mean(USD gold) x mean(all daily FX); M3 gold of the last month; M4 gold of the first month; M6 monthly FX = last day of the month; M7 monthly FX = first day (M6/M7 keep the six-month mean of gold).

| Method | Max abs. deviation | Mean abs. | Median abs. | Mean signed |
|---|---|---|---|---|
| M2 | 0.343% (1981-H1) | 0.064% | 0.039% | -0.048% |
| M2d | 0.421% (1981-H1) | 0.093% | 0.056% | -0.071% |
| M6 | 2.704% (1985-H2) | 0.757% | 0.667% | +0.093% |
| M7 | 1.827% (1991-H1) | 0.654% | 0.597% | +0.021% |
| M3 | 17.521% (1979-H2) | 4.049% | 3.136% | +0.499% |
| M4 | 21.672% (1979-H2) | 4.472% | 3.345% | +0.451% |

By era, max abs.: M3 6.45% (1975-78), 17.52% (1979-98), 4.98% (1999-2000); M4 6.95%, 21.67%, 7.56%; M2 0.17%, 0.34%, 0.06%. Sample grams (M1 / M2 / M3 / M4): 1975-H1 6645.71 / 6645.53 / 6997.23 / 6395.72; 1995-H1 11069.50 / 11064.68 / 11243.47 / 10522.05; 2000-H2 18082.03 / 18092.83 / 18417.77 / 18534.52. For the CBS comparison, weighting the monthly gold by the CBS transaction counts (M5) differs from M1 by at most 0.354% (1997-H2), mean 0.163% (12 half-years).

## 6. Currency transition 1998/1999

Local gold 1998-12 (retro EUR) to 1999-01 (observed): -0.8312%; this reconciles with World Bank gold 292 -> 287 (-1.71%) and the FX step (-0.89%, HIST-08). NVM grams 1998-H2 -> 1999-H1: +8.22%; CBS grams monthly 1998-12 -> 1999-01: +1.53%. A definitional part of the step cannot be quantified (UNRESOLVED); the two eras are separate series and the break is documented, never bridged.

## 7. Limits (UNRESOLVED)

World Bank gold is whole USD (rounding bound 0.22% for 1979-1998, up to 0.45% in 1975-1978; HIST-08); Fed noon-rate lineage and parser independence not verified; rights for World Bank, Fed, ECB reuse beyond the accepted gold scope, NVM and CBS (CBS CC BY 4.0) are not decided; the 41 oldest NVM values rely on Project Control's page 135 verification (HIST-09). The derived dataset exists as a 14-day workflow artifact and is reproducible from the pinned inputs and the live sources; where to store it is decision D5.
