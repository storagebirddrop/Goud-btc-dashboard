# GOLD-03A/B — Controlled release preparation and rollback runbook

**Status:** PREPARATION ONLY / NOT DEPLOYED. ADR-004 remains unchanged. GOLD-01 limited owner decision is not deployment authorization.

## Immutable inputs
- GOLD-02B run 39315816446; review artifact 12217264711; exact candidate SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`.
- Approved public JSON SHA-256 `bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e`.
- Approved CBS CSV SHA-256 `ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6`.
- World Bank source SHA-256 `ea1c350827878ea3bbe30e3cda16a13fd3bd5b409b8458940dc94a36b5a33154`; ECB source SHA-256 `95fb4ccee80310cb2c91e7fce988ffeee6498df71b21d37912487bf71c5d82b7`. No source download is permitted during GOLD-03.
- GOLD-02B was merged on main at `2069a4fea4b528300916967719a21ea15683c9b8`.

## Preparation / no release
1. The read-only GOLD-03 workflow downloads **only** the named GOLD-02B review artifact, verifies the candidate bytes against the pinned SHA-256 and checks approved baseline hashes.
2. `tools/gold_03_preflight.py` checks all 320 months, both approved indicators, JSON-v1 schema, CBS invariants, null raw gold field, Jan 2000 basis, then copies **exact candidate bytes** to a temporary preview; it never invokes external APIs or gold calculations.
3. The isolated rollback test restores exact pre-release public JSON bytes and verifies its SHA-256. Outputs include preview, rollback snapshot, diff, manifest. No public files are changed.
4. Frontend build and Python regression suite must pass on exact feature-branch HEAD.
5. **Open release blocker:** GOLD-02B Actions artifacts expire. The current workflow has an exact artifact dependency and fails closed if it expires. Before any release approval, copy the already validated **derived** candidate and audit evidence into a durable, access-controlled, immutable release store, record its object version, retention and SHA-256; do not store or redistribute raw World Bank/ECB bytes. A durable pin has not yet been established.

## Future activation — separate authorization required
1. Record separately authorized owner approval referencing the exact candidate SHA, deployment target and reviewed preflight run.
2. Verify the durable candidate and rollback snapshot hashes; record actual currently deployed commit and deployment ID from the deployment provider. **A main commit is not evidence of a deployed commit.**
3. Apply only the reviewed candidate bytes via the repository's protected publication/deployment path. Never fetch new gold/FX/CBS source data or regenerate gold indicators during activation.
4. Verify live served JSON hash and chart behavior (gold index, grams per house, attribution and June 2025 definition notice). If any check fails, halt and roll back.
5. Restore the exact saved pre-release JSON and the actual pre-release deployed commit through the protected deployment path; do not refetch or recalculate data. Verify served JSON SHA equals the recorded rollback hash and inspect CBS/HPI fields and frontend charts.
6. Record actor, approval, deployed and rollback commits, deployment IDs, source artifacts, hashes and timestamps.

**Fail closed** if any artifact is missing/expired, hashes disagree, the actual deployed commit is unknown, or the protected deployment procedure cannot restore exact bytes. No release or rollback operation is authorized by this runbook alone.
