# HIST-06: Dutch house-price history from ~1975 (NVM, CBS/Kadaster, overlap, currency, pre-1975) - research only

Status: **RESEARCH ONLY. NOTHING IS APPROVED OR PUBLISHED.** No change to `data/`, `etl/`, `frontend/`, ADRs or public JSON. ADR-011 (long-history ambition) is an ambition, not an authorization. Any pre-2000 housing series on the dashboard, any source priority, splice, unit or aggregation choice is ROOD (`docs/governance/CHANGE_CONTROL.md`) and belongs to the owner. Created 2026-10-21 from `main` 0bfc040 on branch `feat/hist-foundation`.

Builds on, and does not redo: HIST-01 (`HIST_01_NVM_CBS_COMPARABILITY.md`), HIST-02 (`HIST_02_NVM_CBS_OVERLAP.md`, `HIST_02_SOURCE_DISCOVERY_FOLLOWUP.md`), HIST-05 (`HIST_05_CBS_KADASTER.md`, `HIST_05_CBS_DEFINITIONS.md`, `HIST_05_NVM_AND_LONG_RUN.md`), HIST-04 (`HIST_04_NLG_SOURCES.md`: the 2.20371 rate is verified there). Established facts are cited, not re-measured.

Labels: **CONFIRMED** = primary text read or value measured in CI; **PROPOSED**; **INFERRED** (derived from confirmed pieces, or from secondary text); **UNRESOLVED**. Evidence: tool `tools/hist_06_housing.py`, tests `tests/test_hist_06_housing.py` (synthetic only, they prove code not data), workflow `.github/workflows/hist-06-housing.yml` (`contents: read`, aggregates and hashes only, artifact `hist-06-housing-summary-review-only`, 14 days). Raw third-party bytes were never written to the repository or uploaded.

## 1. Verdict table

| # | Question | Verdict | Label |
|---|---|---|---|
| 1 | Is a downloadable, pinnable NVM/Vastgoedmarkt average-price series 1975+ available? | **NO.** The only candidate (`kerncijfers-vastgoedmarkt-1974-2024.pdf`, imgix host) serves a PNG image for every URL variant tried; OCR of the 26 variants returned 15-16 characters, no table. NVM itself publishes only current quarterly PDFs and forbids reproduction (HIST-05). | CONFIRMED (blocker) |
| 2 | Earliest/last NVM-attributed level values obtained | 1975 = EUR 47k and 1995 = EUR 105k (quoted via HIST-01/02, rounded to EUR 1,000, secondary); NVM Wonen **median** 1985/1990/1995/1999 in NLG (ESB 1999, secondary, HIST-05). Nothing else. | CONFIRMED as quotations, UNRESOLVED as series |
| 3 | CBS/Kadaster average price: coverage | Monthly 1995-01..2026-08 (380 obs, 0 gaps, HIST-05); annual 1995..2025, 31 values re-read in CI (93,750 .. 479,527 EUR, section 4); public repo data 2000-01.. only. | CONFIRMED |
| 4 | Any CBS/Kadaster level before 1995 | Only a printed method annex: annual 1993 = 81,037 and 1994 = 88,846 EUR (HIST-05 definitions, fact 13). Not a StatLine series. | CONFIRMED (printed), usage OPEN |
| 5 | Is NVM comparable to CBS as-is? | **NO.** Different statistic (NVM median/"weighted average of medians" vs Kadaster mean), population (NVM members, "little over half" of sales vs full Kadaster registration), price concept (ESB: *kosten koper* included; CBS *koopsom* excludes them), timing. | CONFIRMED (definitions) |
| 6 | Numerical NVM-vs-CBS overlap | **NOT EXECUTED on real NVM data** (blocker 1). Only labelled illustrations from quoted values (section 5): 1995 +12.0% (Vastgoedmarkt mean) and +7.9% (ESB median); 1999 +3.1% (ESB median). | UNRESOLVED / illustration |
| 7 | One combined series? | **No.** Recommend separately labelled segments (section 8). | PROPOSED |
| 8 | Is the 1970-1992 index in BIS/OECD/JST an NVM series? | **Yes, by primary text (KSS appendix B.10):** the Kadaster index for 1970-1992 is computed from the NVM median sales price; repeat sales from 1992; CBS SPAR from 1995. Index only, no level. | CONFIRMED |
| 9 | Pre-1970 national average | **None exists.** KSS: "no house price series for the Netherlands as a whole is available for the years prior to 1970"; the pre-1970 Dutch component of JST/KSS is the Eichholtz Herengracht index (Amsterdam, about 200 canal buildings). Not a national average. | CONFIRMED |
| 10 | Which use cases need average price vs HPI | section 7 | PROPOSED |

## 2. Source matrix (what is new in HIST-06 is marked NEW)

| Source | Issuer / identifier | Obtained in HIST-06 | Type, unit, frequency, coverage | Status |
|---|---|---|---|---|
| Vastgoedmarkt "Kerncijfers 1974-2024" | Vastgoedmarkt compilation; figure source line "NVM (voorheen NBM)" (HIST-02 follow-up); `https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf` | NEW: 26 URL variants (base, `?fm=pdf`, `?page=1..12`, `?page=N&w=2400`) fetched: all PNG. Distinct sha256 prefixes: base `fb41e65ef11f` (158,009 B); `4f64c21463cd` (157,513 B, identical for `fm=pdf` and all 12 `page` values, so the parameter is ignored); `d222e46016ba` (105,756 B) and `50fe9ff21bb9` (105,679 B) for `w=2400`. Tesseract (nld+eng, psm 4 and 6): 15-16 characters per image, no year rows. The image content was not viewed. | would be mean, kEUR (rounded), annual 1975-2023, "per ultimo", existing homes only | **BLOCKED**, UNRESOLVED |
| NVM Wonen via ESB 1999 | NVM Wonen median in NLG, existing dwellings, 4 selected years (HIST-05) | not redone | median, NLG, 1985/1990/1995/1999 | secondary |
| NBM data in ESB 1981 "De markt voor koopwoningen in Nederland, 1976-1980" | NBM (Nederlandse Bond van Makelaars, later NVM) registry; `https://esb.nu/wp-content/uploads/2022/11/editie_pdfs_1981_0233_tcm445-252946.pdf` | NEW: PDF fetched (779,189 B, sha256 prefix `f088e0ac5c9a`), text extracted. Primary-era analysis of NBM data 1976-1980; 7,135 observations for Jan-Mar 1980; 26 dwelling types; Table 2 mean sale prices incl. *kosten koper* by province and type (Jan-Mar 1980, NLG); Table 5 price **index 1976=100** per province and type, 1977-1980. | mean per cell, NLG, a quarter and an index 1976-80 | OBTAINED text; values not transcribed; usable as definition evidence |
| Knoll-Schularick-Steger working paper (Dallas Fed WP 208) | `https://www.dallasfed.org/-/media/Documents/research/international/wpapers/2014/0208.pdf` | NEW: fetched (3,626,287 B, sha256 prefix `6d105d23a6b7`), 434,178 characters read: Netherlands section 3.9, Table 14, Figure 51, appendix B.10 | index, 1870-2012 | CONFIRMED text |
| CBS longread "Achtergrond bij de huizenprijsstijgingen vanaf 2013" | CBS, 2022; cites CPB (2020) | NEW: fetched. Sentence: "In 1978 bedroeg de gemiddelde verkoopprijs van een woning 200 duizend gulden, bijna twee keer zo veel als drie jaar eerder"; "In 1985 lagen deze maar liefst 54 procent lager (CPB 2020)"; "Pas begin jaren negentig bereikten de prijzen weer het niveau van 1978." No table, no series. | prose | secondary, INFERRED value |
| CPB note March 2020 "Beweging op de woningmarkt: prijzen en volumes" | CPB | NEW: PDF URL rejected by the redirect policy (`UNAUTHORIZED_ENDPOINT_OR_REDIRECT`), `www.` variant not retrieved; the CPB landing page was fetched and lists the PDF (2.48 MB). Not read. The 1978/1985 numbers cited by CBS are therefore not traced to their table. | | UNRESOLVED |
| huizenmarkt-zeepbel.nl; hypotheker.nl | blogs | NEW: fetched. Zeepbel: nominal average ƒ201,800 (H2 1978) and ƒ137,300 (H2 1982) with "bron financiële data: prof. dr. P.J. (Peter) Boelhouwer" (underlying dataset not identified). Hypotheker: 1970 "omgerekend" EUR 23,578, no source. | secondary, unsourced | not usable as data |
| CBS 85773NED annual | CBS/Kadaster | NEW (re-read in CI): 31 annual published averages 1995-2025 | EUR, annual, mean | CONFIRMED |
| CBS CPI tables | CBS | NEW: catalogue read in CI (section 6) | index | candidates only |
| BIS / OECD / JST / Dallas Fed / Eurostat | HIST-05 | not redone | index only | see HIST-05 |

## 3. Definitions (confirmed unless stated)

| Item | CBS/Kadaster average price | NVM / NBM |
|---|---|---|
| Statistic | Plain mean of registered *koopsom* of existing dwellings sold to a private buyer; count-weighted annual mean (HIST-05 fact 5); no mix adjustment. The index (SPAR, WOZ-based) is a separate measure. | 1981 ESB: mean per cell of NBM registrations. Current NVM: "average" is in practice a weighted average of medians per dwelling type and region (NVM press text, search summary, SECONDARY_ONLY). ESB 1999 table: median. Vastgoedmarkt: "average sale price of existing homes". The mean/median basis of the 1975-2023 table is UNRESOLVED. |
| Price concept | *Koopsom* excl. notary, broker, transfer tax; incl. land; excl. movables (HIST-05 fact 6) | 1981 ESB tables: "verkoopprijzen kosten koper" (including costs). Whether later NVM series keep this: UNRESOLVED. |
| Population | Complete Kadaster registration of notarial transactions from 1993-01; whole country | Sales by brokers affiliated to NBM/NVM; the NBM's own estimate in 1981: "iets meer dan de helft" of sales; CBS method text puts pre-2000 coverage at about 50% (HIST-01). Coverage over time UNRESOLVED. |
| Timing | Date the notary deed is registered (Kadaster) | Broker-reported sale (Kadaster notes it records "een ander moment ... dan bijvoorbeeld de NVM") |
| New construction | Excluded | Vastgoedmarkt: existing homes, new construction excluded |
| Annual observation | calendar-year count-weighted mean of transactions | Vastgoedmarkt "per ultimo": year-end value vs annual mean UNRESOLVED |
| Currency | Labelled "euro" for all periods including 1995-1998 (first published 2009, retrospective); NLG originals not found; conversion method undocumented (HIST-05) | Vastgoedmarkt table in kEUR; whether converted from NLG at 2.20371 and where rounded: UNRESOLVED |
| Revisions | direct-definitief; revised only for significant error; levels identical across table versions (HIST-05) | unknown |

**HPI vs average price.** CBS states the average price "is geen indicator voor de prijsontwikkeling": it moves with the composition of what sells. The SPAR index corrects that. This is measurable on the committed data (section 4).

**Pre-1993 Kadaster/NVM chain (new, KSS appendix B.10, primary text).** "A second index covering ... all types of existing dwellings in the Netherlands during 1970-1994 is constructed by the Dutch land registry (Kadaster). Though the index is not directly available, it is included in the international house price database maintained by the Federal Reserve Bank of Dallas ... and the OECD database. For the time 1970-1992 the index is computed from the median sales price of dwellings as reported by the ... NVM. For the years since 1992 the index is based on the Land Registry's records of sales prices ... repeat sales method (De Haan et al., 2008)." Consequences: (a) the index in BIS/OECD/JST for 1970-1992 rests on NVM median prices; (b) there is a source and method change at 1992 and again at 1995 (CBS SPAR) that no splice has been tested against; (c) the original Kadaster/NVM level series is not directly available.

## 4. Measured CBS side (committed data and CI, no splice)

* Annual published average (EUR), re-read from 85773NED in CI: 1995 93,750; 1996 102,607; 1997 113,163; 1998 124,540; 1999 144,778; 2000 172,050; 2005 222,706; 2008 254,918; 2009 238,259; 2013 213,353; 2020 334,488; 2022 428,591; 2023 416,153; 2025 479,527 (31 values, 1995-2025).
* Printed method annex (HIST-05): 1993 81,037; 1994 88,846 (growth 1994/1993 +9.6%; 1995/1994 +5.5%; computed here).
* Average price vs constant-quality index, annual means of the 12 committed monthly values, 2001-2025 (25 growth years, tool `mix_effect`): mean(avg growth - HPI growth) = +0.09 pp; mean absolute gap 1.06 pp; maximum 3.04 pp; years with gap above 2 pp: 2009, 2010, 2011, 2014, 2022, 2025. Examples (avg growth / HPI growth): 2001 +9.7 / +11.2; 2009 -6.3 / -3.3; 2013 -5.8 / -6.3; 2022 +10.9 / +13.3. Ratio average/HPI level: 3,123 (2000) to 3,202 (2025), +2.5% over 25 years. Reading: on the CBS side composition effects are small on average but reach 3 pp in single years (largest in downturns and the 2022 boom).

## 5. NVM vs CBS overlap

**Real overlap (Vastgoedmarkt 1975-2023 vs CBS 1995-2023, up to 29 common years): NOT EXECUTED.** Blocker: no readable table (section 2). The tool computes it automatically if a table with 20+ year rows is ever recovered (percentage difference relative to CBS, ratio, drift of the ratio, YoY growth differences with outlier years, mean-shift break scan on log ratio, growth difference against the CBS HPI); this path is covered by synthetic tests only. A recovered OCR table would still be OCR-derived and would need visual confirmation against the printed page.

**Labelled illustrations from quoted secondary values (not a validation; different statistics and populations; EUR rounded to 1,000 so +-0.5%):**

| Year | CBS mean (EUR, CI) | NVM-attributed value | Derived / difference | Note |
|---|---|---|---|---|
| 1995 | 93,750 | Vastgoedmarkt mean 105,000 (HIST-01) | +11,250, +12.00% | "per ultimo", mean |
| 1995 | 93,750 | ESB NVM Wonen median 223,000 NLG = 101,193 EUR (derived at 2.20371) | +7.94% | median, NLG original |
| 1999 | 144,778 | ESB NVM median 329,000 NLG = 149,294 EUR | +3.12% | |
| 1985, 1990 | no CBS annual level | NVM median 130,000 / 159,000 NLG | not comparable | |
| 1995 | | Vastgoedmarkt mean 231,390 NLG-equivalent vs NVM median 223,000 NLG | mean 3.8% above median | both NVM-attributed |

Observations: the difference is not a stable offset (12.0% vs 7.9% vs 3.1% for different NVM-attributed statistics and years); NVM values are above the Kadaster mean in every comparison made, which is not what a median of an overlapping population would suggest and is consistent with *kosten koper* inclusion and NVM-member market mix (INFERRED, untested). Cross-check of the early 1970s-1980s level (INFERRED, secondary): CBS longread 1978 average ƒ200,000 = EUR 90,756; CBS annex 1994 = EUR 88,846 and 1995 = 93,750, matching the longread claim that prices regained the 1978 level in the early 1990s; Vastgoedmarkt 1975 EUR 47k = ƒ103,574, about half of ƒ200,000 ("bijna twee keer zo veel als drie jaar eerder"). Two independent secondary statements are therefore mutually consistent at the order of magnitude, but both remain unpinned.

**Break indicators.** Structural breaks to expect (by documentation, not measured): 1992 (NVM median to repeat sales), 1993 (Kadaster complete registration), 1995 (CBS SPAR; euro-labelled retro conversion), 1999-01-01 (euro), 2013/2014 (index weights). Transaction-mix: section 4 (CBS side, measured); NVM side not measurable.

## 6. Currency, deflation, inflation candidates

* NLG to EUR: 1 EUR = 2.20371 NLG is a **redenomination**, not purchasing power (verified in CI, HIST-04). The tool only converts via `nlg_to_eur`, which returns a *derived* series (unit `EUR_FROM_NLG`) that cannot be compared with original-EUR series without an explicit decision (negative test).
* Keep three layers separate: original nominal (NLG as printed, or EUR as printed with its retro-conversion caveat), derived nominal EUR, and inflation-adjusted. `deflate` refuses missing CPI years and already-real inputs.
* Inflation-adjustment candidates read from the CBS catalogue in CI (none adopted; a choice and base year are ROOD): 71905NED "prijsindex 1900=100", annual 1900-2025 (modified 2026-02-12); 83136NED "basisjaren vanaf 1969", monthly 1969-01..2026-09; 83433NED "werknemers laag, alle basisjaren 1969-1995"; 83131NED CPI 2015=100 monthly 1996-2025; 86141NED CPI 2025=100 from 2009-12; HICP 83133NED/86144NED from 1996. Chain-linking across base years and the CPI-vs-house-price conceptual gap (owner-occupied housing treatment) are unresolved.
* Index series (BIS/OECD/JST/CPB) are not price levels; no level is back-calculated.

## 7. Which use case needs which measure (PROPOSED)

| Use case | Needs | Why |
|---|---|---|
| "How many grams of gold / BTC does an average home cost" (level) | average price (CBS mean from 1995; NVM level only if obtained and licensed) | a level is required; accept composition effects (up to ~3 pp in a single year, section 4) and label it "average transaction price, not constant quality" |
| Relative performance or cycle comparison of housing vs gold/BTC/equities | constant-quality index (CBS HPI from 1995; BIS/OECD/JST index 1970+ with the 1992/1995 caveats) | removes composition effects; no level needed |
| Long history before 1995 | index-only view if the owner accepts it; no level | no pre-1993 national level is pinnable |
| Anything before 1970 | none national | Herengracht is local |

## 8. Recommendation on combined vs separate series (PROPOSED, nothing implemented)

1. Do **not** build one combined average-price series from NVM and CBS. Comparability is not shown (section 1 row 5) and the overlap could not even be measured.
2. If an NVM-based history is ever shown, present it as a **separately labelled segment** (annual, NVM-attributed, retro-EUR, rounded) with a visible source/frequency break, never extended into months and never rescaled to CBS.
3. For the CBS segment keep 1995-01.. monthly with the 1995-1999 months labelled retrospective euro. The existing 2000-01 baseline is untouched.
4. The index-only pre-1995 view (BIS/OECD/JST) needs a rights decision (BIS terms, JST CC BY-NC-SA, HIST-05) and must carry the 1992 and 1995 method-change notes.
5. Before any of this: obtain the Vastgoedmarkt table as text (or NVM written permission and data), and run the overlap tool.

## 9. Pre-1975 and toward 1900 (ADR-011)

| Candidate | Finding | Use |
|---|---|---|
| Eichholtz Herengracht index 1628-1973 | repeat-sales, hedonic, about 200 buildings on one Amsterdam canal, data from "Vier eeuwen Herengracht" (1975); buildings "of constant high quality"; many converted to offices after the early 20th century (KSS footnote, primary text) | local; **record, do not use as national** |
| JST/KSS Netherlands 1870-1969 | = Eichholtz (KSS 3.9: "Prior to the 1970s, the data are based on Eichholtz (1994) who calculated a repeat sales index for Amsterdam"); KSS flags "the Netherlands prior to 1970 ... very narrow geographical coverage" and "no house price series ... as a whole" | not national; resolves the HIST-05 open question on pre-1970 provenance |
| CBS new-build cost/price indices (37989MPP from 1914; 80334NED from 1914) | construction costs, index | not a house price |
| CBS dwelling stock from 1921, rent increases from 1959 (70675NED), CPI from 1900 (71905NED) | context | not prices |
| Kadaster | no pre-1995 public statistic found; the 1970-1994 Kadaster index is "not directly available" (KSS) | open |
| Amsterdam rent index 1550-1850 and similar academic series | rents, local | out of scope |
| Dutch national accounts/long-run databases | no house-price series located | UNRESOLVED |

No national average can be constructed before 1993 from what exists; none is invented here.

## 10. Blockers

1. Vastgoedmarkt table unreadable (image only; OCR empty; no alternative URL located; searches found no text copy). Without it: no NVM 1975-1999 levels, no real overlap, no break test.
2. CPB 2020 note not retrieved (redirect off the allowlist); the source of the 1978/1985 figures in the CBS longread is untraced.
3. NVM written permission needed for reproduction (HIST-05); Kadaster licence for the "CBS, Kadaster" tables not established.
4. Original NLG values for 1993-1998 not available; conversion method undocumented.
5. Dallas Fed international database (which carries the Kadaster/NVM 1970-1994 index) not obtained (HIST-05: URL 404).

## 11. Open owner decisions

1. Is an index-only (no level) housing history 1970-1994 acceptable, given its NVM-median basis to 1992, method changes in 1992 and 1995, and licence limits?
2. Accept the printed CBS annex values for 1993 and 1994 (annual, euro) as a pre-1995 CBS data point? Rights not checked.
3. Authorise a written request to NVM/Vastgoedmarkt (the table as text/CSV and permission) and to CBS (NLG originals/conversion note)? No contact has been made.
4. Choose which statistic a future long housing level should be: Kadaster-type mean vs NVM-type median/weighted average, and whether a "kosten koper" level must be adjusted.
5. Which CPI (if any) for a separate real view.

## 12. Evidence

| Run | Head SHA | Content |
|---|---|---|
| [39584712338](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39584712338) | a29b586 | first complete probe: 26 imgix variants, ESB 1981, KSS, CBS annual, CPI catalogue |
| [39585369148](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39585369148) | d08e339 | grouped fetch summary, ESB captions |
| [39594396515](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594396515) | aa186b1 | ESB tables, KSS appendix B.10, labelled illustration |
| [39594886950](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594886950) | 7c1b5ff | CBS annual values and illustration printed (defects: 0) |

All runs: offline tests passed, `defects=0`. Section 4 mix-effect numbers were computed locally by the same tool from the committed CSV (deterministic). Tests: `python -m pytest -q tests/test_hist_06_housing.py tests/test_governance_docs.py`.
