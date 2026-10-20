# HIST-02 — follow-up source discovery (2026-10-20)

Status: **SOURCE LOCATED, RAW BYTES NOT PINNED**. This is a factual supplement to HIST_02_SOURCE_ACQUISITION.md, not approval of historical calculations.

## Housing — NVM attribution confirmed in secondary publication

Vastgoedmarkt's original compiled PDF explicitly states under Figure 7: **“Bron: Voor alle genoemde prijzen: Nederlandse Vereniging van Makelaars NVM (voorheen NBM)”**. The table reports average sale prices for existing housing types, excluding new construction, rounded to EUR 1,000, with 1975–2023 annual rows; the 1975 row is 47 (thousands of EUR). The original NVM/NBM underlying transaction extract, geographic selection, mean calculation, meaning of *per ultimo*, original NLG conversion, vintage and rights remain UNVERIFIED. Thus NVM **attribution** is evidenced, but original NVM data provenance is not.

Primary secondary document: https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf

## FX — exact authoritative historical series found

**Federal Reserve Bank of St. Louis FRED series EXNEUS**, source release *Transitional Euro Country Exchange Rates*, is explicitly **Dutch Guilder to One U.S. Dollar**, **monthly**, not seasonally adjusted, from **1971-01 through 2001-12**, last updated 2006-03-08. This supplies the exact needed quote direction NLG_PER_USD and covers the requested 1975–1999 window *according to source metadata*. It is **not** a DNB-published series; document provider distinction. FRED table sample: January 1975 2.4565 NLG/USD, December 1998 1.8816, January 1999 1.9012. These are web-observed source examples, **not pinned original bytes**.

- https://fred.stlouisfed.org/series/EXNEUS
- https://fred.stlouisfed.org/data/EXNEUS
- https://alfred.stlouisfed.org/category?cid=268 (revision/vintage discovery)

Caveat: FRED's metadata and table establish a credible official-US-institution FX candidate, but historical **1999 synthetic guilder quote treatment after euro introduction**, calendar methodology, license, vintage and complete 300-row byte-level verification must be independently assessed. The separate FRED series CCUSMA02NLM618N is **Euro** and should not be silently substituted for the historical NLG quote.

## Gold — World Bank original source identified, still not acquired

The established World Bank workbook endpoint remains https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx . External references describe the monthly Pink Sheet extending to 1960, but 1975–1999 column-level completeness and the exact original workbook SHA-256 are NOT VERIFIED. Do not use a third-party rehost as an original World Bank source.

## Execution and retention

An actual HTTPS GET to the World Bank endpoint from the isolated execution container was attempted on 2026-10-20. It failed with DNS NameResolutionError before receiving any HTTP response. **0 original source files downloaded, 0 SHA-256 source-byte pins**, no historical real-data replay. No raw bytes stored, no DATA-01B allowlist changed, no release or public data changes.

Next controlled acquisition: add explicit FRED EXNEUS HTTPS endpoint to a separately reviewed research-only acquisition allowlist (not silently to DATA-01B production); pin World Bank XLSX, EXNEUS response and legally available NVM/Vastgoedmarkt inputs in an authorized isolated runner; verify bytes, metadata, rights and 300 aligned months before generating any historical numerical output.

---

**Update 2026-10-20 (HIST-03):** the 'Gold' and 'Execution and retention' statements above ('still not acquired', '0 original source files downloaded', '0 SHA-256 source-byte pins') described the isolated sandbox, where DNS failed, and stay true for that sandbox. They are superseded for the World Bank workbook by a later GitHub Actions run. Now demonstrated: the World Bank Pink Sheet workbook was acquired in GitHub Actions through the single approved path (`tools.hist_02_acquire.fetch`, run in `hist-03-worldbank-validation.yml`); sheet `Monthly Prices`, column BR (`GOLD`), unit row `($/troy oz)`; 300 of 300 months 1975-01..1999-12 present with no gaps, duplicates or invalid values; the sheet spans 1960-01..2026-09 (801 months); two parsers (stdlib XML and openpyxl) read the same bytes identically; canonical series SHA-256 `283901356b716b4fa455be4e06a3145675f9464385c778b692ee1f3e437c4cf7`. Raw bytes stay ephemeral; only metadata is retained (workbook SHA-256 in the review-only artifact `hist-03-worldbank-gold-summary-review-only`).

NOT demonstrated: a second, independent data source for GOLD (the two parsers prove parser reproducibility on identical bytes, not correctness of the series); historical USD/NLG FX (FRED EXNEUS still times out on response headers); a EUR/NLG gold price; house price expressed in grams of gold; source rights and retention (UNVERIFIED); and the open anomaly that part of the in-range GOLD values are whole numbers (precision statistics are reported, cause unresolved). The FRED EXNEUS, NVM and Vastgoedmarkt statements above are unchanged.
