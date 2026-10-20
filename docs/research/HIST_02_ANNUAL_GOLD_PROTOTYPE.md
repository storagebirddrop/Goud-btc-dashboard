# HIST-02 — isolated annual gold/housing research prototype

Code: `tools/hist_02_annual_research.py`; tests: `tests/test_hist_02_annual_research.py`. **Synthetic only**, no actual 1975–1999 observations or production dataset changes.

Formula (research candidate, not approved historical methodology): `house_nlg * 31.1034768 / gold_nlg_per_troy_ounce`.

Monthly aligned local gold: `gold_usd_per_oz * nlg_per_usd` for NLG_PER_USD; inverse quote uses division. Annual option A: arithmetic mean of 12 matching month-level local gold prices; year housing price divided by this mean. Option B: year-end local gold price (only if 'per ultimo' refers to a justified matching year-end house measure). A and B differ when gold prices vary. `mean(gold_usd * fx)` is generally not `mean(gold_usd) * mean(fx)`; annual price ratio is not average monthly ratios.

The offline module rejects missing/mismatched month sets, nonpositive or noncanonical numeric inputs, invalid quote direction, and incomplete year coverage. The fixed 2.20371 NLG/EUR conversion is for retrospective denomination, never historical USD/NLG FX.

**Historical numeric output: NOT GENERATED**. Required original annual housing observations, all 300 World Bank GOLD months and aligned 300 FX months have not been independently acquired. No public JSON-v1 changes, no monthly ADR-004 changes, no source fallback, no synthetic values presented as facts.
