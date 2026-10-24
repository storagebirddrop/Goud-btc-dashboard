# HIST-13 — Contract validation (`hist-publication/1`, HIST-12 gate)

All results are from `contract_validation` in `tools/hist_13_candidate.py` on the REAL candidate (hashes and booleans only).

- The candidate itself is **refused** (release block PENDING and unauthorized): by design it can never pass the gate.
- Without pin or external record: refused.
- Preflight payload, comparison off, with an **in-memory** external record: accepted. Comparison on: accepted only with an in-memory external HP3 authorization, refused without it.
- Control: a no-op mutation passes (the mutation harness is not what refuses).
- **Negative cases: 21/21 refused**: wrong pin; one changed byte; no external record; default (empty) allowlist; wrong release hash; extra series; missing half-year; extra 2000 month; swapped currency; mean labelled median; median definition on the mean; euro != guilder / 2.20371; missing quality; unresolved quality; undocumented flag; missing provenance; source hash mismatch; synthetic marker in production; changed comparison scope; comparison without HP3; release block not authorized.
- Browser gate (TypeScript, HIST-12) on the real payloads: see the private browser report; TS and Python agree on the synthetic fixtures (HIST-12 parity test, in CI).
- Nothing persisted: no pin, record, allowlist entry or `historical.json` exists in the repository (test).
