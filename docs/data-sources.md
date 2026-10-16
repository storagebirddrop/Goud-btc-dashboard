# Historical source registry (pending verification)

**Do not ingest live data until exact series identifiers, terms of use, and transformation logic are reviewed.**

| Series | Proposed publisher | Required identification | Method |
| --- | --- | --- | --- |
| Dutch existing-home price index | CBS / Kadaster | Exact CBS StatLine dataset and price-index field | Monthly, preserve/rebase source index as documented |
| Dutch average existing-home transaction price | CBS | Exact CBS dataset, field, transaction population | Monthly EUR, not quality-adjusted |
| Gold | Documented gold benchmark/market data provider | Exact daily fixing/spot field, quote time, license | Daily quote USD/troy oz, then FX conversion, then monthly mean |
| EUR/USD | ECB Data Portal | Exact exchange-rate key and observation calendar | Match gold dates; document holiday treatment |

## Acceptance rules

- Verify that the source allows redistribution/display in this dashboard.
- Record source table IDs, revisions, dates, coverage and URLs in a source manifest.
- Do not claim a 2000-starting gold EUR history until source and FX data are validated.
- Reject duplicates, missing or nonpositive values, non-finite numbers and future dates.
- Align common base months before interpreting indexed relative performance.
- Distinguish the average house sale price from the quality-adjusted price index.

The CSV validation code checks input structure, ranges and duplicates. It does not establish the truth or licensing of submitted data.

## Verified identifiers for adapter development

- CBS national existing-home series: [85773NED](https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table). Verify exact OData fields and category codes before ingesting.
- ECB USD per EUR: [EXR.D.USD.EUR.SP00.A](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A). The adapter in `etl/sources/ecb.py` downloads daily quotes to a local CSV only.
- Convert same-date gold USD per ounce to EUR per ounce by **dividing** by USD per EUR. Do not invert the rate.
- Gold data provider and redistribution rights remain unverified. No production data is loaded.
