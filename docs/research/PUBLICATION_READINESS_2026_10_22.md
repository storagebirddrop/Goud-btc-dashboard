# Publication readiness after HIST-09 / HIST-10 / BTC-03 — Project Control, 2026-10-22

**Scope:** decision preparation only. This matrix is not a licence opinion, methodological production ADR or release authorization. Baseline `main` `4758e251ac1c5ad0216da38a8d1cc0abca7ac4cd`. Existing GOLD-03/04 public gold indicators (from 2000-01) remain live and are **not** being reassessed here.

| Candidate public comparison | Verified research basis | Method / quality | Open prerequisites | Current decision |
|---|---|---|---|---|
| **NVM median house in grams gold, 1975-H1..2000-H2** | HIST-09 52 semiannual NVM prices; HIST-10 gold reconstruction; separate NLG/EUR currency eras | `HIST10_M1_V1` accepted research-only; GOLD_LEVEL_B 1975–1978, A 1979–1998; explicit 1998/1999 currency transition; median, **not** CBS average | NVM/OTB, World Bank and historical Fed/ECB rights/reuse review; historical gold methodology release ADR; consumer labels and caveats; public schema and full end-to-end release tests | **HOLD** |
| **CBS mean house in grams gold, 1995–1999 (pre-existing 2000+ published gold stays unchanged)** | HIST-09 verified CBS monthly data 1995–2000 and HIST-10 local gold | Retrospective EUR 1995–1998, observed EUR 1999; `HIST10_M1_V1` for halfyears; do not splice different frequency/statistics | Pre-2000 public method decision, historical FX/gold rights, data-contract and display treatment; existing 2000 gold index basis may not change implicitly | **HOLD** |
| **CBS mean house in BTC and sats, EUR-native Bitstamp, 2016-05..2026-08** | BTC-03 124 monthly housing ratios; source-window pins; derived hashes | `BTC03_A1_C1_V1` research status; Q1 EUR-native (no FX needed for native route), complete UTC months, separate venue | Bitstamp derived-data/public-display rights and attribution; explicit BTC production ADR and price definition/source approval; front-end public contract and release/browser/rollback QA; owner authorization | **HOLD; first BTC candidate to assess** |
| **CBS mean house in BTC and sats, USD-derived Bitstamp, 2013-07..2016-04 (or research comparisons thereafter)** | BTC-03 USD and ECB data; liquidity/provenance and source comparisons | Q2 quality label; `C1` monthly-means FX; USD 1m/day sustained threshold provisional | Rights for Bitstamp/ECB, BTC production ADR, accept liquidity heuristic / eligible start and explicitly labelled source transition, independent source checks | **HOLD; later phase** |
| **CBS mean house in BTC and sats, pre-2013-07 Q3 Mt. Gox/early Bitstamp** | BTC-03 separate early segments (2010-08+ Mt. Gox, 2011-09+ Bitstamp); thin market and archived copy | Low-quality Q3; Mt. Gox/Bitstamp differences up to 14.3%, 2011-06 missing | Provenance/rights for archive copy, quality representativeness and integrity; explicit owner risk decision and release specification; no automatic splice | **HOLD; research only** |
| **NVM median house in BTC/sats** | NVM ends in 2000-H2, first complete BTC trade month 2010-08 | No matching source periods | Requires a truly observed, separately validated housing series overlapping BTC (not invented monthly NVM) | **NOT APPLICABLE with current data** |

## Priority and owner decision gate

**Recommended next assessment:** narrow BTC Q1 (EUR-native Bitstamp from 2016-05) as a bounded, separate publication candidate. This is *not* a recommendation to activate it now: source rights and a public-method ADR remain open. In parallel, investigate conditions for historic pre-2000 gold and median NVM visualizations, rather than treating successful CI as a license.

**Required explicit decisions before release:**
1. Per-provider rights/attribution for derived public values (not simply API access).
2. BTC production methodology and first public month / quality threshold; direct EUR and derived USD segments may not be invisibly switched.
3. Public data-contract, provenance disclosures, labels, handling of missingness, performance and rollback.
4. Specific release candidate (public fields, period range, dataset hashes, CI and live-browser evidence), followed by separate owner publication/merge authorization.

**Engineering boundaries:** no `monthly.json` modification, no public BTC selector, no source splicing, no ADR change in this document-only task. Research source-window hashes are not a store of historical raw bytes. Future implementation uses a distinct scoped PR after explicit decisions.
