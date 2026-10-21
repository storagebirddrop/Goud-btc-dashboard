# BTC-01: methodology research for expressing the average Dutch house price in BTC and satoshi

Status: **research only, PROPOSED**. Not a decision, not legal advice. Nothing is approved or published. Bitcoin and satoshi stay `withheld`. ADR-004 (BTC part), ADR-007 and ADR-008 remain `PROPOSED`; ADR-010 only names the existing trading history a research candidate. No public data, ETL code, frontend, JSON or ADR status is changed by this document. Date of research: 2026-10-21.

Evidence labels (section 11): **CONFIRMED** = repo file or measurement in the repo; **ASSUMPTION**; **NOT VERIFIED**. Important limit: in this sandbox `WebFetch` failed for every host (`getaddrinfo ENOTFOUND`), so no provider page could be read as primary text. Every external fact below comes from a `WebSearch` summary of the cited URL and is tagged **NOT VERIFIED (S)**: secondary, to be re-read as primary text in BTC-02 (the GOLD-01 probe pattern, `docs/research/GOLD_01_RIGHTS.md`, does this via a CI runner).

## 1. Verdict summary

| Item | Proposal (PROPOSED) |
|---|---|
| Preferred research source | The ADR-010 candidate: `script-trading-anlytics/data/history.csv`, `BTC-USD` `1d` close (Yahoo). It is the only series with measured, gap-free coverage in the repo (4,409 days from 2014-09-17, zero missing). Rights are unresolved, see section 8. |
| Preferred independent cross-check and possible EUR-native alternative | Coin Metrics Community `ReferenceRateEUR` / `ReferenceRateUSD` `1d`. Its EUR availability and start date are NOT VERIFIED and must be measured first (BTC-02). If `ReferenceRateEUR` is complete it removes the FX-calendar problem entirely. |
| Fallback / recent-only check | CoinGecko Demo/public: 365-day lookback only, so a recent cross-check, never the history. |
| Monthly definition | Arithmetic mean of daily values over the calendar month, no imputation, same family as the accepted gold method. Two computation variants are specified in section 4; for a USD source the gold-parallel variant (V1: monthly mean of USD closes divided by monthly mean of ECB USD per EUR) needs no weekend/holiday FX policy. |
| Reliable start month | **2014-10** (first complete calendar month of the audited series; 2014-09 is partial and stays `null`). Earlier months stay `null` unless a second source is validated in BTC-02; no splice. |
| Readiness for BTC-02 | Ready as a measurement and review-bundle task. **Not ready for publication**: rights, price-definition and FX-policy decisions are open (section 10). |

## 2. Existing evidence in the repo (not repeated, only cited)

- **Method gate.** `docs/btc-price-methodology.md` ("Aggregation and missing data"): monthly price = arithmetic mean of validated daily EUR observations, 100% coverage by default, no forward fill; USD quotes converted per dated observation, never one FX value on a USD monthly mean. `house_eur / btc_eur` and `*100000000` for sats. Status PROPOSED.
- **Trading-history audit.** `docs/btc-trading-history-audit-2026-10-17.md` ("Verified evidence"): run 39050246824; BTC/USD 1d 4,409 unique positive observations 2014-09-17..2026-10-12, zero gaps; EURUSD 4,368 observations 2010-01-01..2026-10-12 with 1,761 missing calendar days; same-day overlap 3,142; 1,267 BTC days without same-day FX. Source is Yahoo via `yfinance` (`BTC-USD`, `EURUSD=X`), upstream branch `master` is mutable.
- **Source matrix.** `docs/governance/DATA_01_BTC_DECISION.md`: Yahoo = preferred historical research candidate; Coin Metrics = independent price anchor; CoinGecko Demo = recent cross-check only. Five owner policy choices listed (fixing, FX, history start/splice, rights, revision/anchor tolerance). Publication BLOCKED.
- **Provider validation.** `docs/btc-source-validation-2026-10.md`: Coin Metrics Community described as non-commercial under Creative Commons, exact licence/attribution/derived-data rights unverified; catalog min/max dates for BTC `ReferenceRateEUR` not yet recorded; CoinGecko Demo limited to one year.
- **Adapters.** `docs/coinmetrics-adapter.md`, `etl/sources/coinmetrics.py` (BASE_URL `community-api.coinmetrics.io/v4/timeseries/asset-metrics`, metrics `ReferenceRateUSD|EUR`, UTC date label, pagination, missing-date report), `etl/sources/coingecko.py` (earliest UTC timestamp per date, not a close). `.github/workflows/bitcoin-backfill.yml` is the manual metadata-only backfill (suggested first test 2011-01-01..2011-01-31 EUR; never run with a recorded result in the repo docs).
- **Quality library.** `docs/asset-price-quality.md`: reject duplicates, NaN, non-positive; 100% monthly coverage default; cross-source relative tolerance default **5%**; no implicit FX fallback; 100,000,000 sats per BTC.
- **Pinning.** `docs/governance/DATA_01B_SOURCE_PINNING.md` and `tools/data_01_source_pin.py`: SHA-256 over exact received bytes, content-addressed manifest, offline `replay`, `coinmetrics-btc-research` allowlisted but research-only; raw third-party bytes must not enter public Git/Releases/Artifacts (storage class B not configured). `docs/governance/DATA_01_UPDATE_CONTRACT.md`: append-first states, revision review, "BTC-specific hold".
- **Governance state.** `docs/governance/DECISIONS.md`: ADR-004 gold ACCEPTED, BTC PROPOSED; ADR-007 PROPOSED; ADR-008 PROPOSED; ADR-010 research candidate. `docs/governance/METHODOLOGY.md` section 2 and "Update v2.1": `btc_per_avg_sold_home = H/B`, `sats = H/B*1e8`, matched-day USD to EUR, no carry-forward approved. `docs/governance/CONFLICT_MATRIX.md`: FX weekend/holiday "red decision open"; BTC history before 2014-09-17 unconfirmed.
- **Gold baseline.** ADR-004 and `etl/gold_monthly.py`: `gold_eur_oz = mean(WB monthly USD/oz) / mean(valid ECB USD per EUR in month)`, Decimal math, no imputation, historical gap is an error, `pending_publication` is not a gap; `etl/static_export.py` `validate_gold` plus `GOLD_PUBLICATION_ENABLED`/`GOLD_PUBLICATION_APPROVAL` env gate. `fx_days` only has to be a positive integer (no minimum-days rule exists for gold).
- **Housing side.** `data/cbs-housing.csv`: `nl_house_avg_eur` 2000-01..2026-08 (320 months). `docs/research/HIST_05_CBS_DEFINITIONS.md` rows 1, 3, 8: average of existing dwellings sold to private buyers, based on Kadaster-registered notary transactions per month, registration moment is when the notary enters the deed.
- **Frontend.** `frontend/src/series.ts` already has `sat_per_house` with `publication:'withheld'`; withheld series are never shown whatever the JSON holds. `btc_per_house` has no registry entry yet.

## 3. Source comparison

Columns: coverage (first reliable month), EUR native, monthly frequency derivable, price definition, reproducibility (pinnable bytes), reliability/limits/cost, independent verifiability, attribution/ToS. All external cells are NOT VERIFIED (S) unless marked repo-CONFIRMED.

| Source | Coverage | EUR | Price definition | Reproducibility | Limits / cost | Rights text (as found) |
|---|---|---|---|---|---|---|
| **Yahoo `BTC-USD` via trading repo** (repo) | 2014-09-17.. (CONFIRMED, audit run 39050246824) | No; USD x ECB (or Yahoo `EURUSD=X`) | Vendor daily close, cutoff/timezone unverified | Pinnable CSV only if upstream is pinned to commit+SHA (now mutable `master`) | Free; vendor can adjust history | No redistribution grant found. Search result only reaches Yahoo general ToS and third-party commentary (https://legal.yahoo.com/us/en/frontier/terms/otos/index.html). Rights NOT VERIFIED. |
| **Coin Metrics Community `ReferenceRateEUR/USD` 1d** | Start date NOT VERIFIED (catalog query pending). BTC history is long, EUR start unknown | Yes if catalog confirms | Reference rate at 00:00 UTC "1d" (https://docs.coinmetrics.io/market-data/reference-rates-overview: "ends at 00:00:00 in the UTC timezone"); methodology v2.0: "historical daily reference rate has been replaced by the hourly reference rate for midnight UTC" | JSON/CSV responses can be hashed with `tools/data_01_source_pin.py`; revisions possible: providers "occasionally recalculate limited portions of history" (https://gitbook-docs.coinmetrics.io/coin-metrics-prices/coin-metrics-prices/reference-rate-metrics) | No key; "10 requests per 6 seconds sliding window" per IP (https://coinmetrics.readthedocs.io/en/stable/community.html); other doc: 1,000 req / 10 min (https://gitbook-docs.coinmetrics.io/access-our-data/api); free | "free for non-commercial use" under a Creative Commons licence, version not named; commercial use: contact info@coinmetrics.io (https://docs.coinmetrics.io/packages/coin-metrics-community-data, https://coinmetrics.io/?p=6495); terms page https://coinmetrics.io/api/terms unread. Attribution: "Coin Metrics" name/logo and link where feasible (secondary). Third-party mirror claims CC BY-NC 4.0, unverified (https://github.com/chengmarc/coinmetrics-data). |
| **CoinGecko public/Demo `market_chart/range`** | Last 365 days only on Demo | Yes (`vs_currency=eur`) | Auto granularity; adapter takes earliest timestamp per UTC day (repo, CONFIRMED), not a close | Sampled, drifts; not pinnable as a definition | Demo "1 year" historical (https://www.coingecko.com/en/api/pricing); Beta, attribution required, no commercial licence (search summary) | "scope of use ... dependent on the usage plan" (https://www.coingecko.com/en/api_terms); attribution wording not confirmed. |
| **Checkonchain** (charts.checkonchain.com) | NOT VERIFIED | NOT VERIFIED | Chart site, price provenance unknown | No official export found; only third-party scrapers (`ocfinance`, `chaindl`, https://chaindl.readthedocs.io/en/latest/) | n/a | No terms found. Verification-by-eye only. |
| **BlockHorizon** | NOT VERIFIED | NOT VERIFIED | Unknown | Search returned nothing about it | n/a | Nothing found. Treat as unassessed. |
| **Bitstamp public OHLC** (`/api/v2/ohlc/btceur`) | BTC/USD from 2011 (secondary: https://www.cryptodatadownload.com/blog/posts/historical-bitstamp-ohlcv-data-api-python/); BTC/EUR pair: a source dates the EUR market launch to 26 April (year not shown, 2016 likely) (https://www.diariobitcoin.com/noticias/bitstamp-es-desde-hoy-el-primer-exchange-bitcoin-con-licencia-en-la-union-europea); before that EUR deposits were converted to USD (https://bitcoinmagazine.com/articles/introducing-the-exchanges-bitstamp-1360800096) | Yes, from ~2016 | Single-venue daily candle, UTC close | API history needs windowed paging (`limit` 1..1000); bytes pinnable | Free, public | Terms not read. Single venue, so a verification series, not a market average. |
| **Kraken `XBTEUR`** | Downloadable full-history OHLCVT ZIPs, 1440-min file, "from the beginning of each market" (https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data); REST OHLC returns only the latest 720 candles regardless of `since` (https://docs.kraken.com/api-reference/market-data/get-ohlc-data.md) | Yes | Single-venue candles, only when trades occurred | ZIP is a pinnable artifact; REST is not | Free | Terms not read; the support page has no licence text. |
| **Coinbase via FRED `CBBTCUSD`** | Start NOT VERIFIED | USD only | Coinbase daily | FRED CSV pinnable | Free | "Copyright, 2018, Coinbase"; reproduction "prohibited except with the prior written permission of Coinbase" (search summary of https://fred.stlouisfed.org/series/CBBTCUSD). Poor fit for any derived publication. |
| **Blockchain.com market-price** | NOT VERIFIED | USD | Market average, method not confirmed | JSON via charts API (timezone UTC) (https://blockchain.info/api/charts_api) | Free | Terms not read. Verification only. |
| **CryptoCompare / CoinDesk Data `histoday`** | NOT VERIFIED | Yes | Aggregated index | API | Free tier credits/day limits from an aggregator only (https://apis.io/rate-limits/cryptocompare/cryptocompare-rate-limits/) | Older support page: CC Attribution Non-Commercial, commercial tiers sell redistribution rights (https://support.customer.coindesk.com/hc/en-gb/articles/360011839813-Do-I-need-to-pay-for-the-API-or-can-I-use-it-for-free). Current terms unread. |
| **bitcoin-data.com / BGeometrics** | NOT VERIFIED | NOT VERIFIED | Unknown | API | Free key: "8 requests per hour, 15 requests per day" (https://bgeometrics.com/terms) | Too tight for a backfill. Not suitable as a series source. |
| **ECB** | No BTC series. Only EUR/USD (already used for gold, `EXR.D.USD.EUR.SP00.A`) | n/a | n/a | n/a | n/a | Existing gold attribution text applies to the FX leg. |

Not assessed (no evidence gathered): Bundesbank, Bank of England (no BTC series expected, ASSUMPTION), Mt. Gox / pre-2014 sources.

Reading of the table: only Yahoo (via the trading repo) has measured coverage; only Coin Metrics and exchange files offer a documented definition (UTC midnight reference rate, venue candles). Every source with free, full-history access is restricted to non-commercial use or leaves redistribution unanswered. No source found so far grants explicit republication of derived monthly values.

## 4. Monthly price definition and rationale

CBS side (CONFIRMED, HIST_05 rows 1, 3, 8): the average price of transactions registered by the Kadaster in a month. It is a month-wide average of events spread across the month, not a month-end snapshot. The gold side (ADR-004) is a monthly mean of daily values. A comparable BTC definition is therefore a **mean over all days in the calendar month**.

| Candidate | Comparable to CBS/gold? | Verdict |
|---|---|---|
| Mean of daily closes (V2 or V1, below) | Yes: every day weighs equally like the month-wide transaction stream; same family as ADR-004 | **Preferred (PROPOSED)** |
| Mean of daily means / reference rates | Same; Coin Metrics 1d is a UTC-midnight reference rate, not a daily mean, so it is a "mean of daily fixings" | Equivalent family, label it accordingly |
| Month-end close | No: one day decides the month, ignoring intramonth range | Reject for the headline; may serve as a sensitivity indicator |
| VWAP | Would weigh by BTC volume, which has no counterpart in CBS transactions; needs venue volume data, not reproducible from free daily files | Reject |

Why intramonth volatility matters: BTC can move tens of percent within one month, while the CBS average describes the whole month. A month-end close would compare end-of-month BTC with an average of the month's house sales and shifts the ratio by the whole intramonth drift. This is an ASSUMPTION about magnitude; BTC-02 should quantify it (mean vs month-end divergence per month) rather than assert it.

Two computation variants for the EUR price (both PROPOSED, to be reported side by side in BTC-02):

- **V1 (ratio of means, gold-parallel).** `btc_eur[m] = mean(btc_usd[d], d in m) / mean(usd_per_eur[d], valid ECB days in m)`. Needs no daily FX matching, no weekend policy, no forward fill. Mirrors ADR-004 exactly (including its stated caveat that ratio of means is not mean of ratios). Uses all 24/7 BTC days; weekends are present in the numerator only.
- **V2 (mean of daily EUR prices).** `btc_eur[d] = btc_usd[d] / usd_per_eur[d]` for matched days, then mean. This is what `docs/btc-price-methodology.md` currently says. With a USD source and strict matching it silently drops weekends/holidays (1,267 of 4,409 BTC days in the audit have no same-day ECB-equivalent FX), so the mean covers weekdays only; with carry-forward it breaks the no-forward-fill rule. Either way it needs the open owner decision on FX.
- **V3 (native EUR).** `btc_eur[m] = mean(btc_eur[d], all days in m)` from a source that quotes EUR directly (Coin Metrics `ReferenceRateEUR`, or Bitstamp/Kraken EUR after ~2016). No FX at all, 100% calendar coverage possible, strongest definition if rights and start date hold.

Recommendation: V3 where a verified EUR-native series exists, otherwise V1 (it is the only option that satisfies "no forward fill" and "complete months" at the same time and stays parallel to the accepted gold method). V2 is a sensitivity check. Owner must choose (open decision D2).

Weekend/holiday handling summary: BTC trades 24/7, ECB publishes on TARGET business days. Missing ECB days stay missing; the monthly FX mean uses only valid ECB days (as in ADR-004). No carry-forward. A month with zero valid FX days is `null`.

## 5. Start date

- **Proposed first publishable month: 2014-10** (ASSUMPTION that Yahoo is accepted as source). Evidence: the audited series starts 2014-09-17 (CONFIRMED, audit run 39050246824), so 2014-09 has 14 days and fails the 100%-coverage rule; 2014-10 is the first complete month.
- Months before: `null` with reason `NOT_APPLICABLE`/`SOURCE_UNAVAILABLE` per METHODOLOGY section "missing_reason" vocabulary; never zero (METHODOLOGY).
- Earlier start possible only if BTC-02 measures a second source (Coin Metrics catalog min date; Bitstamp or Kraken EUR files) with overlap and the owner approves no-splice handling: either one source per contiguous range with a visible break, or no earlier months. The first "first EUR-quoted exchange pricing" date (Bitstamp BTC/EUR ~2016, Kraken unknown) is later than 2014-10, so for 2014-10..~2016 only USD x ECB exists.
- The BTC index (section 6) cannot use 2000-01 as base. 2014-10 as first available month is the only base that needs no extra data.

## 6. Formulas, units, rounding

Definitions (month `m`, all Decimal):

| Quantity | Symbol / field | Unit | Formula |
|---|---|---|---|
| House price | `H[m]` = `house_eur` | EUR per average sold home | CBS `nl_house_avg_eur` (existing) |
| BTC price | `B[m]` = `btc_eur` | EUR per BTC | V1/V2/V3 above |
| BTC per house | `btc_per_house` | BTC per average sold home | `H / B` |
| Sats per house | `sat_per_house` | satoshi per average sold home | `btc_per_house * 100_000_000` |
| BTC price index (optional) | `btc_index` | index points | `100 * B[m] / B[first]` with `first` = first published month (2014-10) |

Notes:
- `btc_eur`, `btc_per_house`, `sat_per_house` and `btc_index` are separate quantities; do not label sats as "price". `btc_index` is a price index and is not comparable with `hpi_index` (base 2000-01 = 100) or `gold_index`; it must carry its own base label or be omitted. Option D4 below: ship without `btc_index`.
- Dimension check (METHODOLOGY): EUR/home divided by EUR/BTC = BTC/home. Property test: `sat = btc * 1e8` exactly.
- Arithmetic: `decimal.Decimal` throughout, same context policy as `etl/gold_monthly.py`; parse source strings with `Decimal(str)`, never float. **No rounding anywhere in the pipeline or the candidate**; rounding happens in the display layer only (e.g. 0 decimals for sats, 4-8 decimals for BTC, 2 decimals for EUR). The pinned JSON, if ever published, would carry the full-precision Decimal string or a documented fixed precision (open item for the JSON contract, not decided here).
- Reconstructability: `btc_eur = house_eur * 1e8 / sat_per_house` recovers the monthly EUR price exactly from published data, because `house_eur` is already public. Publishing `sat_per_house` or `btc_per_house` is therefore equivalent to publishing the monthly BTC/EUR price. This is the same class of problem as GOLD-01 (derived values that expose the source series; see `docs/research/GOLD_01_RIGHTS.md`) and is a per-source rights question, not a technical one.

## 7. Data quality controls and thresholds

All checks fail closed; a failure produces a review bundle with the reason and no candidate. Thresholds marked "to be measured" are proposals for BTC-02.

| Control | Rule (PROPOSED) |
|---|---|
| Completeness in accepted period | Every month from the start month to the last complete month is present; missing historical month = error (as in gold `classify_coverage`); the current month is `INCOMPLETE_PERIOD`/pending, never published partially |
| Duplicates, order | Unique `(date)` daily keys, unique `(month)`; contiguous ordered months (`expected_months`) |
| Values | Positive, finite, `Decimal`; reject zero/negative/NaN; units checked (USD vs EUR per BTC) |
| Daily coverage per month | Default: 100% of calendar days present for the BTC leg (CONFIRMED default in `docs/asset-price-quality.md`); no lower minimum accepted without owner decision. For V1: at least 1 valid ECB day, but a floor of roughly 15 business days is suggested as sanity check (ASSUMPTION; record `fx_days` like gold; the gold validator itself accepts any positive count) |
| Currency conversion | FX is USD per EUR; `btc_eur = btc_usd / usd_per_eur`; reject `*` direction; reuse `validate_gold` style recomputation `close(a,b)` tolerance of `1e-12` relative |
| Satoshi conversion | `sat == btc * 10^8` exact in Decimal; `btc == house/btc_eur` within `1e-12` relative |
| Pinning | Source bytes hashed before parsing (`tools/data_01_source_pin.py`); manifest records endpoint, params, SHA-256, byte size, retrieval time; replay offline reproduces the candidate hash. Raw bytes stay out of public Git/Releases/Artifacts (storage class B not configured) |
| Revision detection | Any change in a previously approved month's value or in pinned bytes = `REVISION_REVIEW_REQUIRED` (DATA_01_UPDATE_CONTRACT). Yahoo vendor adjustments and Coin Metrics recalculation both qualify; compare old and new sets per month |
| Jump/outlier | Flag, never alter, a daily change above a threshold and a monthly-mean change above a threshold. Daily thresholds "to be measured in BTC-02" from the 4,409-day series; do not take numbers from this document. Flags need human review; BTC genuinely moves, so flags are not errors |
| Cross-check | Second source monthly mean vs primary monthly mean per month. The repo default is **5% relative** (`docs/asset-price-quality.md`) and applies to different daily conventions. A stricter monthly tolerance (ASSUMPTION: 1% when both are daily UTC-midnight style fixings) is only a hypothesis; BTC-02 must measure the actual distribution of per-month deviations Yahoo vs Coin Metrics (and CoinGecko for the last 12 months) and then propose the tolerance. Nothing in the repo yet quantifies BTC deviation. |
| Partial months | First month 2014-09 and current month are `null`/pending; leading/trailing missing dates are reported, not trimmed |
| Alignment | Exact `YYYY-MM` join with CBS; CBS latest month (2026-08) bounds the series; BTC months beyond CBS are not published; CBS months before the BTC start are `null` |
| Sanity vs ADR-008 | Missing stays `null` with reason; `0` never used |

## 8. Limits and risks

1. **Rights (blocking).** No surveyed source gave explicit permission to republish derived monthly values. Coin Metrics Community is described as non-commercial under a Creative Commons licence with the exact version unread; CoinGecko Demo has no commercial licence and requires attribution; FRED/Coinbase prohibits reproduction without permission; Yahoo terms are unresolved. Whether the dashboard counts as "non-commercial" and whether monthly means count as "redistribution" are legal questions the repo cannot settle; need the quoted primary terms (BTC-02) and likely a written request.
2. **Reconstructability.** See section 6. Publishing `sat_per_house` (or `btc_per_house`) exposes `btc_eur` to anyone with the public `house_eur`. If a source's licence forbids publishing its prices or derivatives, sats are equally forbidden.
3. **Definition mismatch.** Yahoo "close" has an unverified cutoff; Coin Metrics 1d is a midnight-UTC reference rate; CoinGecko is a sampled tick. Cross-source differences are methodological, not necessarily errors (`docs/btc-price-methodology.md`).
4. **Source mutability.** The trading repo is read from mutable `master`; Yahoo can revise history; no raw-byte custody exists (DATA_01B, class B BLOCKED).
5. **FX policy.** A V2 monthly mean over weekdays only is biased relative to a 24/7 asset; V1 avoids it but is a ratio of means and cannot be reconstructed as daily EUR prices.
6. **History gap.** Pre-2014-10 absent; any earlier start needs a second validated source and an owner decision on splicing.
7. **Sample/lag mismatch.** CBS uses Kadaster registration month; the deed may precede registration. Mean BTC over the registration month is an alignment choice, not an exact timing match (ASSUMPTION).
8. **API risk.** Coin Metrics Community rate limits and catalog/metric changes ("sets of available assets and metrics can be changed at any time", mirror README); CoinGecko Demo 365-day cap; Kraken REST 720-candle cap; BGeometrics free tier far too small for backfill. Coin Metrics also retires community metrics over time (https://coinmetrics.io/?p=27754).

## 9. BTC-02 implementation proposal (all review-only, nothing published)

Reuse, do not rewrite:
- `etl/sources/coinmetrics.py` and `etl/sources/coingecko.py` unchanged for cross-checks; a new `etl/sources/btc_trading_history.py` that parses the pinned trading CSV (or a pinned download) into Decimal daily rows, reusing `etl/asset_quality.py` validation.
- `tools/data_01_source_pin.py` for hashing and manifest; add a source id only via the existing allowlist pattern (BTC always research only).
- New `etl/btc_monthly.py` (mirrors `etl/gold_monthly.py`): V1/V2/V3 computation in Decimal, `classify_coverage`, `build_candidate` returning `{"data","coverage","publication_authorized": False}`; fields `month, btc_usd_mean, usd_per_eur_mean, fx_days, btc_days, btc_eur, house_eur, btc_per_house, sat_per_house`, plus per-variant deviation table.
- New `etl/btc_publication_candidate.py` (mirrors `etl/gold_publication_candidate.py`): review bundle with pinned hashes of the CBS CSV and the public JSON, source manifests, quality report, cross-check report, deviation statistics.
- `etl/static_export.py`: add `BTC_FIELDS = ("btc_eur", "btc_per_house", "sat_per_house")` and a `validate_btc` gate with its own env flags (`BTC_PUBLICATION_ENABLED`, `BTC_PUBLICATION_APPROVAL=APPROVED`) and `--approve-btc-publication`, off by default, all fields `null` in committed JSON. This is a ROOD/ORANJE change (public JSON meaning, pinned hashes) and needs the owner's explicit go; BTC-02 may add the gate only if the owner says so, otherwise it stays a documented design.
- Frontend: `frontend/src/series.ts` already has `sat_per_house` as `withheld`; add `btc_per_house` the same way (`publication:'withheld'`). The gate in `series.ts` ignores JSON values for withheld series, so no UI change is visible.
- Workflow: new `.github/workflows/btc-02-review.yml`, manual, `permissions: contents: read`, no write token, no deploy; steps: pinned acquisition, offline replay check, monthly computation, quality and cross-check, upload review bundle artifact (14-day retention, not durable custody), `git diff --exit-code` on public files. Raw prices not uploaded as artifacts if rights unresolved (metadata and aggregated monthly hashes only, as the existing audit does).
- Tests: `tests/test_btc_monthly.py` (fixtures: valid month, partial first month, missing day, duplicate, non-positive, FX direction, zero FX days, sats exactness, reconstructability round trip, determinism, source revision, publication blocked by default), `tests/test_btc_publication_candidate.py`, and `tests/test_static_export.py` additions proving BTC fields stay null without the gate. Governance check `scripts/check_governance_docs.py` must still pass.
- BTC-02 measurement tasks (no values hard-coded in docs): Coin Metrics catalog min/max for BTC `ReferenceRateEUR|USD|PriceUSD`; primary-text read of Coin Metrics, CoinGecko, Yahoo, Kraken, Bitstamp terms via a CI probe (as `gold-01-terms-probe.yml`); per-month Yahoo vs Coin Metrics deviation; V1 vs V2 vs V3 differences; mean vs month-end divergence; daily/monthly jump distribution; first EUR-quoted exchange month (Bitstamp, Kraken).
- Stays unpublished: all BTC/sat fields, raw daily BTC or FX data, any pre-2014-10 value, `btc_index` unless decided.

## 10. Open owner decisions (essential only)

- **D1 Rights path.** Which source is acceptable for public derived monthly values and is a written request to the provider needed? Without this, BTC remains `withheld`.
- **D2 Method for USD sources.** V1 (ratio of means, gold-parallel) versus V2 (daily conversion, needs an FX weekend/holiday rule) versus V3 (EUR-native only). Includes the exact monthly definition label ("mean of daily closes" vs "mean of reference rates").
- **D3 Start month and splicing.** Accept 2014-10 as the start, or require a validated earlier/EUR-native source; the rule for source breaks.
- **D4 Fields.** Publish `btc_per_house` and/or `sat_per_house` only (no `btc_index`, no `btc_eur`), accepting reconstructability, or publish nothing until rights are cleared.
- **D5 Cross-check tolerance.** After BTC-02 measurement.

## 11. Evidence labels

| Claim | Label | Evidence |
|---|---|---|
| Yahoo BTC-USD 4,409 days 2014-09-17..2026-10-12, no gaps; EURUSD 1,761 missing; 1,267 BTC days without same-day FX | CONFIRMED | `docs/btc-trading-history-audit-2026-10-17.md`, run 39050246824 (document claims `VERIFIED_REPO`; not re-run here) |
| ADR-004 gold method, Decimal, no imputation; BTC part PROPOSED | CONFIRMED | `docs/governance/DECISIONS.md`, `etl/gold_monthly.py` |
| CBS month = Kadaster-registered transactions | CONFIRMED | `docs/research/HIST_05_CBS_DEFINITIONS.md` rows 1, 3, 8 |
| 5% default cross-source tolerance | CONFIRMED | `docs/asset-price-quality.md` |
| `sat_per_house` already withheld in frontend registry | CONFIRMED | `frontend/src/series.ts` |
| Coin Metrics 1d = 00:00 UTC; daily/hourly published within 5 minutes; weekends not shifted | NOT VERIFIED (S) | https://docs.coinmetrics.io/market-data/reference-rates-overview |
| Coin Metrics Community: Creative Commons, non-commercial, commercial via info@; rate limit 10 req / 6 s | NOT VERIFIED (S) | https://docs.coinmetrics.io/packages/coin-metrics-community-data, https://coinmetrics.readthedocs.io/en/stable/community.html |
| Coin Metrics `ReferenceRateEUR` BTC start date and EUR availability | NOT VERIFIED | catalog not reachable; BTC-02 |
| CC licence version (BY-NC 4.0?) | NOT VERIFIED | only a third-party mirror claims it |
| CoinGecko Demo 365-day history, attribution required, no commercial licence | NOT VERIFIED (S) | https://www.coingecko.com/en/api/pricing |
| CoinGecko attribution wording | NOT VERIFIED | https://www.coingecko.com/en/api_terms unread |
| Kraken REST OHLC 720-candle cap; downloadable OHLCVT ZIPs incl. 1440-min | NOT VERIFIED (S) | https://docs.kraken.com/api-reference/market-data/get-ohlc-data.md, support article above |
| Kraken XBTEUR first date | NOT VERIFIED | not found |
| Bitstamp BTC/USD from 2011; EUR pair launch around 26 April, year not shown (2016 likely) | NOT VERIFIED (S) | sources in table 3; year is an ASSUMPTION |
| FRED CBBTCUSD copyright text; start date | NOT VERIFIED (S) / start NOT VERIFIED | https://fred.stlouisfed.org/series/CBBTCUSD |
| Checkonchain and BlockHorizon data, export, licence | NOT VERIFIED | nothing found for licence/export; BlockHorizon nothing at all |
| bitcoin-data.com free tier 8 req/h, 15 req/day | NOT VERIFIED (S) | https://bgeometrics.com/terms |
| CryptoCompare/CoinDesk Data terms | NOT VERIFIED (S) | older support page only |
| Yahoo terms allow/deny redistribution | NOT VERIFIED | no relevant text found |
| Mean of daily values is the best comparable definition; month-end/VWAP unsuitable | ASSUMPTION | argued in section 4, to be quantified in BTC-02 |
| 2014-10 as first complete month | ASSUMPTION conditional on Yahoo acceptance | follows from CONFIRMED 2014-09-17 start |
| 1% monthly cross-check tolerance; 15 FX days floor | ASSUMPTION | hypotheses, measure in BTC-02 |
| Bank of England / Bundesbank have no usable BTC series | ASSUMPTION | not searched |

## Samenvatting voor DECISIONS.md (Nederlands, PROPOSED, geen besluit)

- BTC-01 (onderzoek, 2026-10-21): voorstel voor BTC-maandwaardering; niets gepubliceerd, Bitcoin en satoshi blijven `withheld`; ADR-004 (BTC), ADR-007, ADR-008 blijven `PROPOSED`.
- Voorgestelde maanddefinitie: rekenkundig gemiddelde van alle dagwaarden in de kalendermaand (gelijk aan de gouddefinitie); voor USD-bronnen maandgemiddelde BTC/USD gedeeld door maandgemiddelde ECB USD/EUR (geen FX-carry-forward); EUR-native bron heeft voorkeur als die gevalideerd is.
- Bron: tradinghistorie (Yahoo BTC-USD, ADR-010) als onderzoekskandidaat; Coin Metrics `ReferenceRateEUR` als onafhankelijke controle; CoinGecko Demo alleen recente maanden (365 dagen).
- Startmaand voorstel 2014-10 (eerste volledige maand na 2014-09-17); eerdere maanden `null`, geen splice zonder besluit; formules `btc_per_house = house_eur / btc_eur`, `sat_per_house = btc_per_house * 100000000`, Decimal, afronden alleen bij weergave.
- Risico: `btc_eur = house_eur * 1e8 / sat_per_house` is exact reconstrueerbaar, dus publicatie van sats is gelijk aan publicatie van de koers; rechten (Yahoo, Coin Metrics niet-commercieel CC) zijn open; externe feiten zijn nog niet uit primaire tekst bevestigd.
- Open besluiten: bronrechten, methode voor USD-bronnen (ratio van gemiddelden versus dagomrekening versus EUR-native), startmaand/splice, te publiceren velden, tolerantie na meting in BTC-02.
