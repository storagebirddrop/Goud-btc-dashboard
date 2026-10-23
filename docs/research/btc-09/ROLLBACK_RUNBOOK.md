# BTC-09 — Rollback runbook (operator: Project Control / designated engineer)

Rollback target (pinned in the release record, `rollback_ref`): the legacy gold/CBS payload with SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`, state `LEGACY_GOLD_CBS_NO_BTC`. No new architecture: static JSON + static frontend on Cloudflare Pages.

## Before any release (record these)
1. Current production deployment id and commit; `sha256` of the live `/data/monthly.json` (expect `1afb0bf9…91d8cd`); the frontend commit; the release record id and composite SHA-256; the snapshot id; the previous deployment id (Cloudflare Pages keeps prior deployments).
2. `python -m tools.btc_09_distribution_check state --json <live-json>` → ok (this is the exact state a rollback must restore).

## Rollback (two independent levers; do either, then verify)
A. Frontend lever (fastest): redeploy the previous Pages deployment, or revert the release commit (restores `BTC_APPROVED_COMPOSITE_SHA256=[]`). With an empty pin list the page shows no Bitcoin even if the new JSON is still served.
B. Data lever: restore `frontend/public/data/monthly.json` to the pinned legacy bytes (`git revert` of the release commit, never a hand edit); redeploy.

## Post-rollback validation (all must hold)
1. `python -m tools.btc_09_distribution_check state --json <fetched live json>` → ok (sha `1afb0bf9…`, no Bitcoin keys, pin list empty, registry empty).
2. `python -m tools.btc_09_distribution_check dist --dist frontend/dist` on the rebuilt output → ok.
3. In a clean browser profile: no Bitcoin text, series or control; gold and CBS charts render; no console errors.
4. Cache: repeat the header check from FRONTEND_DISTRIBUTION_REPORT from two locations; purge if an old etag is served.
5. `bc.rollback_target_ok(record, live_bytes)` → true.

## Failure simulations (tested with SYNTHETIC payloads only)
- Release then rollback restores exact legacy state and hides Bitcoin; a truncated/partial restore is rejected (`tests/test_btc_09_preflight.py`). Mixed vintages (second snapshot) and tampered records are refused (`tests/test_btc_08b_release_contract.py`). Wrong or stale bytes show no Bitcoin (browser B10/R04).
- NOT EXECUTED: an actual production rollback (not authorized).
