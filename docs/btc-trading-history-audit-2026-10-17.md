# BTC source decision and trading-history audit — 2026-10-17

## Verified evidence

- Trading source: [storagebirddrop/script-trading-anlytics](https://github.com/storagebirddrop/script-trading-anlytics), default branch `master`, `data/history.csv`.
- Collection method: `backfill_historical.py` uses Yahoo Finance through `yfinance` for `BTC-USD` and `EURUSD=X`; `START_DATE=2010-01-01` does **not** imply BTC coverage since 2010.
- Verified run: [trading BTC history audit #39050246824](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824), job 117447184267, succeeded.
- BTC/USD `1d`: **4,409** unique positive finite observations, **2014-09-17 through 2026-10-12**, **zero** missing calendar days and **zero** malformed/duplicate records.
- EURUSD `1d`: **4,368** unique observations, **2010-01-01 through 2026-10-12**; **1,761** missing calendar days across its entire span. FX does not trade every calendar day.
- Same-day BTC and EURUSD overlap: **3,142** days. BTC days without same-day FX: **1,267**.
- Audit status: `audit_only`; `publication_approved=false`. Report contains aggregate metadata only; source prices are not copied into dashboard outputs.

## Decision

**Candidate primary historical BTC source:** existing trading repository BTC/USD daily **close** series, beginning 2014-09-17. This is a candidate, not a publication authorization or a finalized pricing methodology.

**Earlier years:** 2010 through 2014-09-16 require a separately validated historical source if included. Do not assume zero BTC value, extrapolate, or silently splice providers.

**FX:** Yahoo `EURUSD=X` is USD per EUR. Convert each BTC/USD daily close using `BTC_EUR = BTC_USD / EURUSD` for an explicitly matched date. Never multiply by EURUSD or convert a monthly BTC/USD average using one monthly FX value. **No weekend/holiday carry-forward rule has been approved.** Quantify FX gaps and evaluate a licensed, documented FX source/policy before publishing EUR-denominated BTC series.

**Aggregation:** BTC daily closes are not daily mean prices or standardized reference rates. A monthly mean of daily closes must be labelled accordingly. Keep 100% calendar-day coverage as the default gate, unless an explicit documented alternative is approved.

**Licensing:** Yahoo Finance/yfinance collection does not itself grant redistribution rights. Do not publish raw or derived BTC prices without reviewing applicable source terms and permissions.

## GitHub Actions organization

Keep production and CBS workflows intact. Use **Audit existing trading BTC history** as the active read-only BTC coverage audit. Retire the redundant Coin Metrics **catalog probe** workflow from the Actions menu; its Python adapter, tests and validation notes remain for historical reference. Keep **Bitcoin historical backfill (validation only)** and **CoinGecko BTC API smoke test (read-only)** as manual, non-production research tools for independent verification. No BTC price publishing job is enabled.

## Next acceptance gates

1. Approve FX weekend/holiday policy and dated source; measure coverage after conversion.
2. Document daily close semantics and validate monthly aggregation.
3. Investigate 2010–2014 historical BTC availability separately.
4. Confirm redistribution and attribution rights for any public dashboard data.
5. Run independent anchor-date crosschecks, fixture tests, and CI before enabling any public output.
