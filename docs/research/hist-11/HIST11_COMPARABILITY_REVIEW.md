# HIST-11 — Comparability review

Status: assessment only. Sources of truth: `HIST_09_INTEGRATION.md`, `HIST_10_DECISION_MEMO.md`, `HIST_10_GOLD_HOUSING.md`, `etl/hist_model.py`, `docs/governance/DECISIONS.md` (ADR-004, ADR-011, GOLD-01, GOLD-03). Nothing is spliced, interpolated or bridged here, and no value is changed.

## 1. Rule

NVM median (half-year, guilders) and CBS mean (monthly, euro) are **different statistics**. They are never concatenated into one series. The model already enforces this: `average_price` x `median_price` is an incompatible pair, the only relation is the explicit `statistic_ratio` (flag `STATISTICS_DIFFER`), and `convert_frequency` refuses every conversion (monthly -> half-year only through the audited `weighted_half_year_mean`; half-year -> monthly never).

## 2. The five required distinctions

| Distinction | Where it bites | Treatment |
|---|---|---|
| Median vs mean | NVM (median, brokers' population) vs CBS (mean of registered sales) | separate series ids and definition ids; overlap 1995-H1..2000-H2 shown only as a labelled comparison (mean gap +7.13%, range -0.09%..+10.52%); no bridge before 1995 |
| Half-year vs monthly | NVM is half-year only; CBS monthly | no interpolation or synthetic months; the CBS comparison is aggregated to half-years by the audited transaction-weighted mean, all six months required, otherwise null |
| NLG-native vs retrospective EUR | NVM and CBS before 2002-01 (CBS) / the NLG era (gold up to 1998-12) | NLG original is primary for NVM; EUR = NLG / 2.20371 is a denomination, always labelled `RETROSPECTIVE_EUR`; never presented as an observed euro price. CBS publishes euro only (NLG originals not obtained) |
| Historical vs current source coverage | Fed H.10 (to 1998-12) vs ECB (from 1999-01); World Bank whole-USD rounding; benchmark definition change 2025-06 | era `Break` at 1998-12/1999-01; quality levels B 1975-78, A 1979-98, E 1999, ADR-004 period 2000+; the 2025-06 break remains annotated in the current view |
| Observed vs derived; provisional vs production quality | grams, ratios, half-year aggregates are derived; NVM/CBS levels are source/normalized | layer shown in the tooltip ("gemeten" / "afgeleid"); historical views carry a permanent "historisch, niet gelijk te stellen met de actuele reeks" notice until Project Control decides otherwise |

## 3. Definition and methodology breaks requiring a visible UI annotation

| # | Break | Period | Applies to | Annotation |
|---|---|---|---|---|
| B1 | Statistic and population change: NVM median -> CBS mean | overlap starts 1995-01 | any view showing both | "NVM = mediane verkoopprijs (makelaars), CBS = gemiddelde verkoopprijs (alle registraties); niet onderling vervangbaar" |
| B2 | Frequency: half-year vs monthly | whole historical view | NVM panels | "halfjaarcijfers; geen maandwaarden" |
| B3 | Denomination: NLG original -> retrospective EUR | euro era starts 1999-01 (gold FX), physical euro 2002-01 (CBS housing) | NVM, CBS before 2002, gold before 1999 | "omgerekend tegen 2,20371 NLG/EUR; geen waargenomen europrijs" |
| B4 | FX source: Fed H.10 (to 1998-12-31) -> ECB (from 1999-01-04) | 1998-12/1999-01 | gold phase | "bronwisseling wisselkoers" |
| B5 | Gold quality level changes | 1978/1979, 1998/1999 | gold phase | quality badge B / A / E |
| B6 | NVM page-135 values (41) visually verified by Project Control | 1975-H1..1995-H1 | NVM | "handmatig gecontroleerd" marker |
| B7 | Boundary to the current dashboard | 2000-01 | CBS, current view | explicit end of the historical view; no connecting line |
| B8 | Production months 2000-2001 are retrospective euro for housing | 2000-01..2001-12 | **existing** current view | currently NOT annotated (labelling gap in production; separate decision HP2b, ORANJE) |
| B9 | Partial final month rule (`PARTIAL_FINAL_MONTH`) | latest month | gold phase | existing rule, no new annotation |

## 4. Index base and currency treatment

- **Production base stays January 2000 = 100** for `gold_index` and `hpi_index` (ADR-004, immutable; a missing base blocks calculation). Nothing here changes it.
- **Housing index before 2000:** CBS 85773NED carries no HPI before 2000. A price-level index built from the CBS mean or the NVM median would be an `average_price`/`median_price`-based index; the model forbids relating those to a `constant_quality_index` (`INCOMPATIBLE_KINDS`). So no HPI extension exists; a Kadaster/NVM index-only presentation (D4) is not obtained.
- **Gold index before 2000:** on the retrospective-EUR route it is computable relative to 2000-01, but it is part of the pre-2000 gold decision (GOLD-01/-03 exclude pre-2000 gold values, ADR extension is ROOD). Within the NLG era an index of the guilder gold price and an index of the retrospective-EUR price are identical (the constant 2.20371 cancels in a ratio), but the base month 2000-01 lies in the ECB era, so any index across 1998/1999 inherits the FX-source break B4.
- **Options for historical indexes:** (a) a common approved reference period — the only candidate is 2000, which already is the production base; (b) distinct historical indexes with their own explicit base (for example "2000-H1 = 100, NVM") — acceptable only as separately labelled, non-comparable-to-CBS-HPI series; (c) **no index chart until comparability is resolved**. **Recommendation: (c) for the first historical release.** Nominal levels and, later, grams of gold carry the story without a new base.
- **Implications of the denomination:** nominal levels in NLG and retrospective EUR differ by the constant 2.20371 only, so shape is identical but the unit label matters. **Grams of gold per house are denomination-invariant** (NLG route equals retrospective-EUR route, max relative difference 8.3e-34); the currency transition therefore affects nominal levels and the FX source, not the grams construction, except for the definitional step 1998/1999 (NVM grams +8.22%, CBS grams +1.53%, partly unquantifiable). Index comparisons across the transition inherit that step.

## 5. Can CBS 1995-1999 safely extend the CBS nominal series?

- **Technically and statistically, yes for the nominal level `house_eur`:** same publisher, same table (85773NED), same statistic, 72/72 months, counts reconcile with the 24 official quarterly counts, 0 conflicts with the existing series, 2000 values equal.
- **Not silently:** (1) the series would have no HPI, no gold index and no gold grams for 60 months; (2) values before 2002 are retrospective euro (and so are production 2000-2001, currently unlabelled); (3) the pre-2000 months are a pinned vintage (CBS revises; ADR-005 PROPOSED); (4) CBS definition notes for 1995-2000 were not inspected (NOT VERIFIED, read-only follow-up); (5) the public contract and the BTC release identity change (section 7).
- **Conclusion:** possible as a clearly labelled separate historical series; extending the main `monthly.json` series is a separate ROOD decision and is **not recommended now**.

## 6. Independent QA of the comparability design

| Risk | Finding | Mitigation |
|---|---|---|
| Silent median/mean splicing | model forbids; UI must not draw one line | separate series, separate panels, notice B1 |
| Artificial monthly interpolation | `convert_frequency` refuses; NVM stays half-year | no monthly NVM; negative tests |
| Confusing index bases | production has 2000 and 2020 bases already | no historical index chart (4.c) |
| Currency conversion errors | direction encoded in unit; 2.20371 applied once; routes proven equal | keep tests; label retrospective EUR |
| Hidden source discontinuities | Fed->ECB, quality levels, CBS notes | break table B1-B9 drawn/listed |
| Misleading trend lines | lines across breaks or across a null | gaps stay gaps (`connectNulls` false); no trend/regression overlays |
| Missing quality labels | model carries `quality` + flags per point | UI shows badge and flag marker per point |
| Unauthorized exposure | raw source rows are never published (`publication_gate`); research bundles are 14-day artifacts | separate payload, hash-pinned |
| Production gold/CBS change | out of scope | `monthly.json` untouched; parity tests |
| Bitcoin interference | see below | historical data in a separate file |

## 7. Finding: the legacy public hash is bound into the BTC release

`etl/btc_contract.py` pins `LEGACY_PUBLIC_SHA256` (`1afb0bf9…91d8cd`, the current `monthly.json`). The approved D07 BTC identity binds `legacy_projection_sha256`, the rollback target and the composite payload (which embeds those 320 legacy rows). **Any change to `monthly.json` content — including prepending 1995-1999 rows — changes that hash and invalidates the approved BTC release identity (new candidate, new composite hash, new D07).** This is the decisive argument for keeping historical observations in a **separate static file** and leaving `monthly.json` byte-identical.
