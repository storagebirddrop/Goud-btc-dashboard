# HIST-11 — Minimal implementation plan (proposal; nothing implemented)

Classification: design and plan GROEN (documentation). Implementation: **ORANJE** for inert code and tests, **ROOD** for anything that makes data visible (publication meaning, source rights, new public contract). Principle: smallest path, inert first, `monthly.json` byte-identical throughout, BTC release identity untouched.

## Phases
| Phase | Content | Needs | Visible to users |
|---|---|---|---|
| P0 | Project Control decisions HD1-HD3 (see owner pack) | owner | no |
| P1 inert implementation | `hist-publication/1` types and validator; `etl/hist_model.publication_series` projection; `frontend/src/hist.ts` (loader, `activateHist(sha, doc, pins=[])`, label maps); Historisch tab behind the empty pin list; synthetic fixtures only | HD1-HD3 | **no** (pin list empty) |
| P2 private candidate | manual workflow (read-only, price-free log, no public artifact of values) that rebuilds the five C0 series from `data/fixtures/hist09` and `data/cbs-housing.csv`, writes the candidate privately, reports hashes; checks 2000 half-year equality with `monthly.json` | P1 | no |
| P3 owner review | exact payload hash, wording of sources (HP1/HP2), HP3, HP4, HP6 | owner | no |
| P4 release PR (separate authorization) | only: allowlist record, pin, `historical.json`, docs/tests; verified by a three-commit change-set check analogous to `tools/btc_10_changeset_check.py` | all HP | after deploy authorization |
| P5 deploy/rollback | static deploy, cache check, rollback by pin/revert | owner | yes |
| C1 gold/grams | after HG decisions; separate plan | HG | later |

Estimated size: P1 about 6-8 files (one Python module + tests, `hist.ts`, a view component, series registry entry for the historical panels, tests); no change to `etl/static_export.py`, `etl/data_quality.py` parity for `monthly.json`, `data/cbs-housing.csv`, BTC code or pins.

## Reuse
`hist_model` (Series, canonical_json, release_hash, ReleaseRecord, publication_gate, weighted_half_year_mean), `tools/hist_09_bundle.py` (A/B/C bundles, hashes in `HIST_09_INTEGRATION.md`), `data/fixtures/hist09`, BTC pattern for frontend pin and fail-closed payload (`frontend/src/btc.ts`, `activateBtc`), the private-workflow and price-free-log pattern of BTC-09/10.

## Targeted negative-test plan (small; each must fail closed)
1. Median and mean in one series id or one line -> validator rejects (`DefinitionMismatch`).
2. NVM half-year converted/expanded to months, or a missing month interpolated -> `FrequencyError`; payload with monthly NVM periods rejected.
3. Weighted half-year with a missing month or non-positive weight -> null, never a number.
4. Index series in the payload (`currency INDEX` without an approved base) -> rejected in C0.
5. NLG value presented as EUR without `RETROSPECTIVE_EUR`, EUR conversion applied twice, or wrong constant -> rejected / test equality 2.20371.
6. Series without `breaks` for a known boundary, or a flag with no Dutch mapping -> UI mapping test fails.
7. Point without quality, or `UNRESOLVED` with a value -> rejected.
8. Unpinned, tampered (one byte), extra-field, `publication_authorized` without pin, empty pin list -> Historisch tab absent; current dashboard identical (DOM test).
9. A line across a null or across the 1999/2000 boundary in the historical view -> chart test (`connectNulls=false`, no cross-panel series).
10. Raw source layer or private fixture path in the payload / build -> `publication_gate` and a dist scan refuse (BTC-09 `btc_09_distribution_check` pattern).
11. `monthly.json` sha equals `1afb0bf9…91d8cd`, `data/cbs-housing.csv` unchanged, `BTC_APPROVED_COMPOSITE_SHA256=[]`, `ARTIFACT_RECORDS=()`, `HIST_APPROVED_PAYLOAD_SHA256=[]` -> asserted in CI.
12. BTC composite gate and `btc_10_changeset_check` tests still pass; a release PR touching both payloads in one commit is rejected by the change-set check.
13. 2000 half-year values built from the committed CSV equal `monthly.json` values; mismatch -> build fails.
14. Cache/version: new frontend + stale `historical.json`, or old frontend + new file -> tab absent (hash mismatch), no mixed vintage.

## Rollback
Remove the pin or the file in a revert commit, or redeploy the previous Pages deployment; verify `monthly.json` hash, absence of the Historisch tab, BTC defaults.

## Explicitly not planned now
Gold and grams, any index, CPI/real values, pre-1975, a combined series, a change to `monthly.json`/export/`data_quality`, a database or backend.
