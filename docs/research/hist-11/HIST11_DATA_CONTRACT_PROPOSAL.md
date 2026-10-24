# HIST-11 — Historical data contract proposal (`hist-publication/1`, PROPOSED)

Status: PROPOSED; not a decision, not implemented. It is the smallest compatible contract: a **separate static file** `frontend/public/data/historical.json`; the current `monthly.json` (`1afb0bf9…91d8cd`) stays byte-identical so the approved BTC identity is unaffected. No database, no backend, no Pages Function. Reuses `etl/hist_model.py` (canonical JSON, `Series`, `ReleaseRecord`, `publication_gate`) and the BTC pattern of a frontend payload-hash pin.

## 1. File shape
```
{"schema":"hist-publication/1",
 "release":{"id","decision_ref","publication_authorized":true,"generated_from":"hist-model/1"},
 "provenance":{"method_ids":[...],"sources":[{"id","title","url","license","rights_status","sha256","vintage","acquired_at"}],
               "source_pins_sha256","bundle_sha256s":{...}},
 "series":[{"series_id","kind","statistic","frequency","unit","currency","denomination":{"native","display","conversion"},
            "layer","definition_id","basis","breaks":[{"period","reason"}],"annotations":[...],
            "points":[{"period","value","quality","flags":[...]}]}]}
```
Values are Decimal strings (canonical serialization, no floats); gaps are `null`; periods are `YYYY-Hn` (semiannual) or `YYYY-MM` (monthly).

## 2. Series identifiers (Phase C0)
| series_id | frequency | unit / currency | statistic | layer |
|---|---|---|---|---|
| `hist_nvm_median_nlg_h` | semiannual | NLG | nominal median, existing homes, NVM brokers | normalized |
| `hist_nvm_median_eur_retro_h` | semiannual | EUR, `RETROSPECTIVE_EUR`, NLG / 2.20371 | same | normalized |
| `hist_cbs_avg_eur_m` | monthly 1995-01..1999-12 | EUR (retrospective before 2002) | average of sold existing homes | normalized |
| `hist_cbs_avg_eur_h` | semiannual 1995-H1..2000-H2 | EUR | transaction-weighted mean (audited rule, all six months) | derived |
| `hist_nvm_over_cbs_ratio_h` | semiannual 1995-H1..2000-H2 | ratio | `statistic_ratio`, flag `STATISTICS_DIFFER` | derived |

Phase C1 (after the gold decisions) adds gold-local and grams series with quality levels B/A/E and era breaks. 2000+ monthly CBS values are **not** republished: the half-year 2000 aggregates are built from the committed series and checked equal to `monthly.json` at build time.

## 3. Required properties
- **Frequency, unit, currency, statistic, definition_id**: every series declares them; mixing kinds is rejected by the model (`average_price` x `median_price`).
- **Provenance**: per source id, rights status, sha256 of the obtained bytes, vintage, acquisition time; window pins from `data/fixtures/hist10/source_pins.json` for gold phases; raw source observations are never included (`publication_gate` refuses layer `source`).
- **Quality**: per point; a point with `UNRESOLVED` quality and a value is refused.
- **Method / vintage identifiers**: `METHOD:HIST10_M1_V1` where gold applies; `HIST09` adapter version for NVM/CBS; source-vintage ids in the manifest.
- **Publication authorization**: an `etl/hist_model.ALLOWLIST` entry (`ReleaseRecord`: release id, release sha256 = `release_hash(members)`, authorizer, authorized_on, decision_ref, series_ids) AND the payload's SHA-256 in a frontend pin list `HIST_APPROVED_PAYLOAD_SHA256` (default `[]`). Both default to empty = nothing visible. Neither a flag in the file nor a URL authorizes anything.
- **Immutable artifact hashes**: `release_hash` over series members (existing) plus the SHA-256 of the exact `historical.json` bytes (new, mirrors `composite_sha256`). The two must be reproducible from pinned inputs (`data/fixtures/hist09`, `source_pins.json`) by a private/manual workflow, price-free logs.
- **Projection**: `publication_rows` is monthly-only; a small `publication_series` projection (semiannual + monthly, no frequency conversion) is the only new model code.

## 4. Gate and failure behaviour (fail closed)
Missing, malformed, mismatched or unpinned file -> the Historisch tab is not rendered and the current dashboard is untouched. Wrong hash, extra field, unknown series id, floats, missing quality, unmapped flag, `publication_authorized` without a pin: all rejected. A frontend with an empty pin list shows nothing even for an authorized file.

## 5. Rollback
Static file only: remove the pin (or the file) in a revert commit / redeploy the previous Pages deployment; `monthly.json` and the BTC composite state are unaffected. Validation after rollback: `historical.json` absent or unpinned, Historisch tab absent, `monthly.json` sha `1afb0bf9…`, BTC defaults empty.

## 6. Why not extend `monthly.json`
It would change the legacy hash bound by the approved BTC identity (`LEGACY_PUBLIC_SHA256`, record `legacy_projection_sha256`, `rollback_ref`), break the strict export and `data_quality` parity (exact columns, no gaps, base 2000-01), and require a new export decision. A single static file with its own hash pin avoids all three.
