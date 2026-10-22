# HIST-09 integration into HIST-08 / ARCH-02 (research only, nothing published)

Status: **RESEARCH ONLY. NOT AUTHORIZED FOR PUBLICATION.** Project Control accepted HIST-09 as `RESEARCH VERIFIED / CLOSED`; that authorizes research ingestion, not release and not a joined series. `ALLOWLIST` of `etl/hist_model.py` stays empty. No change to `frontend/public/data/monthly.json`, `data/cbs-housing.csv`, production gold, ADR-004 or any ADR.

Code: `tools/hist_09_bundle.py`; model additions in `etl/hist_model.py`; tests `tests/test_hist_09_bundle.py` (26). Inputs (small, hash-pinned, in Git per proposed D5): `data/fixtures/hist09/` (HIST-09 package and the original CBS export zip). Rebuild: `python -m tools.hist_09_bundle --inputs data/fixtures/hist09 --out OUT --cbs-csv data/cbs-housing.csv`.

## Verified inputs (SHA-256)

| File | sha256 |
|---|---|
| `85773NED-202609220630.zip` (owner-supplied CBS StatLine export, CBS catalogue licence CC BY 4.0) | `01d2aea00c19026e41b18ccd3a17b6beb004cd1b914a8a4a3f6683e15700584f` |
| `HIST09_NVM_1975_2000_RESEARCH.csv` | `099489a42548f81c009607d464756871d11b8a646bfc54d0a28e687e3d5dffda` |
| `HIST09_CBS_1995_2000_MONTHLY.csv` | `8ca8470b1128dd662cfa0e3013f4e6d3f69ee0a8c7915f6bef2ae5526280df85` |
| `HIST09_NVM_CBS_OVERLAP_1995_2000.csv` | `37d48f2027ce6047ba45ab5d1d82dcc1d9fcb7af669dd076f6fafb0c352ebfca` |
| `HIST09_VALIDATION_RESULTS.json` | `853a91b87ac64e8a90657c0fa3d4fc9b8c97393d5bd93e36c1d8badb070b1082` |
| `HIST09_FINAL_REPORT.md` | `4dbce423cc5c7690f5d6d2d3606d010f824af21e0b5391668ab9c9e411eed6ce` |
| `hist09_finalize.py` | `d05a28236bff3b1925c546632392b2e273c2bd718a2ca07012aec3acd75986e2` |
| `SHA256_MANIFEST.json` (lists the six files above, not itself) | `f9ca15412b6b6bcabc30fffd94c5495086e45a2a672d4cc83417faa60b8a280a` |
| OTB page 136 screenshot (owner-supplied; **not** stored in Git, publisher content) | `a994c666f00ce917bbeeab9743ae4bf5c38accbc8614a8e4151491306ef6049a` |

The adapter verifies all manifest entries, the pinned zip hash and the pinned NVM hash before it reads anything, and re-parses the **original CBS zip** itself (it does not trust the HIST-09 monthly CSV; it checks equality with it).

## Bundles (hist-model/1, deterministic)

| Bundle | Series (layer, frequency, currency/unit, kind, count) | sha256 |
|---|---|---|
| A `hist09_A_nvm.json` | `nvm_median_nlg_halfyear` (source, semiannual, NLG, median_price, 52, 1975-H1..2000-H2); `nvm_median_eur_halfyear` (normalized, EUR, redenomination only: `NVM_EUR = NVM_NLG / 2.20371`, applied once) | `5a11b7d0a89d6637434ae0a4e91c2f2899f63fc91a7430f62c8b8715aa0c479e` |
| B `hist09_B_cbs.json` | `cbs_avg_price_1995_2000` (source, monthly, EUR, average_price, 72), `cbs_sold_homes_1995_2000` (monthly, homes, transaction_count, 72), `cbs_total_value_1995_2000` (monthly, EUR_million, transaction_value, 72), `cbs_avg_price_eur_halfyear` (normalized, semiannual, transaction-weighted mean, 12) | `da95cf35d8ecdff84e7121d933b72d61c7ac770d16fa67e4cbb65b8b66843b2e` |
| C `hist09_C_overlap.json` | A and B members plus `nvm_over_cbs_ratio_halfyear` (derived, 12, ratio; gap % = (ratio-1)*100) and four growth-ratio series (sequential and year-over-year, NVM EUR and CBS half-year; 51, 50, 11, 10) | `33f5f15043084ac6154c184ee20a975b493c72b14e83e57c43f90c74d94ad3e9` |

Rebuilding twice gives byte-identical files; `tools/hist_model_check.py` returns OK for A, B and C. The bundle hashes change only if the adapter or the inputs change.

## Model changes (minimal, research-only; existing behaviour and tests unchanged)

New frequency `semiannual` (periods `YYYY-H1`/`YYYY-H2`); kinds `median_price`, `transaction_count`, `transaction_value`, `statistic_ratio`, `growth_ratio`; `average_price` x `median_price` added to the incompatible kinds, so a median and a mean can only be related through the explicit `statistic_ratio` (flag `STATISTICS_DIFFER`); `weighted_half_year_mean` (the only monthly to semiannual step: all six months with positive weights, otherwise an explicit null); `growth_ratio` (ratios, because model values must be positive). `convert_frequency` still refuses every conversion.

## Verified results (reproduced here from the pinned inputs)

* NVM 52/52 half-years preserved; the 11 values of page 136 (1995-H2..2000-H2) re-read by me from the owner screenshot and equal to the csv; 1975-H1..1995-H1 (41 values, page 135) carry flag `VISUAL_P135_PER_PROJECT_CONTROL`: their visual verification was performed in the earlier HIST-09 execution and **was not reproduced here** (the page 135 image was not supplied to this session). All values carry `quality CONFIRMED`, source OTB 2001 Table B3.8, statistic nominal median existing homes, NLG; population NVM brokers / Vastgoedmarkt / press reports (as printed under the page 136 table).
* CBS 72/72 months for each of price, count and total value, all positive; monthly counts equal every one of the 24 official quarterly counts.
* 12/12 overlap rows reproduced exactly (6 decimals), including levels, gaps, sequential and year-over-year growth; independent Fraction recalculation of 1995-H1, 1996-H1, 2000-H2 in the tests. NVM above CBS in 11/12 half-years; mean gap +7.1273%, range -0.0885% to +10.5214%.
* HIST-08 reconciliation: the existing CBS series (fixture 1995-1999: 60 observations; committed csv 2000: 12 observations) equal the HIST-09 prices; **0 conflicts**. HIST-09 series are separate series with their own ids; nothing is merged or overwritten, no definition of an existing series changes.

## Not claimed / remaining questions (UNRESOLVED)

1. Page 135 (41 values) visual verification not reproducible here; accepted on Project Control's authority and labelled as such. Supplying that screenshot would remove the flag.
2. Table number "B3.8" and the population wording come from the HIST-09 report; the screenshot shows the column text "Nominale mediane verkoopprijs van bestaande koopwoningen, NVM-makelaars/Vastgoed en persberichten" but not the table number.
3. The NVM values 1975-1994 have no CBS counterpart; the 1995-2000 gap is 12 observations only and cannot justify a stitched series or an estimated pre-1995 mean (not done).
4. CBS euro values before 2002 are retrospective (flag `RETROSPECTIVE_EUR`); NLG originals were not obtained. The CBS export time (2026-09-22 06:30) is taken from the file name.
5. Rights: CBS catalogue licence CC BY 4.0 (CONFIRMED in the export); OTB/NVM table rights UNVERIFIED, so no publication.
6. How the median to mean relationship should be presented to users (if ever) is an owner decision (D1/D4); publication stays closed.
