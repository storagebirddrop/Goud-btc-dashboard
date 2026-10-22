# BTC-07B — Publication safety and release verification

Status: ENGINEERING EVIDENCE — PUBLICATION HOLD. Nothing was published, deployed, merged or authorised. `frontend/public/data/monthly.json`
(sha256 `1afb0bf9…91d8cd`) and `data/cbs-housing.csv` are byte-identical; `etl/btc_contract.py` `ARTIFACT_RECORDS` and `RELEASE_APPROVALS` stay empty.
Base: main `bf5542fbcbc10849926b97e7113878318539a7a5` (verified as the actual HEAD). Synthetic tests prove code, not data or rights.

## Gate table

| Gate | Result | Evidence |
|---|---|---|
| G10 Price-free public CI output (P0) | **PASS (code + real CI run)** | `tools/btc_public_report.py`; `tests/test_btc_07b_p0_containment.py` (content canaries over uploaded files and stdout); real CI run 39862736805 on the first commit printed only allowlisted sections (no stale value, no independent numbers) |
| Existing price-bearing artifacts/logs | **OPEN — PC decision** | `BTC_07B_P0_ARTIFACT_INVENTORY.md` (metadata only, nothing deleted; 9 old `btc-04e-summary-not-approved` artifacts, expire 2026-11-05) |
| Snapshot retention / restore protocol (P1) | **PASS locally (synthetic); durable owner storage OPEN** | `tools/btc_07b_package.py`, `tests/test_btc_07b_p1_restore.py` |
| Owner-designated private location, real restore from it | **OPEN** | no location designated; no claim of operational storage |
| Exporter / validator connected to the composite gate (P2) | **PASS (synthetic records)** | `etl/btc_release.py`, `etl/data_quality.py` delegation, `tests/test_btc_07b_p2_release_path.py` |
| Frontend BTC/SAT display, locally testable (P3) | **PASS (logic + real Chromium)** | `frontend/src/btc.ts`, `tests/test_btc_07b_p3_frontend.py`, browser run B01–B11 below |
| Browser acceptance B01–B11 | **PASS 59/59 checks, executed locally in a real Chromium (playwright 1194), synthetic fixtures, loopback only; not an acceptance of any real production vintage** | `tools/btc_07b_browser.py/.mjs` |
| Local release / rollback rehearsal (P4) | **PASS (sandbox, synthetic)** | `tools/btc_07b_rehearsal.py`, `tests/test_btc_07b_p4_rollback.py` |
| Real release dossier (vintage, final bytes, record) | **OPEN** | no owner-approved vintage; no real record |
| NC exploitation statement, CM/Talos contract check | **OPEN — owner** | not asserted or simulated as done |
| PC-BTC06-6 conditions | **OPEN (conditional)** | unchanged |
| Cloudflare deployment / public rollback | **NOT EXECUTED** | out of scope |

## P0 — what is, and is not, public

Private (runner only): `$RUNNER_TEMP/btc-04e-private/summary.json` (prices, derived values, June 2011 diagnostics), the vintage snapshot, the BTC-06C
candidate and sidecar. Public (uploaded and printed): `btc04e-public-summary/1`, built key by key from an allowlist: statuses, counts, dates, hashes, booleans.
`independent` is reduced to `btc_agrees`/`sats_agrees` verdicts; `stale_runs` keep first/last/days without the price; free text (`source_notes`) is
reduced to a count; exception messages are scrubbed. A second, independent backstop refuses floats, decimal numbers, forbidden key names, unknown top-level
keys and oversized documents; if it refuses, nothing public is written and the run fails.

## P1 — restore protocol (tested form)

```sh
# pack (outside the repository; writes a new tar; prints the anchor sha256 that PC must record elsewhere)
python -m tools.btc_07b_package pack --snapshot SNAPSHOT_DIR --cbs-csv data/cbs-housing.csv \
    --legacy-json frontend/public/data/monthly.json --out /private/store/vintage.tar
# restore (new empty directory; needs the external anchor; network is blocked during the replay)
python -m tools.btc_07b_package restore --package /private/store/vintage.tar --expect-sha256 ANCHOR --dest /private/restored
```
`restore` refuses a package whose sha256 differs from the anchor before extracting anything, rejects unsafe tar members (absolute or `..` paths, links),
verifies `SHA256SUMS`, replays offline and compares snapshot id, manifest, CM/ECB canonical, CBS input, derived, candidate and sidecar hashes with the
provenance recorded at pack time. Evidence is price-free. Only a LOCAL directory was tested.

## P2 — release path

`etl/btc_release.py` is the only way an extended payload leaves the contract: `export_composite` writes a new file only if `composite_release_gate` opens
for exactly these bytes (record needed), never into the committed public path, never overwriting; `data_quality.validate_production_state` hands an
extended public JSON to `validate_composite_state` (gate + unchanged legacy validation of the projection). No env var, JSON boolean, URL or CLI option can
supply a record; the `records` argument is for synthetic tests only. `etl/static_export.py` is untouched.

## P3 — frontend

Bitcoin series are `publication:'pinned'`: visible only when the SHA-256 of the exact served `/data/monthly.json` bytes is in the code pin
`BTC_APPROVED_COMPOSITE_SHA256` (empty), the `btc` root block is structurally valid, and the month is PUBLISHED inside the authorised coverage (default start
2014-02 unless early history is authorised; June 2011 never). The browser acceptance builds a TEMPORARY COPY of `frontend/` whose pin list holds the hashes
of the synthetic fixtures; the repository sources and the production build keep an empty pin.

Reproduce: `cd frontend && npm ci`, install Playwright (global or NODE_PATH) and a Chrome, then
`python -m tools.btc_07b_browser --out-dir /private/new/dir --chrome /path/to/chrome` (output outside the repository; screenshots are private).
Executed result (this branch, Chromium from /opt/pw-browsers, 1280 and 375 px): `RESULT: ALL CHECKS PASSED (59/59)`; B01 and the legacy half of B09 ran against the
UNCHANGED production build (empty pin), B02–B11 against the pinned test copy. Earlier attempts in the same session failed and were corrected, not hidden: the early-history
fixture first lacked Q3 values (the standard sidecar carries none, so the fixture now adds FICTIONAL ones) and the tooltip probe first used a wrong locator and an
off-screen chart. Screenshots/DOM evidence stay in the private output directory.

Optional pytest hook: `BTC07B_BROWSER=1 CHROME_PATH=... python -m pytest tests/test_btc_07b_p3_frontend.py`.

## P4 — rehearsal

`python -m tools.btc_07b_rehearsal --work-dir /private/new/dir`: invalid candidates leave the sandbox live file unchanged; a synthetic composite is validated
only in the sandbox with an in-process record (the default registry denies it); an injected failure during the switch leaves the live file and no temp file;
rollback restores the exact approved legacy bytes (sha256 equal, gold/CBS projection equal).

## Remaining release blockers

1. Owner/PC decision on the existing price-bearing artifacts and logs (and visibility of the repository / artifact access, not verified here).
2. Owner-designated private retention location and a real restore from it with the actual candidate package and external anchor.
3. Owner statements: non-commercial exploitation, existence/terms of any separate Coin Metrics / Talos contract (PC-BTC07-2/3), PC-BTC06-6 conditions.
4. A real candidate vintage chosen by PC, its exact record, browser acceptance on the real candidate bytes, and a reviewed commit that adds the record AND the frontend pin.
5. Real (not sandbox) release and rollback authorisation by the owner; this change deploys nothing.
