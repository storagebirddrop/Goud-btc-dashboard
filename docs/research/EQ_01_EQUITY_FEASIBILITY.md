# EQ-01: feasibility of an S&P 500 and AEX comparison against Dutch house prices

Status: **research only, PROPOSED. Not a decision, not legal advice.** Nothing is approved or published. No chart, JSON field, ETL code, frontend change or ADR status is touched; S&P 500 and AEX stay `withheld`/out of scope (`docs/governance/PROJECT_SCOPE.md`). Date of research: 2026-10-21. Branch `feat/hist-foundation` (PR #91).

Evidence labels: **CONFIRMED** = primary text read, or a measurement in a CI run (run URL given); **PROPOSED** = recommendation; **INFERRED** = derived from confirmed facts or from a search-tool summary of an official document that the CI runner could not read; **UNRESOLVED** = not established.
Method limits: the sandbox cannot reach external hosts (`WebFetch` fails), so official documents were located with `WebSearch` and read, where possible, by the GitHub Actions runner through `tools/hist_02_acquire.fetch` (exact-URL allowlist, no redirect, 15 MB cap, sha256). Raw third-party bytes were never committed; the artifact holds aggregates and quotes of at most 25 words (14-day retention).
Evidence: `tools/eq_01_probe.py`, `.github/workflows/eq-01-probe.yml`, `tests/test_eq_01_probe.py` (synthetic fixtures only; they prove code, not data).

| CI run | Head SHA | Result |
|---|---|---|
| [39585320850](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39585320850) | 3cc78fb | first measured coverage (Yahoo series, Euronext texts) |
| [39594887020](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39594887020) | 7c1b5ff | S&P hosts 403, Stooq JS wall, Shiller page and file link read |
| [39595138648](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39595138648) | f3012cc | Shiller workbook read from the link on shillerdata.com (Yale URL gives a connection error) |

## 1. Verdict summary

| Question | Verdict (PROPOSED) |
|---|---|
| Is a long-term S&P 500 / AEX versus Dutch housing comparison methodologically feasible? | **Yes as a ratio of rebased index series (concept A)**, constrained by the housing side, not by the equity side. Equity histories (S&P 1927/1957, AEX 1983) are longer than any housing series the project can currently defend (CBS HPI 2000-01, NVM annual about 1975 PROPOSED/UNVERIFIED). |
| Can it be published with the data that were measured? | **No, not yet.** Every measured series is third-party (Yahoo Finance, rights UNVERIFIED). Official provider terms found forbid redistribution without a licence (Euronext, CONFIRMED) or require written permission (S&P DJI via FRED notice, INFERRED/secondary). A rebased index is close to the raw index, so the reconstruction risk is higher than for the gold ratio (GOLD-01 class, section 7). |
| Price return or total return? | They are different economic quantities and never interchangeable. For an investor view the total-return (or net total-return) variant is the meaningful one; free total-return history was measured only for the S&P 500 (from 1988-01-04, Yahoo) and not for the AEX. |
| Index points per house (concept B)? | **Not presentable.** Index points are not purchasable units. A valuation ratio needs an investable proxy with its own pricing method; if the proxy is defined as "value of EUR 100 invested at the baseline" it carries the same information as concept A (section 5). |
| Do S&P 500 and AEX share a starting point? | **No.** Credible starts differ (table in section 4); a common comparison window is the intersection and is limited by the shortest series. |

## 2. Source matrix (official documents first)

Quotes are verbatim, at most 25 words, from the runner unless marked secondary.

| Source / URL | Evidence | Key text | Meaning for EQ-01 |
|---|---|---|---|
| Euronext, "The composition of the AEX from 1983" `https://www.euronext.com/sites/default/files/aex_index_history_evolution_of_the_composition_from_1983.pdf` | CONFIRMED (OFFICIAL_TEXT_READ, run 39594887020) | "3 January 1983 Start of the Amsterdam Exchanges-index (AEX) at a level of 100." ; "4 January 1999 AEX index calculated in Euro's" ; "The contract size is 100 NLG times the index." | AEX inception and base value 100 (guilder-era level) on 1983-01-03; euro-denominated calculation from 1999-01-04. |
| Euronext, AEX Index Factsheet `https://live.euronext.com/sites/default/files/documentation/index-fact-sheets/AEX_Index_Factsheet.pdf` | CONFIRMED (text read; 3,064 characters) | "The AEX is a free float market capitalisation weighted index that reflects the performance of the 30 largest and most actively traded shares listed on Euronext Amsterdam" (as of 2026-09-30) | Current AEX has 30 constituents (older material says 25): composition changes over time; no introduction dates for AEX GR / AEX NR on the current factsheet text. |
| Euronext, Use of Euronext Index Data `https://live.euronext.com/en/products/indices/data-use` | CONFIRMED | "Euronext reserves all rights to the index data, and any unauthorized use, reproduction, or distribution of this data is strictly prohibited." ; "redistribution, reproduction, or incorporation into commercial products or services, a licensing agreement with Euronext is required." ; "for informational purposes only and are not intended for trading or investment purposes." | AEX values may not be published without a Euronext licence. Same class as GOLD-01 (IBA). |
| Euronext 2019 AEX factsheet `https://www.euronext.com/sites/www.euronext.com/files/aex_20190329.pdf` | INFERRED (search summary; the runner got a 301 to `http://`, which the allowlist rejects) | AEX introduced 1983-01-03; AEX GR introduced 1999-09-02; AEX NR introduced 2010-12-29; all three show 45.38 on 1983-01-03 | GR and NR start values are shown at 1983-01-03, so their earlier history is back-calculated (INFERRED; method text not read). 45.38 is 100 / 2.20371 (euro rebasing). |
| S&P Dow Jones Indices: "S&P 500 through history" `https://www.spglobal.com/spdji/en/documents/campaigns/sp-500-through-history-202301.pdf`, methodology page `https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/`, index page `https://www.spglobal.com/spdji/en/indices/equity/sp-500/`, terms `https://www.spglobal.com/spdji/en/terms-of-use/` | **NOT READ**: HTTP 403 from the GitHub runner for all four (`spglobal.com` without `www` answers 301 to `www`) | n/a | UNRESOLVED from primary text. The owner, or a browser session, must read them. |
| S&P DJI launch and back-test statements (search summary of S&P material) | INFERRED (secondary) | "launched on March 4, 1957"; "All information presented prior to this Launch date is back-tested"; back-tests use "the same methodology that was in effect on the Launch date"; base value 10 for 1941-1943 | The 1957 index is live from 1957-03-04; earlier S&P 500 values (S&P 90 composite since 1926, daily from 1928) are a historical reconstruction. |
| FRED SP500 notes `https://fred.stlouisfed.org/series/SP500` | NOT READ (timeout 30 s from the runner, as in HIST-02 and HIST-04) ; INFERRED (search summary of FRED graph copies dated 2016) | "10 years of daily history"; "Reproduction of S&P 500 in any form is prohibited except with the prior written permission of S&P Dow Jones Indices LLC"; requests to index_services@spdji.com | FRED is not a long-history source (rolling 10 years) and it carries an explicit S&P reproduction prohibition. |
| S&P DJI general terms (third-party copies, search summary) | INFERRED | Index Data "may be used only for your personal, non-commercial purposes"; no copying, retransmission or redistribution | Public display on a dashboard is outside personal use; a licence is needed (UNRESOLVED which). |
| Shiller, `https://shillerdata.com/` | CONFIRMED (page text read, run 39594887020) | "Stock price data are monthly averages of daily closing prices." ; "This data set consists of monthly stock price, dividends, and earnings data" ; link `ie_data.xls` | Shiller's monthly price is a monthly **average of daily closes**, not month-end. File content: section 3 (1871-01..2026-10, 1,870 monthly values, no gaps). No licence text was found on the page (UNRESOLVED). |
| Shiller lineage (search summary of papers) | INFERRED | Cowles and Associates 1871-1926, Standard and Poor 90 1926-1957, S&P 500 1957 onward | Pre-1957 history is a splice of different indices (composition, weights and constituents differ). |
| Yahoo Finance chart endpoint (`^GSPC`, `^SP500TR`, `^AEX`) | CONFIRMED technically (run 39594887020); rights UNVERIFIED | Yahoo terms not read | Free and reachable, but a vendor feed, not an index-provider source; no redistribution grant found. |
| Stooq CSV (`^spx`, `^aex`) | CONFIRMED unavailable | Response was an HTML page: "This site requires JavaScript to verify your browser. Please enable JavaScript and reload." | Not reproducible in CI. |

## 3. Measurements (CI, run 39594887020, daily closes, Decimal, raw bytes not stored)

Month gaps = calendar months strictly inside the range without any observation. All series: 0 duplicate dates, 0 unordered dates.

| Candidate | Index / variant | First | Last | Observations | Gaps | Per month (min/median/max) | Currency | Notes |
|---|---|---|---|---|---|---|---|---|
| Yahoo `^GSPC` | S&P 500 price return | 1927-12-30 | 2026-09-21 | 24,797 | 0 months | 1 / 21 / 23 | USD | Starts 1927 (S&P 90 composite era), not at the 1957 launch; sha256 `fa932ba4de2e...`. |
| Yahoo `^SP500TR` | S&P 500 total return (gross) | 1988-01-04 | 2026-09-21 | 9,752 | 0 | 14 / 21 / 23 | USD | sha256 `69a53e97c82c...`; the provider's own start of the TR index is INFERRED to be 1988-01-04 (not read). |
| Yahoo `^SP500NTR` | S&P 500 net total return | none | none | 0 (HTTP 200, empty) | n/a | n/a | n/a | Not available via Yahoo. |
| Yahoo `^SPXTR` | alias for TR | n/a | n/a | HTTP 404 | n/a | n/a | n/a | Wrong symbol. |
| Yahoo `^AEX` | AEX price return | 1992-10-12 | 2026-09-21 | 8,661 (94 null closes skipped) | 0 | 15 / 21 / 23 | EUR (Yahoo metadata) | **Yahoo starts 9.8 years after the index start (1983-01-03)**; sha256 `63733be2e24...`. Pre-1992 history not obtained. |
| Yahoo `^AEXGR` | AEX gross return | n/a | n/a | HTTP 404 | n/a | n/a | n/a | Symbol does not exist. |
| Shiller `ie_data.xls` | S&P Composite, monthly average of daily closes | 1871-01 | 2026-10 | 1,870 | 0 months | monthly | USD | Run 39595138648; sha256 `7cd02c342922...`; the last month is likely a partial month average (INFERRED); spliced lineage (section 2). The Yale URL `econ.yale.edu/~shiller/data/ie_data.xls` failed (connection error). The wsimg link carries a version query (`ver=`) and will change on update. |
| FRED `SP500` CSV | S&P 500 price | n/a | n/a | timeout 30 s | n/a | n/a | USD | Unreachable from the runner; licence limits it to 10 years anyway. |
| Stooq | S&P 500 / AEX | n/a | n/a | JavaScript wall | n/a | n/a | n/a | Not reproducible. |

Housing overlap (committed `data/cbs-housing.csv`): `nl_hpi` and `nl_house_avg_eur` 2000-01..2026-08, 320 months, no gaps. The three Yahoo series overlap this fully (daily to monthly via both bases below), so the common baseline is **2000-01**. Illustration only, with the repo's own helpers (not a result, not EUR-investor): relative performance `100 * idx_equity / idx_HPI`, both rebased to 2000-01, USD or EUR local index versus the EUR HPI:

| Series (local currency) | Basis | Min..Max over 320 months | sha256 of derived series |
|---|---|---|---|
| S&P 500 price (USD) | month average | 33.86 .. 176.85 | `afa47d15690d...` |
| S&P 500 price (USD) | month end | 33.28 .. 180.21 | `b85dfa9bfa27...` |
| S&P 500 total return (USD) | month average | 39.84 .. 287.74 | `867541cdfe4f...` |
| S&P 500 total return (USD) | month end | 39.09 .. 293.25 | `f27d9ee14b7f...` |
| AEX price (EUR) | month average | 21.04 .. 101.94 | `004bd14a0b51...` |
| AEX price (EUR) | month end | 22.59 .. 107.01 | `5b3ccec64d8...` |

The spread between price and total return (S&P maximum 177 versus 288) shows why the variants must never be interchanged. The USD rows ignore currency; the EUR-investor view needs section 4.3.

## 4. Definitions

### 4.1 Index variants

| Variant | Definition | S&P 500 | AEX |
|---|---|---|---|
| Price return (PR) | Index level from constituent prices; dividends are not included. | Launch 1957-03-04 (INFERRED); S&P composite reconstruction back to 1926/1928; Yahoo 1927-12-30 (CONFIRMED). | AEX: start 1983-01-03 at 100 (CONFIRMED), 45.38 in euro terms (INFERRED); Yahoo only from 1992-10-12 (CONFIRMED). |
| Total return, gross (TR/GR) | Gross dividends reinvested at the ex-date, before withholding tax. | S&P 500 TR: Yahoo from 1988-01-04 (CONFIRMED); earlier history not obtained. | AEX GR: introduced 1999-09-02, values shown from 1983-01-03 (INFERRED, back-calculated); no free series obtained. |
| Net total return (NR/NTR) | Dividends reinvested after withholding tax of a reference investor; the tax assumption is part of the definition and must be read per index. | S&P 500 NTR: no series obtained; assumption UNRESOLVED. | AEX NR: introduced 2010-12-29 (INFERRED); Dutch dividend withholding is the expected assumption (INFERRED from general knowledge, not read). |

A back-calculated value is not an observed value: it applies today's methodology to the past (S&P statement above). The project's labelling rule (METHODOLOGY v2.4: no splice, no synthetic backfill without a model label) applies; back-tested history needs an explicit label and an owner decision.

### 4.2 Denomination

S&P 500: USD throughout. AEX: guilder level until 1998-12-31, euro level from 1999-01-04 (CONFIRMED); the euro-denominated history is the guilder level divided by the fixed rate 2.20371 NLG per EUR (Council Regulation (EC) 2866/98; the rate is labelled UNVERIFIED in HIST-04 until fetched from EUR-Lex). Rebasing makes this division irrelevant for a **relative** series (a constant factor cancels), which is the main reason to prefer rebased indices over levels.

### 4.3 Local-currency versus EUR-investor performance

For the S&P 500 the EUR investor holds a USD asset: `idx_EUR[t] = idx_USD[t] / USD_per_EUR[t]`, at the same period and the same basis (month average over month average, as in ADR-004 for gold; month end over month end). Candidate FX (HIST-04, not approved): ECB `EXR.D.USD.EUR.SP00.A` daily from 1999-01-04 (monthly mean agrees with the provider's monthly series to 5.3E-14; Jensen gap up to 0.23% when inverted rates are averaged, so average the quoted direction first); before 1999 the Fed H.10 historical USD/NLG (daily noon rates, 1971-01-04..1998-12-31, 288/288 months from 1975-01, public domain by Fed text) divided by 2.20371. A missing FX day stays missing; no weekend or holiday carry-forward (CONFLICT_MATRIX: red decision open). The AEX needs no FX (EUR/NLG already). Local-currency (USD) and EUR-investor series are different quantities and must carry different labels.

## 5. Comparison concepts

### Concept A: relative performance (PROPOSED specification)

1. Choose one **index variant** per equity series and one **housing definition**; never mix (helpers raise `RETURN_TYPE_MIXING`, `HOUSING_DEFINITION_MIXING`, `CURRENCY_MIXING`).
2. Choose the **baseline period** B = earliest period where both series have an observation of the same frequency and basis (`common_baseline`); a baseline that does not exist in both is rejected, no nearest-date substitution.
3. `A_index[t] = 100 * A[t] / A[B]`, `H_index[t] = 100 * H[t] / H[B]`.
4. `relative_A_to_housing[t] = 100 * A_index[t] / H_index[t]`, only for periods present in both; others stay absent. Interpretation: the number of "baseline houses" one baseline-worth of index is worth; above 100 the index outperformed the house price since B.
5. Housing side: **CBS HPI** (constant quality) is the right denominator for "price of a house of constant quality" and is monthly from 2000-01; the **average transaction price** (CBS `nl_house_avg_eur`, NVM) mixes composition and volume effects and answers "what did the average sold home cost", a different use case. They are not interchangeable (METHODOLOGY v2.4).
6. Frequency: monthly equity (derived from daily by an explicit basis, section 6) versus monthly CBS; **annual** NVM (about 1975, PROPOSED/UNVERIFIED) versus annual equity (calendar-year mean of daily closes or year-end, explicit). Annual housing is never turned into monthly values (`annual_to_monthly` always raises); daily is never compared directly to monthly.
7. Date range: the intersection of both ranges; baseline in that range. Examples: CBS HPI 2000-01..2026-08 with any measured equity series (320 months, baseline 2000-01); NVM annual 1975.. with S&P 500 annual (needs the equity series to 1975; Yahoo 1927 suffices) but with AEX only from 1983 (Euronext) or 1992 (Yahoo).

### Concept B: nominal valuation ratio

`house_eur / index_level` is **not** presentable: an index level is a unit-less number whose absolute value depends on the base date and base value (S&P 500: 10 in 1941-1943; AEX: 100 in 1983, or 45.38 in euro). Index points are not shares, prices or portfolio units, so "houses per index point" has no economic reading and changes with rebasing (`houses_per_unit(..., 'index_points')` raises). Acceptable alternatives (PROPOSED):

- **B1, baseline-euro portfolio:** `V[t] = 100 EUR * idx_EUR_TR[t] / idx_EUR_TR[B]`; `houses_per_portfolio[t] = house_eur[t] / V[t]`. This is concept A on the average transaction price with a euro scale and carries no extra information.
- **B2, investable proxy:** a named total-return tracker (fund or ETF) with a defined pricing basis (NAV or close, month basis), its own ongoing charges and tracking difference, and its **own, shorter history** (typically from the 1990s-2000s; not researched here, UNRESOLVED). Only B2 can say "units purchasable", but it is a different series with a different rights position (fund data).

## 6. Methodology options and recommendation (PROPOSED, never ACCEPTED)

| Option | Description | Pro | Contra |
|---|---|---|---|
| M-A | Monthly **average of daily closes** (Shiller definition, consistent with ADR-004's monthly means) | Matches Shiller (independent cross-check possible); consistent with the gold method; smooths day noise | Weaker as a "performance" figure than a point-in-time close |
| M-B | **Month-end close** (last observed trading day) | Standard return convention; point-in-time | No independent free cross-check found; sensitive to a single day; differs from CBS (which averages transactions in the month) |
| M-C | Annual (calendar-year mean or year-end), annual housing only | Reaches back to NVM 1975 | Coarse; only valid annual versus annual |

Recommendation (PROPOSED):

1. Primary comparison = concept A with **total return** (S&P 500 TR in EUR) and the **CBS HPI**, monthly from 2000-01, basis M-A for both equity and FX (ratio of monthly means, as ADR-004); price-return versions only as separately labelled context. AEX: use only a variant whose history the owner can license and verify (price from 1983-01-03 per Euronext; GR/NR labelled back-calculated before 1999-09-02/2010-12-29 respectively).
2. Long-run extension: annual versus annual with NVM, separately labelled, with equity annual means; no monthly manufacture.
3. Earliest defensible start per series: see section 8. The common window is the intersection; do not pad the shorter series.
4. Do **not** publish equity levels, rebased equity indices or the relative series until rights are cleared (section 7); the fallback that avoids redistributing a provider's series is not available, because a rebased index plus the public CBS HPI reconstructs the index (see 7).
5. Independent cross-checks: Shiller monthly average versus the Yahoo-derived month-average for the S&P composite/500 (price); price versus total return consistency (TR growth minus PR growth equals dividend contribution, sign check only); Euronext composition PDF for the AEX start level; nothing free was found for AEX total return.

## 7. Rights and reconstructability risks (GOLD-01 class)

- **Euronext (AEX):** CONFIRMED text prohibits redistribution, reproduction or incorporation into commercial products without a licence. The dashboard would show a derived monthly series from 1983/1992; reconstructability is high because a rebased index preserves the shape of the AEX exactly.
- **S&P DJI (S&P 500):** terms not readable from the runner (403). Secondary evidence: written permission needed to reproduce the S&P 500 (FRED notice) and personal non-commercial use only (general terms). A licence enquiry (index_services@spdji.com per the FRED notice) is an owner action.
- **Yahoo Finance:** vendor terms not read; Yahoo redistributes licensed index data; its rights do not pass to the dashboard. Reproducibility risk: undocumented endpoint, history can change; the repo's BTC-01 analysis of the same vendor applies.
- **Shiller:** page states the definition; no licence statement found (UNRESOLVED); the file is a third-party research compilation, with S&P-derived values after 1957.
- **Derived-data risk:** unlike the gold ratio (gold price / FX / house price, three inputs hiding the gold price), `100*A/H` with a public H gives A exactly. Treat any relative series as equivalent to publishing the index.
- **FX inputs** (ECB, Fed H.10) have the open-reuse terms already read in GOLD-01 and HIST-04; the Fed text says information is in the public domain.

## 8. Earliest defensible start per index and variant

| Series | Official start (evidence) | Measured free coverage | Defensible start for a published comparison |
|---|---|---|---|
| S&P 500 PR | Index live 1957-03-04 (INFERRED); S&P 90 composite 1926/1928 (INFERRED) | Yahoo 1927-12-30 | 1957-03 as "S&P 500"; 1928-1957 only labelled as composite/back-calculated; limited in practice by housing (2000-01 CBS HPI; about 1975 NVM annual) |
| S&P 500 TR | S&P TR history start not read | Yahoo 1988-01-04 | 1988-01 (measured); earlier needs a source (S&P licence or Shiller-based third-party reconstruction, labelled) |
| S&P 500 NTR | not read | none | UNRESOLVED |
| AEX PR | 1983-01-03 at 100 (CONFIRMED) | Yahoo 1992-10-12 | 1983-01 only with a licensed Euronext series; 1992-10 from the free measured feed (partial first month) |
| AEX GR | 1999-09-02 introduction, values from 1983-01-03 (INFERRED) | none | UNRESOLVED; pre-1999-09 is back-calculated |
| AEX NR | 2010-12-29 introduction (INFERRED) | none | UNRESOLVED; pre-2010-12 is back-calculated |
| Shiller S&P Composite (monthly average) | 1871 (INFERRED lineage) | see section 3 | usable as a cross-check; splice of Cowles/S&P 90/S&P 500 means 1871-1957 is not the S&P 500 |

S&P 500 and AEX have **different credible starting points**; a joint chart must start at the later one, and the shortest housing series fixes the real window.

## 9. Open owner decisions

1. Which variant is the project's equity definition: total return (gross or net) in EUR, or price return? (Recommended: total return, separately labelled; RED under CHANGE_CONTROL: economic definition.)
2. Monthly basis: month average (M-A, consistent with ADR-004) or month end (M-B)? FX alignment must match (RED: price/time aggregation).
3. Is back-calculated history acceptable, and with what label (S&P composite before 1957, AEX GR/NR before introduction)? (RED: historical data meaning.)
4. Is a licence enquiry to S&P DJI and Euronext authorised, and is publication without a licence acceptable as a registered residual risk as in GOLD-03? (RED: publication meaning and security boundaries.)
5. Source priority: Yahoo (reproducibility and rights risk) versus a licensed provider; independent check with Shiller. (RED: source priority.)
6. FX for the EUR-investor view: ECB from 1999-01 plus Fed H.10/NLG with 2.20371 before; weekend/holiday policy (existing open item).
7. Is concept B2 (investable proxy) wanted? If so, a separate research task for fund pricing, charges and history.
8. Housing denominator per use case: CBS HPI for relative performance, average transaction price for "cost of an average home".

## 10. Next steps (research only)

- Read S&P DJI documents from a browser session (403 for runners): launch date, base, back-test statement, TR/NTR start dates and tax assumptions; capture exact terms for public display.
- Read the Euronext AEX index guide (variants GR/NR, introduction dates, back-calculation text) and request the licence terms for historical data.
- Quantify the monthly-average cross-check of the Shiller workbook (fetched, 1,870 months) against the Yahoo month-average (not yet computed).
- Re-run `eq-01-probe.yml` before relying on any number: Yahoo and provider pages change. A green run is not a methodological or publication approval.
