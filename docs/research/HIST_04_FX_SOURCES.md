# HIST-04 FX sources for gold-per-house in NLG/EUR (research, CANDIDATE)

Status: **candidate, not approved; needs owner decision per ADR/CHANGE_CONTROL (RED: source priority, price/time aggregation, FX assumptions).**
Nothing here is a decision, a source authorization, a rights clearance or a publication. `rights_status` stays `UNVERIFIED`, `publication_authorized` stays `false`.
Raw third-party data is never committed. CI artifacts hold aggregates and metadata only (14-day retention).

Evidence: tool `tools/hist_04_fx.py`, workflow `.github/workflows/hist-04-fx.yml`, offline tests `tests/test_hist_04_fx.py` (synthetic fixtures only; they prove code, not data).
CI runs on branch `research/hist-04-gold-fx-consolidated`:

| Run | Head SHA | Result |
| --- | --- | --- |
| https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39437923033 | ad514aa | ECB OK; Fed DDP Choose/Build HTTP 400 |
| https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39438643920 | e004495 | Fed G.5 XML package HTTP 404 |
| https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39439246477 | 62a44a1 | Eurostat probes added |
| https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39439591397 | 41e91f1 | Eurostat series parsed and compared (all numbers below) |

The workflow ends red (exit 2, status `PARTIAL`) on purpose: the Fed G.5 NLG series could not be obtained, and the tool does not hide that.

## 1. Quote direction and unit of every rate

All quotes are "units of the quoted currency per 1 unit of the base currency". The direction is stored in code (`DIRECTIONS`) and asserted where metadata allows.

| Quote | Direction | Meaning | Source status |
| --- | --- | --- | --- |
| Fed G.5 NLG | `NLG_PER_USD` | guilders for 1 US dollar (foreign currency per USD) | NOT obtained (section 2) |
| ECB EXR `D/M.USD.EUR.SP00.A` | `USD_PER_EUR` | US dollars for 1 euro (foreign currency per EUR); CI metadata: `CURRENCY=USD`, `CURRENCY_DENOM=EUR`, `UNIT=USD`, `UNIT_MULT=0` | fetched, parsed |
| Eurostat `ert_bil_eur_m`, USD, AVG | `USD_PER_EUR` (ECU before 1999-01) | USD for 1 euro/ECU, monthly average | fetched, parsed; definition of the pre-1999 basis not verified |
| Fixed conversion 1 EUR = 2.20371 NLG | `NLG_PER_EUR` | guilders for 1 euro | **UNVERIFIED**: from own knowledge of Council Regulation (EC) No 2866/98; no official page was fetched in CI |

## 2. Coverage, units and quality (real CI values, run 39439591397 unless noted)

| Series | Frequency | First | Last | Observations | Gaps / missing | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Fed G.5 USD/NLG (daily, monthly, annual) | n/a | n/a | n/a | 0 | not obtainable | `releases/g5/data/FRB_g5_xml.zip` (linked from the G.5 pages) returns HTTP 404; DDP `Choose/Build/Download/Output.aspx?rel=G5` and `rel=G5A` return HTTP 400 (Cloudflare); the G.5 pages show only current rates (EMU euro), no series hashes found (0 `series=` links). The H.10 package `releases/h10/data/FRB_h10_xml.zip` downloads (2,084,531 bytes) but H.10 is not expected to hold NLG; its content was not inspected. NOT VERIFIED whether the Fed still publishes historical NLG anywhere. |
| ECB EXR `D.USD.EUR.SP00.A` | daily, TARGET days only | 1999-01-04 | 2026-10-20 | 7,118 valid + 62 empty/NaN markers (kept absent) | 0 missing calendar months (334 months, 1999-01..2026-10); 14..23 observations per month (median 21, 1 month below 15) | weekends/holidays are absent in the source and stay absent here |
| ECB EXR `M.USD.EUR.SP00.A` | monthly average | 1999-01 | 2026-09 | 333 | 0 missing months | provider monthly vs own arithmetic mean of provider daily values: max relative deviation 5.311E-14 (2001-08), 0 months above 1E-4 |
| Eurostat `ert_bil_eur_m` USD AVG | monthly average | 1971-01 | 2026-09 | 669 values (336 months before 1999-01) | 0 missing months | 1998-12 = 1.1721, 1999-01 = 1.1608 USD per EUR/ECU; vs ECB monthly on 333 common months: max relative deviation 5.28E-5 (2000-04), 0 months above 1E-4 (values published with 4 decimals) |
| Eurostat `ert_bil_eur_m` NLG AVG | monthly | 1971-01 axis | 2026-09 axis | 0 values | all missing | time axis exists, no values: NLG not available through this query |

Transition 1998-12 / 1999-01: the daily overlap between a Fed NLG series and ECB is unavailable (no Fed NLG data), so the planned consistency check of ECB USD per EUR against `2.20371 / NLG_PER_USD` was NOT EXECUTED. The tool implements it (`transition_report`) and reports it as soon as a daily NLG series is supplied.

## 3. Jensen gap (ECB daily, 334 months)

For each month both `mean(1/x)` and `1/mean(x)` of the daily `USD_PER_EUR` quotes were computed with Decimal (34 digits). Relative gap `(mean(1/x) - 1/mean(x)) / (1/mean(x))`:

| Statistic | Value |
| --- | --- |
| minimum | 4.331E-6 |
| mean | 1.195E-4 |
| maximum | 2.253E-3 (2008-12) |
| months with gap >= 1E-5 | 328 of 334 |
| non-negative in all months | yes (as Jensen requires) |

Consequence: averaging inverted rates is not equivalent to inverting an averaged rate. In the worst month the difference is about 0.23 percent, which is larger than the 4-decimal rounding of the sources. The candidate method therefore averages only the quoted direction and inverts or divides after averaging; this is a documented choice, not an approved one.

## 4. Candidate conversion chain (not approved)

Decimal arithmetic only; no interpolation, no forward-fill of weekends or holidays; a missing quote yields a missing result (`null`).

1. Pre-1999, gold in NLG per ounce: `gold_usd_oz * NLG_PER_USD` (needs a daily or monthly NLG per USD series; none obtained yet).
2. 1999 onward, gold in EUR per ounce: `gold_usd_oz / USD_PER_EUR`, where `USD_PER_EUR` is the arithmetic mean of ECB daily quotes within the calendar month (quoted direction averaged first, division afterwards) or the ECB published monthly average (the two agree to 5.3E-14).
3. NLG to EUR, labelled derivation only: `x_nlg / 2.20371`. The rate is unverified (section 1).
4. Implied USD per EUR from G.5: `2.20371 / NLG_PER_USD` (for the overlap check only).
5. Pre-1999 EUR alternative (candidate, unverified basis): `gold_usd_oz / USD_PER_ECU` from the Eurostat monthly series. It bypasses NLG, but ECU is a currency basket and equals EUR only from 1999-01-01; whether the monthly average basis matches a daily-mean method is not established.

The Fed G.5 CSV parser (`parse_fed_g5`) is implemented for the documented Data Download Program layout (metadata rows, `Time Period` header, `ND` markers counted and kept absent, duplicate periods and non-positive numbers rejected). It has only been exercised on synthetic fixtures because the real file was not reachable.

## 5. Open questions (owner or later research)

1. Where can historical USD/NLG be obtained in a reproducible, rights-clear way (Fed G.5 historical archive, DNB, ECB/BIS/IMF IFS, Eurostat other datasets)? Candidates are listed, none is approved or tested beyond Eurostat.
2. Verify 2.20371 against an official EUR-Lex page fetched in CI; until then it is only a labelled assumption.
3. Is the Eurostat pre-1999 USD per ECU series acceptable as a stand-in for USD per EUR, and what is its exact averaging basis and licence?
4. Monthly aggregation of FX (arithmetic daily mean vs provider monthly average vs month-end) and the gold basis must be aligned with the monthly gold method; this is a RED change under CHANGE_CONTROL.
5. Rights and retention for Fed, ECB and Eurostat data are `UNVERIFIED`.
6. Once a daily NLG series exists: run the 1998-12/1999-01 transition and overlap check and compute the NLG Jensen gap (the tool already does both).
