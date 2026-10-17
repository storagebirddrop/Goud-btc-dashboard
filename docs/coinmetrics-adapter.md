# Coin Metrics read-only adapter

`etl/sources/coinmetrics.py` requests daily BTC reference rates in EUR or USD from the official Coin Metrics Community API. It validates API payloads, timestamps, currency, provenance, pagination, duplicates and missing calendar days.

**Not production-connected**: no API calls in the scheduled job, no committed BTC price data, and no frontend change. Network/API availability and complete historical coverage have **not yet been confirmed by an end-to-end live test**. The tests use deterministic fake responses.

Before publication:
1. Run an opt-in real API smoke test for the earliest available BTC/EUR history, sample recent dates and pagination.
2. Confirm endpoint semantics (UTC date, reference rate construction, historical availability, missing data).
3. Verify terms for public redistribution of the derived series and any rate limits.
4. Compare historical anchor points to an independent provider and log deviations.
5. Only then add a separate, gated export to public monthly JSON.

The default monthly aggregation rejects incomplete calendar months. A partial first or current month must be handled explicitly rather than silently averaged.
