# HIST-12 — Handover

## State
Inert historical implementation, all fail-closed, synthetic fixtures only. Nothing is published, pinned, registered or deployed. PR #112 (governance record of HD1-HD3) was open at implementation time; merging it is a Project Control action.

## To make anything visible (all separate decisions; none taken)
1. Decisions still open: **HP1** NVM/OTB rights; **HP2** CBS 1995-1999 attribution and retrospective-euro labelling (and optional HP2b note for 2000-2001 in the current view); **HP3** NVM/CBS side by side (enables panel 3 via `COMPARISON_RELEASES` and the payload block); **HP4** page-135 values; **HP5** exact release identity and a deployment authorization; **HP6** permanent storage of the derived dataset.
2. Technical steps then needed (not done): P2 private candidate build of the real `historical.json` (from `data/fixtures/hist09` and `data/cbs-housing.csv`, price-free logs, workflow in a private environment, 2000 half-year values checked against `monthly.json`); `ReleaseRecord` in `hist_model.ALLOWLIST`; the payload SHA-256 in `HIST_APPROVED_PAYLOAD_SHA256`; the file as `frontend/public/data/historical.json`; a three-commit change-set check like `tools/btc_10_changeset_check.py` for the release PR (only those locations may change); source wording (HP1/HP2) in the view; replace the synthetic provenance texts.
3. Rollback: remove the pin (or the file) in a revert commit / redeploy the previous deployment; `monthly.json` and the BTC identity are unaffected.

## Running the checks
- `python -m pytest -q tests/test_hist_12_publication.py tests/test_hist_12_frontend.py tests/test_hist_12_production_parity.py`
- `python -m tests.hist12.gate_parity` (needs `npm ci` in `frontend/`; runs in CI)
- `python -m tests.hist12.browser --out-dir <new dir outside the repo> --chrome <chromium>` (manual workflow `hist-12-ui-acceptance.yml`)

## Boundaries kept
No merge, no hash-pin activation, no release-record registration, no real historical value, no change to `monthly.json`, `data/cbs-housing.csv`, gold, BTC contract/pins/records, the historical allowlist or BTC D07. BTC D08 unaffected.
