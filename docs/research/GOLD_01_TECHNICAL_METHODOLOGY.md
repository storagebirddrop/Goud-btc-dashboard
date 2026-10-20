# GOLD-01 publication readiness: technical and methodological assessment

Status: research only. **Nothing in this document is approved.** The gold publication HOLD in the repository is untouched: no ADR, DECISIONS.md, `etl/`, `data/`, `frontend/`, workflow or `monthly.json` change. ADR-004 (gold, ACCEPTED 2026-10-18) is neither amended nor reinterpreted. Rights are only listed as open questions (workstream L). Assessment date 2026-10-20; repository base `3f9aee3` (main). Owner scope under assessment: GOLD-01 limited decision of 2026-10-19 (`gold_index` and `gold_grams_per_house` only, from 2000-01; no `gold_eur_oz`, no raw USD/oz, no pre-2000 values), which itself states "no merge/deploy without separate explicit permission".

Labels: **CONFIRMED FACT** (code/test/CI run, with reference), **ASSUMPTION**, **OPEN LEGAL QUESTION** (listed only), **TECHNICAL DEFICIENCY** (severity H/M/L, smallest fix). Governance class of any fix: GROEN/ORANJE/ROOD per `CHANGE_CONTROL.md`.

## 0. Verdicts

| Question | Verdict | One-line reason |
|---|---|---|
| Technically ready? | **READY WITH CONDITIONS** | The candidate pipeline is deterministic, fail-closed and reproduced twice on live sources (320 complete months, 0 pending). The publication change itself (regenerated JSON, pins, CI, tests, frontend text) does not exist yet and breaks CI as it stands; see section 3 and checklist 3.3. |
| Methodologically ready? | **READY WITH CONDITIONS** | The method is decided (ADR-004) and implemented without deviation. Conditions: no independent 2000+ validation, the June 2025 break is annotated but unquantified, source-revision policy and rounding/back-calculation stance are undecided (section 5). |
| Overall | **NOT approved, HOLD intact** | Both "ready with conditions" verdicts are readiness statements, not authorization. Rights (workstream L) and owner sign-off on an exact candidate hash remain separate gates. |

## 1. Live review runs (existing workflows, dispatched on `research/gold-01-publication-readiness` at `3f9aee3`)

Both workflows are `contents: read`, upload artifacts only, and end with `git diff --exit-code -- data/cbs-housing.csv frontend/public/data/monthly.json` (step green in both runs: no public change). Raw sources are never uploaded.

| Run | Result (CONFIRMED FACT) |
|---|---|
| GOLD-01: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39486174734 (success, artifact 12292544479) | 21 gate tests passed; World Bank workbook 586,099 bytes, sha256 `ea1c3508...3154`; ECB csv 1,433,941 bytes, sha256 `31007867...daad`; `total_months` 320, `gold_complete_months` 320, `gold_pending_months` 0; candidate `monthly.gold-review.json` sha256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`; manifest sha256 `490bdf37...afd`; `publication_authorized: false`. |
| GOLD-02: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39486179684 (success, artifact 12294450088) | Full pytest, frontend build, then `GOLD_02B_INDEPENDENT_PASS`: same candidate sha256 `1afb0bf9...d8cd` (reproduced by an independent run, 80 s apart, byte-identical); independent replay 320 months / 640 indicator values: 1 exact, 639 within tolerance, 0 out; max absolute deviation 3.55e-12, max relative 1.89e-16 (float64 JSON versus Decimal). Server headers: World Bank `Last-Modified` Fri 02 Oct 2026 18:57:55 GMT (no ETag); ECB `Last-Modified` Tue 20 Oct 2026 13:57:02 GMT. |

Limits of this evidence: the artifact zip could not be downloaded from the sandbox (proxy 403), so the values above come from job logs only. The "independent" replay uses the same downloaded bytes and the same sources (own parser and formula code, `tools/verify_gold_02_independent.py:1-5, 238-261`); it proves code independence, not source independence.

## 2. Technically ready?

### 2.1 ADR-004 conformance, line by line

| ADR-004 text | Code | Result |
|---|---|---|
| World Bank `GOLD`, USD/oz monthly mean | `etl/sources/worldbank_gold.py:8` (URL), `:56-57` (period filter, `Decimal(rawvalue)`); sheet chosen by name containing "monthly prices", column by header cell equal "GOLD" (`:19-42`) | CONFIRMED FACT conforms. ASSUMPTION: the workbook column is the ADR-described series (headers and notes sheet are not asserted by code). |
| ECB `EXR.D.USD.EUR.SP00.A`, USD per EUR, mean of present valid days, no calendar divisor, no ffill/interpolation | `etl/gold_monthly.py:9` (URL), `:17-34` (`sum(vals)/len(vals)` per month; empty `OBS_VALUE` skipped; duplicate, non-positive or non-finite raises) | CONFIRMED FACT conforms; offline tests `tests/test_gold_01_readiness.py::test_ecb_monthly_mean_uses_only_present_days_without_imputation`, `::test_empty_ecb_observation_is_skipped_not_filled`, `tests/test_gold_monthly.py`. |
| `gold_eur_oz = usd/fx`; gram = `/31.1034768`; `grams_per_house = house/gram`; `index = 100*eur/eur[2000-01]` | `etl/gold_monthly.py:10, 68-80`; Decimal precision 28 (`:8`) | CONFIRMED FACT; `::test_adr004_formulas_exact_in_decimal`. |
| Base 2000-01 = 100, missing base blocks | `etl/gold_monthly.py:69-75`; `etl/static_export.py:19-` (`validate_gold`, base check) | CONFIRMED FACT. |
| Exact `YYYY-MM` join, only complete historical months, historical gap is an error, trailing lag is `pending_publication` | `etl/gold_monthly.py:55-67, 81-89`; `etl/gold_publication_candidate.py:34-45` (coverage must equal the approved CBS calendar; pending only trailing) | CONFIRMED FACT; tests `tests/test_gold_publication_gate.py`, `tests/test_gold_01_publication.py`. |
| Decimal | Decimal through the candidate; **float64** in the public JSON (`static_export.py` `validate_gold` returns `float(grams)`, `float(idx)`) | Deviation of representation only: measured relative error <= 1.89e-16 (run 39486179684). Not a methodological deviation. |
| Coverage calendar bounded by CBS publication | `etl/gold_publication_candidate.py:110-123, 34-36` (all sources cut at last approved CBS month; must equal JSON periods) | CONFIRMED FACT. Live: 2000-01..2026-08, 320 months, none pending. Consequence: a new CBS month cannot be added without re-pinning (3.2). |

Conclusion: no deviation from ADR-004 found. The CBS side (`house_eur`) is used as committed (`data/cbs-housing.csv`, sha256 `ad98bba9...d8f6`).

### 2.2 Source handling and revisions

| Item | Finding |
|---|---|
| World Bank URL is versioned (`74e8be41...-0050012026`) | CONFIRMED FACT: the same URL returned byte-identical content (sha256 `ea1c3508...3154`) in runs 39486174734 and 39486179684 and equals `KNOWN_WORKBOOK_SHA256` of the HIST-03/04/05 research (`tools/hist_03_worldbank_validate.py:211`). So the URL serves a frozen file; the workbook already holds all months to at least 2026-08 although `Last-Modified` is 2 Oct 2026. |
| What happens if the World Bank publishes a new workbook | ASSUMPTION: a new release gets a new URL token and the old URL keeps serving the old file (consistent with the constant hash over several days, not proven for the future). Then new months and revisions of old months are **not** picked up automatically; a switch needs a code change to `URL` (in three places: `worldbank_gold.py:8`, `tools/verify_gold_02_independent.py:22`, `tools/hist_02_acquire.py:24`). If instead the file at the same URL were replaced, nothing in `etl/` compares the hash. |
| TECHNICAL DEFICIENCY T-1 (M) | **The production code records but never enforces the World Bank workbook hash.** `acquire()` prints the sha256 (`gold_monthly.py:15`), manifests copy it, but no constant is compared (the only pinned workbook hash lives in research tooling under `tools/`). A silently revised workbook would produce a different candidate that still passes every gate; it would be caught only by the owner comparing `candidate_json_sha256` with the approved one. Smallest fix: add `EXPECTED_WORLD_BANK_SHA256` to the candidate builder (fail closed unless an explicit `--accept-source-revision`), ORANJE (it adds a gate; a changed pin is ROOD data). |
| ECB response | The ECB hash changes whenever a day is appended (1,433,941 bytes today), so it cannot be a fixed pin. CONFIRMED FACT that candidate bytes stay identical as long as days up to 2026-08 are unchanged (two runs). TECHNICAL DEFICIENCY T-2 (L): ECB revisions of past daily rates would silently change the candidate. Smallest fix: snapshot per-month `usd_per_eur` and `fx_days` in the release record and compare in the review run (GROEN/ORANJE). |
| ECB monthly mean definition | CONFIRMED FACT: arithmetic mean over published daily reference-rate days (TARGET days); the code accepts any month with at least one day and does not check `KEY`, `FREQ` or `OBS_STATUS` (only `CURRENCY`/`CURRENCY_DENOM` when present, `gold_monthly.py:22`). TECHNICAL DEFICIENCY T-3 (L): `fx_days` is stored but only required to be `> 0` (`static_export.py` `validate_gold`); `tests/test_gold_01_readiness.py::test_no_minimum_fx_day_count_exists_for_a_month` documents that a one-day month is accepted. ADR-004 sets no minimum, so adding one is a policy choice (ROOD-adjacent); smallest GROEN fix: report min/median `fx_days` in the manifest. |
| ECB monthly cross-check (own mean versus ECB `M.USD.EUR.SP00.A` monthly average) | Not done for 2000+ in `etl/`. Research exists only for 1999 and earlier months (`HIST_04_FX_SOURCES.md`, Eurostat versus ECB: max relative deviation 5.28E-5 on common months, scope per that document). TECHNICAL DEFICIENCY T-4 (L): add the ECB monthly series (and Eurostat `ert_bil_eur_m`) as an advisory comparison in the GOLD-02 review job. |

### 2.3 What the existing gates verify, attest, or do not cover

| Gate | Verifies (by code) | Only attests / cannot show |
|---|---|---|
| Baseline pins `etl/gold_publication_candidate.py:17-18, 27, 110` | exact bytes of `cbs-housing.csv` and `monthly.json` | that the CBS data are right |
| `render()` `:25-92`; `make_bundle` `etl/gold_02_release.py:21-83` | calendar equals CBS, non-gold fields unchanged, `gold_eur_oz` null, 2000-01 index 100, gold-only diff, no pre-2000 gold, schema keys equal | the manifest `integrity` block (`gold_02_release.py:71-76`) is hard-coded `"PASS"` text; true only because failures raise earlier. TECHNICAL DEFICIENCY T-5 (L): make these values computed. |
| `validate_gold` `static_export.py:19-` | formula identity for every month against candidate inputs, base, finite/positive | input values themselves |
| Env + CLI gate `static_export.py:15-17, 70, 129-136` | `GOLD_PUBLICATION_ENABLED=="true"` and `GOLD_PUBLICATION_APPROVAL=="APPROVED"` and `--approve-gold-publication` (case-sensitive, tested in `tests/test_gold_export_integration.py`) | who approved; the flags are plain environment variables |
| `etl/data_quality.py` release-record mode `:101-211` | exact record schema, artifact sha256, CBS sha256, month count/first/last, JSON-v1 schema, non-gold fields equal `build(csv)`, contiguous gold block from 2000-01, index base 100, `grams*index/house` constant (`:39-74`), no non-finite tokens | SOURCE hashes (World Bank, ECB), "METHODOLOGY APPROVED", "PUBLICATION AUTHORIZED" are **attested by the record, not verified by code** (stated in `:5-11`); the constant-product check cannot detect a wrong but internally consistent series; only the artifact hash fixes the reviewed bytes |
| Preflight `data_quality.py:214-216, 301-307` | same checks without authorization; always ends with exit code 3 and the text "PUBLICATION NOT AUTHORIZED" | cannot authorize by design |
| GOLD-02B replay `tools/verify_gold_02_independent.py:153-217` | recomputes both indicators from raw bytes (separate parsers), tolerance 1e-9 abs or 1e-12 rel | not a second data source |
| Determinism | two live runs gave identical candidate sha256 | not tested against a changing source |

Missing controls (summary): independent source for 2000+ (CONFIRMED FACT: the only second-source comparisons are HIST-03/04, `tools/hist_03_second_source.py:1,19-20` restricts to 1975-01..1999-12, BoE daily series end 1999-12); World Bank values 2000+ precision not examined (the research reports "0 non-integer values" and whole-USD rounding for 1975-1999 only, `HIST_04_GOLD_NLG.md` section 2; ASSUMPTION that 2000+ values carry decimals, not verified: TECHNICAL DEFICIENCY T-6 (M), smallest fix: add count of non-integer values and a decimals histogram for 2000+ to the review summary, aggregates only, GROEN); workbook notes/definition text not asserted (T-7, L). The three BoE outliers (1980-12, 1983-07, 1985-03) lie outside the 2000+ window (CONFIRMED FACT, `HIST_04_GOLD_OUTLIERS.md`) and do not affect the candidate; their cause (World Bank versus BoE) is still UNVERIFIED, so the 2000+ window cannot be assumed free of similar World Bank-side anomalies.

### 2.4 Public data contract consistency

| Layer | State (CONFIRMED FACT) |
|---|---|
| JSON-v1 columns | `period, gold_eur_oz, house_eur, hpi, gold_grams_per_house, gold_index, hpi_index` in `static_export.py` `build`, `data_quality._check_rows` (`:146`), `gold_02_release.py:37` (schema equality), `DATA_CONTRACT.md` (lists the same old-object fields), `frontend/src/series.ts:21` `Point`. Consistent. |
| Defaults | `gold_*` null in committed JSON; default `data_quality` rejects any non-null gold (`_check_rows(rows, False)`). |
| Frontend registry | `gold_index`, `gold_grams_per_house` are `publication:'gated'` (`series.ts:35-36`); visible only if the JSON holds a finite value (`visibleKeys`, `:63-65`); `gold_eur_oz` is not registered (`:16`). |
| Contract note | `DATA_CONTRACT.md` describes v2 as `PROPOSED` and v1 as current; it does not mention that v1 may hold two derived gold fields. Documentation gap D-1 (see 5). |

### 2.5 Back-calculation and derivation transparency

- CONFIRMED FACT (`tests/test_gold_01_readiness.py::test_public_gold_fields_allow_exact_backcalculation_of_eur_per_oz`): from the public fields alone, `gold_eur_oz[m] = house_eur[m] * 31.1034768 / gold_grams_per_house[m]` is recovered to relative 1e-12, and `gold_index` gives the same series up to the constant `eur[2000-01]`. With the public ECB monthly means, USD/oz is also derivable. So "`gold_eur_oz` stays null" is a presentation choice, not a technical protection. TECHNICAL/METHOD item B-1 (see 5).
- CONFIRMED FACT (`::test_validate_gold_returns_unrounded_floats`): values are published at full float64 precision with no rounding policy. Rounding would reduce the exactness of back-calculation only marginally (4 decimals of grams still gives about 1e-7 relative accuracy). Any display or JSON rounding policy is a ROOD decision (publication meaning).
- Per-month provenance (`fx_days`, `usd_per_eur`, source hashes) exists only in the private candidate and artifact manifest, not in the public JSON (by design: no raw inputs public). The public JSON carries no `generated_at`, source version or methodology version (DATA_CONTRACT v2 fields are PROPOSED only).
- `static_export.main` accepts `--gold-candidate` = the **private** candidate (contains `gold_usd_oz`, `usd_per_eur`, `gold_eur_oz`); no committed tool writes it except `etl/gold_backfill.py --output` (refuses `frontend/public`). The GOLD-01/02 artifacts are the public-shaped JSON. Two possible publication paths exist (regenerate from the private candidate, or copy the reviewed public-shaped bytes under a release record); the process documents do not pick one. TECHNICAL DEFICIENCY T-8 (M, documentation/process; GROEN to document, ROOD to choose): the GOLD-02 checklist should state the chosen path. Only the release-record path binds the published bytes to a reviewed artifact hash.
- `render()` temporarily sets the two env flags in the process (`gold_publication_candidate.py:48-58`) and restores them; tested. Low risk, noted for review.

## 3. Publication mechanics (no step performed)

### 3.1 What changes automatically on publication (frontend)

| Item | Behavior (CONFIRMED FACT from `series.ts`, `main.tsx`) |
|---|---|
| Visibility | Both gold series become visible as soon as the loaded JSON has at least one finite value (`series.ts:63-65`); cards, chart views "Goudprijsindex" / "Gram goud per woning", table columns. The "missing: goud" hint disappears (`main.tsx:125-126`). |
| June 2025 annotation | `WB_GOLD_BREAK` (`series.ts:29`) text "jun 2025: bronwijziging goud"; drawn only when the chart view contains a gold series with values on both sides inside the shown range (`viewAnnotations`, `:108-117`). |
| Sources text | Chart line "Bron: World Bank / ECB, eigen berekening" (`series.ts:35-36`, `main.tsx:131,155`). Full text in the collapsed "Bronnen & methode" section: World Bank GOLD link, ECB series link, own computation, "geen bronorganisatie onderschrijft deze toepassing", and the June 2025 definition paragraph (`main.tsx:169-171`), shown when `hasGold`. |

### 3.2 Attribution versus `GOLD_PUBLICATION_DECISION.md` required text and the owner decision

| Required element | Present? |
|---|---|
| World Bank Pink Sheet GOLD, USD/troy oz | yes (link and text, `main.tsx:170`) |
| ECB EXR.D.USD.EUR.SP00.A (USD per EUR) | yes |
| CBS StatLine 85773NED | yes in the CBS paragraph (`main.tsx:166`); the chart source line for `gold_grams_per_house` names "World Bank / ECB / CBS" |
| Own transformations (monthly aggregation, FX conversion, indexing, gram per home) | yes ("Maandgemiddelden, omrekening, indexering en gram per woning zijn eigen berekeningen") |
| Not endorsed by the source organisations | yes |
| Definition change June 2025, with the full wording (fixing until May 2025, spot averages from June 2025, "not fully benchmark-homogeneous") | partial: full wording only in the collapsed section; the chart annotation is the short label |
| "Zie bronlinks, methodologie en peildatum" | **partial/missing**: no methodology link (the section is titled "Bronnen & methode" but links only sources), and **no as-of date (peildatum)** anywhere, because the JSON carries no date. TECHNICAL DEFICIENCY T-9 (M): a frontend text/field change is needed before publication (ORANJE; adding a date field to JSON would change the contract = ROOD). |
| "Visible near the chart or via directly visible source information" | the section is closed by default (`open` state false, `main.tsx:162`); only the one-line source is directly visible. Whether that satisfies the owner's wording is an owner/L judgment. |

### 3.3 Checklist of steps and switches that a release would need (none performed)

| # | Step | Class | Evidence / note |
|---|---|---|---|
| 1 | Rights position settled or explicitly accepted (owner 2026-10-19 accepted risk; not legal proof) | ROOD / L | `DECISIONS.md` GOLD-01 entry |
| 2 | Owner decisions in section 5 (rounding, `gold_eur_oz` stance, source-revision policy, ECB minimum days) | ROOD | |
| 3 | Fresh review run on the exact release commit: GOLD-01 and GOLD-02 workflows; record candidate sha256 (today `1afb0bf9...d8cd`), World Bank and ECB hashes, run URLs, artifact id | GROEN | runs above |
| 4 | Release record JSON (exact keys, `data_quality.py:30, 101-143`): `artifact.sha256/months/first_period/last_period`, `fields_published == ["gold_index","gold_grams_per_house"]`, `methodology == ADR-004/ACCEPTED`, `sources` (World Bank, ECB, CBS sha), `candidate_validation{candidate_sha256,review_run,result:"PASS"}`, `release_authorization{status:"AUTHORIZED",authorized_by,authorized_at,reference}`. No tool creates it; it is hand-written, so every field is an attestation | ORANJE | `NOT_AUTHORIZED` is the safe state |
| 5 | Preflight rehearsal: `python -m etl.data_quality --gold-release-record REC --preflight` must end exit 3 with "PUBLICATION NOT AUTHORIZED" after all hash/content checks pass | GROEN | `data_quality.py:214, 301-307` |
| 6 | Replace `frontend/public/data/monthly.json` with the reviewed candidate bytes (release-record path) or run `python -m etl.static_export --gold-candidate PRIVATE --approve-gold-publication` with `GOLD_PUBLICATION_ENABLED=true` and `GOLD_PUBLICATION_APPROVAL=APPROVED` | ROOD | publication step |
| 7 | Authorized validation: `GOLD_PUBLICATION_ENABLED=true GOLD_PUBLICATION_APPROVAL=APPROVED python -m etl.data_quality --gold-release-record REC --approve-gold` | GROEN | |
| 8 | **Re-pin the public JSON hash**: `etl/gold_publication_candidate.py:18` `APPROVED_PUBLIC_JSON_SHA256` and `etl/cbs_historical_merge.py:15` `BASELINE_JSON_SHA256` (also used by `etl/cbs_historical_update.py:92, 99`, `.github/workflows/cbs-02-i2a-e2e.yml`, `tests/test_cbs_historical_merge.py`). Without it the CI step "Offline 380-month CBS E2E review-only replay" (`ci.yml:27-33`) fails closed on hash mismatch. Changing committed data and these pins is not GROEN | ROOD | CLAUDE.md note |
| 9 | **CI default check**: `ci.yml:42` runs `python -m etl.data_quality` in default mode, which rejects non-null gold; it must switch to the release-record mode (workflow edit; the env flags would have to be set in CI, which weakens the "flags are off by default" posture and needs a deliberate design) | ROOD | `data_quality.py:259-285` |
| 10 | Tests that assert null gold in committed data must change together: `tests/test_frontend_series.py:100-107`, `tests/test_gold_export_integration.py:21`, `tests/test_data_quality_gold_release.py:106, 336, 473` (real-JSON tests), `tests/test_gold_01_publication.py:16-18`, plus the 2000-01 JSON parity check in `static-data-live-smoke.yml` (regenerates a null-gold JSON on the runner; not committed) | ORANJE | |
| 11 | Frontend text per 3.2 (peildatum, methodology link, visible break wording), then `npm run build`; confirm `viewAnnotations` draws the 2025-06 marker | ORANJE | |
| 12 | Docs consistency (`DATA_SOURCES.md:12,47`, `PROJECT_STATUS.md:84` still say HOLD/blocked; `GOLD_02_RELEASE_CHECKLIST.md` lacks a path choice) | GROEN | Dutch core governance docs are owned elsewhere |
| 13 | Rollback pack per `GOLD_02_RELEASE_CHECKLIST.md`: previous JSON bytes and sha256 `bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e`, deployed commit, no refetch on rollback | GROEN | |
| 14 | Separate explicit owner permission for merge/deploy on the exact candidate hash | ROOD | owner decision text |

The pin consistency answer: **no**, today's pinned hashes in `etl/` identify the **null-gold** JSON (verified equal: `monthly.json` sha256 `bc15f3bd...c78e`, CSV `ad98bba9...d8f6`). A release necessarily invalidates them (steps 8 and 9); this is a ROOD change by project rule, not a defect.

## 4. Conditions summary (technically ready with conditions)

Blocking for a release PR (not for the review state): T-8 path choice, steps 8-11 above. Strongly recommended before release: T-1 (enforce or explicitly accept the World Bank hash), T-6 (precision of 2000+ values), T-9 (peildatum and methodology link). Nice to have: T-2, T-3, T-4, T-5, T-7.

| ID | Severity | Smallest fix | Class |
|---|---|---|---|
| T-1 | M | Pinned World Bank workbook hash constant, fail closed unless explicit revision acceptance | ORANJE |
| T-2 | L | Snapshot monthly ECB mean and `fx_days` in the record, diff in review | GROEN |
| T-3 | L | Report min/median `fx_days` per run (a minimum threshold itself is a policy decision) | GROEN / ROOD |
| T-4 | L | Advisory comparison to ECB monthly average / Eurostat in the review job | GROEN |
| T-5 | L | Compute manifest `integrity` values | GROEN |
| T-6 | M | Aggregate precision report for World Bank 2000+ | GROEN |
| T-7 | L | Assert sheet name, unit and GOLD header text from the notes | GROEN |
| T-8 | M | Document the single publication path | GROEN / ROOD |
| T-9 | M | Frontend: methodology link and as-of date source | ORANJE / ROOD |
| T-10 | M | CI/test/pin changes of steps 8-10 | ROOD |

## 5. Methodologically ready?

**READY WITH CONDITIONS.**

### 5.1 Already decided (do not reopen)

| Decision | Source |
|---|---|
| World Bank monthly mean USD/oz divided by the mean of valid daily ECB USD per EUR; base 2000-01 = 100; no imputation; only complete historical months; ratio of means, not mean of ratios | ADR-004 ACCEPTED 2026-10-18 (`DECISIONS.md`, `METHODOLOGY.md` section 3) |
| June 2025 definition change must be visibly annotated; no splice or correction | ADR-004; `tools/verify_gold_02_independent.py:285` ("no correction or splice applied") |
| Publish only `gold_index` and `gold_grams_per_house`, from 2000-01; exclude `gold_eur_oz`, raw USD/oz, pre-2000 gold; attribution; no merge/deploy without separate permission | GOLD-01 owner decision 2026-10-19 |
| 2000-01 is the current technical boundary and index base, not the project ambition | ADR-011 |

### 5.2 Findings

| ID | Label | Finding |
|---|---|---|
| M-1 | CONFIRMED FACT | The ratio-of-means semantics is documented and measured only for pre-2000 data (up to 0.21 % effect, `HIST_04_GOLD_NLG.md` section 5). For 2000+ nothing is measured in the repo. ASSUMPTION that the effect is of similar size. Advisory check possible (GROEN) with daily gold, which no approved source provides. |
| M-2 | CONFIRMED FACT | The June 2025 break is annotated in the frontend registry but its numeric effect on the series is unquantified: no overlap period or second source exists in the repo (fixing until May 2025, daily spot average from June 2025). ASSUMPTION that the step is small relative to month-on-month moves. ADR-004 requires annotation only; quantification would be new research. |
| M-3 | CONFIRMED FACT | No independent 2000-2026 comparison exists (BoE ends 1999-12 in the fetched data). The three 1980s BoE outliers show the World Bank series can deviate from a primary-like source by up to 9.6 %, cause UNVERIFIED. Owner decision needed on which independent check (if any) is a publication condition (ROOD: source priority/validation threshold; open question 5 in `DECISIONS.md` is still open). |
| M-4 | ASSUMPTION | 2000+ World Bank precision unknown (whole-USD rounding up to 0.45 % was shown for 1975-1999 only). Measurable via T-6. |
| M-5 | CONFIRMED FACT | Revision policy is undecided: ADR-005 (latest revised with raw snapshots) is `PROPOSED` and gold-specific revision handling is not in ADR-004. Practical consequence: the frozen workbook URL means the first release will be pinned to workbook `ea1c3508...3154` (data through at least 2026-08); the update policy for later months and for World Bank restatements needs an owner decision (ROOD). |
| M-6 | CONFIRMED FACT | Public JSON gives the reader enough to reconstruct EUR/oz and, with ECB data, USD/oz (section 2.5). The owner's "gold_eur_oz excluded" is therefore a presentation exclusion. Decision needed whether to (a) accept explicitly, or (b) change the published precision (ROOD). OPEN LEGAL QUESTION for L: whether reconstructability affects the third-party benchmark position. |
| M-7 | CONFIRMED FACT (documents) | `DECISIONS.md` carries two 2026-10-19 entries that could be read as conflicting: GOLD-SOURCE-REASSESSMENT (prioritize alternative-source comparison; "another source may need an ADR amendment") and GOLD-01 (limited publication with the current World Bank/ECB method). Owner should confirm that GOLD-01 supersedes the reassessment for the current release (ROOD; I do not infer it). |
| M-8 | CONFIRMED FACT | Honest-interpretation items already required: house price is the transaction-mix-sensitive CBS average (`METHODOLOGY.md` section 1, ADR-004 "CBS" bullet); frontend carries the CBS caveat and the "eigen berekening" note. `METHODOLOGY.md` section 7 requires a standard chart warning; the exact wording presence in the frontend was not audited here. |
| M-9 | ASSUMPTION | A month where ECB has few valid days (holiday weeks) is averaged over fewer days; effect on ratio-of-means is small but unmeasured (T-3). |

### 5.3 Owner decisions still needed (ROOD) versus not needed

| Needed | Not needed (already decided) |
|---|---|
| D1 Independent validation threshold for 2000+ (M-3), including whether a World Bank anomaly check is a release condition | Method and formulas (ADR-004) |
| D2 Revision/update policy for World Bank restatements and new months, and what is pinned (M-5, T-1) | Index base and window (ADR-004, ADR-011) |
| D3 Stance on reconstructability and published precision (M-6) | Limited field set and exclusions (GOLD-01) |
| D4 Confirm GOLD-01 supersedes the source reassessment for this release (M-7) | June 2025 annotation duty (ADR-004) |
| D5 Minimum ECB observation days per month, if any (T-3) | |
| D6 Whether the June 2025 break needs quantification or an additional visible note beyond annotation (M-2) | |
| D7 Release path and CI design for the published JSON (T-8, T-10, steps 8-9) | |
| D8 Display of peildatum / JSON date field (T-9; a new JSON field changes the contract) | |

## 6. OPEN LEGAL QUESTIONS (listed only, covered by workstream L)

1. Whether the World Bank can license the underlying London fixing / later spot average for derived public indicators (GOLD_PUBLICATION_DECISION, DECISIONS open question 2).
2. Whether two derived series plus public CBS and ECB data (reconstructable, section 2.5) fall under IBA derived-benchmark terms.
3. Whether the owner-accepted risk is sufficient for a public JSON download, as opposed to charts only.
4. Whether the attribution wording (3.2) satisfies World Bank, ECB and CBS terms.

## 7. Evidence and reproduction

- Review runs: 39486174734 (GOLD-01), 39486179684 (GOLD-02) as in section 1. No public file changed in either (workflow `git diff --exit-code` steps green).
- Offline: `python -m pytest -q` (891 passed, 4 skipped before adding `tests/test_gold_01_readiness.py`; 7 new tests), `python scripts/check_governance_docs.py` passed.
- New offline tests only document facts; they change no behavior and authorize nothing.
- Not executed: any publication step, any change to pins, flags, workflows or data. Sandbox cannot reach external hosts and could not download run artifacts; artifact contents beyond log output are NIET UITGEVOERD.
