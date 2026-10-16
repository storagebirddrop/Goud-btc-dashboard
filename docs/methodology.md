# Data methodology and acceptance criteria

## Initial scope

Monthly observations from January 2000 onward, in EUR. Initial series:

- `gold_eur_oz`: monthly arithmetic mean of available daily EUR prices per troy ounce, **only after the quote type and observation calendar have been selected**.
- `nl_house_avg_eur`: CBS average existing-home transaction price; changes in sold-home composition affect this series.
- `nl_hpi`: CBS/Kadaster existing-home price index; changes in index base and revisions must be handled explicitly.

## Calculations

- Gold grams needed to buy an average house = `house_eur / gold_eur_oz × 31.1034768`.
- Indexed gold = `100 × gold_eur_oz / first available gold_eur_oz`.
- Indexed house price index = `100 × hpi / first available hpi`.

**Important:** independently rebasing on each series' first observation can produce misleading comparisons when start dates differ. Before production, require a *shared reference month* where both series have valid values. The current dashboard is a scaffold, not an approved analytical result.

## Data provenance requirements

For every source record: publisher, series/table ID, URL, licensing/terms, publication timestamp, frequency, unit, currency, observation calendar, and revisions. Do not infer missing months, treat forward-filled data as observed, or silently mix nominal and real prices.

If converting USD gold to EUR, use date-matched USD-per-EUR ECB rates, document non-trading days, and compute EUR price as USD price divided by USD-per-EUR. Do not convert a monthly USD mean using an arbitrary end-of-month exchange rate.

## Release gates

1. Confirm exact source identifiers and reuse terms.
2. Document monthly aggregation and time zone.
3. Validate missing months, duplicates, non-finite values, and implausible outliers.
4. Align index base dates and document index rebasing.
5. Check sample months manually against source publications.
6. Test migration and API with seeded D1 data.
7. Require passing CI, reviewed dependency lockfile, and approval before merging.
8. Enable production credentials and scheduled ETL only in a separate reviewed change.
