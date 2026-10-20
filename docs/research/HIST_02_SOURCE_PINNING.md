# HIST-02 — source pinning and retention

DATA-01B principles are binding: explicit HTTPS source identity and redirect policy, 15,000,000-byte maximum, immutable raw byte hash before parsing, deterministic source identity distinct from retrieved_at_utc, offline replay without network fallback, reject missing bytes/hash mismatch and unapproved source substitutions.

HIST-02 implementation: `tools/hist_02_annual_research.py` contains offline-only `verify_source_bytes(path, expected_sha256)`; no network call, production import or source replacement. Synthetic fixture tests exercise match, mismatch, missing and empty source. This verifies a research interface, **not live source acquisition**.

Original NVM, World Bank historical GOLD and official DNB USD/NLG source bytes: NOT ACQUIRED. Source SHA-256: NOT AVAILABLE. Raw storage: NOT_CONFIGURED. Durable replay: NOT VERIFIED. No raw third-party data is committed or uploaded. Source rights and access remain UNVERIFIED.

Future live acquisition requires approved exact endpoint(s), HTTPS redirect allowlist, explicit data use and retention decision, isolated bounded fetch and raw byte pin, parser provenance, content hash and readback. A hash-only manifest without retained accessible bytes does not prove durable replay.

---

**Update 2026-10-20 (HIST-03):** the statement that World Bank historical GOLD source bytes are 'NOT ACQUIRED' with SHA-256 'NOT AVAILABLE' is superseded for GOLD only. Now demonstrated: the World Bank Pink Sheet workbook was acquired in GitHub Actions through the single approved path (`tools.hist_02_acquire.fetch`, run in `hist-03-worldbank-validation.yml`); sheet `Monthly Prices`, column BR (`GOLD`), unit row `($/troy oz)`; 300 of 300 months 1975-01..1999-12 present with no gaps, duplicates or invalid values; the sheet spans 1960-01..2026-09 (801 months); two parsers (stdlib XML and openpyxl) read the same bytes identically; canonical series SHA-256 `283901356b716b4fa455be4e06a3145675f9464385c778b692ee1f3e437c4cf7`. Raw bytes stay ephemeral; only metadata is retained (workbook SHA-256 in the review-only artifact `hist-03-worldbank-gold-summary-review-only`).

NOT demonstrated: a second, independent data source for GOLD (the two parsers prove parser reproducibility on identical bytes, not correctness of the series); historical USD/NLG FX (FRED EXNEUS still times out on response headers); a EUR/NLG gold price; house price expressed in grams of gold; source rights and retention (UNVERIFIED); and the open anomaly that part of the in-range GOLD values are whole numbers (precision statistics are reported, cause unresolved). NVM and DNB/FRED source bytes remain NOT ACQUIRED. Durable raw retention remains NOT_CONFIGURED (bytes are ephemeral; only hash and metadata are kept).
