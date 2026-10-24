# HIST-11 — Publication-readiness matrix (historical gold and Dutch housing prices)

Status: **READ-ONLY ASSESSMENT. HISTORICAL PUBLICATION: HOLD.** Baseline: `main` `19df5757ff702c4e7e940064859c3cbb8b5bf8ac`. No data, code, pin or record was changed. Price-free: no historical value is quoted here except the already documented statistics. Research approval is never read as publication approval (`HIST_10_DECISION_MEMO.md` decision 8; `etl/hist_model.py` `ALLOWLIST == ()`).

Legend: PASS / PASS WITH CONDITIONS (PWC) / HOLD (a decision or missing artifact blocks it) / FAIL / NOT VERIFIED (no evidence in the repository). Authority: PC = Project Control (owner), TECH = engineering.

## 1. Series under assessment and overall verdict

| ID | Series (research id) | Coverage | Technical | Publication |
|---|---|---|---|---|
| S0 | Production baseline: CBS average price, CBS HPI, gold index, gold grams (`monthly.json`) | 2000-01..2026-08 (320) | PASS (protected) | LIVE, untouched |
| S1 | NVM nominal median, NLG original (`nvm_median_nlg_halfyear`) | 1975-H1..2000-H2 (52, half-year) | PWC | **HOLD** (rights NOT VERIFIED; presentation undecided) |
| S2 | NVM median, retrospective EUR (`nvm_median_eur_halfyear`, NLG / 2.20371) | same 52 | PWC | **HOLD** (as S1; denomination label decision) |
| S3 | CBS average price, monthly (`cbs_avg_price_1995_2000`) | 1995-01..1999-12 (60; 2000 duplicates S0) | PWC | **HOLD** (scope/contract decision; CC BY 4.0 attribution to define) |
| S4 | CBS transaction counts / total value, monthly | 1995-01..2000-12 | PWC | HOLD (no approved use; not needed for a first release) |
| S5 | NVM/CBS overlap comparison (`nvm_over_cbs_ratio_halfyear`, growth ratios) | 1995-H1..2000-H2 (12) | PWC | **HOLD** (side-by-side presentation undecided, HIST-10 decision 5) |
| S6 | Historical gold in local currency (NLG era / observed EUR / retro EUR) | 1975-01..1999-12 and 2000+ | PWC (research only) | **HOLD** (GOLD-01/-03 exclude pre-2000; ROOD ADR needed) |
| S7 | Grams of gold per house, NVM median route | 1975-H1..2000-H2 | PWC | **HOLD** (depends on S1, S6) |
| S8 | Grams of gold per house, CBS route (half-year and monthly 1995-1999) | 1995..1999 | PWC | **HOLD** (depends on S3, S6) |
| S9 | Historical indexes (gold or housing, any base) | none approved | n/a | **HOLD / no chart** (see comparability review) |
| S10 | Housing index-only 1970-1994 (Kadaster/NVM, D4) | not obtained | NOT VERIFIED | HOLD |

## 2. Criteria grid (the 12 required criteria)

Columns: 1 source identity, 2 rights, 3 methodology approval, 4 frequency, 5 currency/denomination, 6 statistic and population, 7 quality and coverage, 8 vintage reproducibility, 9 compatibility with production, 10 frontend interpretation risk, 11 release-contract requirements, 12 remaining decisions (see section 3 and `HIST11_OWNER_DECISION_PACK.md`).

| ID | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | PWC | NOT VERIFIED | HOLD | PASS | PWC | PWC | PWC | PWC | PASS | HOLD | HOLD | HD1-4, HP1, HP3-6 |
| S2 | PWC | NOT VERIFIED | HOLD | PASS | PWC | PWC | PWC | PWC | PASS | HOLD | HOLD | as S1 |
| S3 | PASS | PWC | HOLD | PASS | PWC | PASS | PASS | PWC | PWC | HOLD | HOLD | HD1-4, HP2 |
| S4 | PASS | PWC | HOLD | PASS | PWC | PASS | PASS | PWC | PASS | PWC | HOLD | deferred |
| S5 | PWC | NOT VERIFIED | HOLD | PWC | PWC | PWC | PWC | PWC | PASS | HOLD | HOLD | HP3 |
| S6 | PWC | NOT VERIFIED | HOLD | PASS | PWC | PWC | PWC | PWC | PWC | HOLD | HOLD | HG1-5 |
| S7 | PWC | NOT VERIFIED | HOLD | PWC | PWC | PWC | PWC | PWC | PASS | HOLD | HOLD | HG, HP1 |
| S8 | PWC | NOT VERIFIED | HOLD | PWC | PWC | PWC | PWC | PWC | PWC | HOLD | HOLD | HG, HP2 |
| S9 | NOT VERIFIED | NOT VERIFIED | HOLD | n/a | HOLD | HOLD | NOT VERIFIED | n/a | FAIL (if spliced) | HOLD | HOLD | HI |
| S10 | NOT VERIFIED | NOT VERIFIED | HOLD | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | n/a | HOLD | HOLD | HI |

## 3. Evidence, repository reference and smallest follow-up per status

**S1/S2 NVM (1975-2000).**
- 1 PWC: source OTB 2001 table B3.8 (nominal median existing homes, NLG; population "NVM-makelaars / Vastgoedmarkt / persberichten"). 41 values (1975-H1..1995-H1) rest on Project Control's page-135 verification and carry flag `VISUAL_P135_PER_PROJECT_CONTROL`; the table number is taken from the HIST-09 report. Ref: `HIST_09_INTEGRATION.md` (Verified inputs, Not claimed 1-2). Follow-up: owner supplies the page-135 image (removes the flag) or accepts the flag as a visible label (HP4).
- 2 NOT VERIFIED: rights for OTB/NVM tables UNVERIFIED (`HIST_08_OWNER_DECISIONS.md` D1/D7; `HIST_10_DECISION_MEMO.md` s.3). Follow-up: owner rights decision per source (HP1) — either permission or an explicit risk acceptance of the CM-10 kind, with attribution text.
- 3 HOLD: accepted only "for HIST-10 research" (decision 5: NVM and CBS stay separate; public presentation undecided). Follow-up: HD1-HD3.
- 5 PWC: guilder values are the observed unit; EUR = NLG / 2.20371 is a denomination (`HIST_10_GOLD_HOUSING.md` s.1), labelled `RETROSPECTIVE_EUR`. Follow-up: label rules in the UI spec.
- 8 PWC: input CSV and manifest hash-pinned in Git (`data/fixtures/hist09/`, csv sha256 `099489a4…dffda`); the printed-page screenshot is deliberately not stored; the transcribed values of a publisher table in Git are themselves a rights question (HP6).
- 9 PASS: no overlap with S0 (ends 2000-H2, half-year); no existing value touched.
- 10/11 HOLD: no half-year payload projection exists (`publication_rows` is monthly-only); see data-contract proposal.

**S3/S4 CBS 1995-1999.**
- 1 PASS: same table 85773NED, owner-supplied export (`01d2aea0…0584f`) and pinned fixture `data/fixtures/cbs-1995-1999-i1.json`; 72/72 months; monthly counts equal the 24 official quarterly counts; reconciliation with the committed series 0 conflicts (`HIST_09_INTEGRATION.md`).
- 2 PWC: CBS catalogue licence CC BY 4.0 confirmed in the export; needs attribution with the statement of own transformations (half-year aggregation, retrospective-EUR labelling).
- 3 HOLD: extending the public nominal CBS series backwards is a scope/time-boundary change (ROOD; ADR-011 is a vision decision "not for production implementation"). Follow-up HD1.
- 5 PWC: CBS euro values before 2002-01 are retrospective (NLG originals not obtained, flag `RETROSPECTIVE_EUR`). This is already true of production months 2000-2001 (S0), which today carry no such annotation (production labelling gap; decision HP2b).
- 6 PASS: same statistic as S0 (average price of sold existing homes, transaction-mix sensitive).
- 9 PWC: **definition continuity across 1999/2000 is not contradicted** (one table, 12/12 overlap rows and 2000 values equal) **but CBS table notes on any definition change within 1995-2000 were not inspected**: NOT VERIFIED sub-item; read-only follow-up: read the CBS table description for 1995-2000 (TECH, no decision).
- 9 additional: rows before 2000 have no HPI; any extension of `monthly.json` makes `hpi`, `hpi_index`, `gold_index`, `gold_grams_per_house` null for 60 months and breaks the strict export contract (no gaps, columns, base 2000-01) and — critically — the BTC-bound legacy hash (see comparability review s.7).

**S5 overlap.** 12/12 reproduced exactly; NVM above CBS in 11/12 half-years, mean gap +7.1273%, range -0.0885% .. +10.5214% (`HIST_09_INTEGRATION.md`). Statistical differences (median vs mean, population) explain the gap in part; not quantifiable further. Follow-up: HP3 (show or not), and fixed wording "not interchangeable".

**S6 gold.** GOLD-01/-03 publish only `gold_index` and `gold_grams_per_house` for months from 2000-01 and exclude gold values before 2000. Pre-2000 gold needs an ADR extending ADR-004 backwards (ROOD, `HIST_10_DECISION_MEMO.md` s.4). Sources: World Bank GOLD (whole USD; rounding up to 0.45% in 1975-1978, 0.22% in 1979-1998; accepted GOLD-03 scope is >=2000 only), Fed H.10 NLG/USD (noon-rate lineage and parser independence NOT VERIFIED; rights UNVERIFIED), ECB EXR (accepted for >=2000; "statistics not modified" needs explicit own-transformation wording). FX source change Fed -> ECB at 1999-01 is a discontinuity. Quality levels B (1975-78), A (1979-98), E (1999), ADR-004 period (2000+). A guilder-native gold price was not found. Follow-up: HG1-HG5 (deferred).

**S7/S8 grams.** Model reproduces production grams 2000-01..2026-08 within 9.75e-17 (`HIST_10_GOLD_HOUSING.md` s.4), so the chain is sound; NLG-route and retrospective-EUR-route grams are identical (max relative difference 8.3e-34), hence grams are denomination-invariant. The 1998/1999 step (NVM grams +8.22%, CBS +1.53%) has an unquantifiable definitional part. Follow-up: only after S6 decision.

**S9 indexes.** No approved historical index exists. Follow-up: none now (no index chart in the first release).

## 4. Smallest set of follow-up actions (all read-only or owner decisions)
1. TECH: read the CBS table notes for 1995-2000 definition changes (closes S3 criterion 9).
2. PC: HP1 NVM rights decision, HP4 page-135 handling, HD1-HD3 design/contract approvals.
3. Nothing else is needed before an inert (no-data) implementation.
