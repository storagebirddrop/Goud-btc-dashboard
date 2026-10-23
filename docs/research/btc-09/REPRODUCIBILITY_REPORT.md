# BTC-09 — Reproducibility report

Evidence run: manual workflow "BTC-09 final release preflight", run 40027551242, code commit `9dba03cc1e6d750d524a4e88450f2cc31bb70fd0` (later commits on the PR change documents only, not calculation code). Price-free: hashes, counts, booleans, key paths.

## Source identity (VERIFIED_CI, real data, GitHub-hosted runner)
- Snapshot ID `btc04e-e11c2538168b2bde`. Source TAR SHA-256 `19abaa9b47c8172924920249304009bbea47e1c612b190666dfa28991b80d4ce` (external anchor; the run fails on any difference).
- Package obtained from the BTC-07E-A artifact (run 40006735985, artifact 12524137867; expires 2026-10-24T18:51Z). No source was re-acquired.
- Restore scenarios: (1) RESTORE_VERIFIED_LOCAL with replay IDENTICAL at the packing commit `641151b9…` on the CI runner — EXECUTED. (2) Offline regeneration in an empty network namespace (`network_isolated: true`) — EXECUTED. (3) Restore from owner-controlled durable storage — NOT EXECUTED (no owner storage reachable; `REAL_OWNER_RESTORE_NOT_EXECUTED`). (4) Restore in the Claude sandbox — NOT POSSIBLE (artifact blob host blocked, HTTP 403/empty).

## Historical candidate (rebuilt at the packing commit, must equal the recorded hashes)
- Candidate `616ac933e822df5acc22fb7ff5b1fdd7fa063d1f12fbdba54021752fb69645b2`, sidecar `a0bcb9bad3c093033beba741ddd1fed3ad5626f5f1483beb87efb68518c8ba8a`: both reproduced exactly (the workflow fails otherwise).

## Regenerated candidate under the current calculation code
- Calculation commit `9dba03cc1e6d750d524a4e88450f2cc31bb70fd0`; candidate SHA-256 `5244caab51617de1c7da739e9a81f4cefed792a36b592323f800ea7b3a578444`; sidecar SHA-256 `a0bcb9bad3c093033beba741ddd1fed3ad5626f5f1483beb87efb68518c8ba8a` (IDENTICAL to the historical sidecar: every BTC and satoshi value is byte-identical).
- The candidate hash is bound to the calculation commit; it WILL change again for the final release commit. Re-run the workflow (or `tools/btc_09_preflight.py`) at the release commit; the sidecar hash must stay `a0bcb9ba…`.

## Comparison historical vs regenerated (151 months, 2014-02..2026-08)
- Same month set; 0 value differences; 0 preview row differences (state, status, quality, flags); contract equal.
- Preview byte differences are exactly two key paths, both explained: `btc.provenance.calculation_git_commit` (hash-bound commit) and `btc.sources[].attribution` (BTC-08B wording). Any other path would fail the run (`unexplained_preview_paths: []`).

## Independent recomputation (no etl code; plain Decimal from the snapshot daily files and the CBS CSV)
- 151/151 months recomputed (P = mean of complete-month CM PriceUSD, F = mean of ECB fixings, H = CBS EUR, BTC/house = H·F/P, sat = ×1e8); 0 mismatches at relative tolerance 1e-25.

## Limits
- Confirms reproducibility from the preserved vintage, not that the vintage is the best or final source state (owner decision). ECB raw data is NOT_RETAINED by design (the stored daily ECB series is the source of record).
- The package remains publicly downloadable until the artifact expires; durable owner copy is still the open prerequisite.
