# HIST-05: gram gold per average Dutch home, 1995-01..1999-12 (research candidate - not approved)

Status: **research candidate - not approved.** Methodology: owner-approved CANDIDATE, not final. `rights_status = UNVERIFIED`, `publication = NOT APPROVED`. This is an internal research calculation. The derived 60-row table exists only in the CI artifact (14-day retention); it is not committed and nothing under `data/`, `frontend/public`, `etl/`, the ADRs or `monthly.json` was touched. Any use in the dashboard would be a ROOD item under `docs/governance/CHANGE_CONTROL.md`. A green CI run proves only that the tool ran without a hard defect.

Evidence tooling: `tools/hist_05_gold_per_home.py`, `tests/test_hist_05_gold_per_home.py` (synthetic, 40 tests, prove code only), `.github/workflows/hist-05-gold-per-home.yml` (push on this branch and `workflow_dispatch`; `contents: read`). Reused unchanged: `tools.hist_04_gold_nlg.collect` (World Bank workbook, Fed H.10 and ECB parsers, Decimal formulas, acquisition via `tools.hist_02_acquire.fetch`) and `tools.hist_05_cbs_kadaster` (CBS fetch, `parse_props`, `parse_typed`, `load_fixture`). No new parsers.

## 1. Method and formulas

| Input | Definition |
|---|---|
| House | CBS 85773NED monthly **average purchase price** of existing dwellings (price LEVEL, not the index). Measure identified from DataProperties: kind `PRICE_LEVEL`, title "Gemiddelde verkoopprijs", unit "euro" (key `GemiddeldeVerkoopprijs_7`, equal to the documented key). Euro also for 1995-1998 (retrospective denomination). |
| Gold 1995-01..1998-12 | World Bank USD/oz x arithmetic mean of available Fed H.10 daily noon buying rates (NLG per USD) = gold NLG/oz; historical EUR-equivalent = NLG/oz / 2.20371 |
| Gold 1999-01..1999-12 | World Bank USD/oz / ECB `M.USD.EUR.SP00.A` monthly mean (USD per EUR) = gold EUR/oz; NLG-equivalent = EUR/oz x 2.20371 (derived fixed-rate conversion, not a market rate) |
| Constants | troy ounce 31.1034768 g; 2.20371 NLG per EUR (Council Reg. (EC) 2866/98); Decimal strings, asserted (equal to the HIST-04 constant) |

grams per home = house_price_local x 31.1034768 / gold_price_per_troy_oz in the **same** currency.

- EUR route: `house_price_eur x 31.1034768 / gold_eur_equiv_per_oz`.
- NLG route: `(house_price_eur x 2.20371) x 31.1034768 / gold_nlg_per_oz`. The NLG house price (`house_price_nlg_equiv`) is DERIVED because CBS gives euro; no NLG original was obtained.

Unit safety: `Price(value, ccy, per)` carries currency and per-unit; `grams_per_home` raises `UnitMismatchError` (an exit-1 defect class) on currency or per-unit mismatch, untyped numbers or wrong regime rows; a CBS measure whose unit is not euro is a hard error. Output field names carry currency (`house_price_eur`, `house_price_nlg_equiv`, `gold_eur_equiv_per_oz`, `gold_nlg_per_oz`, `fx_applied` plus `fx_applied_unit`).

Missing data: no interpolation, forward-fill or back-fill and no fixture fallback. A month missing any input has null outputs and quality label `INCOMPLETE:<reasons>`. Acceptance requires exactly 60 consecutive unique rows 1995-01..1999-12 (`validate_table`, hard error otherwise). Unreachable sources give status `INCOMPLETE`/`PARTIAL` with `missing_sources`, exit 0; duplicates, invalid values, unit mismatch and structural failures give exit 1.

## 2. Coverage and quality (run 39478413417)

| Item | Result |
|---|---|
| Rows | 60 of 60, all inputs present, 0 null outputs, quality label `OK` for 60 |
| Status | `COMPLETE_RESEARCH_CANDIDATE`, no missing sources, no flags |
| CBS | measure `GemiddeldeVerkoopprijs_7`, 380 monthly observations in the table; DataProperties sha256 `4603147b...2bac1`, TypedDataSet sha256 `650a25c4...41465` (180,963 bytes); no `nextLink` |
| CBS vs pinned fixture `cbs-1995-1999-i1.json` (sha256 `0a557dd1...c543`) | equal 60 of 60, 0 differences (offline equality; the fixture derives from the same CBS tables, so this is not an independent check) |
| Fed observations per month 1995-1998 | min 18, median 21, max 23; 0 months below 15; 38 `ND` days (missing, never filled) |
| World Bank | workbook sha256 `ea1c3508...3154`, equals the known value, no flags; whole USD, rounding bound 0.5 USD per month (field `wb_usd_rounding_bound_pct`) |
| Fed sources | `dat89_ne.txt` `dfad62a4...e8d3`, `dat96_ne.txt` `3329eee3...d325`; ECB monthly `ed68895c...84f1a` |
| Outliers | HIST-04 flag list carried (1980-12, 1983-07, 1985-03, `UNVERIFIED_OUTLIER`); no flagged month lies in the window |
| Independent recomputation (exact fractions, 120 values) | pass; max deviation of 4-decimal display 4.978E-5 g (half-unit bound 5E-5) |

## 3. Results (internal research result only, EUR route, grams per average home)

| Year | Mean grams per home | Mean house price (EUR) | Mean gold EUR/oz (1995-98 EUR-equivalent) |
|---|---|---|---|
| 1995 | 10,378.7057 | 93,309.9167 | 279.8308 |
| 1996 | 10,721.2011 | 102,129.1667 | 296.4581 |
| 1997 | 11,991.5322 | 112,607.2500 | 292.8515 |
| 1998 | 14,615.1662 | 123,978.7500 | 264.6860 |
| 1999 | 17,130.8876 | 143,802.7500 | 261.4597 |

All five years have 12 values. Development: mean 1995 to mean 1999 **+65.06%** (house price mean +54.11%, gold EUR-equivalent mean -6.57%); 1995-01 (9,379.4697 g, also the minimum) to 1999-12 (17,266.3201 g) +84.09%; 1995-12 (10,631.6717 g) to 1999-12 +62.40%. Maximum 19,116.7506 g in 1999-08. In this window a Dutch home bought progressively more gold because house prices rose while gold fell in euro terms.

## 4. Route discrepancy (NLG route versus EUR route)

The routes are algebraically identical, so the comparison is an arithmetic and unit consistency check, not independent validation. At 34-digit Decimal precision the maximum absolute relative difference is **9.86E-34** (1996-01); tolerance asserted 1E-25. Rounded to the 4 decimals the artifact displays, the two routes are **identical in all 60 months** (max absolute difference 0.0000 g, 0 months differ); rounding would matter only if an exact value fell within ~1E-33 relative of a rounding boundary.

## 5. Definition breaks inside the window (not removed)

1. FX source and aggregation: Fed H.10 noon buying rates (mean of available daily values, NLG per USD) until 1998-12, ECB monthly mean (USD per EUR) from 1999-01; different source, aggregation and quote direction.
2. Currency: CBS euro prices for pre-2002 (here pre-1999) periods are retrospective; NLG originals not obtained; `house_price_nlg_equiv` and the 1999 NLG gold are derived fixed-rate conversions. Gold EUR for 1995-1998 is an EUR-equivalent, not a traded euro price.
3. World Bank gold is whole USD (up to ~0.45% of a monthly value).
4. House price is a compositional monthly mean of transactions, gold is a monthly mean of quotes; different time aggregations.

**Step 1998-12 to 1999-01** (grams per home 16,140.3374 to 16,387.3238): **+1.530%** (NLG route identical). Components: house price 129,378 to 130,266 EUR, +0.686%; gold per oz 249.3198 (EUR-equivalent) to 247.2475, -0.831%. Identity (1+grams) = (1+house)/(1+gold), residual 0. In logs 0.015187 = 0.006840 (house) + 0.008346 (minus gold); the **gold step is the larger driver**. The gold step is itself the World Bank USD move -1.712% offset by a USD/EUR step of -0.889% (Fed-mean-implied 1.17118658 to ECB 1.16078); part of that FX step may be definitional (daily-mean noon rate versus ECB monthly average) and is not isolated. The house-price step is within the range of ordinary month-on-month changes in the series.

## 6. Uncertainties

World Bank fixing basis and averaging rule undocumented; Fed noon rates versus the gold fixing time of day; product of monthly means (HIST-04 measured the averaging-order effect at up to 0.21%); CBS average price is not mix-adjusted and its NLG-to-EUR conversion history is undocumented in retrieved sources; the Dutch average price differs from other series (HIST-02 NVM annual comparison unresolved).

## 7. Remaining conditions for any future public extension

- Owner approval of the method (ROOD): monthly FX definition, noon rates, product of means, fixed-rate EUR-equivalent, use of the average price level.
- Rights review for CBS (citation required per the CBS copyright text; separate Kadaster terms not established), Fed, ECB, World Bank (all `UNVERIFIED`).
- Decision on the 1998-12/1999-01 transition label in any chart and on the 1995-1999 window being outside the current 2000-01 public data contract (changes pinned hashes and `etl/` logic; not GROEN).
- Decision on the HIST-04 outlier months and single-source gold status outside this window.

## 8. Evidence

| Run | Commit | Result |
|---|---|---|
| [39478413417](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39478413417) | b2a6993 | success; 161 offline tests passed; `COMPLETE_RESEARCH_CANDIDATE`; artifact `hist-05-gold-per-home-research-candidate-not-approved` (summary.json, table.json, table.csv; 14 days) |

Local: `python -m pytest -q` (815 passed, 4 skipped before the merge with the CBS-definitions work) and `python scripts/check_governance_docs.py` passed.
