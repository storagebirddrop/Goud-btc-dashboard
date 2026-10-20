# Cloudflare deployment plan

> **LEGACY / SUPERSEDED - do not provision.** Under ADR-001 (`DECIDED`) the runtime is GitHub Actions + static JSON + Cloudflare Pages, **without D1 in production**. Do not create a D1 database or a `DB` binding in the Pages project, and do not set `LEGACY_D1_API_ENABLED`. The current deployment plan is in [static-pipeline.md](static-pipeline.md). The Pages Function `frontend/functions/api/monthly.ts` is retained legacy code: it answers 404 unless `LEGACY_D1_API_ENABLED=true` and never returns gold values (the gold publication gate must not be bypassed). The runbook below is kept for history only.


This project has **no Cloudflare account credentials, D1 binding, or deployed site** yet. The following commands are a runbook, not actions already performed.

## 1. Provision D1

Create a D1 database named `gold-housing` in your Cloudflare account. Add the actual database ID to the `[[d1_databases]]` section in `frontend/wrangler.toml`, binding name `DB`. Do not invent or commit credentials.

## 2. Local smoke test

From `frontend/`, run `npx wrangler d1 migrations apply gold-housing --local --migrations-dir ../db/migrations` and optionally import `db/seed/demo.sql` into **local** D1 only. These observations are synthetic and must never be deployed as production data.

## 3. Deploy separately

After a reviewed deployment PR, configure Cloudflare Pages build directory `frontend/dist`, project root `frontend`, and the D1 binding `DB`. Ensure Pages Functions can read D1. Use Cloudflare-managed API tokens/secrets with least privilege. No scheduled production import until data provenance and QA are complete.

## Release requirements

- Verify actual D1 migrations on local and staging databases.
- Test API output with synthetic fixture data.
- Record exact gold quote, FX and CBS source identifiers and licenses.
- Never seed synthetic data into production.
- Verify branch protection, CI, and deployment permissions.
