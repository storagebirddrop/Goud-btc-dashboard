# HIST-04 Gold outliers: World Bank vs Bank of England (1980-12, 1983-07, 1985-03)

Status: research only. No gold methodology decision, no ADR change, no publication, no repository data change.
Labels: PROVEN = a tested hypothesis reproduces the World Bank (WB) value within 0.5 USD while BoE[m] itself does not; PLAUSIBLE = best residual within 2 USD but not reproduced; UNVERIFIED = neither.

## Evidence

- Code: `tools/hist_04_gold_outliers.py`, tests `tests/test_hist_04_gold_outliers.py` (synthetic fixtures only), workflow `.github/workflows/hist-04-gold-outliers.yml` (contents: read, aggregates/metadata-only artifact, 14-day retention, push limited to the branch plus workflow_dispatch).
- Commit analysed: `1560d9cff797b980efb1448381e1e57b0788dbd4` on `research/hist-04-gold-fx-consolidated`.
- Run: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39437490961 (success; numbers below are copied from its job log, section `REPORT`/`MONTH`). An earlier run on `13203c0` (https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39436764867) produced the same monthly numbers.
- Sources fetched in CI through `hist_02_acquire.fetch` (HTTPS allowlist, 15 MB limit): WB `CMO-Historical-Data-Monthly.xlsx` (sheet "Monthly Prices", column Gold, whole USD/oz, 300 months parsed); BoE IADB `XUMAGPD` (monthly) and `XUDLGPD` (daily; response sha256 `b1997422568a2d7c2633aa97528a7b85ffab71a9212287e3645f0c18f11da7e6`), plus the BoE notes page and the gold category page. Raw data is not stored in the repository.

## Findings on the BoE series

- A daily series exists: `XUDLGPD` "Gold price against US$", 1979-01-02 .. 1999-12-30, 5310 observations, no missing markers. Related series on the category page: `XUMAGPD` monthly average, `XUMLGPD` end month, quarterly/annual average and end-period variants, and Sterling variants (`...PS`). A single daily series: there is no separate AM and PM series, so AM-only/PM-only cannot be tested. (`XUDLGBD` guessed by pattern returns values around 0.4 to 0.9, a rate series and not gold; excluded by a scale guard. `XUDAGPD` was refused by the endpoint allowlist.)
- Notes page (CI text): prices are set twice daily (currently 10.30 and 15.00 hours); 1975 Q1 to 1979 Q3 are averages of Friday observations; thereafter based on daily observations; series ends May 2017. The notes do not state which fixing (AM or PM) `XUDLGPD` holds from 1979, nor the monthly averaging rule in words.
- Numerically, BoE monthly equals the arithmetic mean of the daily values: 252 months (1979-01..1999-12), maximum absolute difference 0.0000, 0 months over 0.01. So `XUMAGPD` is a plain mean over all observed days in the month.
- Deviation ranking WB vs BoE monthly (252 common months, 35 over 0.5 USD): 1980-12 57.0952, 1983-07 19.7357, 1985-03 10.0571, then 1979-12 6.0711, 1985-11 3.2905, 1981-01 1.9167, 1985-04 1.7275, 1986-01 1.6227. The three months are the three largest by a wide margin.

## Per-month results (USD/oz, WB minus BoE)

| Month | WB | BoE monthly (= daily mean) | Diff | Diff % of BoE | Days / Fridays | Daily min..max | WB inside daily range? |
|---|---|---|---|---|---|---|---|
| 1980-12 | 538 | 595.0952 | -57.0952 | -9.594 | 21 / 3 | 558 .. 635 | no (below min) |
| 1983-07 | 403 | 422.7357 | -19.7357 | -4.669 | 21 / 5 | 410.75 .. 430.5 | no (below min) |
| 1985-03 | 314 | 303.9429 | +10.0571 | +3.309 | 21 / 5 | 287.25 .. 330.4 | yes |

Neighbours (WB / BoE / diff):

| Offset | 1980-12 | 1983-07 | 1985-03 |
|---|---|---|---|
| -3 | 674 / 673.625 / +0.375 | 433 / 432.8789 / +0.1211 | 320 / 319.0526 / +0.9474 |
| -2 | 661 / 661.1478 / -0.1478 | 438 / 438.0175 / -0.0175 | 303 / 302.7909 / +0.2091 |
| -1 | 625 / 623.4625 / +1.5375 | 413 / 412.8409 / +0.1591 | 299 / 299.1 / -0.1000 |
| 0 | 538 / 595.0952 / -57.0952 | 403 / 422.7357 / -19.7357 | 314 / 303.9429 / +10.0571 |
| +1 | 557 / 558.9167 / -1.9167 | 416 / 416.2636 / -0.2636 | 327 / 325.2725 / +1.7275 |
| +2 | 500 / 499.7625 / +0.2375 | 412 / 411.8023 / +0.1977 | 316 / 316.3667 / -0.3667 |
| +3 | 499 / 498.7614 / +0.2386 | 394 / 393.1024 / +0.8976 | 317 / 316.49 / +0.5100 |

Hypothesis tests (diff = WB minus candidate; none within 0.5):

| Candidate | 1980-12 | 1983-07 | 1985-03 |
|---|---|---|---|
| BoE[m-1] (month shift back) | -85.4625 | -9.8409 | +14.9000 |
| BoE[m+1] (month shift forward) | -20.9167 | -13.2636 | -11.2725 |
| Daily mean, all days (= weekdays; all rows are weekdays) | -57.0952 | -19.7357 | +10.0571 |
| Mean of Fridays only | -46.9167 | -19.0800 | +10.8600 |
| Last day of month | -51.5000 | -19.0000 | -15.2500 |
| First day of month | -97.0000 | -13.2500 | +26.7500 |
| Median | -55.7500 | -20.7500 | +21.3000 |
| Min / Max | -20.0 / -97.0 | -7.75 / -27.5 | +26.75 / -16.4 |
| Any single day within 0.5 of WB | none | none | none |
| WB value (+/-0.5) found in another BoE month | none | none | none |

Whole-USD rounding: WB is an integer, so rounding explains at most 0.5 USD; all three differences are 20x to 114x larger. Rounding is excluded for all three months (the rounding of the other months is also not the whole story: diffs of 1.5 to 1.9 occur at 1980-11 and 1981-01, so WB is not a pure rounding of the BoE mean in general).

## Classification

| Month | Class | Reasoning |
|---|---|---|
| 1980-12 | UNVERIFIED | No tested hypothesis reproduces 538. WB lies 20 USD below the lowest daily observation of the month (558), so it cannot be any average or selection of the BoE daily values; the nearest candidate (month shift +1: 558.9167) is 20.9 off. The cause is therefore on the WB side (different source or fixing, data entry/transcription error) but this is not shown by the numbers. |
| 1983-07 | UNVERIFIED | 403 is 7.75 USD below the lowest daily value (410.75). Closest candidate is the daily minimum (-7.75) and BoE[m-1] (-9.84); neither is a reproduction and neither is a plausible averaging rule. Same side-of-origin statement as above, not proven. |
| 1985-03 | UNVERIFIED | 314 is inside the daily range, but no day lies within 0.5 and no mean variant or month shift is closer than 10 USD. Closest by residual: mean of Fridays (+10.86), BoE[m] (+10.06). Not reproduced. |

No month is PROVEN and none reaches PLAUSIBLE (best residual over 2 USD in all three). Statements such as "WB error" are hypotheses, not findings.

## Limits

- Only one daily series, one fixing basis unknown (AM or PM). A different fixing of the same day cannot be tested; if the WB value comes from the other fixing, it would need a second daily series, which the IADB list does not show (the plausible size of an AM/PM gap is a few USD, far below 57).
- The WB workbook's own definition note and the underlying source of the 1980s history were not retrieved (not in the tested files); the WB historical series may be compiled from a different base (for example the IMF/IFS or Metals Bulletin) than London fixings. UNVERIFIED.
- BoE is treated as the reference only because its daily rows are internally consistent with its monthly mean; BoE correctness against LBMA primary records was not checked.
- Percentages are relative to BoE. No interpolation or forward fill is used; absent months stay absent. Other differences (for example 1979-12 at 6.0711 and 1985-11 at 3.2905) are not analysed here.
- Source rights and licences are unverified; the artifact holds only aggregates.

## Not decided / next step for the owner

No choice is made on whether to flag, correct or exclude these WB months, nor on source priority. That is a ROOD decision (historical data and source priority) for the owner. A possible evidence step is to read the WB monthly note and the IMF IFS/Metals Bulletin value for these months, outside this repository.
