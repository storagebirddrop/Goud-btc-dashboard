# HIST-02 — FX series full coverage verification (2026-10-20)

**PARTIALLY VERIFIED: source metadata and selected table rows; complete 300-month row-by-row verification NOT EXECUTED. Original response bytes NOT VERIFIED.**

Authoritative table: https://fred.stlouisfed.org/data/EXNEUS (Federal Reserve Bank of St. Louis, EXNEUS, *Netherlands / U.S. Foreign Exchange Rate (DISCONTINUED)*). The table explicitly defines frequency **Monthly**, units **Dutch Guilder to One U.S. Dollar**, unadjusted, date range **1971-01 to 2001-12**, last update 2006-03-08. The stated series date range covers **1975-01 through 1999-12** (300 expected months), but no independent row-by-row 300-month completeness test has been executed. The 300-month coverage therefore remains **NOT VERIFIED**. Examples: 1975-01 2.4565, 1998-12 1.8816, 1999-01 1.9012, 1999-12 2.1797. No interpolation or reconstructed values used.

**Critical distinction:** browser-accessible metadata establishes the source's reported date range and quote direction, **not** a cryptographically pinned original CSV response. A direct attempt to retrieve `https://fred.stlouisfed.org/graph/fredgraph.csv?id=EXNEUS` in the isolated container failed DNS resolution. Consequently: original source bytes NOT ACQUIRED; SHA-256 NOT AVAILABLE; offline original-byte replay NOT VERIFIED; durable retention NOT_CONFIGURED. Do not misrepresent a web-rendered table or these examples as a pinned raw source.

**1999 methodological warning:** guilder was replaced by euro in accounting from January 1999; EXNEUS continues to report a synthetic guilder-equivalent quotation. Explicit confirmation of its underlying construction and alignment with the historical housing-price denomination is needed before accepting 1999 annual values.

**Gold:** World Bank original workbook still inaccessible to the web text reader (XLSX unsupported); container DNS unavailable. 0 original World Bank months byte-verified.

**Housing:** Vastgoedmarkt table is a secondary compilation attributed to NVM/NBM. Underlying annual source and statistical metadata remain unavailable.

**Next gate:** obtain original source files through an authorized runner with network access, hash before parsing, retain securely if permitted, independently replay all 300 months and validate housing definition. Until then no historical real-data prototype or public publication.


## HIST-02-H3 — official FRED distribution candidate (NOT APPROVED)

- Existing authorized endpoint: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=EXNEUS`. GitHub Actions: DNS PASS, TLS PASS, no HTTP response headers within 30 seconds. No HTTP status, no response bytes, no rate-limit conclusion. Root cause beyond response-header timeout is UNKNOWN.
- Official FRED table view: `https://fred.stlouisfed.org/data/EXNEUS`. Series EXNEUS is discontinued, monthly, not seasonally adjusted, *Dutch Guilder to One U.S. Dollar* (NLG_PER_USD), published range 1971-01 through 2001-12, last updated 2006-03-08. The web page is an alternative official **display**, not an approved machine acquisition endpoint or a pinned byte artifact.
- Official API v1 candidate: `https://api.stlouisfed.org/fred/series/observations` with `series_id=EXNEUS`, `observation_start=1975-01-01`, `observation_end=1999-12-31`, and explicit `file_type`. FRED requires a registered API key. Do not call without an authorized key, do not log credentials, and do not change the allowlist without explicit approval. API supports vintage/realtime parameters; pin exact requested vintage and original response bytes if approved.
- **Governance**: candidate only; NOT APPROVED; NOT ACQUIRED; NO FALLBACK. Rights and durable retention remain UNVERIFIED. The post-1999 synthetic guilder conversion and series revision policy require separate methodological review.
- The stated date range is **metadata**, not 300 validated observations. Neither FRED EXNEUS nor World Bank GOLD has a completed 300-month offline replay at this point.
- Source references: https://fred.stlouisfed.org/data/EXNEUS ; https://fred.stlouisfed.org/docs/api/fred/series_observations.html ; https://fred.stlouisfed.org/docs/api/terms_of_use.html

---

**Update 2026-10-20 (HIST-03):** the 'Gold' paragraph above ('workbook inaccessible', '0 original World Bank months byte-verified') is superseded for GOLD only. Now demonstrated: the World Bank Pink Sheet workbook was acquired in GitHub Actions through the single approved path (`tools.hist_02_acquire.fetch`, run in `hist-03-worldbank-validation.yml`); sheet `Monthly Prices`, column BR (`GOLD`), unit row `($/troy oz)`; 300 of 300 months 1975-01..1999-12 present with no gaps, duplicates or invalid values; the sheet spans 1960-01..2026-09 (801 months); two parsers (stdlib XML and openpyxl) read the same bytes identically; canonical series SHA-256 `283901356b716b4fa455be4e06a3145675f9464385c778b692ee1f3e437c4cf7`. Raw bytes stay ephemeral; only metadata is retained (workbook SHA-256 in the review-only artifact `hist-03-worldbank-gold-summary-review-only`).

NOT demonstrated: a second, independent data source for GOLD (the two parsers prove parser reproducibility on identical bytes, not correctness of the series); historical USD/NLG FX (FRED EXNEUS still times out on response headers); a EUR/NLG gold price; house price expressed in grams of gold; source rights and retention (UNVERIFIED); and the open anomaly that part of the in-range GOLD values are whole numbers (precision statistics are reported, cause unresolved). The FX statements above are unchanged: FRED EXNEUS 300-month coverage remains NOT VERIFIED (the CSV endpoint timed out on response headers after 30 s in every Actions run; the FRED probe is now a manual, non-fatal workflow).
