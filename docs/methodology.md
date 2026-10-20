# Data methodology and acceptance criteria

## Initial scope

Monthly observations from January 2000 onward, in EUR. Initial series:

- `gold_eur_oz`: **ADR-004 ACCEPTED (2026-10-18):** World Bank Pink Sheet GOLD monthly mean USD/troy ounce divided by the monthly arithmetic mean of available valid daily ECB USD-per-EUR rates. This is not the mean of daily EUR gold prices. London afternoon fixing through May 2025; mean daily spot prices from June 2025 (visible benchmark-break annotation required for public charts).
- `nl_house_avg_eur`: CBS average existing-home transaction price; changes in sold-home composition affect this series.
- `nl_hpi`: CBS/Kadaster existing-home price index; changes in index base and revisions must be handled explicitly.

## Calculations

- Gold grams needed to buy an average house = `house_eur / gold_eur_oz × 31.1034768`.
- Indexed gold = `100 × gold_eur_oz[m] / gold_eur_oz[2000-01]` (fixed January 2000 base).
- Indexed house price index = `100 × hpi / first available hpi`.

**Important:** independently rebasing on each series' first observation can produce misleading comparisons when start dates differ. Before production, require a *shared reference month* where both series have valid values. Gold methodology is approved but public gold publication remains disabled pending separate rights and activation decisions; BTC and CPI methodology remain subject to separate approval.

## Data provenance requirements

For every source record: publisher, series/table ID, URL, licensing/terms, publication timestamp, frequency, unit, currency, observation calendar, and revisions. Do not infer missing months, treat forward-filled data as observed, or silently mix nominal and real prices.

For gold, use the approved ADR-004 monthly ECB USD-per-EUR mean from available valid daily rate observations in the same month, then divide the World Bank monthly USD gold mean by that FX mean. No forward-fill, interpolation or synthetic observations. Missing historical months block; trailing unpublished source months remain pending. For other assets, daily matching rules are not approved by this gold-only ADR.

## Release gates

1. Confirm exact source identifiers and reuse terms.
2. Document monthly aggregation and time zone.
3. Validate missing months, duplicates, non-finite values, and implausible outliers.
4. Align index base dates and document index rebasing.
5. Check sample months manually against source publications.
6. Run the static export and `python -m etl.data_quality` on the committed CSV/JSON.
7. Require passing CI, reviewed dependency lockfile, and approval before merging.
8. Enable production credentials and scheduled ETL only in a separate reviewed change.

## Gold-specific approval boundary (2026-10-18)
Canonical decision: [ADR-004 in DECISIONS.md](governance/DECISIONS.md). The approved gold methodology does not clear World Bank GOLD third-party rights or authorize public gold values; `gold_eur_oz`, `gold_index`, and `gold_grams_per_house` remain null until separately approved. This document is descriptive, not an independent ADR.
