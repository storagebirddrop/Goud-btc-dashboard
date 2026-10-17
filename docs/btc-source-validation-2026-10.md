# BTC source validation: October 2026

**Status: research only; no BTC data approved for publication.**

## Confirmed from provider documentation

| Provider | Finding | Consequence |
| --- | --- | --- |
| Coin Metrics Community | API v4 supports unauthenticated `community-api.coinmetrics.io` requests and publishes daily reference-rate metrics. Community access is described as non-commercial under Creative Commons terms. | Verify the exact license, attribution and whether publicly redistributed monthly aggregates are allowed before publishing. |
| Coin Metrics | Daily reference-rate series are documented, but catalog availability is metric/asset-specific. | Query the live catalog for BTC `ReferenceRateEUR` and `ReferenceRateUSD` min/max dates before attempting a historical backfill. |
| CoinGecko Demo | Market-chart history is limited to the past year on the free Demo tier, with automatic granularity. | Do not use Demo as the full-history source. Its sampled intraday observations are not equivalent to Coin Metrics reference-rate fixings. |

## Evidence

- https://docs.coinmetrics.io/api/v4/
- https://github.com/coinmetrics/docs-website/blob/master/api.md
- https://github.com/coinmetrics/product-docs/blob/master/docs/market-data/reference-rates-overview/reference_rate.md
- https://www.coingecko.com/learn/coingecko-api-troubleshooting-guide-and-solutions

## Mandatory validation sequence

1. **Live catalog check:** confirm availability of BTC/EUR and BTC/USD daily reference-rate metrics and record the earliest and latest dates; do not assume historical coverage.
2. **Live sampling:** use the existing read-only GitHub Actions backfill workflow for a recent full calendar month and representative historical months; preserve the coverage report artifact.
3. **Timestamp and fixing:** verify UTC timestamp interpretation and daily rate construction from provider methodology and real responses.
4. **Cross-source comparison:** compare overlapping dates against CoinGecko, acknowledging different fixing/sampling conventions; record deviation, sample timestamps and missing dates.
5. **License review:** record applicable Creative Commons license version, attribution, restrictions on commercial use and redistribution of derived data; obtain permission if needed.
6. **Release gate:** only after steps 1–5 and CI approval may a separate PR add a historical BTC public export. Keep current null asset values until then.

No price observations or API credentials are stored in this document.
