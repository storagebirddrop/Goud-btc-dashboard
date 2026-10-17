# BTC daily price methodology and publication gate

Status: **PROPOSED / NOT APPROVED FOR PUBLICATION**.

## Current provider semantics

- **Coin Metrics Community**: requests the provider's `ReferenceRateEUR` or `ReferenceRateUSD` at frequency `1d`. The adapter treats the API's date label as a UTC day. The precise reference-rate construction, entitlement and historical coverage require live/provider verification.
- **CoinGecko market_chart/range**: selects the **earliest available UTC timestamp** for each UTC calendar date. This is a sampled price, **not necessarily a midnight fixing, close or daily average**. It can differ from Coin Metrics even on the same date.
- Neither series is production-connected. Do not splice or substitute one provider for the other without an explicit methodology decision and comparison.

## Aggregation and missing data

- Default monthly price is the arithmetic mean of validated daily EUR-denominated observations, only for complete calendar months (100% coverage).
- Missing requested dates, including leading/trailing dates, must be reported. No forward fill, interpolation, silent truncation or replacement with zeros.
- A missing historical BTC observation is not equivalent to a zero price. Distinguish pre-market/no-trading, provider-unavailable and missing-provider-data in any future public schema.
- For USD quotes, convert **each dated observation** using a matched dated FX rate before monthly aggregation. Never convert a USD monthly mean using an arbitrary single FX quote.
- Housing-to-BTC is `house_eur / btc_eur`; satoshis are `house_eur / btc_eur * 100000000`. Both require aligned month and valid provenance.

## Release gate

1. Confirm provider timestamps and reference-rate construction using official documentation and representative live responses.
2. Check historical availability, pagination, rate limits, licensing and redistribution rights.
3. Compare overlapping anchor dates from independent sources, documenting differences and outliers.
4. Require complete calendar coverage for published monthly values, or explicitly approve and label an alternative.
5. Run CI and inspect actual workflow conclusions before merge.
6. No historical BTC public export until these gates are evidenced and approved.
