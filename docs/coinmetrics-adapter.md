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

## Manual historical backfill verification
The workflow `.github/workflows/bitcoin-backfill.yml` can be started manually with a UTC start/end date and EUR/USD quote currency **after merging the branch**. It is intentionally read-only and writes only an artifact containing counts, missing dates and failure reasons, not actual prices. No schedule, repository write permission or public JSON modification.

Suggested first test: 2011-01-01 through 2011-01-31 EUR; a failed run may mean Coin Metrics does not have coverage in that interval, not necessarily a software defect. Follow with verified supported dates, then split longer history into manageable windows. A complete backfill that can be published remains a separate, licensing-gated feature.
