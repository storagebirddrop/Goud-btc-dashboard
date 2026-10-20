# Data-quality gates

The published dataset is checked before each deployment and refresh.

## Automated guarantees
- Source CSV has exactly `date,series,value` columns.
- Every month from 2000-01 to the latest published month exists exactly once for **both** CBS measures.
- No duplicate observations, unsupported series, invalid month strings, NaN, infinity, zero or negative housing values.
- Public JSON has the exact expected schema and matches the deterministic CSV exporter, including the normalized HPI index.
- Gold fields remain null in the committed public JSON until a release is separately approved (owner decision GOLD-03, 2026-10-20, lifted the HOLD for `gold_index` and `gold_grams_per_house` only); `gold_eur_oz` stays null.
- CI checks the **committed** CSV and JSON, not only generated temporary fixtures.
- The scheduled refresh checks generated CSV/JSON consistency before committing and pushing.

## What these tests do NOT prove
- The CBS source itself is correct, or values have not been revised upstream.
- Historic gold/Bitcoin prices are accurate; neither series is imported yet.
- Completeness of future pre-2000 historical sources, licensing, currency conversion or source overlap.

Before importing each new source, add tests for provenance, coverage, currency, units, independent reference points, revision detection and source-specific aggregation. No fabricated missing months or forward-filling.

## Commands
```sh
python -m pytest -q
python -m etl.data_quality --input data/cbs-housing.csv --output frontend/public/data/monthly.json
```
