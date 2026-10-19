# DATA-01A — BTC source and methodology decision matrix
**PROPOSED / NO PUBLICATION AUTHORIZATION.** ADR-010 prioritizes trading history as a research candidate; ADR-007 was superseded for research priority, not for cross-source verification. ADR-004 BTC methodology remains unapproved.

| Candidate | Price semantics | Quote/FX | Coverage and access evidence | Revisions, licensing and key risks | Decision |
|---|---|---|---|---|---|
| Trading analytics / Yahoo `BTC-USD` daily `Close` | Exchange-aggregated vendor daily close; precise cutoff/timezone must be verified | USD/BTC; `EURUSD=X` is USD/EUR; divide **each same-day** USD BTC close by USD/EUR before monthly aggregation | Prior repository audit run 39050246824: 4,409 BTC days 2014-09-17..2026-10-12; 1,267 BTC days without same-day FX; upstream checkout currently `master` mutable | Yahoo/yfinance derived-data redistribution unapproved; vendor-adjustment/correction possible; 2010–2014 gap; weekend/holiday FX unresolved | **PROPOSED preferred historical research candidate only** (ADR-010) |
| Coin Metrics Community `ReferenceRateUSD` / `ReferenceRateEUR` `1d` | Provider daily reference-rate fixing, not Yahoo close; precise UTC fixing must be verified | Direct EUR if available; otherwise USD + separately approved FX | Adapter, catalog and manual backfill exist; historical BTC/EUR entitlement/availability must be checked live | Community terms/non-commercial restrictions; historical metric catalog gaps, pagination, reference-rate methodology revisions | **PROPOSED independent price anchor**, alternative source only after approval |
| CoinGecko Demo `market_chart/range` | Earliest observed UTC timestamp/day in adapter, **not** daily close or standard fixing | EUR/BTC or USD/BTC returned | Manual smoke; Demo historical lookback/automatic granularity prevents unverified full-history use | Rate limits, plan-dependent history, sampled timestamp drift, attribution and reuse terms | **PROPOSED recent crosscheck only** |

## Explicit policy choices requiring owner approval
1. **Price fixing:** choose and document Yahoo daily close vs provider reference-rate fixing, exact UTC cutoff/timezone and whether monthly arithmetic mean of 100%-covered daily closes is accepted. Do not label sampled CoinGecko ticks as closes.
2. **FX:** prefer direct licensed EUR/BTC daily series if independently verified, **or** define matched-date USD-per-EUR FX source and weekend/holiday handling. No fill/nearest-business-day assumption until decided. Without a rule, USD daily series cannot yield a complete EUR monthly BTC series.
3. **History:** choose coverage start (2014-09-17 trading source, or separate validated pre-2014 source) and explicitly prohibit silent splicing. Missing months remain missing, not zero.
4. **Rights:** document contractual entitlement, public display, redistribution of derived monthly values, attribution and retention. Technical API access is not reuse permission.
5. **Revisions and anchors:** choose source version pinning, cross-provider comparison on overlap dates, tolerance and escalation. Different fixing definitions require labeled comparisons, not artificial exact equality.

## Recommended research sequence
Pin upstream trading CSV to exact commit+SHA, validate full daily coverage and timestamp semantics; run read-only Coin Metrics catalog and independent anchor dates; examine CoinGecko recent samples as *different methodology*; quantify FX weekend and holiday gaps; seek license review; submit an explicit owner decision. Until then: **BTC publication BLOCKED**.

References: `docs/governance/DECISIONS.md` ADR-007/010; `docs/btc-price-methodology.md`; `docs/btc-source-validation-2026-10.md`; `docs/btc-trading-history-audit-2026-10-17.md`; `etl/sources/coinmetrics.py`, `etl/sources/coingecko.py`, `etl/trading_history_audit.py`.
