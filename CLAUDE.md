# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Governance comes first

[AGENTS.md](AGENTS.md) is the binding operating instruction for agents (written in Dutch) and takes precedence over defaults. This file only summarizes it; if they ever disagree, AGENTS.md wins. Key points:
- Classify every change by **semantic impact** as GROEN / ORANJE / ROOD ([CHANGE_CONTROL.md](docs/governance/CHANGE_CONTROL.md)). ROOD covers changes to economic definitions, price/time aggregation, source priority, scope, publication meaning, historical data replacement, and security boundaries. For ROOD, research and propose only. Make no substantive change until the owner decides.
- Only items marked `DECIDED`/`ACCEPTED` in [DECISIONS.md](docs/governance/DECISIONS.md) are normative. `PROPOSED` is never a decision, and `VERIFIED_REPO` claims in docs do not prove anything about the current HEAD. See [DOCUMENT_HIERARCHY.md](docs/governance/DOCUMENT_HIERARCHY.md).
- Data integrity: no silent interpolation, forward-fill (including FX weekend/holiday carry-forward), backfill, source switching, or FX assumptions. Missing data stays `null`. Never invent values.
- Work on a task branch and open a PR. Merge only with explicit, prior delegation. Do not merge PR #40 silently. Final reports follow the AGENTS.md format (max 12 lines, `NIET UITGEVOERD` where evidence is missing).
- Documentation languages are mixed. `AGENTS.md` and the core governance documents (DECISIONS, METHODOLOGY, CHANGE_CONTROL, DOCUMENT_HIERARCHY, …) are Dutch. `README.md`, most technical docs under `docs/`, and several governance records (DATA_01_*, GOLD_02_RELEASE_CHECKLIST, BRANCH_PROTECTION_CLOSURE) are English. Keep the existing language of the file you edit, and do not translate documents as a side effect.

## Commands

Python 3.12 (stdlib + `requests`, `pytest`):

```sh
python -m pip install -r requirements.txt
python -m pytest -q                                   # full offline suite
python -m pytest -q tests/test_static_export.py       # one file
python -m pytest -q tests/test_static_export.py -k name   # one test
python -m etl.data_quality                            # verify committed CSV ↔ public JSON parity
python scripts/check_governance_docs.py               # governance inventory + relative-link check
```

Live-network tests are skipped unless an env flag is set (for example `CBS_LIVE_TEST=1`). They run in dedicated workflows, not in CI.

CI (`.github/workflows/ci.yml`) also runs an offline CBS replay. It must leave public files untouched:

```sh
python -m etl.cbs_historical_update --live-csv data/cbs-housing.csv --output-dir /tmp/out
python -m etl.data_quality --input /tmp/out/candidate.csv --output /tmp/out/candidate.json
git diff --exit-code -- data/cbs-housing.csv frontend/public/data/monthly.json
```

Frontend (Node 22):

```sh
cd frontend && npm ci && npm run build   # tsc -b && vite build; `npm run dev` for local server
```

There is no linter or formatter configured.

## Architecture

Decided runtime (ADR-001): GitHub Actions → validated CSV → deterministic static JSON → React/Vite → Cloudflare Pages. **No D1 in production.** `etl/main.py`, `etl/d1_import.py`, `db/`, and `frontend/functions/api/monthly.ts` are legacy D1 code that is kept but unused by the UI.

Data flow:
- `etl/sources/cbs.py` fetches CBS OData v4 table 85773NED (`nl_hpi`, `nl_house_avg_eur`). The committed provenance snapshot is `data/cbs-housing.csv` (`date,series,value`). The public data covers 2000-01 onward. Pre-2000 history (1995–1999, house price only, no HPI) exists only in the pinned fixture `data/fixtures/cbs-1995-1999-i1*.json`, which the review-only update pipeline merges into a 380-month candidate. It is not published.
- `etl/static_export.py` `build()` turns the CSV into `frontend/public/data/monthly.json` (`{"data":[{period, gold_eur_oz, house_eur, hpi, gold_grams_per_house, gold_index, hpi_index}]}`). It is strict: exact columns, no gaps or duplicates, positive finite values, and `hpi_index` based on 2000-01 = 100.
- `etl/data_quality.py` re-runs `build()` and requires the parsed committed JSON to equal its output exactly. Any change to the CSV, the export logic, or the JSON must keep all three consistent. Gold fields must be `null` in the committed JSON.
- The frontend (`frontend/src/main.tsx`, single file) fetches `/data/monthly.json` and charts one metric with Recharts.

Fail-closed, review-only pipelines. These produce workflow artifacts and must not change public files:
- `etl/cbs_historical_update.py` and `etl/cbs_historical_merge.py` build CBS update candidates. They pin SHA-256 hashes of the baseline CSV, JSON, and fixture. A changed overlap with existing months counts as a source revision that needs human approval. If you intentionally change committed data, those pinned hashes (also in `etl/gold_publication_candidate.py`) must change too, and that is not a GROEN change.
- Gold (GOLD-01/02): `etl/gold_monthly.py` computes monthly World Bank USD/oz ÷ monthly-mean ECB USD/EUR (ADR-004, Decimal math). `etl/gold_publication_candidate.py` and `etl/gold_02_release.py` build review bundles. Publishing gold into the JSON requires env `GOLD_PUBLICATION_ENABLED=true`, `GOLD_PUBLICATION_APPROVAL=APPROVED`, `--approve-gold-publication`, and a validated candidate (`validate_gold`). Raw gold/FX data is never committed.
- BTC (`etl/sources/coinmetrics.py`, `coingecko.py`, `etl/trading_history_audit.py`, `etl/btc_fx_calendar_audit.py`, `tools/data_01_*`): research and validation only, with no public BTC export.

Most `.github/workflows/*` other than `ci.yml` are manual or scheduled review workflows that upload artifacts and never commit. `update-static-data.yml` is likewise review-only.

## Gotchas

- `tests/test_governance_docs.py` runs `scripts/check_governance_docs.py`. It fails on broken relative Markdown links in `AGENTS.md`, `README.md`, `docs/next-phase.md`, and `docs/governance/*.md`, and when the DECISIONS.md table rows for ADR-004/007/008/009 stop containing `PROPOSED`. Editing those docs can break `pytest`.
- `docs/next-phase.md` still mentions staging D1. That text is outdated (see ARCHITECTURE.md §6).
