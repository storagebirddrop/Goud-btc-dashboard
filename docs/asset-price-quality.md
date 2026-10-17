# Price feed quality contract — gold and Bitcoin

This is a **pre-ingestion validation library**, not a live market data feed.

- Input records must specify ISO daily date, positive finite price, explicit asset (BTC/XAU), quote currency (EUR/USD/NLG), and a single named source.
- Reject duplicate days, invalid dates, mixed units/currencies/sources, NaN, infinity, zero and negative prices.
- Return missing calendar dates for inspection. Monthly aggregation defaults to **100% calendar-day coverage** and rejects partial months; lower coverage is only possible when the caller explicitly supplies a threshold.
- NLG conversion uses the exact fixed `2.20371 NLG/EUR`. USD prices require an independently verified dated EUR-per-USD exchange rate; there is no implicit spot FX fallback.
- Gold prices use EUR per **troy ounce** (31.1034768 g), Bitcoin uses EUR per BTC (100,000,000 sats/BTC).
- Compare independent sources with a configurable relative deviation tolerance (5% default). Do not silently smooth or replace conflicting observations.
- These tests prove **internal consistency**, not provider authenticity or redistribution permission.

## Before publishing live asset prices
1. Verify each provider's documented history, definitions, licensing and redistribution permissions.
2. Add a read-only adapter and record source URL, observation time, original units, and revision/version.
3. Confirm a set of historical reference points independently, including the oldest and newest dates and market-regime changes.
4. Align housing and asset prices to the same time period and document arithmetic mean versus period-close aggregation.
5. Add source-specific fixture tests and a live smoke test before committing public JSON.
