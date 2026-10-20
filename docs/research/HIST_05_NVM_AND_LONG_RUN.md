# HIST-05: NVM and other reproducible Dutch house-price sources, 1975-1999 and toward 1900 (research only)

Status: **RESEARCH ONLY. NOTHING IS APPROVED.** No source, series, definition, link, splice, aggregation, publication or use is approved. Any use of a pre-2000 series in the public dashboard is a ROOD item (`docs/governance/CHANGE_CONTROL.md`) and belongs to the owner. Nothing here changes `data/`, `frontend/`, `etl/`, ADRs or public JSON. No value is interpolated, no price level is back-calculated from an index, no two series are linked.

Scope boundary: CBS/Kadaster tables and the pinned CBS 1995-1999 fixture are covered by workstream H in separate files; this document only uses the committed 2000-01.. CBS baseline for overlap diagnostics.

Evidence: tool `tools/hist_05_other_sources.py`, workflow `.github/workflows/hist-05-other-sources.yml`, offline tests `tests/test_hist_05_other_sources.py` (synthetic fixtures, they prove parser code only).

| CI run | Commit | Result |
|---|---|---|
| [39451077348](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39451077348) | a571364 | first probe: BIS and OECD obtained; several wrong URLs |
| [39473110887](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39473110887) | 676fd87 | code-based unit classification; JST download redirects to a CDN host |
| [39474310500](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39474310500) | 2bbdf25 | JST workbook obtained via exact CDN URL; ESB NVM median table parsed |
| [39474938656](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39474938656) | bd04a91 | scrambled ESB row rejected; BIS and JST documentation read |
| [39475425694](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39475425694) | 27cc339 | final tool state; all exit 0 (PARTIAL: some sources unreachable, no parser defects) |

Labels: `OBTAINED` = machine-readable or table observations for the Netherlands were parsed in CI (Decimal) from the fetched bytes; `REFERENCE_ONLY` = page or file fetched (or source only named) but no usable observations parsed; `UNREACHABLE` = fetch failed. Evidence levels for rights: `OFFICIAL_TEXT_READ`, `SECONDARY_ONLY`, `NOT_RETRIEVED`. Raw bytes were never written to the repository or uploaded; the artifact `hist-05-other-sources-summary-review-only` (14 days) holds aggregates only. sha256 values below are of the bodies fetched in run 39475425694 unless stated; pages with dynamic content change between runs.

## 1. Headline findings

1. **Price LEVELS 1975-1999: essentially none obtained.** The only level data obtained are four selected years (1985, 1990, 1995, 1999) of the **NVM Wonen median** price of existing dwellings in **NLG**, as printed in an ESB article (secondary reproduction, not an NVM export). The Vastgoedmarkt 1974-2024 table named in HIST-01 could **not** be read: the URL served a **PNG image**, not a PDF (`pdftotext` returned "May not be a PDF file"); no OCR was attempted.
2. **INDEX data (not price levels) are available and long:** BIS (nominal and real, quarterly, **1970-Q1** to 2026-Q1, 2010=100), OECD (annual and quarterly nominal HPI and real RHP, **1970**, base 2015=100) and the Jorda-Schularick-Taylor (JST R6) `hpnom` (annual, **1870-2020**, nominal index, 1990=100, 151 observations, no gaps). An index is not a price level; no level is derived from them.
3. **No source obtained is the NVM series itself.** NVM publishes current quarterly PDF reports (links seen on its market-information page, 3rd quarter 2026); no downloadable historical series was found, and its copyright page forbids reproduction without written permission.
4. **Rights:** BIS statistics in the Data Portal are carved out of the free-reuse clause (separate "Terms of permitted use of BIS statistics", text not read: `data.bis.org/legal` returned 404, the help page only links to it); JST is **CC BY-NC-SA** (non-commercial) which is a publication risk; NVM forbids reproduction without written permission; OECD terms page returned 403.
5. The apparent agreement of BIS/OECD/JST with CBS after 2000 is **not independent evidence** (BIS names CBS StatLine as the Netherlands source; JST takes 2013-2020 from OECD). It says nothing about pre-1995 quality, where the provenance of the BIS/OECD/JST series is **undocumented in what was retrieved**.

## 2. Source matrix

Coverage = periods with an observation (first-last, count). "Level/Index" is the measure type as classified from attribute codes and labels; `RATE` = year-on-year change.

| # | Source | Official page / exact data URL tried | HTTP in CI | Label | Measure type | Coverage, frequency | Notes |
|---|---|---|---|---|---|---|---|
| 1 | **ESB article "Vast aanbod, flexibele vraag" (1999), NVM Wonen median** | `https://esb.nu/vast-aanbod-flexibele-vraag/` | 200, 188,115 B | **OBTAINED** (4 selected years, secondary) | **LEVEL**, NLG per dwelling, **median**, existing dwellings (table heading "bestaande koopwoning", source note "NVM Wonen") | 1985, 1990, 1995, 1999 only; annual; 3 rows kept: all dwellings 130,000 / 159,000 / 223,000 / 329,000 NLG; terraced 116,000 / 141,000 / 204,000 / 285,000; corner 142,000 / 174,000 / 243,000 / 356,000 | a 4th row ("Appartementen") parsed with non-monotone values (148,000 / 346,000 / 228,000 / 549,000), almost certainly misaligned columns of the extracted text; it was **rejected, not repaired**; detached row incomplete, dropped. Text extraction is heuristic: confirm against the printed table. Transaction vs asking, sampling and coverage are not stated in the retrieved text. |
| 2 | Vastgoedmarkt "Kerncijfers 1974-2024" | `https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf` | 200, 158,009 B, sha256 `fb41e65e...` | **REFERENCE_ONLY** | would be LEVEL (x1000 EUR, "per ultimo"), per HIST-01 | not parsed | body begins with PNG magic bytes; image, not PDF. Whether another URL serves a PDF is open. |
| 3 | NVM market information and copyright | `https://www.nvm.nl/wonen/marktinformatie-wonen/`, `https://www.nvm.nl/special-pages/copyright/`, `https://www.nvm.nl/` | 200 (the original `/wonen/marktinformatie/` redirects 308 and was not followed) | **REFERENCE_ONLY** | n/a | page lists current quarterly PDFs (e.g. "marktoverzicht-nederland-3e-kwartaal-2026.pdf") | no historical download found; PDFs not fetched |
| 4 | **BIS Residential property prices (WS_SPP)**, Netherlands | `https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.NL?format=csv` (also `*.NL`, identical sha256 `5222a6ef...`), bulk `https://data.bis.org/static/bulk/WS_SPP_csv_flat.zip` (305,022 B, sha256 `fefec3d9...`, labelled codes) | 200 (old bulk name `www.bis.org/statistics/full_webstats_spp_dataflow_csv.zip` 404) | **OBTAINED** | **INDEX**: nominal and real, 2010=100 (unit code 628) plus RATE series (code 771, y/y %) | quarterly, **1970-Q1 to 2026-Q1**, 225 obs (index), 221 (rates), **0 gaps**, 100 obs in 1975-1999 | definition (BIS data documentation, read): Netherlands compiled from Q1 2005 as "all dwellings, pure price"; Q1 1995-Q4 2004 "all existing dwellings, pure price, NSA"; **the pre-1995 part is not described in the text read**; source named "CBS StatLine" |
| 5 | **OECD house prices** (`DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES`), NLD | `https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/NLD.....?format=csv` (211,008 B, sha256 `a5654b38...`), also `.../all?format=csv` (6.5 MB, same NLD series) | 200 | **OBTAINED** | **INDEX**, base 2015=100: nominal `HPI`, real `RHP`, `HPI_RPI` (price-to-rent), `HPI_YDH` (price-to-income), `RPI` (rent price index); plus long-term averages | annual and quarterly; `HPI`/`RHP` from **1970 (A) / 1970-Q1 (Q)** to 2025 / 2025-Q4, 0 gaps; `HPI_YDH` from 1980; `RPI` from 1960 | no definition text retrieved (OECD terms 403; flow list fetched but not informative) |
| 6 | **Jorda-Schularick-Taylor Macrohistory Database R6** `hpnom`, Netherlands | page `https://www.macrohistory.net/database/`; data via exact CDN URL `https://sfff5b3ac9317c4be.jimcontent.com/download/version/1763503850/module/9834512569/name/JSTdatasetR6.xlsx` (1,408,158 B, sha256 `c1bb91fe...`); documentation PDF from the same CDN (2,181,397 B) | page 200; the page's own link redirects (302) to the CDN host which is outside the allowlist, so the CDN URL was fetched directly as its own exact allowlisted URL | **OBTAINED** | **INDEX**, nominal, **1990=100** (documentation: "House prices (nominal index, 1990=100)") | annual, **1870-2020**, 151 obs, 0 gaps, 25 obs in 1975-1999 | documentation: "1870 - 2012 from Knoll et al. (2014). No price like home: Global house prices, 1870-2012. Year average values. 2013 - 2020 from OECD housing prices database. Nominal series. Chain-linked." Netherlands data contributors listed include Eichholtz (Maastricht). |
| 7 | Knoll-Schularick-Steger "No Price Like Home" (AER 2017) | not fetched (a JST documentation sentence confirms JST uses it for 1870-2012) | n/a | **REFERENCE_ONLY** | INDEX | NL inclusion and start year not verified from the KSS files themselves; only inferred via JST | JST NL series (row 6) is the KSS-derived data in the retrieved form |
| 8 | Eichholtz Herengracht index 1628-1973 | not located | n/a | **REFERENCE_ONLY** | repeat-sales INDEX of Amsterdam canal houses [own knowledge, unverified] | n/a | local, **not national**; pre-1900 and pre-1973 only |
| 9 | Dallas Fed International House Price Database | page `https://www.dallasfed.org/research/international/houseprice` (200); xlsx guesses `.../houseprice/hp2604.xlsx` under three path spellings | page 200; xlsx 404 x3 | **REFERENCE_ONLY** (page) / **UNREACHABLE** (data) | INDEX [own knowledge] | not obtained | the page lists `hp2604.xlsx` but none of the URL forms tried resolved |
| 10 | Eurostat HPI `prc_hpi_q` | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/PRC_HPI_Q/Q.TOTAL.I15_Q.NL?format=SDMX-CSV` | 200, 6,441 B | **OBTAINED** (irrelevant to 1975-1999) | INDEX 2015=100 | quarterly **2005-Q1 to 2026-Q2**, 86 obs | starts after 2000-01 baseline start; no pre-2000 value |
| 11 | IMF Global Housing Watch | `https://www.imf.org/en/Topics/Global-Housing-Watch` | 403 (Akamai) | **UNREACHABLE** | n/a | n/a | no workaround attempted |
| 12 | data.overheid.nl catalogue (CKAN) | `https://data.overheid.nl/data/api/3/action/package_search?q=koopwoningen&rows=10` (and `q=woningprijzen`) | 200 | **REFERENCE_ONLY** | n/a | 54 hits for "koopwoningen", e.g. CBS "Bestaande koopwoningen; verkoopprijzen ... 1995-2023" and several 1995-based price-index tables; 1 hit for "woningprijzen" (unrelated) | no catalogue entry reaching before 1995 was seen in the 10 titles returned; these are CBS tables (workstream H) |
| 13 | ECB RPP, DNB/CPB publications, Dutch long-run national accounts (Smits/Horlings/van Zanden) | not fetched | n/a | **REFERENCE_ONLY** (named only) | unknown | unknown | no machine-readable file located |

## 3. Per-period coverage 1900-1999 (what was actually obtained)

`LEVEL` = price level in NLG/EUR; `INDEX` = index only; `none` = nothing obtained. All entries are annual unless stated.

| Period | Price LEVEL obtained | INDEX obtained | Remarks |
|---|---|---|---|
| 1900-1969 | none | JST `hpnom` annual (1870-1969 complete) | the KSS-derived series; provenance of the pre-1970 Dutch component (national vs Amsterdam-based) not verified; Herengracht data are not national |
| 1970-1974 | none | JST annual; BIS, OECD quarterly (1970-Q1) | |
| 1975-1984 | none | JST annual; BIS, OECD quarterly | no level for any year |
| 1985, 1990, 1995, 1999 | **NVM Wonen median, NLG (selected years only)** | JST, BIS, OECD | the only level points; secondary (ESB) |
| other years 1985-1999 | none | JST, BIS, OECD | no interpolation between the four level years |

Count of observations 1975-1999: BIS/OECD quarterly 100 each (25 years x 4, complete); JST/OECD annual 25 each; ESB levels 4.

## 4. Level versus index (explicit)

- **ESB/NVM Wonen**: LEVEL in NLG (median).
- **BIS, OECD, JST, Eurostat**: INDEX with base period (2010, 2015, 1990, 2015). **Not price levels.** The index cannot be turned into NLG/EUR without an external level anchor, and doing so would be a back-calculation that this task forbids. No such calculation was made.
- Real versus nominal: BIS and OECD publish both; only the nominal series were compared with CBS. The OECD `HPI_RPI`, `HPI_YDH` and `RPI` series are ratios/rents, not house-price series, and were excluded from conclusions (the tool compared them mechanically; their poor agreement, e.g. r = -0.075 for `RPI`, is expected).

## 5. Breaks, definitions and representativeness

- **BIS**: documented definition changes in 1995 and 2005 (existing dwellings only, then all dwellings); the 1970-1994 construction is not described in the text read. Whether the quarterly series is chain-linked across these breaks is not stated; **treat 1995 and 2005 as possible breaks**.
- **OECD**: no definition text retrieved. The BIS and OECD nominal growth rates are numerically near-identical after 2000 (see 6), so they likely share the Dutch source; the pre-1995 source is unknown.
- **JST**: explicitly chain-linked; **break at 2012/2013** (KSS to OECD). Pre-1970 content could not be tied to a national transaction series from the retrieved text.
- **ESB/NVM**: median (not mean) of NVM-member transactions [market share unknown]; HIST-01 cites a CBS methodology report that puts NVM coverage before 2000 at roughly 50 percent; not re-verified here. Not comparable to the CBS average price, which is a Kadaster-based mean.
- **Representativeness**: BIS/OECD/JST are national; the ESB table is NVM-sample national (existing dwellings). Eichholtz is Amsterdam-only and not usable as a national series. Transaction versus asking prices are not stated in any retrieved text; BIS labels the Netherlands series "pure price" (a quality-adjusted index concept) from 1995.

## 6. Comparability with the existing CBS series (diagnostic only, no splice)

Method: annual mean of complete years of the source index versus the annual mean of the 12 monthly CBS `nl_hpi` values (committed baseline 2000-01..), compared as **year-on-year growth in percent** on shared years. Growth comparison is index-base independent. Not a validation of any pre-2000 value.

| Series | Shared growth years | Mean abs difference (pp) | Max abs difference (pp) | Pearson r | Same sign |
|---|---|---|---|---|---|
| BIS nominal index (Q, annualised) | 2001-2025 (25) | 0.31 | 1.20 | 0.997 | 25/25 |
| OECD `HPI` nominal (A) | 2001-2025 (25) | 0.33 | 1.21 | 0.997 | 25/25 |
| JST `hpnom` (A) | 2001-2020 (20) | 0.20 | 0.56 | 0.999 | 20/20 |
| ESB/NVM levels | no shared year (levels end 1999; CBS public data start 2000-01) | n/a | n/a | n/a | n/a |

Mean growth 2001-2025: BIS 4.18 %, CBS 4.25 %. Caveat: these series very probably **are** CBS-based after 2000, so the agreement is expected and carries no information about 1975-1999.

Descriptive level cross-check (labelled derivation, not a validation): NVM median 1995 = 223,000 NLG / 2.20371 = 101,193 EUR (rounded), against HIST-01's CBS 1995 average EUR 93,750 and Vastgoedmarkt 1995 EUR 105,000 (= 231,390 NLG). Median versus mean and different populations; the three figures are not like-for-like. The 1995-1999 comparison of BIS/OECD growth with the pinned CBS 1995-1999 fixture was **not executed** (fixture belongs to workstream H and is not a public file).

## 7. Rights and republication (evidence levels)

| Source | Key sentence (retrieved text) | Evidence | Risk |
|---|---|---|---|
| NVM | "Het is de gebruiker van de website niet toegestaan de inhoud van de website te vermenigvuldigen, door te sturen, te distribueren, te verspreiden of tegen vergoeding beschikbaar te stellen aan derden, zonder de uitdrukkelijke, schriftelijke toestemming van NVM." (copyright page) | OFFICIAL_TEXT_READ | reproduction needs NVM's written permission; a derived series would need clearance |
| ESB | copyright statement page fetched (links to a copyright PDF, not read) | OFFICIAL_TEXT_READ for the page; terms not extracted | NVM figures republished by ESB: both owners' terms apply |
| BIS | "Users may reproduce a limited extract of BIS Material (other than the statistics published in the BIS Data Portal) in other publications or products free of charge, provided the BIS is cited as the source." and "Users may download, display, print out, photocopy or redistribute any BIS Material for non-commercial purposes." | OFFICIAL_TEXT_READ (terms page); the Data Portal statistics have separate "Terms of permitted use of BIS statistics" | **not read** (`data.bis.org/legal` 404); do not assume the carve-out permits redistribution |
| OECD | terms page returned 403 | NOT_RETRIEVED | unknown |
| JST | "Under the Terms of Use and Licence Terms below, the data is made freely available, expressly forbidding commercial data providers from integrating, in addition to any existing data they may already provide, all or parts of the dataset into their services, or to sell the data."; licence page text is **CC BY-NC-SA 4.0** | OFFICIAL_TEXT_READ | **NonCommercial, ShareAlike: publication risk** for a public dashboard; attribution to JST and KSS required |
| Dallas Fed | page asks for citation of the working paper; licence not extracted | OFFICIAL_TEXT_READ (partial) | unknown |
| Eurostat, IMF | not read | NOT_RETRIEVED | unknown |

None of this is legal advice. Retrieval date 2026-10-20.

## 8. Open questions

1. **Vastgoedmarkt table**: is there a PDF (not PNG) URL, or a text/CSV copy? Without it there is no NLG/EUR level series beyond four ESB points. OCR of the image would be a new derivation requiring owner approval.
2. **Pre-1995 provenance of BIS, OECD and JST (1970-1994, and JST 1870-1969)**: which institution compiled it, which dwellings, how it is linked. Needed before any use; the BIS data documentation, the OECD metadata and the KSS paper/data files should be read in full.
3. Does `data.bis.org/legal` (or an equivalent) permit redistribution of the BIS series? Can the NVM grant permission for a derived series?
4. Can BIS/OECD growth for 1995-1999 be compared with the CBS 1995-1999 fixture (workstream H) to test comparability inside the overlap that exists before 2000?
5. Level anchor: any official price level (CBS 1995+) combined with an index would be a back-calculation or splice and remains forbidden here; the owner must decide whether an index-only pre-2000 view is acceptable.
6. Where does the Dallas Fed workbook live now (page lists `hp2604.xlsx`; tried URLs 404)?
7. KSS files: confirm Netherlands inclusion, start year and method directly (only inferred from JST documentation here).

## 9. What this research does not do

No source is selected; no recommendation to publish; the CBS series from 2000-01 is untouched; no value was filled for missing years; the four ESB level years stay four points.
