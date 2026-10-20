# HIST-02 — isolated annual gold/housing research prototype

Code: `tools/hist_02_annual_research.py`; tests: `tests/test_hist_02_annual_research.py`. **Synthetic only**, no actual 1975–1999 observations or production dataset changes.

Formula (research candidate, not approved historical methodology): `house_nlg * 31.1034768 / gold_nlg_per_troy_ounce`.

Monthly aligned local gold: `gold_usd_per_oz * nlg_per_usd` for NLG_PER_USD; inverse quote uses division. Annual option A: arithmetic mean of 12 matching month-level local gold prices; year housing price divided by this mean. Option B: year-end local gold price (only if 'per ultimo' refers to a justified matching year-end house measure). A and B differ when gold prices vary. `mean(gold_usd * fx)` is generally not `mean(gold_usd) * mean(fx)`; annual price ratio is not average monthly ratios.

The offline module rejects missing/mismatched month sets, nonpositive or noncanonical numeric inputs, invalid quote direction, and incomplete year coverage. The fixed 2.20371 NLG/EUR conversion is for retrospective denomination, never historical USD/NLG FX.

**Historical numeric output: NOT GENERATED**. Required original annual housing observations, all 300 World Bank GOLD months and aligned 300 FX months have not been independently acquired. No public JSON-v1 changes, no monthly ADR-004 changes, no source fallback, no synthetic values presented as facts.

---

**Update 2026-10-20 (HIST-03):** the statement that all 300 World Bank GOLD months were 'not independently acquired' is superseded for GOLD only. Now demonstrated: the World Bank Pink Sheet workbook was acquired in GitHub Actions through the single approved path (`tools.hist_02_acquire.fetch`, run in `hist-03-worldbank-validation.yml`); sheet `Monthly Prices`, column BR (`GOLD`), unit row `($/troy oz)`; 300 of 300 months 1975-01..1999-12 present with no gaps, duplicates or invalid values; the sheet spans 1960-01..2026-09 (801 months); two parsers (stdlib XML and openpyxl) read the same bytes identically; canonical series SHA-256 `283901356b716b4fa455be4e06a3145675f9464385c778b692ee1f3e437c4cf7`. Raw bytes stay ephemeral; only metadata is retained (workbook SHA-256 in the review-only artifact `hist-03-worldbank-gold-summary-review-only`).

NOT demonstrated: a second, independent data source for GOLD (the two parsers prove parser reproducibility on identical bytes, not correctness of the series); historical USD/NLG FX (FRED EXNEUS still times out on response headers); a EUR/NLG gold price; house price expressed in grams of gold; source rights and retention (UNVERIFIED); and the open anomaly that part of the in-range GOLD values are whole numbers (precision statistics are reported, cause unresolved). The annual prototype itself is unchanged and still synthetic: historical numeric output remains NOT GENERATED because annual housing observations and aligned 300 FX months are still missing.
