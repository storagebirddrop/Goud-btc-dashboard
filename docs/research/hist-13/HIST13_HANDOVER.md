# HIST-13 — Handover

## Reproduce privately
`python -m tools.hist_13_candidate --inputs data/fixtures/hist09 --out-dir <NEW private directory outside the repository> --production-csv data/cbs-housing.csv [--write-preflight]` (refuses repository or served directories). Private browser run: `python -m tests.hist13.private_browser --candidate-dir <that directory, with --write-preflight> --out-dir <new private directory> --chrome <chromium>`.

## State
Tooling, tests and price-free reports only. No candidate, preflight payload, pin, record, allowlist entry or `historical.json` is in the repository; the session's private files were ephemeral and are not preserved or delivered. Gates closed: `HIST_APPROVED_PAYLOAD_SHA256 = []`, `hist_model.ALLOWLIST = ()`, `COMPARISON_RELEASES = ()`, `BTC_APPROVED_COMPOSITE_SHA256 = []`, `ARTIFACT_RECORDS = ()`.

## Next steps (all separate authorizations)
HP1-HP6 (owner pack) -> owner supplies authorizer/date/decision reference -> private assembly of the final payload and its SHA-256 -> release PR changing only the allowlist record, the frontend pin, `frontend/public/data/historical.json` (and optionally the HP3 entry), verified by a three-commit change-set check like the BTC one -> deployment authorization -> cache/rollback checks as in HIST-12 handover.

## Unchanged
`frontend/public/data/monthly.json` (`1afb0bf9...`), `data/cbs-housing.csv`, gold, BTC calculation paths and D07 identity, BTC pins and registry.
