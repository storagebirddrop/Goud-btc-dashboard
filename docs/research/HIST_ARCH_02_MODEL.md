# HIST-ARCH-02: reusable historical data model (research design, PROPOSED)

Status: **RESEARCH / PROPOSED. Not a decision, not wired into production.** Created 2026-10-21 from `main` `0bfc040`. Reference implementation: `etl/hist_model.py`, tests `tests/test_hist_model.py`, optional CLI `tools/hist_model_check.py`. Nothing here changes `etl/static_export.py`, `data/cbs-housing.csv`, `frontend/public/data/monthly.json`, `DATA_CONTRACT.md`, `frontend/src/series.ts` or any ADR. Changing what is published remains ROOD (`CHANGE_CONTROL.md`) and needs the owner.

Labels: CONFIRMED = read in the repo at `0bfc040`; PROPOSED = design offered for owner review; OPEN = needs an owner decision.

## 1. Goal and constraints

Add house prices (annual and monthly), gold, Bitcoin, S&P 500, AEX, FX and CPI without a new publication pipeline per asset. Constraints (CONFIRMED): ADR-001 (GitHub Actions, validated files, static JSON, no database, no backend); `tests/test_static_architecture.py` (the frontend reads only `/data/monthly.json`); ADR-008 (missing stays null with reason); ADR-004 Decimal math; no raw third-party bytes in Git (`data/README.md`, DATA_01 rules); gold, Bitcoin and sat series stay `gated`/`withheld` until the owner decides.

The model is one Python module plus versioned JSON files. The expensive, asset-specific part is only the **adapter** that turns one pinned source file into layer 1 observations. Everything after that is shared and generic.

## 2. Four logical layers

```
 pinned raw bytes (NOT committed)        data/research/<asset>/...        PROPOSED, default empty
 raw_sha256 --> [1 source observations] --> [2 normalized series] --> [3 derived comparisons] --> [4 publication layer]
                 provenance per value       documented transforms       grams, sats, relative      ReleaseRecord allowlist
                 vintage, quality           lineage = input hashes      performance, one baseline  hash + authorizer + date
```

Each arrow is a pure function with Decimal arithmetic; each output carries `inputs = ((series_id, sha256), ...)` of what it was computed from, so a changed upstream byte changes every downstream hash.

### 2.1 Layer 1: source observations (`Series.layer == "source"`)

One `Series` object holds exactly one **vintage** of one series.

| Field (Observation) | Type | Rule |
|---|---|---|
| `series_id` | `[a-z][a-z0-9_]{0,63}` | equals the series |
| `period` | `YYYY` / `YYYY-MM` / `YYYY-MM-DD` | must match the series `frequency` and be a real calendar period |
| `value` | Decimal string | positive, finite; floats, NaN, Infinity rejected |
| `currency` | `NLG EUR USD INDEX NONE` | equals the series currency |
| `unit` | string | `EUR`, `NLG`, `EUR_per_troy_oz`, `EUR_per_BTC`, `USD_per_EUR`, `index_points`, ... equals the series unit |
| `definition_id` | string | names the definition document; equals the series |
| `source_id` | string | non-empty provenance |
| `raw_sha256` | 64 lowercase hex | SHA-256 of the pinned raw bytes (`tools/data_01_source_pin.py` `source_sha256`) |
| `retrieved_at` | ISO-8601 with timezone | as in the pin manifest (`retrieved_at_utc`) |
| `vintage` | string | one per series object; a new download is a new vintage |
| `quality` | `CONFIRMED PROPOSED INFERRED UNRESOLVED` | the labels the research reports already use |
| `flags` | tuple of `[A-Z0-9_:/=.-]` tokens | e.g. `PRELIMINARY`, `OUTLIER_FLAG`; flags annotate, they never alter values |

Series metadata (shared by all layers):

| Field (Series) | Meaning |
|---|---|
| `series_id`, `layer`, `asset_class` | `housing gold bitcoin equity fx cpi` |
| `frequency` | `annual monthly daily`; fixed per series |
| `currency`, `unit` | see above; `INDEX` requires `index_base` such as `2000-01=100`; `NONE` marks dimensional results (gram, satoshi) |
| `definition_id`, `kind`, `basis` | the **definition kind** (below) and `nominal` or `real` |
| `breaks` | `(Break(period, reason), ...)` methodology and source breaks (for example the World Bank gold change in 2025-06) |
| `observations` / `points` | layer 1 rows / layer 2-3 rows |
| `inputs`, `transforms` | lineage hashes and ordered transformation records (layers 2-3 only) |

**Definition kinds** (never mixed implicitly): `average_price` (CBS/NVM average sale price level), `constant_quality_index` (CBS HPI), `spot_price`, `price_return`, `total_return`, `fx_rate`, `cpi`; plus `basis` `nominal` vs `real`. The model refuses: average-price with constant-quality index in one comparison; price-return with total-return; nominal with real; an index where an absolute price level is required (`grams_per_house` demands `average_price`, consistent with the PROPOSED ADR-003).

### 2.2 Layer 2: normalized research series (`layer == "normalized"`)

A `Point(period, value|None, quality, flags)` list plus `transforms`, each a dict recorded in order. Provided transformations (all pure, all recorded):

| Function | Record | Notes |
|---|---|---|
| `redenominate_nlg_to_eur` | `op=redenominate, constant=2.20371, applied=1` | NLG / 2.20371, exactly once: a second application, or a non-NLG input, raises |
| `convert_currency` | `op=convert_currency, rate_series, rate_unit` | needs an explicit rate series quoted `<FROM>_per_<TO>` at the same frequency; NLG<->EUR is refused here (fixed constant, not a market rate) |
| `monthly_mean` | `op=monthly_mean, min_coverage` | daily to monthly mean; threshold is a **required** argument and is recorded; below it the month is null |
| `rebase_index` | `op=rebase_index, base_period` | value * 100 / value[base]; the result is `INDEX` and cannot be read as a price |
| `deflate` | `op=deflate, cpi_series, base_period` | nominal to real with an explicit CPI series; `basis` becomes `real` |

Quality is the worst of the inputs; flags are the union; breaks are carried (merged per period). A period missing in any input becomes `Point(period, None, "UNRESOLVED", ("MISSING_INPUT",))`.

### 2.3 Layer 3: derived comparison series (`layer == "derived"`)

| Function | Formula (Decimal, 34 digits) | Integrity checks |
|---|---|---|
| `grams_per_house` | `house * 31.1034768 / gold_per_oz` | house `average_price`, gold `spot_price` unit `<CCY>_per_troy_oz`, same currency, same basis |
| `sats_per_house` | `house_eur / btc_eur * 100000000` | house `EUR`, btc unit `EUR_per_BTC` |
| `relative_performance` | `100 * A_index / housing_index` | both `INDEX` with the same explicit `index_base`, value exactly 100 there |
| `relative_performance_from_levels` | rebases both to `common_base_period` first | the base is the **earliest period where both have values**, or an explicit period that must lie inside that overlap; no overlap raises `OverlapError` |

The output span is first to last common period; a period inside the span where either side is null is an explicit null. Display rounding is never applied in the model (values keep full Decimal precision; the frontend or a publication step rounds).

### 2.4 Layer 4: publication layer

`ReleaseRecord(release_id, release_sha256, authorizer, authorized_on, decision_ref, series_ids, restricted_authorized)`. `ALLOWLIST` is `()`. `publication_gate(candidates, records)` returns the approved series or raises `PublicationDenied`. It denies when: no record lists the id; a record is incomplete (no authorizer, decision reference, valid hash or ISO date); a series is in two records; a record member is not supplied; the recomputed `release_hash` (SHA-256 over the canonical `{series_id: series_sha256}` map) differs from the authorized hash; the series is a raw layer-1 source; any published value has quality `UNRESOLVED`; or the series is **restricted** (asset class `bitcoin`/`equity`, an id token such as `btc sat sats satoshi sp500 spx aex equity`, or a restricted input in its lineage) and is not named in `restricted_authorized`. `publication_rows` projects approved monthly series to a `{"data":[{period, <id>: "decimal"|null}]}` shape; annual series raise (they stay annual).

## 3. Invariants and where they are enforced

| Invariant | Enforcement (`etl/hist_model.py`) |
|---|---|
| Unique, ordered periods; frequency consistency | `validate_series`, `period_key` |
| Coverage and explicit gaps (never filled) | `coverage_report`; derivations emit null points |
| No annual to monthly (or any) frequency conversion | `convert_frequency` always raises; no fill/interpolation function exists (tested by name scan); mixed frequencies raise `FrequencyError` |
| Currency and unit integrity | `_expect`, `convert_currency`, `relative_performance` |
| Definition kinds and nominal/real kept apart | `INCOMPATIBLE_KINDS`, `_combine` |
| Revision detection | `detect_revisions` (`value_changed`, `hash_changed`, `dropped`); `require_no_revisions` fails until a human accepts; reusing a vintage label with new content raises |
| Quality and break markers carried | `worst_quality`, `_union_breaks` |
| Canonical serialization and hashes | `canonical_json` (sorted keys, compact, ASCII, Decimal strings, `1.50 == 1.5`), `series_sha256`, `release_hash` |
| Provenance for every observation | `_check_observation` |
| Decimal arithmetic, rounding deferred | `localcontext` prec 34, floats rejected |

## 4. File layout, naming, versioning (PROPOSED)

```
data/research/<asset>/<series_id>.<vintage>.json     layer 1, canonical JSON (small, derived from pinned bytes)
data/research/<asset>/<series_id>.<vintage>.sha256   sha256 of that file
data/research/bundles/<bundle_id>.json                hist-model/1 bundle: series + releases
data/research/releases/<release_id>.json             ReleaseRecord (owner-signed in a PR)
```

Not committed (unchanged rule): raw third-party bytes (World Bank workbook, ECB CSV, exchange/vendor files). They live in the pinned acquisition step and CI artifacts as hashes and metadata only; layer 1 files hold the parsed values only where the source rights allow (`rights_status` is a per-source open item, see `GOLD_01_RIGHTS.md`, `BTC_01_METHODOLOGY.md` section 8). Where redistribution is not cleared, layer 1 stays an uncommitted CI artifact and only hashes are committed. `data/research/` does not exist yet; this PR does not create it.

Naming: `series_id` is the stable machine id (`house_eur_nl_avg`); `definition_id` names the definition document; vintages are ISO dates or release labels; a bundle is `hist-model/1` (`SCHEMA`), a new schema version requires a new constant and a migration note.

## 5. Adding a new asset (no bespoke pipeline code)

1. Write the definition note: what is measured, price vs total return, nominal vs real, daily convention, rights status. Choose `kind`, `basis`, `currency`, `unit`, `asset_class`.
2. Pin the source bytes (`tools/data_01_source_pin.py`); record `raw_sha256`, `retrieved_at`, `source_id`.
3. Parse to rows with a small adapter (the only asset-specific code); build `Observation`s and a `Series`; call `validate_series` and `coverage_report` and review the gaps.
4. Add `Break`s for every known definition or source change.
5. On a later download: build the new vintage, run `detect_revisions` against the previous vintage; any result needs human approval.
6. Normalize with the generic functions: `redenominate_nlg_to_eur`, `monthly_mean`, `convert_currency`, `deflate`, `rebase_index`.
7. Derive with `grams_per_house`, `sats_per_house` or `relative_performance_from_levels`; read the output transform records.
8. Assemble a bundle and run `python tools/hist_model_check.py bundle.json` (exit 1 on any violation).
9. Do **not** add the id to any allowlist. Publication needs an owner decision (ROOD) and a `ReleaseRecord`.

Equities need two further items before step 7: a total-return vs price-return decision and a currency/calendar policy (OPEN, section 8).

## 6. Relation to `monthly.json` and `series.ts` (PROPOSED extension, text only)

Today `monthly.json` is a closed, strict contract (`period, gold_eur_oz, house_eur, hpi, gold_grams_per_house, gold_index, hpi_index`); `static_export.build()` and `data_quality` require byte equality with the CSV derived output; `series.ts` classes each key as `open`, `gated` or `withheld`. The model does not alter any of that. A future owner-approved extension could work as follows:

- The export step would accept only series that `publication_gate` returns, then map each approved `series_id` to a JSON key through an explicit, versioned mapping that also fixes the `series.ts` registry entry (`publication`: `open` for CBS, `gated` until a record exists, `withheld` as default). A key not in that mapping cannot appear.
- The existing keys keep their names and meaning. New keys would be added to `Point` and `SERIES` in one reviewed change together with the contract text; `sat_per_house` stays `withheld` until a `ReleaseRecord` names it in `restricted_authorized`.
- Annual series would need a **separate** file or section (for example `annual.json`); they are never merged into the monthly rows. Whether the frontend may read a second static file contradicts the current `test_static_architecture.py` rule and is an owner decision.
- `data_quality` would verify that each published value equals the layer 3 value rounded by a documented display rule; rounding happens only there.

None of this is implemented or approved. `DATA_CONTRACT.md` is not edited by this work.

## 7. Migration and rollback

Adoption is additive: new files and a new module; no existing path imports the model (tested). Migration order: (1) existing research scripts (`tools/hist_05_gold_per_home.py`, `etl/gold_monthly.py`) may emit hist-model bundles in parallel and be compared with their current outputs; (2) the parallel outputs are reviewed against ADR-004 results for equality; (3) only then does the owner consider routing publication through the gate. Rollback at any step: delete the new files; production data and JSON are untouched. A bundle with a wrong hash is simply rejected by `hist_model_check.py`; revisions never overwrite earlier vintages, so rollback of data is "use the previous vintage file".

## 8. Risks and open owner decisions

Risks:
- Over-strictness: positive-only values reject legitimately zero/negative series (for example real rates, returns). Levels and indices only; a return model would need a separate kind.
- A single `Series` per vintage means merging vintages for a time-series view is deliberately a manual, reviewed act.
- `kind` mixing rules cover known pairs only (`average_price`/`constant_quality_index`, `price_return`/`total_return`); a new kind needs the matrix extended with a test.
- The restricted-id token list is a safety net, not a classifier; the primary control is the allowlist being empty.
- 34-digit Decimal results are hash-stable only while the formulas and precision are unchanged; changing `PREC` changes hashes and must be versioned.
- Layer 1 values may fall under source licences; committing parsed values is a rights decision per source.

OPEN owner decisions:
1. Where layer 1 files may live (`data/research/` committed, CI artifact only, or hashes only) per source rights.
2. Whether `ReleaseRecord` authorization is a JSON file in Git (proposed) or a DECISIONS.md entry referenced by `decision_ref`.
3. Minimum daily coverage per month for each aggregation (`min_coverage`: gold/ECB vs 100% for 24/7 Bitcoin).
4. Equity policy: price-return or total-return, currency of listing vs EUR, trading-calendar gaps, and whether a total-return vs price-return pair may ever be compared.
5. Whether annual series may be published at all and in which file, given the single-file rule.
6. Real values: which CPI series and base year (ADR-009 is PROPOSED).
7. Whether `NLG` display series are allowed or all pre-1999 values are shown as redenominated EUR only.
