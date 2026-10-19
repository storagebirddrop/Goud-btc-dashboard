# GOLD-02 release candidate

Status: PREPARATION ONLY. No live publication or deployment authorized.

## Required gates

1. Pin the exact main commit and approved CBS CSV and public JSON SHA-256 baselines.
2. Regenerate the isolated gold candidate with World Bank Pink Sheet and ECB observations, recording source response hashes, UTC run timestamp, and output artifact hash.
3. Verify contiguous 2000-01 onward coverage, 2000-01 index=100, formulas and no historical missing months. Any pending months must be trailing only.
4. Compare every CBS house_eur, hpi, hpi_index, and period against the approved public JSON, without accepting revisions.
5. Confirm public fields gold_index and gold_grams_per_house only; gold_eur_oz always null, no raw gold or FX inputs in public assets.
6. Run full Python tests, frontend build, static CBS smoke, and independent gold release checks. Reject changed baselines and failing checks.
7. Produce a reproducible review artifact with candidate monthly JSON, manifest, hashes, source versions, row counts, diff summary and rollback instructions. Keep it outside frontend/public.
8. Review visible World Bank, ECB, CBS attribution and June 2025 methodology change notice.
9. Require separate explicit owner sign-off on the exact candidate hash and deployment target before any public file changes or deployment.

## Rollback

Before deployment record the existing public JSON SHA-256 and deployed commit. Roll back to that exact reviewed public JSON and commit if live verification fails; do not recalculate a replacement from newly fetched sources during rollback.

The GOLD-01 owner decision permits the limited indicators but is not a GOLD-02 deployment authorization. ADR-004 and CBS fail-closed controls remain unchanged.

## GOLD-02 rollback runbook (review only)

Before any separately authorized release, record the **deployed** immutable commit, exact public `frontend/public/data/monthly.json` bytes and SHA-256, deployment identifier, and rollback operator approval. Keep the approved backup in controlled release storage (not a live source fetch).

If deployment verification fails, halt promotion, restore the **exact previously approved JSON bytes** and deployment commit from that immutable backup, redeploy the pinned commit using the normal protected release path, then verify its SHA-256 equals the pre-release approved checksum. Confirm the CBS CSV, HPI and JSON-v1 schema remain unchanged. Do not fetch World Bank, ECB or CBS during rollback; do not re-run ETL to reconstruct the prior JSON. Record incident, before/after hashes, deployment ID and reviewer sign-off. If the prior artifact/commit is missing or its hash differs, **BLOCKED**; do not substitute newly generated data.

GOLD-02 review bundle: `monthly.gold-release-review.json`, `manifest.json`, `diff.json` in an isolated Actions artifact. The artifact ID is allocated by GitHub **after** manifest generation and is therefore established by the workflow artifact record, not prefilled in the manifest. A PR-triggered Actions checkout uses a synthetic merge SHA; the manifest records the actual PR head through `GOLD02_SOURCE_SHA`.
