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
