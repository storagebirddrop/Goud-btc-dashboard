# BTC-08B — Technical release contract (btc-release-record/2)

Status: IMPLEMENTED AND TESTED WITH SYNTHETIC FIXTURES. No production record exists. BTC publication remains HOLD (`BTC_APPROVED_COMPOSITE_SHA256=[]`, `ARTIFACT_RECORDS=()`). Code references are plain text (etl/btc_contract.py).

## Three distinct artifacts (never confuse them)
1. Candidate (PRIVATE): `candidate-preview.json` + private values sidecar from tools/btc_06c_candidate.py. Validity of a candidate is NOT an authorization.
2. Authorized release artifact: the composite payload bytes (`compose_release`) plus ONE owner-signed `btc-release-record/2` that binds them.
3. Public payload: the byte-identical composite served as `/data/monthly.json`. It is shown only when the frontend pin list contains its SHA-256.

## What the record binds (exact key set, 30 keys; any missing or extra key = closed)
- Identity: schema, record_id, release_id, decision_ref, approved_by, approved_on, owner_approval=APPROVED, status.
- Bytes: composite_sha256 == public_payload_sha256, btc_selection_sha256, legacy_projection_sha256 (gold/CBS unaffected).
- Source vintage: snapshot_id, snapshot_manifest_sha256, provenance_sha256 (whole provenance block), cbs_input_sha256, calculation_git_commit.
- Private inputs: candidate_preview_sha256, private_sidecar_sha256 (owner-supplied; verified by `reproduce_composite`, never read by the public gate).
- Method: method_id (CM_PRICEUSD_MONTHMEAN_C1_V1), quality_version, exception_policy_version.
- Scope: authorized_fields, authorized_months (exact list), authorized_qualities, quality_by_month_sha256 (month -> quality), exceptions (2011-06 hold), early_history_authorized, review_refs (rights, contract check).
- Rollback: rollback_ref = previous public state (pinned legacy payload, state LEGACY_GOLD_CBS_NO_BTC).

## Fail-closed properties (tests/test_btc_08b_release_contract.py, 06c, 07b_p2, 07b_p4)
Default deny; wrong/other hash; one tampered byte; extra or missing record field; PENDING or malformed hashes; month-scoped and quality-scoped (Q2-only, Q1-only, forged quality label, Q3/2011-06 unauthorizable); other snapshot; other calculation commit; no self-authorization (nothing inside the payload can supply a record); mixed vintages rejected (a second snapshot with one revised price needs a new record); regeneration from private inputs must be byte-identical; withdrawal returns to the pinned legacy bytes only.

## Preflight functions
- `release_preflight(composite, record, preview_bytes, sidecar_bytes, previous_public_bytes)`: MANDATORY before any record is registered or a pin added. Runs the public gate, byte-identical regeneration from the bound private inputs, the rollback check and refuses PENDING fields. Demonstrated need: a payload with one edited value and a record recomputed for it passes the public gate (shape/hash only) and is caught only by regeneration (tests/test_btc_08b_release_contract.py).
- `record_template(composite, authorization)`: what the OWNER would approve; owner_approval stays PENDING.
- `reproduce_composite(record, preview_bytes, sidecar_bytes)`: independent byte-identical regeneration.
- `rollback_target_ok(record, public_state_bytes)`: rollback target check.
- tools/btc_06c_candidate.py `verify_release_path`: in-memory proof of the closed gate incl. new denial labels other_quality_scope, other_snapshot, owner_fields_pending.

## Not executed / not proven
- No production record created (forbidden). Real-data owner restore (REAL_OWNER_RESTORE_NOT_EXECUTED), Cloudflare cache/preview behavior and a real deployment are NOT executed.
- Code identity: changing etl/ or BTC tools changes the commit-bound calculation identity (`calculation_git_commit` is hash-bound in the candidate). The historical BTC-07E-A package restores only at its packing commit 641151b900df1403f8b4f3879ef45028d64552f2; the final release must re-pack/rebuild the candidate from the SAME snapshot bytes under the final release commit (derived values identical; the candidate preview hash WILL change because it binds the commit and, since BTC-08B, the corrected source attribution strings). See BTC09_HANDOVER.md.
