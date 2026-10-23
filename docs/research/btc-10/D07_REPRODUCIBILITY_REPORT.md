# BTC-10 / D07 — Reproducibility report

Run 40033193216 (CI runner, real vintage, price-free output).

1. **Source availability.** The BTC-07E-A package (run 40006735985, artifact 12524137867) was downloadable in CI (artifact expires 2026-10-24T18:51Z). SHA-256 equals the anchor `19abaa9b…d4ce` (the run fails otherwise). It cannot be downloaded in the Claude sandbox (blob host blocked), so nothing was restored there.
2. **Historical candidate** reproduced at packing commit `641151b9…`: candidate `616ac933…`, sidecar `a0bcb9ba…` (equality enforced).
3. **Regenerated under frozen C** (`c11f82a83234593ace70369da07ca183c0cc3db3`, code identity proven by `git diff C HEAD` over the calculation paths): candidate `2aeed0f634c264340afffc45f2a3b926b1ae2abaef2cb444d1b7d8d6eaa65a11`; sidecar `a0bcb9bad3c093033beba741ddd1fed3ad5626f5f1483beb87efb68518c8ba8a` — identical to the historical sidecar, so every BTC and satoshi value is byte-identical.
4. **Preview differences** are exactly `btc.provenance.calculation_git_commit` and `btc.sources[].attribution`; `unexplained_preview_paths: []`.
5. **Independent recomputation** (plain Decimal from the snapshot daily files and the CBS CSV): 151/151, tolerance 1e-25.
6. **Determinism:** a second candidate build in a separate process is byte-identical; the composite regenerates byte-identically from the private inputs (`reproduce_composite`).
7. **Offline:** the preparation ran in an empty network namespace (`network_isolated: true`).

Limits: restore from owner-controlled storage is NOT EXECUTED (D05 disaster-recovery copy). After the artifact expires the owner TAR is the only build input; recipe: restore with `tools/btc_07b_package restore` at commit `641151b9…`, then run `tools/btc_10_d07.py` in a checkout whose calculation paths equal C.
