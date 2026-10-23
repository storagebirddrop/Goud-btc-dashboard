# BTC-10 / D07 — Owner approval pack

**D07 is PENDING Project Control. D08 is NOT AUTHORIZED. BTC publication is HOLD.** This pack is price-free; the composite bytes are not delivered through any public channel (see Delivery).

## Decision proposed (D07): approve this exact release artifact
| Item | Proposal |
|---|---|
| Source | snapshot `btc04e-e11c2538168b2bde`, TAR `19abaa9b…d4ce`, manifest `ba71c577ad33552b34556df0a0e88317b311eb5ffa4186eb048cdfb59cecc6f3` |
| Calculation | commit C `c11f82a83234593ace70369da07ca183c0cc3db3`; method `CM_PRICEUSD_MONTHMEAN_C1_V1` |
| Months / classes | 2014-02..2026-08 (151); Q2 27; Q1_CANDIDATE 124 (provisional); no Q3; 2011-06 withheld |
| Identity | release_id `BTC-REL-2026-10-001`; decision_ref `PC-BTC10-D07-2026-10-001`; rights_review_ref `PC-BTC09-A1+PC-BTC07D-CM10` (PROPOSED: owner may rename; the composite hash then changes) |
| Candidate / sidecar | `2aeed0f634c264340afffc45f2a3b926b1ae2abaef2cb444d1b7d8d6eaa65a11` / `a0bcb9bad3c093033beba741ddd1fed3ad5626f5f1483beb87efb68518c8ba8a` |
| **Public composite SHA-256** | **`e6dcc4ad3c818fc84a710b6e4f28255517c0a990c29c79b4ee5246a5826a3d93`** |
| Rollback target | legacy payload `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`, state `LEGACY_GOLD_CBS_NO_BTC` |
| Approval fields (owner fills) | `owner_approval=APPROVED`, `approved_by`, `approved_on` — nothing pre-filled |

## What the owner approves by approving D07
Only that these identities are the intended release. It does not authorize registration, pin, deployment or activation (D08).

## Remaining owner actions (minimal)
1. D07: approve or amend the identity (names; approver; date).
2. D05: keep the TAR in private storage and record `REAL_OWNER_RESTORE_PASS` (artifact 12524137867 expires 2026-10-24T18:51Z; afterwards the owner TAR is the only build input).
3. D08: separate deployment authorization.

## Delivery of the private artifact (limitation)
The composite and candidate contain real prices. The only channels available to the agent are the public repository and GitHub Actions artifacts of a public repository; neither is access-controlled, so they are NOT used. The bytes exist only on the ephemeral runner. They are deterministically reproducible: restore the TAR (anchor above) and run `python -m tools.btc_10_d07 ...` in a checkout whose calculation paths equal C; the printed composite SHA-256 must equal the value above. Delivery of the bytes themselves therefore requires the owner to regenerate privately (or an access-controlled channel the owner provides).

## Release-window checklist (after D07 + D08)
1. Create the release branch only now; build the three changes (record, pin, composite bytes); run `tools.btc_10_changeset_check --calc-commit C --baseline-commit B --release-commit R --record RECORD.json` (B = main after PR #109) and the full suite locally before pushing (a push publishes a Cloudflare preview).
2. Verify on the release commit: `etl.data_quality` (extended payload through the release gate), browser acceptance of the exact composite (72 checks: BTC/satoshi values, Q2 and provisional Q1-kandidaat labels, attribution, bronstand, 151 months, missing-value handling, wrong-bytes and empty-pin cases), gold/CBS parity (legacy projection = `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`).
3. Deploy only on explicit authorization. Record deployment id, commit R, live JSON SHA-256 (= composite SHA-256), frontend asset containing the pin.
4. CDN/cache: `curl -sI` JSON and main JS from two locations (`cache-control`, `etag`, `age`); body hash equals the composite SHA-256; clean-profile and hard-reload agree; purge only if an old etag persists (purge is a release-window action, not done in preparation).
5. Rollback: redeploy the previous Pages deployment or revert R; validate with `tools.btc_09_distribution_check state` (legacy hash, no Bitcoin keys, empty pins) and a clean-profile browser check (ROLLBACK_RUNBOOK in btc-09).

## Not executed / unverified
Owner-storage restore; a preflight on an owner-approved record; Cloudflare cache headers and purge; real rollback; the release PR itself.
