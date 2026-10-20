# Goud & Bitcoin Dashboard

Historical purchasing-power comparisons of gold and Bitcoin against Dutch housing prices, CPI, and fuel prices.

**Status:** early development; not production-ready. The initial scope is **gold versus Dutch house prices**, monthly from January 2000, displayed in EUR. Bitcoin, CPI, fuel, USD and historical NLG conversions are future work.

## Project governance

The authoritative version-controlled governance framework is [AGENTS.md](AGENTS.md) and the [governance document hierarchy](docs/governance/DOCUMENT_HIERARCHY.md). [Decisions](docs/governance/DECISIONS.md) are normative only when explicitly marked `DECIDED`; technical documentation and historical audits are preserved separately. [Conflict matrix](docs/governance/CONFLICT_MATRIX.md) tracks unresolved discrepancies. Open PRs do not constitute approval.

## Repository structure

- `frontend/` — React/Vite UI loading static JSON from Pages
- `etl/` — CBS API ingestion, CSV validation, static JSON generation
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
```

Example values above are illustrative, **not historical facts**.

The static JSON is generated and checked with `python -m etl.static_export` and `python -m etl.data_quality` (see [static data pipeline](docs/static-pipeline.md)).

## Deployment

Deployment is **Cloudflare Pages without D1 or Functions**: the dashboard reads only the static `/data/monthly.json`. See [static data pipeline](docs/static-pipeline.md). Source attribution, licensing and data QA must be reviewed before public launch.

## Contribution and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Changes are proposed via feature branches and reviewed pull requests. No secrets or generated datasets in Git.
