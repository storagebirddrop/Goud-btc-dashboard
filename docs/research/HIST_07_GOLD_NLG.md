# HIST-07: gold before 2000 and the competing NLG/EUR constructions (research only, nothing approved)

Status: **RESEARCH. Not a decision, not a methodology change, not a publication.** ADR-004 (`etl/gold_monthly.py`, 2000-01 onward), the published CBS data and the gold HOLD/GOLD-03 state are untouched; no existing file was edited. Any use of these constructions in the dashboard is ROOD under `docs/governance/CHANGE_CONTROL.md`. Labels: CONFIRMED (measured in CI or primary text read), INFERRED, PROPOSED, UNRESOLVED. Rights for all sources remain `UNVERIFIED` (see `HIST_04_SOURCE_RIGHTS.md`); artifacts hold aggregates and a derived table only, raw third-party bytes are never committed.

Builds on (not repeated here): `HIST_04_GOLD_NLG.md` (Fed-based NLG candidate 1975-1998, transition), `HIST_04_NLG_SOURCES.md` / `HIST_04_FX_SOURCES.md` (source recovery, 2.20371 verified in CI), `HIST_04_GOLD_OUTLIERS.md` (WB vs BoE outliers), `HIST_05_GOLD_PER_HOME.md` (1995-1999 grams per home), `HIST_05_NVM_AND_LONG_RUN.md` (NVM years), `GOLD_01_TECHNICAL_METHODOLOGY.md`, HIST-03 tooling (`tools/hist_03_worldbank_validate.py`).

**What is new here:** (1) the World Bank GOLD column read over its full extent 1960-01..2026-09 (HIST-03 covered 1975-1999 only), including the Description-sheet definition text, rounding statistics for every decade, and a vintage comparison; (2) NLG/USD monthly coverage extended back to 1960-01 (BIS-derived, IMF, CBS) and to 1971-01 for the Fed daily file; (3) the euro/guilder overlap test 1999-01..2001-12 as an empirical error bound for the FX definition, using Fed H.10 euro files (new source) against the ECB; (4) a typed-unit reference implementation of the four constructions with an independent cross-check; (5) grams-per-home sensitivity under each FX source and gold source, plus the NVM selected years; (6) a documented negative result for a direct guilder gold price (C2).

Evidence: tools `tools/hist_07_gold_constructions.py` (pure Decimal functions, canonical sha256, fail-closed CLI), `tools/hist_07_collect.py` (CI collector); tests `tests/test_hist_07_gold_constructions.py`, `tests/test_hist_07_collect.py` (synthetic, prove code only; include an independent `Fraction` re-implementation of the formulas); workflow `.github/workflows/hist-07-gold.yml` (`contents: read`, PR on own paths and `workflow_dispatch`, artifact `hist-07-gold-research-not-approved`, 14 days).

| CI run | Commit | Result |
|---|---|---|
| [39585094711](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39585094711) | 8e9a9ba | success, status `PARTIAL` (FRED timeout, Bundesbank 404 recorded), all numbers below unless noted |
| [39594351410](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594351410) | df9d7cf | success; derived table sha256 identical to run 39585094711 (`de122b01...4c0b`), i.e. reproducible across two runs about 75 minutes apart |
| [39585368950](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39585368950) | d08e339 | success; datahub vs World Bank, Fed euro long run, CBS catalogue search, BIS regime values |

## 1. Verdict table

| ID | Construction | Definition | Coverage measured | Quality | Verdict |
|---|---|---|---|---|---|
| C1 | `gold_nlg_oz` = WB USD/oz x monthly-mean market NLG per USD | observed guilder pricing basis | Fed noon rates 1971-01..1998-12 (336 of 336 months, 17-23 daily obs); BIS-derived 1960-01..1998-12 (468 of 468); CBS 1965-01..1998-12 (408 of 408 in range, 2 decimals); IMF 1960-01..1998-12 (468 of 468) | see section 5 | 1975-1998: **ready for owner decision** (error bound known); 1971-1974: needs more evidence; 1960-1970: not ready |
| C2 | direct guilder gold price | observed NLG price from an authority | **none found**: CBS catalogue title search for "goud", "Goud", "delmetaal" returns 0 tables (CONFIRMED, 3 queries); DNB site 403 from CI (HIST-04); Bundesbank key `BBK01/WT5511` HTTP 404 on two URL forms; FRED EXNEUS timeout again | n/a | **UNRESOLVED**, not usable |
| C3 | `eur_equivalent_oz` = C1 / 2.20371 | **nominal redenominated equivalent, NOT an observed contemporaneous euro market price** | same months as the C1 source it is derived from | inherits C1 | label only; value-neutral for grams per home (section 4) |
| C4 | `gold_eur_oz` = WB USD/oz / ECB monthly-mean USD per EUR (ADR-004) | observed euro price | ECB 1999-01..2026-09 complete (333 monthly values plus current); ADR-004 production starts 2000-01, so **1999-01..1999-12 is new, available coverage** | as ADR-004 | cannot be projected before 1999-01-04 (CONFIRMED: no ECB reference rate exists earlier) |

## 2. World Bank Pink Sheet gold (scope item 1)

| Item | Result | Label |
|---|---|---|
| Workbook | pinned URL `.../74e8be41...-0050012026/related/CMO-Historical-Data-Monthly.xlsx`, sha256 `ea1c3508...3154` (586,099 bytes) equals the repo pin; sheets: Mismatch Details, Monthly Prices, Monthly Indices, Description, Index Weights; Monthly Indices states "Updated on October 02, 2026" | CONFIRMED |
| Newer vintage | the World Bank commodity-markets page (fetched, 56,273 bytes) lists exactly one workbook link, identical to the pin; no differing vintage exists as of this run | CONFIRMED |
| Column / unit | column BR header `Gold`, unit row `($/troy oz)`; one Gold column | CONFIRMED |
| Coverage | 1960-01..2026-09, 801 of 801 months, 0 missing, 0 duplicates, 0 invalid | CONFIRMED |
| 1975-01..1999-12 | canonical series sha256 `28390135...4cf7` equals the HIST-03 pin | CONFIRMED |
| Definition (Description sheet, verbatim extract) | "Gold, spot average of daily rates, from June 2025; previously (UK), 99.5% fine, London afternoon fixing, average of daily rates". The lineage list printed for the row is not per period: "Bloomberg Finance L.P.; Kitco.com; International Monetary Fund, International Financial Statistics; London Bullion Market; Metals Week; Platts Metals Week; Shearson Lehman Brothers, Metal Market Weekly Review; Thomson Reuters Datastream; World Bank." | CONFIRMED text; which provider serves which period is UNRESOLVED |
| June 2025 break | values 3,309 (2025-05), 3,353 (2025-06), 3,340 (2025-07); no overlap source exists to quantify the break | CONFIRMED values; effect UNRESOLVED |
| Precision | **all 801 values are whole USD in every decade, including 2000-2026** (0 non-integer values in 1960-67, 1968-74, 1975-79, 1980-89, 1990-99, 2000-09, 2010-26). This replaces the unmeasured assumption in `GOLD_01_TECHNICAL_METHODOLOGY.md` T-6 that 2000+ values carry decimals | CONFIRMED |
| Rounding bound 0.5 USD as share of value (arithmetic from measured minima) | up to 1.43% at 35 USD (1960-1974), 0.45% at 110 USD (1975-79 minimum), 0.17% at 299 (1980s), 0.20% at 256 (1990s), 0.19% at 260 (2000s), 0.05% at 1,076 (2010+) | derived |
| Regimes | 1960-01..1967-12: 96 consecutive months at exactly 35 (longest equal run 96) - this is the official parity, not a market observation (INFERRED); 1968-02..05: 36, 37, 38, 41; 1971-07..09: 41, 43, 42; 1974-12: 184; 1975-01: 176. 1968-1974 runs of equal values are at most 4 months | CONFIRMED values, regime reading INFERRED |
| Revisions | the secondary dataset `datahub gold-prices` (package text: data from 1960 sourced from the World Bank Commodity Markets portal, licence ODC-PDDL-1.0) is an **older World Bank vintage**: it equals the pinned workbook in 786 of 801 months. The 15 differences: 13 in 1960-1964 (World Bank flat 35 vs 35.10-35.27, e.g. 1960-01 35.270, 1961-01 35.250, 1962-04 35.230, 1964-05 35.100), 1989-12 (409 vs 409.39) and 2000-08 (274 vs 274.47). So the older vintage carried decimals in places and the current workbook rounds to whole USD and flattens 1960-1964 | CONFIRMED difference, direction of revision INFERRED |
| Independence | datahub is **not** an independent second source (same origin). The only independent monthly cross-check is the Bank of England IADB `XUMAGPD`, which starts 1979-01 (240 common months to 1998-12) | CONFIRMED |

Usability by period: **1979-1998** usable with a cross-check (WB vs BoE monthly: 1979-1989 median |dev| 0.0725%, p95 0.470%, max 9.594% (1980-12, a known unexplained outlier, also 1983-07 -4.669%, 1985-03 +3.309%); 1990-1998 median 0.0616%, p95 0.183%, max 0.267%; 1999 median 0.090%, max 0.160%; only 2 of 240 months identical, consistent with whole-USD rounding plus different fixing bases). **1975-1978** single lineage, no second source (UNRESOLVED). **1968-1974** single lineage, whole USD (rounding bound up to 1.4%), two-tier gold market in this period (INFERRED from general knowledge, not tested); **1960-1967** flat official price, not usable as a market series for a house-price comparison without an owner decision.

## 3. NLG/USD sources and the overlap test

Monthly NLG per USD, all Decimal, no filling (section 1 coverage). Fed H.10 daily noon buying rates: monthly mean of available days, 17-23 observations per month (median 21). BIS `WS_XRU` `M.NL` average is euro-denominated (EUR per USD, 877 months 1953-09..2026-09, collection `A` and `E` both present) and converted with x 2.20371 (labelled derivation, not an NLG original). IMF `NLD.XDC_USD.PA_RT.M` 1957-01..1998-12 (504 months, one series). CBS 7139SHFO 1965-01..2001-12 (444 months, 2 decimals). FRED EXNEUS timed out again (30 s).

Regime before 1971 (BIS-derived, median per year, NLG per USD): 1960 3.7708, 1961 3.6005 (monthly 1961-02 3.7870, 03 3.6241, 04 3.5940: the March 1961 revaluation, INFERRED), 1962-1970 within 3.5996-3.6220, 1971 3.5567, 1972 3.2120. Before 1971 the rate is a pegged/managed parity, not a free market rate.

Source spread, monthly relative difference (percent):

| Comparison | months | median abs | p95 abs | max abs (month) | mean signed |
|---|---|---|---|---|---|
| BIS-derived vs Fed, 1971-1998 | 336 | 0.0543 | 0.2355 | 0.4647 (1991-03) | -0.0074 |
| CBS vs Fed, 1971-1998 | 336 | 0.1296 | 0.3861 | 0.9951 (1973-03) | -0.0141 |
| IMF vs Fed, 1971-1998 | 336 | 0.0639 | 0.2690 | 5.4119 (1971-12) | +0.0177 |
| CBS vs BIS-derived, 1960-1970 | 72 | 0.0671 | 0.1464 | 0.2409 (1969-12) | -0.0055 |
| IMF vs BIS-derived, 1960-1970 | 132 | 0.4776 | 0.7657 | 0.7933 (1960-06) | +0.3449 |

Reading: Fed, BIS and (coarsely) CBS agree to a median 0.05-0.13%; the IMF series deviates systematically before 1971 (+0.45% median) and by 5.4% in 1971-12 (cause UNRESOLVED; IMF is not used as a primary candidate). Agreement is not independence (HIST-04: shared 1991-03 deviation of IMF and BIS).

### The 1999-01..2001-12 overlap (scope item 3)

Because the guilder was fixed to the euro from 1999-01-01, USD/NLG in the overlap is a **mechanical cross of USD/EUR** (NLG per USD = 2.20371 / USD per EUR). The test therefore cannot show whether a guilder market rate "would have differed"; it measures exactly the difference between an NLG-route construction using a *non-ECB* monthly FX mean and the ADR-004 construction. Same World Bank USD gold on both sides, so the gold side cancels. C3 = USD x (2.20371 / USD-per-EUR) / 2.20371; C4 = USD / ECB monthly mean. Deviation = C3/C4 - 1 (positive: C3 above C4).

| FX used for C3 | months | median abs | mean signed | p95 abs | max abs (month) |
|---|---|---|---|---|---|
| Fed H.10 euro noon rates (monthly mean of daily) | 36 | 0.0582 | +0.0324 | 0.3035 | 0.3074 (2000-10) |
| BIS M.NL average | 36 | 0.0110 | +0.0162 | 0.0410 | 0.0442 (2000-12) |
| CBS 7139SHFO (2 decimals) | 36 | 0.1180 | -0.0207 | 0.4223 | 0.5338 (1999-07) |
| IMF | 0 | no data after 1998-12 | | | |

Mean signed by year (Fed): 1999 +0.0113, 2000 +0.0710, 2001 +0.0149. Longer Fed-versus-ECB run, 149 months 1999-01..2011-05 (the 2011-06 file month has only 8 observations and is dropped, not used): median abs 0.0509, p95 0.2404, max 0.4591 (2008-12), mean signed -0.0144, worst 2008-12, 2008-10 (+0.4207), 2003-09 (-0.4018); median abs by year 0.017-0.111.

Interpretation. (a) **Empirical error bound for the FX definition** (New York noon buying rate mean versus ECB reference-rate mean): about 0.05% typical, 0.24-0.30% at the 95th percentile, 0.31-0.46% worst month; no bias beyond +-0.07% by year. This bound is consistent with the pre-1999 cross-source spread (BIS vs Fed max 0.46%, same magnitude), which raises confidence that it describes the monthly-mean definition difference rather than anything specific to 1999-2001. (b) BIS after 1999 agrees with the ECB to 0.01%, i.e. it is ECB-derived there (INFERRED); it is no independent confirmation. (c) The CBS spread is dominated by 2-decimal rounding. (d) The test does **not** bound the gold side (see the WB-vs-BoE numbers above), the 1998-12/1999-01 step (HIST-04: part of the -0.89% USD per EUR move may be definitional) or anything before 1999: the present ECB method cannot be projected backwards because no euro rates existed.

## 4. Grams of gold per home (scope item 4)

Formula: `house_price x 31.1034768 / gold price per oz` in the same currency (typed units; NLG vs EUR mixing raises an error). CBS 85773NED monthly average price, pinned fixture `data/fixtures/cbs-1995-1999-i1.json` (sha256 `0a557dd1...c543`, 60 months). Annual means of the 12 monthly grams values.

| Construction (FX source) | 1995 | 1996 | 1997 | 1998 | 1999 | max monthly dev vs Fed base |
|---|---|---|---|---|---|---|
| C3 Fed, then C4 in 1999 (base; equals HIST-05 to rounding) | 10,378.71 | 10,721.20 | 11,991.53 | 14,615.17 | 17,130.89 | base |
| C3 BIS-derived | 10,378.83 | 10,722.73 | 11,993.00 | 14,611.78 | 17,130.89 | 0.183% (1997-09) |
| C3 IMF | 10,378.28 | 10,723.18 | 11,992.85 | 14,611.18 | 17,130.89 | 0.183% (1997-09) |
| C3 CBS (2 decimals) | 10,371.64 | 10,728.65 | 11,995.79 | 14,601.82 | 17,130.89 | 0.418% (1997-09) |
| C3 Fed with BoE monthly gold instead of WB | 10,378.13 | 10,717.76 | 11,991.39 | 14,614.15 | n/a (BoE file ends 1999-12 in window, not used) | 0.267% (1998-12) |
| 1999 only: C3 from Fed euro noon rates instead of C4 | | | | | 17,129.25 | 0.172% (1999-07) |

(1999 is C4 in all rows except the last; 1999-12 grams 17,266.32 in HIST-05.) Findings: (i) **The NLG route and the EUR route are identical** (HIST-05 measured 1E-33; here the NLG-route and EUR-route values of the NVM check agree to the cent): redenomination is a unit conversion applied to house and gold alike, so the choice between C1 and C3 does not change grams per home; it changes only the displayed currency. (ii) What does move the result is the FX source/definition (median 0.04-0.12%, max 0.18-0.42% per month; on annual means at most 0.09%, CBS 1998) and the gold source (WB rounding, WB vs BoE up to 0.27% in this window). In relative terms grams per home move inversely one-to-one with the guilder gold price, hence with the FX error. (iii) All variants give the same economic picture: +65% grams per home from 1995 to 1999 because house prices rose faster than gold in guilder/euro terms (HIST-05).

NVM median, selected years (NLG, ESB secondary quote from `HIST_05_NVM_AND_LONG_RUN.md`: 130,000 / 159,000 / 223,000 / 329,000), annual option A (mean of 12 monthly gold prices), grams per home:

| Year | Fed | BIS-derived | IMF | CBS | note |
|---|---|---|---|---|---|
| 1985 | 3,835.10 | 3,835.03 | 3,834.76 | 3,834.44 | spread 0.017% |
| 1990 | 7,081.14 | 7,081.05 | 7,080.41 | 7,074.48 | spread 0.094% |
| 1995 | 11,247.70 | 11,247.65 | 11,247.07 | 11,240.05 | spread 0.068% |
| 1999 | 17,760.11 (C4, EUR route) | | | | only C4 computed |

NVM median 1995 gives 11,248 g versus 10,379 g from the CBS mean (+8.4%): median vs mean and different populations, **not comparable and not a validation** (HIST-05). Annual gold NLG per oz (Fed) 1985 1,054.33, 1990 698.40, 1995 616.67.

## 5. Quality levels (PROPOSED)

| Level | Period | Basis |
|---|---|---|
| A | 1979-01..1998-12 | WB gold cross-checked against BoE monthly (median 0.06-0.07%), Fed daily FX with 17-23 observations, BIS/IMF/CBS monthly cross-checks within 0.5% (CBS 1%); three WB outlier months stay `UNVERIFIED_OUTLIER` |
| B | 1975-01..1978-12 | as A but gold has no second source |
| C | 1971-01..1974-12 | Fed daily FX available; gold single lineage, whole USD (rounding bound 1.4%), two-tier market; floating regime begins 1971 |
| D | 1960-01..1970-12 | FX is a pegged parity (BIS-derived, CBS, IMF disagree by up to 0.8%); WB gold flat 35 for 1960-1967 (official price), older vintage shows 35.10-35.27 |
| E | 1999-01..1999-12 | observed euro C4; WB gold unchanged; Fed euro noon rates differ from ECB by <= 0.31% (36-month bound) |

## 6. Blockers and negative results

1. No independent monthly USD gold source for 1960-1978 was reachable: BoE starts 1979; Bundesbank `WT5511` returned 404 (two URL forms); IMF PCPS guess returned an empty dataset (key not identified); FRED times out; LBMA/IBA data are rights-restricted (HIST-04 rights note). UNRESOLVED.
2. C2: no credible direct guilder gold price located (CBS catalogue empty, DNB blocked, no machine-readable archive found by search). A paper source (DNB annual reports, Amsterdam bourse list) would need manual transcription; not attempted.
3. WB provider by period and the 1980-12/1983-07/1985-03 anomalies remain unexplained (HIST-04). The vintage comparison shows the World Bank has changed historical values between releases, so a pin plus revision policy (GOLD_01 M-5, T-1) matters for any pre-2000 extension.
4. FX before 1971: a managed parity; BIS-derived and CBS values exist but whether a monthly average of a pegged rate is the right "market rate" for gold conversion is an owner question. IMF series rejected as primary.
5. Overlap test limitation: it cannot test guilder-specific market effects (fixed cross) or the gold side.
6. CBS house price starts 1995-01 in the fixture; NVM has four annual medians only. Grams per home before 1995 therefore exist only for four NVM years.

## 7. Recommendations

READY for owner decision (ROOD, research-grade): **C1 (NLG-native) and its C3 label for 1975-01..1998-12 using Fed H.10 monthly means** (level A/B), as already proposed in HIST-04/05, now with a measured FX-definition error bound (median 0.05%, p95 0.24-0.30%, max 0.46%) and a gold-side bound (WB vs BoE median 0.06-0.07%, plus three flagged outliers); and **C4 for 1999-01..1999-12** from the existing ADR-004 formula, labelled as observed and as a definition break against the preceding months. Recommended presentation (PROPOSED): grams per home in guilders-native terms before 1999, C3 only as a clearly captioned nominal equivalent, never mixed with observed euro prices in one unlabelled series.

NEEDS MORE EVIDENCE: 1971-01..1974-12 (second gold source, regime annotation), 1960-01..1970-12 (parity FX, flat-35 gold; likely a separate annotated "official price era" if shown at all), any claim about provider lineage, C2.

Most defensible construction for grams per home: C1/C3 with Fed monthly mean FX and WB gold, because (i) C1 and C3 give identical grams, (ii) Fed is public-domain text read in CI, daily and complete, (iii) BIS and IMF agree within 0.05-0.06% median, (iv) CBS is too coarse, (v) the euro-era test shows the Fed-versus-ECB definition gap is small relative to the 65% change in grams over the window.

## 8. Open owner decisions

1. Approve or reject Fed noon-rate monthly means (vs BIS/IMF monthly averages) as the NLG FX definition; accept the 0.24-0.30% p95 definition bound.
2. Accept whole-USD World Bank values and the rounding bounds above, and the treatment of the three outlier months.
3. Decide the earliest published month (1999, 1979, 1975, 1971 or 1960) per quality level, and the annotation of regime breaks (official price era, floating from 1971, euro/ECB from 1999, World Bank June 2025).
4. Decide whether to pin the current World Bank workbook for pre-2000 months given that an older vintage differs in 15 months.
5. Rights review for all sources (all `UNVERIFIED`).
6. Whether to commission a manual search for C2 (DNB archive) or a second 1960-1978 gold source.

## 9. Reproducibility

`python -m pytest -q tests/test_hist_07_gold_constructions.py tests/test_hist_07_collect.py` (offline). `python -m tools.hist_07_gold_constructions --inputs in.json --out out.json [--expect-sha256 H]` exits 1 on any input defect and 2 on a hash mismatch. Collector table sha256 (canonical, 877 rows, run 39585094711): `de122b01c2ffe24ac7719fc79dd621f5442130e6635dd695d37e0b6fde7b4c0b`. Source hashes: WB `ea1c3508...3154`, Fed `dat89_ne.txt` `dfad62a4...e8d3`, `dat96_ne.txt` `3329eee3...d325`, ECB monthly `ed68895c...84f1a`, BIS `5996ed2a...e1df`, CBS 7139 data `035ed44f...d021`, BoE monthly `f2265367...1116`, Fed euro `dat96_eu.txt` `7bcb9833...3905`, `dat00_eu.txt` `e8159e23...4813`, datahub `f5945c29...ebcf5`.
