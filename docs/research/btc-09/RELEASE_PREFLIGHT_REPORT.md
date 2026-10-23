# BTC-09 — Release preflight report

Contract: existing `btc-release-record/2` (no competing contract). Tool: `tools/btc_09_preflight.py`; real-input evidence run 40027551242; synthetic evidence in `tests/test_btc_09_preflight.py` and `tests/test_btc_08b_release_contract.py`.

## Actual (real private inputs, synthetic in-memory approval — never a production record)
- `release_preflight` positive path: PASS. `reproduce_composite`: byte-identical. `rollback_target_ok`: true. Record key set exact (30 keys). Registry empty (`ARTIFACT_RECORDS=()`).
- Negative battery on the REAL inputs, all refused (14/14): PENDING private hash, owner not approved, extra field, missing field, fewer months, wrong quality scope, wrong month→quality hash, other snapshot id, other calculation commit, other private candidate bytes, other private sidecar bytes, wrong rollback bytes, mutated-but-hash-consistent payload, non-canonical payload.
- The public gate alone ACCEPTS the mutated hash-consistent payload (`gate_alone_cannot_see_forged_payload: true`); only the private-input regeneration refuses it. Therefore `release_preflight` is the mandatory pre-registration step (RELEASE_CONTRACT in btc-08b).
- Scope: 151 contiguous months 2014-02..2026-08, Q2 27, Q1_CANDIDATE 124, no Q3, 2011-06 not published.
- The composite hash printed by the run (`bb7f5889…`) belongs to a SYNTHETIC release id; it is not the release artifact. The real artifact identity exists only after the owner chooses release id, decision reference and rights reference.

## Not executed
- A real owner approval record (forbidden), registration, pin change, deployment.
- Preflight against the owner's durable copy (storage open).
