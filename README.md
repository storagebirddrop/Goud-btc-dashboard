# Goud & Bitcoin Dashboard

Historical purchasing-power comparisons of gold and Bitcoin against Dutch housing prices, CPI, and fuel prices.

**Status:** early development; not production-ready. The initial scope is **gold versus Dutch house prices**, monthly from January 2000, displayed in EUR. Bitcoin, CPI, fuel, USD and historical NLG conversions are future work.

## Project governance

The authoritative version-controlled governance framework is [AGENTS.md](AGENTS.md) and the [governance document hierarchy](docs/governance/DOCUMENT_HIERARCHY.md). [Decisions](docs/governance/DECISIONS.md) are normative only when explicitly marked `DECIDED`; technical documentation and historical audits are preserved separately. [Conflict matrix](docs/governance/CONFLICT_MATRIX.md) tracks unresolved discrepancies. Open PRs do not constitute approval.

## Repository structure

- `frontend/` — React/Vite UI loading static JSON from Pages
- `etl/` — CBS API ingestion, historical CSV validation, static JSON generation; legacy SQL tooling retained
- `db/migrations/` — optional legacy Cloudflare D1 schema (not needed for static deployment)
- `tests/` — Python ETL tests
- `.github/workflows/ci.yml` — pull request checks; no deployment

## Local checks

Python 3.12:

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

Node.js 22:

```sh
cd frontend
npm install
npm run build
```

The frontend lockfile is committed. Use `npm ci` for reproducible dependency installation in CI and locally.

## Data format

Supply reviewed, licensed CSV files with columns `date,series,value`. See [data/README.md](data/README.md) and [methodology](docs/methodology.md). Example:

```csv
date,series,value
2000-01,nl_hpi,100
2000-01,nl_house_avg_eur,150000
2000-01,gold_eur_oz,280
```

Example values above are illustrative, **not historical facts**.

To generate a local SQL import:

```sh
python -m etl.main --input data/validated.csv --output data/upsert.sql
```

This does **not** import to D1. The SQL is generated locally and excluded from Git.

## Deployment

The preferred deployment is Git-integrated **Cloudflare Pages without D1**. See [static data pipeline](docs/static-pipeline.md). The legacy D1 binding remains commented out. Source attribution, licensing and data QA must be reviewed before public launch.

## Contribution and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are proposed via feature branches and reviewed pull requests. No secrets or generated datasets in Git.
