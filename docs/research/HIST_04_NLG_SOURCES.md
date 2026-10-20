# HIST-04: USD/NLG source recovery, 1975-01..1998-12 (research only, nothing approved)

Status: **RESEARCH CANDIDATES. NO source, series, definition, aggregation or use is approved.** No methodology decision is taken here (a monthly FX definition for NLG is a ROOD item under `docs/governance/CHANGE_CONTROL.md` and belongs to the owner). No rates are synthetic, interpolated, forward-filled or ECU-based. Raw third-party data was never uploaded or committed; the workflow artifact holds aggregates only (14-day retention).

Why this document exists: the Fed G.5 route failed in CI (XML package `FRB_g5_xml.zip` HTTP 404, Data Download Program HTTP 400 behind Cloudflare). That was a failed **route**, not evidence that the data do not exist. This probe tried other official routes from GitHub Actions.

Evidence: tool `tools/hist_04_nlg_sources.py`, workflow `.github/workflows/hist-04-nlg-sources.yml`, offline tests `tests/test_hist_04_nlg_sources.py` (synthetic fixtures; they prove parser code only).

| CI run | Commit | Result |
|---|---|---|
| [39441611198](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39441611198) | be14f73 | exit 0, first probe (Fed, CBS, BIS, IMF, OECD, DNB, fixed rate) |
| [39442657057](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39442657057) | b10ae65 | exit 0, adds SDMX-XML parser, EUR-denominated handling, cross-checks vs Fed |

Evidence levels: `OFFICIAL_TEXT_READ` = text fetched in CI from the official page; `SECONDARY_ONLY` = only via a search result or third party; `NOT_RETRIEVED`.

## 1. Candidate table (real CI results)

Coverage = calendar months in 1975-01..1998-12 (288 expected) with at least one observation. "Direction" was asserted from the file text **and** the value range; a conflict would have failed the run.

| # | Candidate | Official page / exact data URL tried | HTTP in CI | Coverage, frequency, definition | Direction, unit, missing markers | Terms (evidence) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Fed H.10 historical, Netherlands, through 1989** | page `https://www.federalreserve.gov/releases/h10/hist/thru89.htm`; data `.../h10/hist/dat89_ne.txt` (also `dat89_ne.htm`, 885 kB, `<pre>` block) | 200 | file 1971-01-04..1989-12-29, 4,757 daily obs, 198 `ND`; 180/180 months in range (1975-01..1989-12), 17-23 obs/month, median 21; noon buying rates in New York for cable transfers (OFFICIAL_TEXT_READ: "The data are noon buying rates in New York for cable transfers payable in foreign currencies.") | header `NETHERLANDS -- SPOT EXCHANGE RATE, GUILDERS/US$` = **NLG per USD** (text and value range agree); 4 decimals; missing marker `ND` (counted, never filled) | Fed disclaimer, OFFICIAL_TEXT_READ: "Unless otherwise indicated, information on Board's website is in the public domain and may be copied and distributed without permission. Please cite to the Board as the source of the information." Rates "certified by the Federal Reserve Bank of New York for customs purposes" | **USABLE** |
| 2 | **Fed H.10 historical, Netherlands, 1990 onward** | data `.../h10/hist/dat96_ne.txt` (also `dat96_ne.htm`) | 200 | file 1990-01-02..1998-12-31, 2,264 daily obs, 85 `ND`; 108/108 months in range, 18-23 obs/month, median 21 | same header and direction, 4 decimals | same as #1 | **USABLE** |
| | Combined #1 + #2 | | | **288/288 months, 0 missing months, no overlap between the two files** (`fed_h10_file_overlap_months = []`) | | | |
| 3 | **IMF, exchange rates, new SDMX API** (IFS code `ENDA_XDC_USD_RATE` successor) | `https://api.imf.org/external/sdmx/2.1/data/IMF.STA,ER/NLD.XDC_USD.PA_RT.M?startPeriod=1975-01&endPeriod=1998-12&format=sdmx-csv` (the `format` parameter is ignored; the API returns SDMX-ML structure-specific XML) | 200 | monthly, period average (`TYPE_OF_TRANSFORMATION=PA_RT`), `INDICATOR=XDC_USD`, `COUNTRY=NLD`, 288/288 months, no missing | domestic currency per USD; unit identified as **NLG** only by comparison with Fed (median ratio 0.99995); 2-9 decimals; `ACCESS_SHARING_LEVEL=PUBLIC_OPEN` | IMF terms of use NOT_RETRIEVED | **USABLE as monthly cross-check; terms open** |
| 4 | **BIS WS_XRU** (US dollar exchange rates) | `https://stats.bis.org/api/v2/data/dataflow/BIS/WS_XRU/1.0/M.NL?format=csv`, `.../D.NL?format=csv`, `.../*.NL?format=csv` | 200 | series `REF_AREA=NL`. Daily (D, collection A) 1953-09-01..2026-10-13, 18,881 obs, 288/288 months, 18-23 obs/month. Monthly average (M, A) 1953-09..2026-09, 288/288. Monthly end of period (M, E) 288/288. Also Q and A frequencies | **EUR-denominated**: `CURRENCY=EUR`, title "Exchange rates against USD Netherlands". Values are EUR per USD, i.e. the guilder series divided by 2.20371 (median ratio to Fed 0.45374 = 1/2.2038). NLG = EUR x 2.20371 is a labelled derivation, not an original NLG observation. 3-6 decimals | BIS terms NOT_RETRIEVED | **PARTIAL** (full coverage, but unit is euro-converted) |
| 5 | **CBS StatLine 7139SHFO** "Guldenwisselkoersen; maand- en jaargemiddelden, 1962-2001" | `https://opendata.cbs.nl/ODataApi/OData/7139SHFO/{TableInfos,DataProperties,TypedDataSet}` | 200 | monthly averages 1965-01..2001-12 (444 monthly obs, 39 missing values, 37 annual rows), 288/288 months in range; table stopped, last modified 2002-02-06 | property `Amerikaanse dollar (per 1)`, unit `guldens` = **NLG per USD**; **1-2 decimals only** (e.g. 2.46, 1.90) | OFFICIAL_TEXT_READ (cbs.nl copyright page, links CC BY 4.0): "the re-use of the content of this site is permitted, provided Statistics Netherlands is cited as the source." | **PARTIAL** (full coverage, 2-decimal rounding up to 0.55% vs Fed) |
| 6 | FRED `EXNEUS` | `https://fred.stlouisfed.org/data/EXNEUS.txt`, `.../series/EXNEUS` | timeout after 30 s (both, both runs; HIST-02 saw the same for the CSV) | listed range 1971-01..2001-12 monthly per HIST-02 (SECONDARY_ONLY) | not seen | not read | **UNREACHABLE from CI** |
| 7 | De Nederlandsche Bank | `https://www.dnb.nl/statistieken/`, `.../en/statistics/`, `.../en/money-exchange/exchanging-guilder-banknotes/` | 403 (`AkamaiGHost`) for all three | no historical USD/NLG series located by search either (SECONDARY_ONLY); no workaround attempted | n/a | n/a | **UNREACHABLE from CI**, existence of a DNB series unproven |
| 8 | OECD SDMX (`DF_FINMARK`) | `https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/NLD.M.......`; flow list `.../dataflow/all` | 200 | NLD monthly series in this flow are interest rates and other financial-market measures, **no exchange rate**; the first guessed key returned 404; the flow list only offers an annual PPP/exchange-rate table | none | not read | **UNSUITABLE** (no monthly NLG/USD found; not exhaustive) |
| 9 | BIS bulk files | `https://www.bis.org/statistics/full_webstats_xru_current_dataflow_csv.zip` and `..._d_dataflow_csv_row.zip` (URLs taken from a third-party changelog) | 404 | n/a (superseded by the API in #4) | n/a | n/a | **UNREACHABLE** (URL wrong; API works) |
| 10 | IMF legacy IFS JSON | `https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.NL.ENDA_XDC_USD_RATE` | DNS error | n/a | n/a | n/a | **UNREACHABLE** (retired host) |
| 11 | Bank of England IADB | no NLG series code identified; a third-party mirror claims BoE USD/NLG 1975-2001 and says BoE no longer publishes it (SECONDARY_ONLY) | not probed | n/a | n/a | n/a | **NOT_RETRIEVED** |
| 12 | Eurostat / ECB legacy (EUR or ECU per national currency) | not probed | n/a | these are EUR/ECU-per-NLG tables, not market USD/NLG; ECU proxy is excluded by instruction | n/a | n/a | **UNSUITABLE** |

## 2. Cross-checks against Fed H.10 monthly means (arithmetic mean of daily noon rates, NLG per USD, before any conversion)

Unit was identified from the median ratio, not assumed. Comparisons are on the same 288 months.

| Series | Median rel. diff | Max rel. diff (month) | Months >1% off |
|---|---|---|---|
| BIS M.NL average (EUR x 2.20371) | 0.067% | 0.465% (1991-03) | 0 |
| BIS D.NL daily mean (EUR x 2.20371) | 0.067% | 0.465% (1991-03) | 0 |
| BIS M.NL end of period | 1.07% | 6.9% (1985-03) | 155 (a different definition, as expected) |
| IMF XDC_USD period average | 0.065% | 0.467% (1991-03) | 0 |
| CBS 7139SHFO monthly | 0.136% | 0.550% (1984-04) | 0 |

Anchor monthly means (Fed, NLG per USD): 1975-01 2.4565, 1980-01 1.9038, 1985-01 3.5819, 1990-01 1.9073, 1995-01 1.7159, 1998-12 1.8816. IMF gives 2.4565, 1.9035, 3.5787, 1.9085, 1.7178, 1.8820; CBS gives 2.46, 1.90, 3.58, 1.91, 1.72, 1.88.

Interpretation limits: agreement within about 0.5% shows consistent definition and unit, **not independence**. The BIS and IMF series diverge from Fed in the same month (1991-03), which hints at a common origin or a shared source difference, unexplained. Origins of the IMF, BIS and CBS series are not documented in what was retrieved.

## 3. Fixed conversion 1 EUR = 2.20371 NLG: VERIFIED in CI

- ECB press release "Determination of the euro conversion rates", 31 December 1998, `https://www.ecb.europa.eu/press/pr/date/1998/html/pr981231_2.en.html`, HTTP 200, OFFICIAL_TEXT_READ. Exact extract of the table: "... Luxembourg franc 40.3399 Dutch guilder 2.20371 Austrian schilling 13.7603 Portuguese escudo 200.482 ..." (value follows the currency name in this flattened table).
- Council Regulation (EC) No 2866/98, copy at `https://www.legislation.gov.uk/eur/1998/2866/data.html`, HTTP 200, OFFICIAL_TEXT_READ (UK National Archives copy, not EUR-Lex). Exact extract: "... = 2,20371 Dutch guilders = 13,7603 Austrian schillings ...".
- EUR-Lex (`...CELEX:31998R2866`, `.../eli/reg/1998/2866/oj/eng`) answered HTTP 202 (challenge page): UNREACHABLE from CI.

This is a retrospective unit conversion and **not** a substitute for the 1975-1998 market USD/NLG rate.

## 4. Ranked recommendation (a ranking of candidates for the owner to evaluate, not a selection)

1. **Fed H.10 historical files `dat89_ne.txt` + `dat96_ne.txt`.** Official, daily, NLG per USD, directly quoted, public-domain terms read, 288/288 months with 17-23 observations each, missing days explicit as `ND`. Fully reproducible from CI. Lead candidate.
2. **IMF `ER` dataflow, `NLD.XDC_USD.PA_RT.M`.** Monthly period average in national currency per USD, 288/288 months. Useful as a provider-published monthly cross-check and as an alternative if the owner prefers a published monthly average over a mean of daily noon rates. Terms not yet read.
3. **BIS WS_XRU `M.NL` / `D.NL`.** Complete, but euro-denominated; getting NLG needs the 2.20371 derivation and adds rounding. Cross-check only. Terms not yet read.
4. **CBS 7139SHFO.** Open licence (CC BY 4.0, source citation), but values rounded to 1-2 decimals; a precision-limited fallback or a third check.

Not usable from CI now: FRED (timeouts), DNB (403), OECD (no FX flow found), EUR-Lex (challenge).

## 5. Remaining uncovered periods

- 1975-01..1998-12: **none** at month level for the Fed route (288/288), for IMF, BIS and CBS.
- Individual days: 198 + 85 `ND` days in the Fed files stay missing (no carry-forward); every month still has at least 17 observations.
- Outside the requested window: Fed daily data start 1971-01-04 (not needed here); from 1999-01-01 the guilder no longer exists and only the fixed rate applies. 1999 and later need euro-era sources, outside this task.

## 6. Open questions (owner or later phases)

1. Monthly definition for the guilder: arithmetic mean of daily noon buying rates (computed here only as an aggregate for comparison), end-of-month, or a provider-published monthly average. This is a ROOD methodology decision and must be made before any use.
2. Whether a noon-buying-rate series (New York) is acceptable against the gold series' fixing and the housing series' time basis.
3. Terms of use for IMF and BIS data (NOT_RETRIEVED); CBS and Fed texts were read but a formal rights review is still pending (`rights_status` stays `UNVERIFIED`).
4. Provenance and independence of the IMF, BIS and CBS series, and the shared 1991-03 deviation of IMF and BIS from the Fed.
5. Whether DNB holds an own historical series reachable by another route (403 from CI; not proven either way).
6. G.5/G.5A annual and monthly Fed releases were not retried here; their failed routes (XML 404, DDP 400) were left as reported.

## 7. Explicit statement

Nothing in this document approves a source, a series, a monthly definition, an aggregation, a derivation (EUR to NLG), a retention or a publication. All tooling is research-only, writes no repository data, and the tool summary carries `source_approved: false`, `publication_authorized: false`, `rights_status: UNVERIFIED`.
