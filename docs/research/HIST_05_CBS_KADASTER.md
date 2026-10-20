# HIST-05: Dutch house prices before 2000 in CBS and Kadaster sources (research only, nothing approved)

Status: **RESEARCH FINDINGS. NOTHING IS APPROVED.** No source, series, definition, unit conversion, splice or publication is decided here. Any use of pre-2000 house-price data in the dashboard would be a ROOD item under `docs/governance/CHANGE_CONTROL.md` and belongs to the owner. No interpolation, no synthetic monthly values, no price level back-calculated from an index, no linking of different series. Nothing under `data/`, `frontend/`, `etl/` or the ADRs was touched. Raw third-party data was never committed or uploaded; the workflow artifact holds aggregates, sha256 hashes and short quotes only (14-day retention).

Evidence tooling: `tools/hist_05_cbs_kadaster.py`, `tests/test_hist_05_cbs_kadaster.py` (synthetic fixtures; they prove parser code only), `.github/workflows/hist-05-cbs-kadaster.yml` (push on this branch and `workflow_dispatch`; `contents: read`). All acquisition ran in GitHub Actions (the dev sandbox cannot reach external hosts). Labels: **OBTAINED** = fetched and parsed in CI; **REFERENCE_ONLY** = only mentioned or linked in something obtained, not retrieved; **UNREACHABLE** = fetch failed (HTTP code recorded). Evidence levels for rights: `OFFICIAL_TEXT_READ`, `SECONDARY_ONLY`, `NOT_RETRIEVED`.

## 1. Answer in one paragraph

Within the CBS open-data catalogue (273 distinct tables returned by the first 10 title-keyword searches; 17 keywords in later runs) **no table was found that contains a Dutch house price level, or a price index for existing dwellings, before 1995-01**. The existing-dwellings family (average sales price and price index, CBS with Kadaster) starts in 1995 in every table obtained (85773NED, 83906NED, 81884NED, 83913NED and regional/type siblings). Before 1995 CBS offers only **new-construction cost/price indices** (index only, not house prices: 37989MPP from 1914, 80334NED output price index from 1914, 80444NED input price index from 1990), farmland prices (37411LLB, 1990-2001, per hectare), stock and building counts, and rent increases. Kadaster: its public pages obtained in CI give nothing before the CBS series; no pre-1995 Kadaster price statistic was found (absence in the pages fetched is not proof of absence at Kadaster). The 1995-1999 monthly average sales prices in the repo fixture equal the CBS table values exactly (60 of 60); they are the **earliest** price levels found, and they are already in the repo as a review-only fixture.

## 2. Source matrix

| # | Candidate | Official page / exact data URL tried | HTTP in CI | Label | What was actually obtained (parsed with Decimal) | Measure type |
|---|---|---|---|---|---|---|
| 1 | **85773NED** Bestaande koopwoningen; verkoopprijzen prijsindex 2020=100 | `https://opendata.cbs.nl/ODataApi/OData/85773NED/{TableInfos,DataProperties,TypedDataSet}`; v4 `https://datasets.cbs.nl/odata/v1/CBS/85773NED/{MeasureCodes,Dimensions,Observations}`; page `https://www.cbs.nl/nl-nl/cijfers/detail/85773NED` | 200 (all 7) | OBTAINED | monthly 1995-01..2026-08, 380 obs, 0 gaps, 0 nulls; quarterly 1995-Q1..2026-Q2 (126); annual 1995..2025 (31). Measures: `GemiddeldeVerkoopprijs_7` (euro, price LEVEL: 88,991 in 1995-01), `PrijsindexVerkoopprijzen_1` (2020=100, INDEX), total value in mln euro. v3 and v4 values identical (380 of 380) | average price (level) AND index; transactions (Kadaster); existing dwellings; national |
| 2 | **83906NED** (… prijsindex 2015=100 1995-2023, discontinued, source "CBS, Kadaster") | same URL pattern, v3 + v4 | 200 | OBTAINED | monthly 1995-01..2023-12 (348), 0 gaps; Q 116, A 29; average price (euro), index 2015=100, number of sales | level + index + counts |
| 3 | **81884NED** (… prijsindex 2010=100 1995-2017, discontinued) | v3 | 200 | OBTAINED | monthly 1995-01..2017-12 (276), 0 gaps; same measures, index base 2010=100 | level + index + counts |
| 4 | **83913NED** (… prijsindex 2015=100, regio) | v3 | 200 | OBTAINED | dimension `RegioS` (21 codes incl. national `NL01`); quarterly and annual only, 1995-Q1..2023-Q4 | level + index, regional |
| 5 | 81885NED, 84997NED (regional/COROP), 81886NED/ENG, 83910NED/ENG (by dwelling type), all discontinued | v3 | 200 | OBTAINED | all begin 1995-Q1; quarterly; index and/or averages by region or dwelling type | regional or type breakdown |
| 6 | 71533NED/ENG, 80330NED (2005=100, 1995-2012), 83625NED (average prices by region, annual 1995-2025) | v3 `TableInfos`, `DataProperties` obtained; `TypedDataSet` | info/props 200; **data 500** | metadata OBTAINED, data UNREACHABLE | table titles and periods only (all start 1995); no values | index / regional average |
| 7 | **82101NED** (named in the task) | v3 `TableInfos`, `DataProperties`, `TypedDataSet` | **404** (all three) | UNREACHABLE | nothing. The id does not exist on this endpoint; the task named it as a guess | n/a |
| 8 | **37989MPP** "Prijsindexcijfers van nieuwbouwwoningen." (stopped, modified 2001-03-09) | v3 | 200 | OBTAINED | annual index 1914..1999 (86 obs, 0 gaps) base 1938/39=100; quarterly series 1980-Q1..1999-Q4 incl./excl. VAT with bases 1980=100, 1990=100, 1995=100 (partial overlap, several bases) | **index only, new construction**, not existing dwellings, not a price level |
| 9 | **80334NED/ENG** Nieuwbouwwoningen; outputprijsindex bouwkosten 2000=100, vanaf 1914 | v3 | 200 | OBTAINED | annual 1914..2025, quarterly 1950-Q1..2026-Q2; second index from 1969 | index only, building-cost output prices of new dwellings (cost, not market price) |
| 10 | 80444NED/ENG (input price index building costs, monthly from 1990), 37631mpp (rebuilding costs 1990-2003), 37132mpp/03756mpp (new-dwelling costs 1995-2004) | v3 | 200 (03756* values not parseable, see 4.4) | OBTAINED / finding | cost indices | cost index, not market price |
| 11 | **37411LLB** Landbouwgrond; koop- en pachtprijzen, regio, 1990-2001 | v3 | 200 | OBTAINED | price per hectare of agricultural land (`PrijsVerkooptransacties`, euro/ha), annual 1990..2001 national `PV99`, regional dimension (108 combinations) | farmland, **not houses** |
| 12 | 3529308E Prijsindexcijfers woninginboedels (household contents, 1991-1997) | v3 | 200 | OBTAINED | index of household contents | not houses |
| 13 | 37512 / 82827NED (institutional investors' real-estate holdings 1980-2016), 37261mfo (mortgages 1993-2003) | v3 | 200 | OBTAINED but not usable as parsed | a value convention that the strict level parser rejects (reported as finding, see 4.4) | portfolio/mortgage values, not house prices |
| 14 | 71527ned, 82235NED (dwelling stock and construction 1921-), 70675NED (rent increases from 1959), 37556ENG/85524ENG (population 1899-) | v3 | 200 | OBTAINED | counts, stock, rent change in %; no house prices | context only |
| 15 | 37831mfo "Particuliere woningtransacties naar regio" (1998-2002), 37610 (WOZ values 1997-2020) | listed in catalogue only | not fetched | REFERENCE_ONLY | title and period from the catalogue | not retrieved; candidate for follow-up |
| 16 | CBS Statistisch Jaarboek / "Honderd jaar statistiek" / "Tweehonderd jaar statistiek in tijdreeksen" / Eeuwcijfers | catalogue keyword searches `historisch` (1 row) and `eeuw` (0 rows) | 200 | REFERENCE_ONLY (from general knowledge, SECONDARY_ONLY) | publications not located as StatLine tables or fetched | whether printed historical series contain house prices is **unknown** |
| 17 | **Kadaster** `https://www.kadaster.nl/zakelijk/vastgoedinformatie/vastgoedcijfers` | page | 200 | OBTAINED (page only) | quarterly "Woningmarkt" news ("In het 2e kwartaal van 2026 werden 77.000 woningen verkocht"), a link to a "Vastgoeddashboard" and a "Toelichting vastgoedcijfers" explaining the difference between Kadaster figures, the average purchase price and the CBS "Prijsindex bestaande koopwoningen"; no downloadable series and no pre-1995 data seen | recent statistics, dashboard |
| 18 | Kadaster `https://www.kadaster.nl/` | page | 200 | OBTAINED | home page, no price statistics | n/a |
| 19 | Kadaster `.../over-ons/open-data`, `.../vastgoedinformatie/kadaster-cijfers` (URL guesses) | page | **404** | UNREACHABLE | nothing | n/a |
| 20 | CBS method description `.../korte-onderzoeksbeschrijvingen/prijsindex-bestaande-koopwoningen` (URL guess) | page | **404** | UNREACHABLE | nothing; methodology text for SPAR is therefore **not read** (SECONDARY_ONLY, see 5) | n/a |
| 21 | CBS copyright (nl, en), CBS open data page | pages | 200 | OBTAINED | rights text, see section 7 | n/a |
| 22 | CBS catalogue `https://opendata.cbs.nl/ODataCatalog/Tables?$format=json&$filter=substringof('<kw>',Title)` | 17 keywords | 200 | OBTAINED | 273 distinct table ids (10 keywords). Searches `verkoopprijs`, `woningprijs`, `huizenprijs`, `koopsom`, `woz`, `eeuw` returned **0 rows** (85-byte empty answers) | catalogue |

Reproducibility: all CBS StatLine tables above have stable ids and public OData v3 and (for 85773NED/83906NED) v4 endpoints; no API key. Byte hashes (sha256 of fetched bodies) are in the CI log and the artifact, for example 85773NED `TypedDataSet` in run 1 is listed there; hashes of living tables change with every CBS update, so they pin a retrieval, not the table.

## 3. Coverage by period: price LEVEL versus INDEX only

| Period | Existing dwellings, average price LEVEL | Existing dwellings, price INDEX | New construction | Other |
|---|---|---|---|---|
| 1900-1974 | none found | none found | cost/price index (37989MPP annual from 1914, 80334NED annual from 1914, quarterly from 1950) | CPI 1900=100 (71905NED, not a house series), dwelling stock from 1921 |
| 1975-1989 | none found | none found | same indices (annual; 80334NED quarterly) | institutional investors' real-estate holdings from 1980 (37512, not prices) |
| 1990-1994 | none found | none found | 37989MPP, 80444NED monthly input cost index from 1990 | farmland price per ha from 1990 (37411LLB) |
| **1995-01 onward** | **yes**, monthly, euro, national (85773NED etc.) | yes (several bases: 2005, 2010, 2015, 2020) | yes | regional/type breakdowns, quarterly |

So: **usable price LEVEL data for existing dwellings exist from 1995-01 only**; for 1975-1994 only new-construction cost indices (index, not market prices and not for existing dwellings) were found in CBS StatLine. An index must not be turned into a level (HIST rule); this document does not do so. The earlier history asked for in the task (1975-1994 and toward 1900) is **not available from the CBS/Kadaster sources probed**. Whether CBS print publications or Kadaster archives hold such series is **open** (REFERENCE_ONLY, not retrieved).

## 4. Definitions, breaks and caveats

1. **Start 1995.** The CBS/Kadaster existing-dwellings series start in 1995 (table period strings "januari 1995 - ..."). The repo's public data start at 2000-01; the 1995-1999 months exist only in the pinned fixture `data/fixtures/cbs-1995-1999-i1.json` (60 observations, built from 85773NED and 83906NED CSV selections, per its provenance file).
2. **Unit.** The price measures are labelled "euro" in `DataProperties` for the whole table including 1995-1998, that is, **before the euro existed** (fixed rate 2.20371 NLG per EUR from 1999-01-01). The tables therefore present retrospectively euro-denominated values. The original NLG observations were not obtained; whether CBS converted from NLG with the fixed rate, and at which rounding step, is **not documented in anything retrieved**. A guilder/euro unit break is not visible in the data, but it is a property of the history.
3. **Average price versus index.** `Gemiddelde verkoopprijs` is the mean of the sales prices in the period (compositional, not mix-adjusted); `Prijsindex bestaande koopwoningen` is a separate measure (SPAR-type, 2020=100 in the current table). The Kadaster page obtained says it explains the difference between the average purchase price and the CBS index; the explanation text itself was not parsed. Table titles say "CBS, Kadaster", so the source is Kadaster transactions; the SPAR mix-adjustment method is **SECONDARY_ONLY** here (the CBS method page URL tried returned 404).
4. **Base-year changes.** The index is republished with different bases in successive tables (2005, 2010, 2015, 2020): index levels in different tables are not comparable without rebasing, and the tables are stopped ("Stopgezet") successors of each other.
5. **Parsing findings.** `03756ENG` and `03756mpp` (building costs 1995-2004), `37512`, `82827NED` and `37261mfo` contain value conventions (non-numeric markers or non-positive levels) that the strict parser rejected in run 3; these are discovered, non-core tables and are reported as findings (`DISCOVERED_TABLE_NOT_PARSEABLE`) rather than pipeline defects. Core tables (the five named in the task) are strict. `71153NED` (census 1930) returned a body that is not the expected OData shape; `71135NED`/`71136NED` data endpoints returned 500.
6. **Missing data.** In every obtained price-level series (85773NED, 83906NED, 81884NED) there are 0 nulls and 0 gaps between first and last month. Missing values elsewhere were counted, not filled.
7. **Dimension tables.** Where a table has regional dimensions (e.g. 83913NED, 21 `RegioS` codes) the tool does not pick a region silently; comparisons are made only for single-combination (national) series.

## 5. Overlap and continuity numbers (descriptive only; no splice)

| Comparison | Common periods | Result |
|---|---|---|
| repo fixture 1995-01..1999-12 (monthly average price, euro) vs 85773NED | 60 | exact equal 60/60, max abs diff 0 |
| fixture vs 83906NED | 60 | 60/60 exact |
| fixture vs 81884NED | 60 | 60/60 exact |
| 85773NED vs 83906NED, average price | 348 (1995-01..2023-12) | 348/348 exact |
| 81884NED vs 83906NED and vs 85773NED | 276 (1995-01..2017-12) | 276/276 exact |
| OData v3 vs v4 for 85773NED / 83906NED | 380 / 348 | identical |
| Level continuity at the 1999/2000 boundary within 85773NED (same table) | 1999-12 to 2000-01 | month-on-month change +1.211 percent versus a median absolute month-on-month change of 1.958 percent over the preceding 12 months: no level jump at the boundary |

Interpretation: the overlap proves that the fixture, the two successor tables and the current table carry the **same average-price observations** (the fixture is a derivation of these tables, so it is not an independent check). The 1999/2000 boundary is not a series break inside the CBS table. The earlier HIST-02 NVM-based comparison (Vastgoedmarkt 1995: EUR 105,000 versus CBS EUR 93,750, annual) is unaffected and remains unresolved; 93,750 is the CBS annual 1995 average obtained here, 88,991 the January 1995 monthly value.

## 6. Series breaks summary

- 1995: start of every CBS/Kadaster existing-dwellings series; nothing earlier found.
- Unit: euro labelling covers pre-1999 periods (retrospective), NLG originals not obtained.
- Index base changes between tables (2005, 2010, 2015, 2020).
- Source change NVM-based to Kadaster-based data (mentioned in the task) is **not documented in anything retrieved**; the tables' source field reads "CBS, Kadaster" for all existing-dwellings tables obtained.
- Regional tables 83913NED etc. only quarterly and annual; monthly national only in 85773NED/83906NED/81884NED.

## 7. Republication rights

| Source | Evidence level | Quote (verbatim, from CI) |
|---|---|---|
| CBS copyright page (nl) `https://www.cbs.nl/nl-nl/over-ons/website/copyright` | OFFICIAL_TEXT_READ | "Dit houdt in dat hergebruik van de inhoud van deze site is toegestaan, mits CBS als bron wordt vermeld." and "Hergebruik Bij hergebruik van de inhoud van deze website is naamsvermelding verplicht." |
| CBS copyright page (en) | OFFICIAL_TEXT_READ | "This means that the re-use of the content of this site is permitted, provided Statistics Netherlands is cited as the source." and "This means that you are obliged to state that the data were sourced from CBS." Re-use is excluded where a part is marked with a copyright exception. |
| CBS open data page | OFFICIAL_TEXT_READ | "Alle datasets die via StatLine te bekijken en te downloaden zijn, worden ook beschikbaar gesteld als open data." The explicit label "CC BY 4.0" was not seen in the quoted sentences of this run (earlier HIST-04 recorded the CBS copyright page linking CC BY 4.0). |
| Per-table terms for tables whose `Source` is "CBS, Kadaster" | NOT_RETRIEVED | whether the Kadaster contribution carries separate conditions is **not established** |
| Kadaster terms / open-data licence | NOT_RETRIEVED | `.../over-ons/open-data` returned 404; no licence text read |

Nothing is cleared: rights status stays `UNVERIFIED` for publication purposes (source citation would be mandatory under the CBS text).

## 8. Open questions for the owner

1. Is 1995-01 acceptable as the earliest house-price level, or is a search outside StatLine wanted (CBS print publications "Honderd jaar statistiek"/Statistisch Jaarboek, Kadaster archive, DNB or NVM series)? Existing HIST-02 NVM results are separate.
2. Original NLG values for 1995-1998: obtainable from CBS (older table versions, e.g. before the euro relabelling) or only euro as presented?
3. Methodology text for SPAR and the Kadaster/CBS explanation page (read in full) and the Kadaster open-data licence for the "CBS, Kadaster" tables.
4. Follow-up candidates not fetched: 37831mfo (private dwelling transactions by region 1998-2002), 37610 (WOZ values 1997-2020), 83625NED (regional average prices, data returned HTTP 500), 71533NED (old index 2005=100, data HTTP 500; retry later).
5. Any use of new-construction cost indices as a "house price" proxy is a ROOD methodology matter; they measure costs, not market prices of existing dwellings.

## 9. Evidence (CI runs, branch `research/hist-05-nl-housing-prices-pre-2000`)

| Run | Commit | Result |
|---|---|---|
| [39450938631](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39450938631) | b852fec | success; first probe (5 core tables + 12 discovered, v4 for 85773NED/83906NED, 10 catalogue keywords) |
| [39451338972](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39451338972) | f4bda4b | success; overlap/continuity statistics in section 5 |
| [39451645138](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39451645138) | 4350654 | failure by design: strict parsing of discovered non-core tables (37512, 82827NED, 37261mfo, 03756*) raised defects; 17 catalogue keywords, 30 discovered tables, Kadaster page text |
| [39473012138](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39473012138) | c20f389 | success; discovered non-core tables with odd values (37512, 82827NED, 37261mfo, 03756ENG, 03756mpp) are findings, `defects: []`, 28 tables OBTAINED, same missing_sources as run 3 (all HTTP 404/500) |

Artifact: `hist-05-cbs-kadaster-summary-review-only` (aggregates only, 14 days). Offline tests: `python -m pytest -q tests/test_hist_05_cbs_kadaster.py`.
