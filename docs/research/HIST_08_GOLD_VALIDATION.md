# HIST-08: validation of the HIST-07 gold constructions C1, C3, C4 (research only, nothing approved)

Status: **RESEARCH. Not a decision, not a methodology, not a publication.** Labels: CONFIRMED (measured in CI run or read from primary text, run ids below), INFERRED (reasoned from measurements or general knowledge, not tested), PROPOSED (a suggestion for the owner), UNRESOLVED (open). Any use of these constructions in the dashboard is ROOD under `docs/governance/CHANGE_CONTROL.md`.

**NOT authorized by this document:** replacing or extending production gold (ADR-004, `etl/gold_monthly.py`, 2000-01 onward), accepting any gold methodology, accepting Fed noon rates or any FX source as a definition, publishing any pre-2000 or 1999 gold value, or changing `data/`, `frontend/`, existing `etl/` files or any ADR. C1 is a **research candidate with quality levels**, nothing more. Rights for all sources stay `UNVERIFIED`; artifacts contain aggregates and a 36-row derived overlap table only, no raw third-party bytes.

Subject under test: `docs/research/HIST_07_GOLD_NLG.md`, `tools/hist_07_gold_constructions.py`, `tools/hist_07_collect.py`, `tools/hist_04_*.py`.
Candidates: **C1** = World Bank USD/oz monthly x NLG per USD (1975-01..1998-12 and earlier), **C3** = C1 / 2.20371 (retrospective nominal EUR equivalent), **C4** = USD/oz / ECB USD per EUR from 1999-01 (ADR-004 logic).

## 0. Method and evidence

New tool `tools/hist_08_gold_validate.py` (workflow `.github/workflows/hist-08-gold-validate.yml`, `contents: read`, push on this branch, PR on own paths, `workflow_dispatch`; artifact `hist-08-gold-validation-not-approved`, 14 days). All statistics are **new exact `Fraction` code** (aggregation rules, nearest-rank and linear percentiles, overlap deviations, rounding bounds, sensitivities). The HIST-07 functions (`c1`, `c3`, `c4`, `overlap_compare`, `deviation_stats`) are called only afterwards on identical inputs to compare (`agreement_with_hist07_code`). File parsers (Fed text, BIS/IMF/CBS, World Bank workbook) are reused, so **parser faults are not independently covered** (UNRESOLVED, section 12). Tests: `tests/test_hist_08_gold_validation.py` (35 offline tests: direction, unit conversions, aggregation, overlap recompute on synthetic data, corrupted fixtures, no network). Full `python -m pytest -q` passes locally.

| CI run | Commit | Result |
|---|---|---|
| [39603054673](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39603054673) | 4304cb5 | success; ECB reachable for none of M/D (HTTP error); World Bank, Fed, BIS, IMF, CBS, BoE sections complete |
| [39603429227](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39603429227) | 07fea90 | success; ECB daily reachable, ECB monthly HTTP error (transient); ADR-004 comparison complete |
| [39603667519](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39603667519) | 1f84bd3 | success, `missing_sources` empty, `defects` empty, `not_performed` empty: overlap, grams, changeover, direction continuity |
| [39603870292](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39603870292) | 522fef4 | success, complete; source hashes below, remaining sections |

Source hashes (run 39603870292) equal the HIST-07 hashes: World Bank workbook `ea1c3508...3154` (matches the pin), ECB monthly `ed68895c...84f1a`, ECB daily `26c7d991...3c00`, Fed `dat89_ne.txt` `dfad62a4...e8d3`, `dat96_ne.txt` `3329eee3...d325`, Fed euro `dat96_eu.txt` `7bcb9833...3905`, `dat00_eu.txt` `e8159e23...4813`, BIS `5996ed2a...e1df`, CBS 7139 data `035ed44f...d021`, BoE monthly `f2265367...1116` (CONFIRMED: inputs identical to HIST-07, so differences below are method, not data). The ECB monthly series was unreachable in the first two runs (HTTP error, ~1 s); the tool then used the exact mean of the ECB daily rates and flagged it (`ECB_MONTHLY_UNAVAILABLE_USED_EXACT_MEAN_OF_ECB_DAILY`). All numbers quoted below come from runs 3 and 4 where the provider monthly series was used.

## 1. Result in one table

| Question | Result | Label |
|---|---|---|
| FX direction | Fed series is NLG per USD; all four independent readings agree (section 2) | CONFIRMED |
| Overlap numbers of HIST-07 (36 months, 149-month run) | reproduced by independent code: all stats equal to 4 dp, month-level difference <= 5.4E-34 | CONFIRMED |
| What the overlap measures | only the difference between a non-ECB monthly FX mean and the ECB mean; exact identity C3(ECB fixed cross) == C4 in 36 of 36 months | CONFIRMED |
| Monthly aggregation | mean of daily values; the alternative end-of-month moves C1 by a median 1.1%, i.e. 20x more than any source difference | CONFIRMED |
| Currency units | consistent: NLG per USD 1.55..3.74, C3/USD 0.70..1.70, troy-oz unit text present | CONFIRMED |
| World Bank whole dollars | all 801 months are whole USD in every period, including 2000-2026; none "before year X" only | CONFIRMED |
| Rounding impact on C1 | worst case 0.45% (1976-08), median 0.14%; 1979-1998 worst case 0.22% | CONFIRMED |
| Pre-1971/1973 regime | World Bank gold is a flat 35 in 1960-1967 and shows 7 further months at 35 up to 1970-08; not a market series before 1971 | CONFIRMED values, regime reading INFERRED |
| ADR-004 (C4) | production `etl.gold_monthly` equals the exact independent calculation (321 months, difference 0.000000%) | CONFIRMED |

## 2. FX quote source and direction (scope item 1)

CONFIRMED:
- Fed H.10 history files `dat89_ne.txt` + `dat96_ne.txt`: 7,021 daily observations 1971-01-04..1998-12-31, 4 decimals, 283 `ND` markers (not filled). The header text of the two files matches the pattern `GUILDERS/US$` (tokens "guilder" and "US$" present) and the value median is 2.1500, so `by_text == by_value == NLG_PER_USD`.
- The header text does **not** contain the words noon, buying, New York, certified or customs (all `false`). That the series are New York noon buying rates therefore rests on the Fed H.10 documentation read in HIST-04, not on the data file. INFERRED for this run; not re-read here.
- Euro changeover continuity: implied USD per EUR from the Fed mean of 1998-07..12 is 1.14136 under the NLG-per-USD reading and 4.25488 under the inverted reading; ECB 1999-01..06 mean is 1.09014. Deviation +4.70% versus +290.31%. The +4.70% is a real market move (the euro fell in early 1999) and sits close to the 5% threshold I set in the tool; the test discriminates the two readings by a factor of 60 but is not tight evidence on its own. The decision rests on text, values and the agreement below.
- Other sources against the Fed monthly mean (median ratio, 336 months 1971-1998): BIS EUR per USD x 2.20371 = 1.00000, IMF = 0.99994, CBS = 0.99982. All three use NLG per USD after conversion.
- BIS `WS_XRU` `M.NL` is EUR-denominated (EUR per USD), so the NLG value is a **derivation** (x 2.20371), never an NLG original.

## 3. Monthly aggregation: mean of what (scope item 2)

CONFIRMED definition used by C1/C3: arithmetic mean of the available Fed daily noon rates of the calendar month (17-23 observations, median 21, 0 months below 15). The World Bank gold value is "average of daily rates" (HIST-07 Description-sheet text), so the mean is the only aggregation that has the same basis on both factors.

Alternative monthly FX values, effect on C1 (relative change; grams per home move inversely one-to-one), Fed daily 1975-01..1998-12, 288 months:

| Alternative | median abs | p95 abs | max abs (month) |
|---|---|---|---|
| last observation of month (end of month) | 1.146% | 3.709% | 6.758% (1985-03) |
| first observation of month | 1.049% | 3.844% | 4.780% (1978-10) |
| median of daily values | 0.161% | 0.755% | 1.579% (1995-08) |

For 1971-1974 the same rules give median 0.55-0.60% (last/first) and max 5.7%. End-of-period against average in the BIS series (collections E and A, 468 months 1960-1998): median 0.532%, p95 3.149%, max 7.190% (1985-03). Fed last observation against BIS end-of-period (derived), 336 months: median 0.174%, max 1.958%, so the two "end of month" definitions differ from each other by far less than from the mean.

Mean of products versus product of means (BoE daily gold x Fed daily, 240 months 1979-1998, independent recompute): median 0.0066%, p95 0.0385%, max 0.2104% (1980-03). This reproduces HIST-04 section 5 exactly (CONFIRMED). Using monthly gold times monthly FX is therefore harmless against the mean aggregation choice.

Consequence (INFERRED): the aggregation rule dominates every source-noise term in this document. It is a ROOD definition choice (price/time aggregation), not a technical detail.

## 4. Currency-unit consistency (scope item 3)

CONFIRMED:
- Constants: 2.20371 NLG per EUR and 31.1034768 g per troy oz are identical (exact `Fraction`) in HIST-07 and the new code. World Bank unit row mentions troy oz and `$`.
- C1 / USD ratio (= NLG per USD) ranges 1.5474..3.7387 over 1975-1998; C3 / USD ranges 0.7022..1.6966. A reversed direction would give ratios near 0.3-0.6.
- Euro-era identity: for 1999-01..2001-12 (36 months) C3 built from the fixed cross `NLG per USD = 2.20371 / (USD per EUR)` equals C4 **exactly** (zero difference, `Fraction` arithmetic).
- Grams per home is invariant to the redenomination rate when house and gold are converted with the same rate (exact, test `test_redenomination_is_value_neutral_for_grams_per_home_exactly`). It is **not** invariant when the house price is already in EUR at the official rate and gold at a wrong rate: a +1% rate error gives C3 -0.990099% and +1.000000% grams per home (exact numbers, 1998-06 example; section 10).
- Quote/unit confusion checks in HIST-07 (`UnitError` on NLG/EUR or USD/oz mixing) are matched by synthetic negative tests here (inverted ECB series shows a >10% deviation, inverted Fed series is rejected).

## 5. World Bank whole-dollar values and rounding (scope item 4)

CONFIRMED (workbook sha256 equals the pin, 801 of 801 months 1960-01..2026-09, 0 gaps):
- **0 non-integer values in 801 months**, in every period. The premise that only early years are whole-dollar is wrong for the current vintage; 2000-2026 is whole dollars too. HIST-07 reported that an older vintage (datahub) carried decimals in 15 months; that comparison was not repeated here.
- Rounding bound 0.5 USD as share of value, and the expected mean absolute error if rounding were uniform (0.25 USD):

| Period | n | min / median USD | bound at min | bound at median | expected mean abs error |
|---|---|---|---|---|---|
| 1960-67 | 96 | 35 / 35 | 1.429% | 1.429% | 0.714% |
| 1968-74 | 84 | 35 / 43 | 1.429% | 1.163% | 0.490% |
| 1975-78 | 48 | 110 / 149.5 | 0.455% | 0.334% | 0.165% |
| 1979-89 | 132 | 227 / 399.5 | 0.220% | 0.125% | 0.064% |
| 1990-98 | 108 | 284 / 367 | 0.176% | 0.136% | 0.070% |
| 1999-2001 | 36 | 256 / 275.5 | 0.195% | 0.182% | 0.091% |
| 2002-2026 | 297 | 282 / 1,280 | 0.177% | 0.039% | 0.027% |

- Worst-case rounding effect on C1 (it equals 0.5 / USD value because FX cancels): 1975-1998 median 0.136%, p95 0.360%, max 0.455% (1976-08); 1979-1998 median 0.131%, p95 0.171%, max 0.220% (1979-01).
- Is the World Bank value a rounded copy of a decimal series? Against BoE monthly (decimals): 1990-1998 all 108 months within 1 USD, 98 within 0.5 USD, 98 equal to round-half-up of BoE, median abs 0.231 USD (uniform rounding predicts 0.25), mean signed -0.044 USD, max 0.952 USD (1993-12). 1979-1989: 107 of 132 within 0.5 USD and equal to rounded BoE, 118 within 1 USD, 14 beyond 1 USD, median abs 0.300, p95 1.728, max 57.095 (1980-12), mean signed -0.531 USD. 1999: 12 of 12 within 0.5. Reading (INFERRED): from 1990 the World Bank value is consistent with a whole-dollar rounding of a London-fixing average plus a small basis difference for about 10 of 108 months; 1979-1989 carries the three known outliers and a negative mean offset of about half a dollar. Which provider serves which period stays UNRESOLVED.
- Effect on C1 of using the World Bank instead of BoE gold with the same FX (240 months 1979-1998): median 0.069%, p95 0.263%, mean -0.051%, max 9.594% (1980-12; also 1983-07 -4.669%, 1985-03 +3.309%). Reproduces the HIST-07/HIST-04 outlier numbers (CONFIRMED).
- Grams per home with World Bank gold shifted by -0.5 / +0.5 USD (1995-1999): maximum annual change 0.181% / 0.180% (section 8).

## 6. Early official-price regime (scope item 5)

CONFIRMED values: 1960-01..1967-12 is a flat 35 (96 consecutive months, one distinct value). 103 months in total equal 35, so 7 further months after 1967-12 equal 35, the last in 1970-08; 1968-01..1974-12 has 40 distinct values and a longest equal run of 4 months. Later values: 1971-07/08/09 = 41/43/42, 1971-12 = 43, 1972-01 = 46, 1973-02 = 74, 1973-03 = 84, 1974-12 = 184, 1975-01 = 176.

FX: BIS-derived NLG per USD 1960-1972 largest monthly steps -4.302% (1961-03), -2.306% (1971-09), -1.859% (1971-08), -1.828% (1972-01), -1.629% (1971-12). The most frequent 4-decimal values 1960-1970 occur only 2-3 times (3.5958, 3.6012, 3.7711), so the BIS-derived series is not a constant parity but a monthly average of a managed rate. Fed monthly steps 1971-1975: +7.417% (1973-11), +6.058% (1975-07), -5.984% (1973-02), -5.584% (1973-06), -5.487% (1973-07).

INFERRED (general knowledge, not tested): official gold price 35 USD until the 1971 suspension, two-tier market from 1968, official changes in 1971-1973, free market from the mid-1970s; guilder revaluation in March 1961; floating from 1973. UNRESOLVED: why 7 months after 1967-12 sit at exactly 35 while neighbouring months exceed it (a mixed official/market series in 1968-1970 is possible).

Consequence (PROPOSED): before 1971 the series is not a market price and the FX is a managed parity (CBS vs BIS-derived median 0.067%, IMF vs BIS-derived median 0.478% with +0.345% mean bias). 1971-1974 is a floating-FX, regime-change period with a gold series of whole dollars and a bound up to 1.4%.

## 7. Provenance and reliability of the FX series (scope item 6)

**Fed H.10 (CONFIRMED measurements):** 7,021 daily values, 4 decimals (rounding effect <= 0.003%), 17-23 observations per month, 0 months below 15, longest gap 10 days (ends 1971-08-23), 13 daily moves above 3%, largest +6.596% (1978-11-01), -5.459% (1973-02-13), -4.307% (1973-09-17), +4.192% (1971-08-23), -3.946% (1971-08-24). The dates coincide with well-known policy events (INFERRED); whether any single value is a typing error was **not tested** (no one-day reversal test was run). The same file family covers the euro era (`dat96_eu.txt`, `dat00_eu.txt`).

**BIS-derived (CONFIRMED):** `WS_XRU` `M.NL`, collections A (average) and E (end of period) each 877 months 1953-09..2026-09, EUR per USD, mostly 5-6 decimals. After 1999 it is **not** an exact copy of the ECB: against the reciprocal of the ECB monthly mean, 333 months, median 0.0073%, p95 0.036%, max 0.225% (2008-12). This softens the HIST-07 wording "BIS after 1999 is ECB-derived (INFERRED)": at 0.01% typical it follows the ECB closely but is a separate compilation. Pre-1999 fingerprints (months within 5E-5 NLG per USD): BIS vs Fed 50 of 336, BIS vs IMF 85 of 468, BIS vs CBS 3 of 408; within 1E-3: 150, 257, 85. BIS is therefore not a copy of any of the other three (INFERRED that it is an independent compilation; shared upstream quotations cannot be excluded).

**IMF (CONFIRMED):** values with 9-11 decimals in 317 of 504 months, i.e. a computed series; vs Fed 1971-1998 median 0.064%, max 5.412% (1971-12), vs BIS-derived 1960-1970 median 0.478%, max 0.793%. Not suitable as a primary source (cause UNRESOLVED). **CBS 7139SHFO:** 2 decimals in 387 of 444 months (1 decimal in 57); vs Fed median 0.130%, max 0.995% (1973-03).

Pairwise spreads recomputed independently, 1971-1998, 336 months: BIS-derived vs Fed median 0.0543%, p95 0.2355%, max 0.4647% (1991-03); CBS vs Fed median 0.1296%, max 0.9951%; IMF vs Fed median 0.0639%, max 5.4119%. All equal the HIST-07 table. Agreement is not independence (UNRESOLVED).

Reliability reading (PROPOSED): Fed is the most granular and complete source (daily, no missing month, 17-23 observations) and its direction is fully asserted; BIS-derived is the best monthly cross-check (median 0.054%, max 0.46%); CBS is too coarse; IMF fails before 1973 and in 1971-12. None of the four has verified rights.

## 8. The 1999-2001 overlap, independently recomputed (scope item 7)

Construction (CONFIRMED algebra): with `NLG per USD = 2.20371 / (USD per EUR_alt)`, `C3/C4 - 1 = ECB / alt - 1`, so the overlap measures only the monthly-mean FX difference between an alternative source and the ECB. The tool computes the full formulas and asserts the closed form in exact arithmetic for every month. The overlap **cannot** test a guilder-specific market effect (the cross was fixed) or the gold side (same World Bank USD on both sides).

| Alternative FX (36 months) | median abs | mean signed | p95 abs (nearest rank / linear) | max abs (month) | HIST-07 reproduced |
|---|---|---|---|---|---|
| Fed euro noon, monthly mean | 0.0582% | +0.0324% | 0.3035% / 0.2370% | 0.3074% (2000-10) | yes, 4 of 4 stats |
| BIS `M.NL` average | 0.0110% | +0.0162% | 0.0410% / 0.0396% | 0.0442% (2000-12) | yes |
| CBS 7139SHFO (2 dp) | 0.1180% | -0.0207% | 0.4223% / 0.4135% | 0.5338% (1999-07) | yes |
| IMF | no data after 1998-12 | | | | n/a |

Mean signed by year (Fed): 1999 +0.0113%, 2000 +0.0710%, 2001 +0.0149%. Long run Fed vs ECB, 149 months 1999-01..2011-05 (2011-06 has 8 observations and is dropped): median 0.0509%, mean -0.0144%, p95 0.2404% (linear 0.2351%), max 0.4591% (2008-12); all four statistics and the month count reproduce the HIST-07 values. Agreement with the HIST-07 code: maximum month-level difference 5.4E-34 (Fed), 1.6E-34 (BIS), 2.9E-34 (CBS); same month sets.

Findings that go beyond HIST-07:
1. The HIST-07 p95 range "0.24-0.30%" mixes two percentile definitions. HIST-07 uses nearest rank (0.3035% for the 36 Fed months); linear interpolation gives 0.2370%. With n = 36 the nearest-rank p95 is the second-largest month. The honest statement is "p95 0.24-0.30% depending on definition, max 0.31%".
2. With a mismatched aggregation the gap is not small. Fed last observation vs ECB mean: median 1.33%, mean signed +0.55%, max 4.42% (2000-12). Fed mean vs ECB last: median 1.32%, max 3.85% (2000-04). Fed last vs ECB last (same "end of month" basis, different fixing time and place): median 0.268%, p95 0.884%, max 0.989% (2001-12), i.e. about 4.6x the mean-vs-mean gap. ECB end-of-month vs ECB mean (the effect on C4 itself): 1999-2001 median 1.38%, max 4.23%; 2002-2026 median 0.76%, max 5.10% (2010-11). INFERRED: the mean-vs-mean gap of 0.06% is small because averaging removes day-level noise, not because the New York noon rate and the ECB fixing are the same quantity.
3. Changeover: implied USD per EUR from the Fed mean of 1998-12 is 1.171187; ECB 1999-01 is 1.160780 (-0.8886%); World Bank gold 292 -> 287. The overlap bound (0.06% typical, 0.31% max) is much smaller than this -0.89% step, so most of the step is market movement, but a definitional part cannot be excluded or quantified (UNRESOLVED, as in HIST-04).

## 9. ADR-004 and C4 (scope item 8)

CONFIRMED: the ECB provider monthly series equals the exact arithmetic mean of the ECB daily rates in all 333 months 1999-01.. (difference 0.000000% at 6 dp). `etl.gold_monthly.parse_ecb` + `compute` (prec 28) reproduce the independent `Fraction` mean (334 months) and C4 (321 months from 2000-01) with a maximum relative difference below 1E-20 (printed 0.000000%). The 12 months of 1999 are available with the same formula but production starts 2000-01 (extending is a scope change, ROOD).

## 10. Sensitivity of grams of gold per home 1995-1999 (scope item 9)

Annual mean of the monthly values, EUR route, CBS fixture `data/fixtures/cbs-1995-1999-i1.json`, 12 months required per year, pre-1999 C3, 1999 C4:

| Variant | 1995 | 1996 | 1997 | 1998 | 1999 | max annual change vs base |
|---|---|---|---|---|---|---|
| base: Fed mean, World Bank | 10,378.71 | 10,721.20 | 11,991.53 | 14,615.17 | 17,130.89 | base |
| BIS average derived | 10,378.83 | 10,722.73 | 11,993.00 | 14,611.78 | 17,130.89 | 0.023% |
| Fed last of month | 10,428.56 | 10,706.28 | 11,947.31 | 14,623.27 | 17,130.89 | 0.480% |
| Fed first of month | 10,360.19 | 10,745.63 | 12,041.25 | 14,564.65 | 17,130.89 | 0.415% |
| Fed median of month | 10,354.79 | 10,720.26 | 11,996.80 | 14,621.15 | 17,130.89 | 0.231% |
| World Bank -0.5 USD | 10,392.23 | 10,735.07 | 12,009.80 | 14,640.08 | 17,161.85 | 0.181% |
| World Bank +0.5 USD | 10,365.22 | 10,707.37 | 11,973.32 | 14,590.33 | 17,100.04 | 0.180% |
| rate 2.20371 +1%, house EUR fixed | 10,482.49 | 10,828.41 | 12,111.45 | 14,761.32 | 17,130.89 | 1.000% |

The base column reproduces HIST-07 and HIST-05. Monthly maxima against base: BIS 0.183% (1997-09), Fed last 3.08% (1995-02), first 4.58% (1995-08), median 1.55%. The base grams rise 65.1% from 1995 to 1999; every variant shows the same direction and size of change. Fixed-rate sensitivity (exact): rate +1% changes C3 by -0.990099% and grams per home by 0.000000% if house and gold use the same rate, by +1.000000% if only gold does.

"2.20371 versus observed EUR/USD" (INFERRED from the algebra in section 8): inside 1999-2001 the observed and the fixed route are the same quantity (zero difference). Before 1999 no observed euro market rate exists (CONFIRMED in HIST-07: no ECB reference rate earlier), so a "market EUR" comparison is impossible; the only measurable proxy is the changeover step above.

## 11. Quality levels and decision-ready recommendation

Quality levels (PROPOSED, thresholds are a suggestion, not decided). Typical = median, bound = p95 or worst case, all for the C1 monthly value:

| Level | Period | Evidence | Typical uncertainty | Bound |
|---|---|---|---|---|
| A | 1979-01..1998-12 | WB cross-checked with BoE; Fed daily; BIS/IMF/CBS monthly checks | gold 0.07% (WB vs BoE), FX 0.05% (BIS vs Fed), rounding 0.13% | gold p95 0.26%, three outliers up to 9.6%; FX p95 0.24%, max 0.46%; rounding 0.22% |
| B | 1975-01..1978-12 | as A, gold has no second source | rounding 0.16% expected | rounding 0.45%; gold not cross-checkable |
| C | 1971-01..1974-12 | Fed daily; whole-dollar gold in a regime-change period | rounding 0.49% expected | up to 1.43%; Fed monthly steps up to 7.4%, aggregation sensitivity up to 5.7% |
| D | 1960-01..1970-12 | managed parity, flat or mixed 35 | not meaningful | not a market series |
| E | 1999-01..1999-12 | C4, ADR-004 formula; World Bank unchanged | rounding 0.18% | Fed-vs-ECB bound 0.31% max if Fed euro is used instead (not needed, ECB is available) |

Recommendation (PROPOSED, for owner decision, each item ROOD):
1. Keep C1 as a research candidate for 1975-1998 with levels B and A; do not publish levels C and D. Present C3 only as a captioned nominal equivalent next to the NLG value; never mix it with C4 in one unlabelled series. The grams-per-home result is the same for C1 and C3 (exact), so this is a presentation choice.
2. The decision with the largest effect is the monthly aggregation, not the FX source: mean of daily values (consistent with the World Bank "average of daily rates") versus end of month changes C1 by a median 1.1% and annual grams per home by up to 0.48%. If the owner prefers any other rule, section 3 gives the cost.
3. Accept source noise explicitly as: FX definition 0.05% typical and 0.46% worst pre-1999 (0.31% max in the euro overlap); rounding 0.13% typical and 0.22% worst for 1979-1998; gold source 0.07% typical with three flagged outliers. Total typical 0.1-0.2%; this is small against the 65% change in grams per home 1995-1999.
4. Do not "repair" the whole-dollar rounding or the outliers; publish the bound. Pin the workbook hash and a revision policy (HIST-07 found an older vintage differing in 15 months).
5. C4 for 1999 is the ADR-004 formula and was confirmed equal to the independent calculation; whether to extend production to 1999-01 is a scope decision.
6. Do not claim the 1998-12 -> 1999-01 step (-0.89%) as a pure market move.

Uncertainty of this recommendation: the Fed provenance text, rights, provider lineage of the World Bank series and parser independence are not verified (below). Two options for the owner: (a) 1979-1998 only (level A, most defensible), (b) 1975-1998 with B labelled. Advice: (b), because the rounding bound at B (0.45% worst) is still below the smallest aggregation alternative (median 1.1%).

## 12. Not verified / UNRESOLVED

1. Parsers (Fed text, BIS, IMF, CBS, World Bank workbook) are reused; an error shared by all would not show. The cross-source agreement (median 0.05%) makes a gross parsing error unlikely but does not prove none.
2. That the Fed series are New York noon buying rates is not in the data file header (section 2); it rests on HIST-04 documentation. Not re-read here.
3. Provider lineage of the World Bank gold by period; the 7 months at 35 after 1967-12; the outliers 1980-12, 1983-07, 1985-03; the IMF deviation in 1971-12.
4. Rights and licensing of every source (`UNVERIFIED`); no rights opinion is given.
5. Single-day typing errors in the Fed daily file (no one-day reversal test).
6. The older World Bank vintage comparison and the June 2025 World Bank provider break were not repeated here.
7. 2.20371 itself was verified in HIST-04 CI against the primary text, not re-verified here.
8. ECB monthly was intermittently unreachable (2 of 4 runs); the reported numbers come from the runs that used the provider series, and the fallback is flagged in the artifact.
9. A guilder-native gold price (C2) was not searched again.

## 13. Reproducibility

`python -m pytest -q tests/test_hist_08_gold_validation.py` (offline). `python -m tools.hist_08_gold_validate --summary-out S.json --overlap-csv-out O.csv [--workbook local.xlsx]` (CI only; exits 1 only on defects; unreachable sources are listed in `missing_sources`, dependent sections in `not_performed`). `--print-summary S.json --keys a.b,c` prints sections (dotted paths allowed). Summary keys: `unit_consistency`, `fx_direction`, `fx_provenance`, `fx_regimes`, `worldbank`, `aggregation_sensitivity`, `overlap_1999_2001`, `adr004_production_vs_independent`, `grams_per_home_1995_1999`, `fixed_rate_sensitivity_example_1998_06`, `changeover_step`, `checks`.
