# Goud & Bitcoin Dashboard

Historical purchasing-power comparisons of gold and Bitcoin against Dutch housing prices, CPI, and fuel prices.

**Status:** early development; not production-ready. The initial scope is **gold versus Dutch house prices**, monthly from January 2000, displayed in EUR. Bitcoin, CPI, fuel, USD and historical NLG conversions are future work.

## Repository structure

- `frontend/` — React/Vite UI and Cloudflare Pages Function API
- `etl/` — CSV validation and SQL generation (no remote writes)
- `db/migrations/` — Cloudflare D1 SQLite schema
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

The frontend currently uses `npm install` as a bootstrap step because no reviewed `package-lock.json` has been committed. **Before merging**, generate and commit the lockfile and switch CI to `npm ci`.

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

Cloudflare Pages and D1 have not been configured. The D1 binding in `frontend/wrangler.toml` is intentionally commented out. Do not enable deployment or scheduled writes until provenance, licensing, data QA, and secrets are reviewed.

## Contribution and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are proposed via feature branches and reviewed pull requests. No secrets or generated datasets in Git.
