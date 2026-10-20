# HIST-01 — gold and FX history

## Gold
The existing ADR-004 monthly methodology from January 2000 remains unchanged: World Bank Pink Sheet GOLD USD/troy oz, ECB daily USD/EUR monthly arithmetic mean, then grams per house using 31.1034768 g/troy oz. The World Bank GOLD definition change from June 2025 remains a separate warning.

The known World Bank historical workbook URL is https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx . Historical 1975–1999 monthly observations, revisions, workbook hash and vintage were **not independently inspected or pinned in this task**. A different LBMA fixing or daily spot series is not an automatically acceptable substitute.

## Currency
For 1975–1998 use a historically observed **NLG per USD** rate for the same year/month as the gold price and a house price in NLG. `gold_nlg_per_oz = gold_usd_per_oz * nlg_per_usd`. For the reverse quote `usd_per_nlg`, divide rather than multiply. Validate source direction and units. Official DNB historical USD/NLG series identification, full date coverage, original byte hash and rights remain **UNVERIFIED**; DNB starting point https://www.dnb.nl/statistieken/ .

ECB verifies fixed **1 EUR = 2.20371 NLG**, see https://www.ecb.europa.eu/euro/exchange/nl/html/index.nl.html . This is a retrospective unit conversion, **not** the USD/NLG market FX rate in 1975–1998. 1999 requires explicit euro-era pricing and USD/EUR series matching; do not assume that modern ECB endpoint extends to 1975.

## Temporal aggregation
For annual housing prices, choose a justified annual gold price in matching currency; document whether the annual price is the average of monthly USD-gold converted at each monthly NLG/USD rate or another specified daily/annual convention. `mean(gold_usd_month * fx_month)` generally differs from `mean(gold_usd_month) * mean(fx_month)`. No fill, interpolation, silent provider swap, or arbitrarily selected month. All months, valid quote directions and annual coverage must be verified before numerical output.

## Evidence
The current task did not fetch or pin raw gold/FX bytes, so no independent gold/FX numeric results are claimed. Raw external data must not be committed publicly without rights review.
