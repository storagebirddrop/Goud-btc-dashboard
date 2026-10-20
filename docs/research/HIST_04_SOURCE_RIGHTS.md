# HIST-04 Source identity, terms of use and republication conditions

Status: research only. Not a decision, not legal advice. Nothing here is normative; only `DECIDED`/`ACCEPTED` items in `docs/governance/DECISIONS.md` are.
Retrieval date: 2026-10-20.

## 1. Evidence limits (read first)

Evidence levels used per statement:

- `OFFICIAL_TEXT_READ`: the official page text was fetched and read in this session.
- `SECONDARY_ONLY`: only a search-engine excerpt or summary of an official page, or a third-party page, was seen. Quotes below marked "search excerpt" are what the search tool surfaced from the official page; they were not verified against the live page.
- `NOT_RETRIEVED`: nothing usable obtained.

In this session direct fetches (WebFetch and curl) of `worldbank.org`, `bankofengland.co.uk`, `federalreserve.gov` and `ecb.europa.eu` failed (DNS error / proxy 403 on CONNECT). **No official page was read directly, so no statement in this document is `OFFICIAL_TEXT_READ`.** Every term below must be re-read on the live official page before anyone relies on it. The file `CMO-Historical-Data-Monthly.xlsx` itself (its notes/footer sheet) was `NOT_RETRIEVED`.

## 2. Summary table

| Source | Use for internal research | Republication of raw or derived data | Attribution | Main open uncertainty | Evidence |
|---|---|---|---|---|---|
| World Bank Pink Sheet (monthly xlsx) | Appears allowed (CC BY 4.0 by default for World Bank datasets) | Appears allowed with attribution unless dataset metadata says third-party terms apply; gold series provenance (LBMA/IBA) not confirmed | Yes: "The World Bank: Dataset name: Data source" | Whether the Pink Sheet is "labeled otherwise" and whether gold inherits IBA/LBMA terms | SECONDARY_ONLY |
| Bank of England IADB (gold XUMAGPD) | Likely allowed | BoE says database reproduction is under the UK Open Government Licence (OGL), but gold may be third-party (LBMA/IBA) data; XUMAGPD definition not confirmed | OGL-style attribution (BoE supplies wording for some series) | Underlying provider and licence of XUMAGPD; whether OGL covers third-party data | SECONDARY_ONLY |
| Federal Reserve Board G.5 / H.10 | Allowed | Allowed (public domain unless otherwise indicated) | Requested, not a legal condition as worded | Whether a specific release page carries an exception; FX rates are sourced from market data (provider not confirmed) | SECONDARY_ONLY |
| ECB euro foreign exchange reference rates | Allowed | Allowed with accurate reproduction and source acknowledgement, per search summary; commercial terms of the rates themselves unclear | Yes: ECB as source; reproduce accurately | Rates are "for information purposes only"; exact reuse wording for the rates page not read | SECONDARY_ONLY |
| Underlying gold fixings (LBMA Gold Price, IBA) | Licence required for valuation/pricing/financial products per IBA/LBMA (search excerpt) | Restricted; FRED, World Gold Council and S&P Platts removed or stopped republishing IBA data | n/a | Whether Pink Sheet / BoE redistribution passes through IBA terms to downstream users | SECONDARY_ONLY |

## 3. Per-source notes

### 3.1 World Bank Commodity Price Data ("Pink Sheet")

- Official source page (not read): `https://www.worldbank.org/en/research/commodity-markets`. File of interest: `thedocs.worldbank.org/.../CMO-Historical-Data-Monthly.xlsx` (path not verified here). `NOT_RETRIEVED`.
- Terms page: `https://www.worldbank.org/ext/en/legal/terms-conditions/datasets` (Terms of Use for Datasets; URL from search results, page not read). `SECONDARY_ONLY`.
- Search excerpt of that page: "Unless specifically labeled otherwise, these Datasets are provided to you under a Creative Commons Attribution 4.0 International License (CC BY 4.0)". `SECONDARY_ONLY`.
- Third-party data, search excerpt: such datasets "may not be redistributed or reused without the consent of the original data provider", with conditions shown in dataset or indicator metadata. `SECONDARY_ONLY`.
- Attribution format per the same summary: "The World Bank: Dataset name: Data source (if known)". `SECONDARY_ONLY`.
- Whether the Pink Sheet page or workbook is "labeled otherwise" is not established. Third-party aggregators describe it as CC BY 4.0 (paraphrase, aggregator catalogs; not authoritative). `SECONDARY_ONLY`.
- Identity: publisher World Bank (Prospects Group); monthly commodity prices in nominal USD; gold reported in USD per troy ounce. Series name and underlying provider (the Pink Sheet notes are believed to describe a London market price, presumably LBMA-derived) not confirmed from official text. `SECONDARY_ONLY` for the unit, `NOT_RETRIEVED` for the provider.
- Open: whether the gold column carries third-party restrictions (IBA); the workbook's own notes sheet must be read.

### 3.2 Bank of England Interactive Database (IADB)

- Official pages (not read): `https://www.bankofengland.co.uk/legal`; IADB at `https://www.bankofengland.co.uk/boeapps/database/`; series detail page `https://www.bankofengland.co.uk/statistics/details/further-details-about-gold-prices-against-us$-data` (surfaced in search; not read). `NOT_RETRIEVED` as text.
- Search summary of the Legal page: database information is Bank copyright "unless otherwise stated", and reproduction is "subject to the terms of the UK Open Government Licence" (paraphrase). Outside database/rulebook terms, general material is limited to personal or internal non-commercial use. `SECONDARY_ONLY`.
- Search summary: the Bank states it uses market data, not the LBMA Gold Price, to value reserves (page last updated 2026-01-06 per search metadata). Meaning for series code XUMAGPD: unconfirmed. Whether it is an LBMA/IBA-derived series, and what its observation dates cover, was not found. `SECONDARY_ONLY` / `NOT_RETRIEVED`.
- Open: an OGL grant from the Bank may not extend to third-party components; the Bank's page says "unless otherwise stated". A lawyer or the Bank should confirm for XUMAGPD.

### 3.3 Federal Reserve Board G.5 / H.10

- Official pages (not read): `https://www.federalreserve.gov/disclaimer.htm`; releases `https://www.federalreserve.gov/releases/g5/` and `https://www.federalreserve.gov/releases/h10/` (URLs by convention, not verified). `NOT_RETRIEVED`.
- Search excerpt of the disclaimer: "Unless otherwise indicated, information on Board's website is in the public domain and may be copied and distributed without permission. Please cite to the Board as the source". `SECONDARY_ONLY`.
- Third-party material on the site needs permission from the non-Board source (search excerpt). `SECONDARY_ONLY`.
- No warranty on accuracy (search excerpt). `SECONDARY_ONLY`.
- Identity: Board of Governors; G.5 monthly/annual foreign exchange rates, H.10 weekly/daily; the underlying quote provider is not established here. `NOT_RETRIEVED`.
- Note: the repo's ADR-004 proposal uses ECB EUR/USD, so Fed data is at most a cross-check or a pre-1999 candidate. Unverified.

### 3.4 ECB euro foreign exchange reference rates

- Official pages (surfaced in search, not read): `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html`; terms `https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html`; framework PDF `https://www.ecb.europa.eu/stats/pdf/exchange/Frameworkfortheeuroforeignexchangereferencerates.en.pdf`. `SECONDARY_ONLY`.
- Search summary of the disclaimer (paraphrase): reproduced information must be reproduced accurately and the ECB credited; if included in documents that are sold, buyers must be told the information is free via the website. `SECONDARY_ONLY`.
- Search summary of the rates page (paraphrase): rates are published for information purposes only; use for transactions is strongly discouraged; no liability. `SECONDARY_ONLY`.
- The broader "educational and non-commercial reproduction" wording belongs to ECB publications, not necessarily to the rates; the summary found no blanket statement for commercial use of the rates. `SECONDARY_ONLY`.
- Identity: ECB / Eurosystem; daily reference rates at about 14:15 CET from the concertation procedure (from general knowledge, not re-verified here); series USD key `EXR.D.USD.EUR.SP00.A` (not re-verified here). Coverage starts 1999-01-04.

### 3.5 Underlying gold fixings: LBMA Gold Price / IBA

- Search results: the LBMA Gold Price is administered by ICE Benchmark Administration (IBA), set in USD at 10:30 (AM) and 15:00 (PM) London time; IBA converts to EUR and GBP. Use "for valuation and pricing activities and in transactions and financial products" requires an IBA usage licence (search excerpt). `SECONDARY_ONLY`.
- IBA took over from the London Gold Fixing in 2015 (general knowledge, not re-verified here).
- FRED announcement (search excerpt): from 2022-01-31 IBA data, including LBMA gold series, is removed from FRED. `SECONDARY_ONLY`.
- World Gold Council (search excerpt): as of 2025-03-18 historical LBMA Gold Price data removed at the request of IBA. `SECONDARY_ONLY`.
- S&P Platts notice (search excerpt): stops republishing LBMA gold and silver prices; date unclear. `SECONDARY_ONLY`.
- Earlier finding in this research line (not re-verified in this session): LBMA historic tables moved behind a Members Portal with licence self-certification.
- Open: whether downstream publication by the World Bank or BoE of derived or monthly series carries IBA restrictions to third-party re-users; this cannot be settled from the material seen.

## 4. Use by this repo today versus a derived-indicator publication

Today (per repo instructions, not re-audited here): research aggregates only appear in CI artifacts; no raw gold or FX data is committed; the public dashboard publishes only CBS housing data (`gold_eur_oz` etc. are `null`). Internal research use of the four sources therefore has the lowest exposure.

What would change if derived indicators (gram gold per house, gold index) were published publicly:

- Publication becomes a public redistribution of a value derived from gold fixing data, so the third-party IBA/LBMA question in 3.5 becomes material. Whether a monthly derived ratio counts as redistribution of the fixing is a legal question not answered here.
- Attribution strings for each source actually used would be needed (World Bank format; BoE/OGL; ECB as source; Fed citation requested).
- The ECB "information purposes only" wording would need a visible non-reliance note on the dashboard (design suggestion, not a requirement found).
- Publishing gold already requires the existing gates (`GOLD_PUBLICATION_ENABLED`, `GOLD_PUBLICATION_APPROVAL`, `--approve-gold-publication`); publication meaning is a ROOD item under `CHANGE_CONTROL.md`, so the owner must decide.

## 5. Decisions for the owner or a lawyer

1. Re-read the four official terms pages and the Pink Sheet workbook notes on a network that reaches them, and record `OFFICIAL_TEXT_READ`.
2. Obtain legal view (or written confirmation from World Bank, BoE, IBA) on whether publishing derived monthly or annual gold-based indicators is covered, given the IBA licensing stance.
3. Decide, as a ROOD matter, whether to publish any gold-derived indicator before that is settled; alternatives are unpublished internal research or a licensed source. No recommendation is made on legal certainty.
