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
