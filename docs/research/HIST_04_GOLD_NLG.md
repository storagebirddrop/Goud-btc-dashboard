# HIST-04: monthly gold in NLG (1975-1998) and EUR (1999), research candidate - not approved

Status: **research candidate - not approved.** The method below is an owner-approved research candidate, not a final methodology and not a publication approval. Every artifact row carries `rights_status = UNVERIFIED` and `publication_status = research candidate - not approved; not approved for publication`. Nothing is written to `data/`, `frontend/public` or the production pipeline; derived values live only in the CI artifact (14-day retention, no raw third-party data). A green CI run proves only that the tool ran without a hard defect.

Evidence: tool `tools/hist_04_gold_nlg.py`, workflow `.github/workflows/hist-04-gold-nlg.yml`, offline tests `tests/test_hist_04_gold_nlg.py` (synthetic data; they prove code behaviour only). The tool reuses `tools.hist_02_acquire.fetch` (https allowlist, size limit, sha256) through `tools.hist_04_fx.acquire`, the strict World Bank validator of `tools.hist_03_worldbank_validate`, the Fed H.10 and IMF parsers of `tools.hist_04_nlg_sources`, the ECB parser and Decimal formulas of `tools.hist_04_fx`, and the BoE/outlier helpers of `tools.hist_04_gold_outliers`. One additive change: `parse_dated_text` now also returns `missing_dates` (so `ND` days can be counted per month). The 2000+ production gold pipeline (`etl/gold_monthly.py`) is untouched and not re-implemented.

| CI run | Commit | Result |
|---|---|---|
| [39446827603](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39446827603) | 42a441e | exit 0, status `COMPLETE_RESEARCH_CANDIDATE`, 154 offline tests passed, no missing sources, no flags; artifact `hist-04-gold-nlg-research-candidate-not-approved` (summary.json, table.json, table.csv) |

## 1. Method and formulas

| Period | FX | Gold |
|---|---|---|
| 1975-01..1998-12 (288 months) | Fed H.10 daily noon buying rates New York, NLG per USD (`dat89_ne.txt` + `dat96_ne.txt`). Monthly FX = arithmetic mean of the available daily observations of the calendar month. `ND` days stay missing and are counted (`fx_nd_count`); no interpolation, no forward-fill. | `gold_nlg_oz = usd_oz x fx_nlg_per_usd` (World Bank monthly USD/oz, Decimal, 34 digits) |
| 1975-01..1998-12, comparability | fixed rate 2.20371 NLG per EUR (Council Regulation (EC) 2866/98) | `hist_eur_equivalent_oz = gold_nlg_oz / 2.20371`. This is a **historical EUR-equivalent, NOT a contemporaneous traded euro price.** |
| 1999-01..1999-12 (12 months) | ECB EXR `M.USD.EUR.SP00.A`, USD per EUR (provider monthly average) | `gold_eur_oz = usd_oz / usd_per_eur` |

Checks built in (hard error = exit 1): Fed header must say `GUILDERS/US$` and the value range must agree (NLG per USD), otherwise the run fails; duplicate dates within or across the two Fed files; ECB currency fields must be USD per EUR; World Bank workbook must validate structurally (300 months 1975-01..1999-12, one Gold column, troy-oz unit). Flagged, not hard (hist-03 semantics): a workbook or canonical-series sha256 different from `KNOWN_*` is reported as a source revision for human review. Independent recomputation with exact `Fraction` arithmetic checks every non-null gold value.

Unreachable sources do not fail the run: status `PARTIAL` (optional source missing) or `INCOMPLETE` (core source missing) with an explicit `missing_sources` list, exit 0. Missing inputs give null outputs and a quality label; nothing is filled.

Output fields per month: `period, regime, usd_oz, fx_nlg_per_usd, fx_usd_per_eur, fx_obs_count, fx_nd_count, gold_nlg_oz, hist_eur_equivalent_oz, gold_eur_oz, quality_label, outlier_flag, outlier_* (WB minus BoE numbers), sens_pom_vs_mop_rel, source url and sha256 for USD/oz and FX, rights_status, publication_status`. Quality labels: `OK`, `INCOMPLETE_FEW_OBS` (< 15 daily observations), `NO_FX_OBSERVATIONS`, `NO_USD_OZ`, combined with `+`.

## 2. Coverage (run 39446827603)

| Item | Result |
|---|---|
| NLG months in table | 288 of 288 expected (exactly) |
| Months with USD/oz, FX, `gold_nlg_oz`, `hist_eur_equivalent_oz` | 288 / 288 / 288 / 288; 0 null months |
| Daily observations per month (Fed) | min 17, median 21, max 23; 0 months below 15; 0 months without observations |
| `ND` days (missing, never filled) | 237 in total over 1975-1998 |
| EUR months 1999-01..1999-12 with `gold_eur_oz` | 12 of 12 |
| Quality labels | `OK` for all 300 rows |
| Outlier flags | 1980-12, 1983-07, 1985-03 flagged `UNVERIFIED_OUTLIER`, values unchanged |
| Fed direction | both files `NLG_PER_USD`, evidence `TEXT_AND_VALUE_RANGE` |
| Formula recomputation (exact fractions) | 588 values checked, max relative deviation 6.1E-34, pass |
| World Bank | workbook sha256 equals the known value `ea1c3508...3154`, canonical series sha256 equals the known value (no flags); 0 non-integer values; rounding bound 0.5 USD is at most 0.4545% of a monthly value (median 0.1377%) |

Source sha256 (this run): Fed `dat89_ne.txt` `dfad62a4...e8d3` (297,434 bytes), Fed `dat96_ne.txt` `3329eee3...d325` (141,074 bytes), ECB monthly `ed68895c...84f1a`, ECB daily `26c7d991...3c00`, IMF `3bb756f2...f7bc`, BoE monthly `f2265367...1116`, BoE daily XUDLGPD `b1997422...a7e6` (identical to the earlier outlier run). The full hashes are in the artifact summary.

## 3. Transition 1998-12 to 1999-01

Definitional breaks (stated, not quantified): FX source changes from Fed noon buying rates New York (NLG per USD, mean of daily values) to ECB reference rates (USD per EUR, provider monthly average); quote direction changes from multiply to divide; the currency changes from guilder to euro, so the 1998 EUR-equivalent is a fixed-rate conversion; the gold source is one World Bank series on both sides (no source break, whole-USD values).

Monthly numbers:

| Quantity | Value |
|---|---|
| World Bank USD/oz 1998-12 / 1999-01 | 292 / 287, change -1.712329% |
| Historical EUR-equivalent 1998-12 (NLG/oz / 2.20371) | 249.3198 |
| Gold EUR/oz 1999-01 (ECB monthly 1.16078 USD per EUR) | 247.2475 |
| EUR-equivalent change | -0.831164% |
| Implied USD per EUR 1998-12 (2.20371 / Fed mean NLG per USD) | 1.17118658 |
| ECB USD per EUR 1999-01 | 1.16078, change -0.888550% |
| Identity (1+EUR change) = (1+USD change)/(1+FX change) | residual 2E-34 |

Reading: the -0.83% move in EUR terms is the -1.71% move in USD gold, offset by a -0.89% move of USD per EUR. Part of the FX move can be definitional (daily-mean noon rate versus ECB monthly average); that part is not isolated here.

Daily boundary (Fed 1998-12-31 versus ECB 1999-01-04): Fed last value 1.8770 NLG per USD, implied 1.17405967 USD per EUR; ECB first value 1.1789; change +0.412273% over 4 calendar days; no common days. For comparison, the day-to-day absolute change of the implied rate over the last 250 Fed observations has median 0.3395%, p95 1.0578%, max 2.0023%; the first 60 ECB observations have median 0.3765%, p95 1.0322%, max 1.9444%. The boundary change is 1.21 times the Fed median daily move and within the observed range of ordinary moves. Numbers only: this does not show whether any part is a definitional break; no cause is claimed.

## 4. Fed versus IMF monthly (288 common months)

IMF `NLD.XDC_USD.PA_RT.M` against the Fed monthly mean of daily noon rates, relative difference: median 0.0647%, mean 0.0843%, p90 0.1778%, p95 0.2437%, p99 0.4090%, max 0.4669% (1991-03); median ratio 0.99995; signed median -0.0057%. Worst months: 1991-03 (-0.4669%), 1986-03 (-0.4560%), 1984-04 (-0.4090%), 1985-04 (-0.3314%), 1985-03 (+0.3265%). 90 months differ by more than 0.1%, none by more than 0.5%. This is a plausibility check, **independence of the underlying sources is not assumed** (both may derive from the same underlying quotations; the repeated 1991-03 deviation of IMF and BIS from the Fed is unexplained).

## 5. Product of monthly means versus mean of daily products (240 months, 1979-01..1998-12)

Months with BoE daily XUDLGPD and Fed daily values on common days (17-23 common days per month, median 21). A = mean(BoE) x mean(Fed) over the common days, B = mean(BoE x Fed) over the same days.

| Comparison | median | p95 | max (month) | months > 0.1% |
|---|---|---|---|---|
| (A - B) / B, pure methodology effect | 0.0066% | 0.0385% | 0.2104% (1980-03) | 3 |
| (WB monthly x Fed monthly mean - B) / B, includes WB-vs-BoE gap | 0.0847% | 0.3565% | -9.5971% (1980-12) | 101 |

The pure averaging-order effect is at most 0.21% in any month and has a median below 0.01%. The larger second row is dominated by the World Bank versus BoE differences, including the three flagged outliers (1980-12 -9.60%, 1983-07 -4.75%, 1985-03 +3.47%). This is a methodology sensitivity, not a correction; no value was changed.

## 6. Flagged outliers (World Bank values kept, BoE numbers shown)

| Month | WB USD/oz | BoE monthly (= mean of daily) | WB - BoE | % of BoE | BoE daily min..max |
|---|---|---|---|---|---|
| 1980-12 | 538 | 595.0952 | -57.0952 | -9.594% | 558..635 (21 days) |
| 1983-07 | 403 | 422.7357 | -19.7357 | -4.669% | 410.75..430.5 (21 days) |
| 1985-03 | 314 | 303.9429 | +10.0571 | +3.309% | 287.25..330.4 (21 days) |

These months stay `UNVERIFIED_OUTLIER` (see `HIST_04_GOLD_OUTLIERS.md`); their `gold_nlg_oz` and EUR-equivalent values inherit the World Bank value.

## 7. Methodological uncertainties

1. Fed noon buying rates (New York, cable transfers, certified for customs) versus the fixing of the gold source: different times of day and markets; effect not quantified.
2. Mean of daily noon rates is one of several monthly definitions (end-of-month, provider average); the IMF figures differ from it by a median 0.065%.
3. Product of means is used; its difference to the mean of daily products is small (section 5) but only measured for 1979-1998 against BoE.
4. World Bank gold is rounded to whole USD before 2000 (up to 0.45% of a monthly value) and its fixing basis and averaging rule are not documented in retrieved sources.
5. 1975-01..1978-12 has no daily second source in this run (BoE daily starts 1979-01); the BoE monthly series is not shown to be independent of the World Bank.
6. The EUR-equivalent before 1999 is a fixed-rate conversion and cannot be compared to a market euro price.
7. Transition: two FX sources with different definitions; the boundary move cannot be split into definition and market movement with the data at hand.

## 8. Remaining conditions before linking to Dutch house prices

- Rights review for Fed, ECB, IMF, BoE and World Bank data (all `UNVERIFIED`) and a retention decision.
- Comparability of the pre-2000 CBS house-price series (1995-1999 fixture, house price only, no HPI; public data starts 2000-01) with this gold series.
- Owner approval of the method (monthly FX definition, noon rates, product of means, fixed-rate EUR-equivalent): a ROOD decision under `CHANGE_CONTROL`.
- Decision on the World Bank outliers (1980-12, 1983-07, 1985-03) and on the single-source status of 1975-1978 gold.
- Decision on the 1999 ECB monthly average versus a daily mean and on handling of the transition label in any chart.
- Review of the artifact before any publication path is opened; no table, field or value here is a decided data contract.
