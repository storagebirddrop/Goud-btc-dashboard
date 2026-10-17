# Static data pipeline (Cloudflare Pages, no D1)

The preferred runtime is **static**: GitHub Actions retrieves CBS 85773NED monthly history, commits `data/cbs-housing.csv` as the provenance-bearing historical snapshot and exports `frontend/public/data/monthly.json`. The React UI fetches `/data/monthly.json`; Vite copies `public/` into `dist/`. A Cloudflare Pages Git integration can publish on each push to `main`.

Run locally:

```sh
python -m pip install -r requirements.txt
python -m etl.sources.cbs --output data/cbs-housing.csv
python -m etl.static_export --input data/cbs-housing.csv --output frontend/public/data/monthly.json
python -m pytest -q
cd frontend && npm ci && npm run build
```

To refresh from GitHub, manually dispatch **Update static CBS dashboard data**, or let the Monday schedule run. Its first successful execution replaces the intentionally empty JSON placeholder. The workflow fails closed if CBS data is missing, incomplete or malformed; an unsuccessful run does not commit new data.

Set up Cloudflare Pages with this GitHub repo, production branch `main`, root directory `frontend`, build command `npm ci && npm run build`, output directory `dist`. **No D1 binding, Cloudflare API token, or scheduled remote database write required.**

Historical D1 code and tests are retained for now as optional legacy infrastructure; the UI does not use them. Gold/Bitcoin/CPI/fuel series require separate validated source pipelines; placeholders are `null`, never invented data. Review CBS attribution and data terms before public launch.
