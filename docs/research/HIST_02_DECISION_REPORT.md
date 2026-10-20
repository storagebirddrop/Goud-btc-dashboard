# HIST-02 — evidence-based decision

**Outcome: BLOCKED for reproducible 1975–1999 numerical prototype; CONDITIONAL GO only for continuing controlled source acquisition. Publication readiness: NO-GO.**

| Criterion | Outcome | Evidence |
|---|---|---|
| Source availability | PARTIAL | Secondary Vastgoedmarkt 1975 table referenced in HIST-01; original NVM, exact DNB historical FX and raw World Bank historical bytes not acquired |
| Source verification | BLOCKED | 0 independently byte-pinned historical NVM years; 0 independently replayed World Bank GOLD months; 0 independently verified USD/NLG months |
| Reproducibility | BLOCKED for real history | Offline deterministic calculator and synthetic tests only; raw source storage NOT_CONFIGURED |
| Comparability | NOT VERIFIED | Mean/median, per-ultimo, population, mix and original currency unresolved |
| Rights | NOT VERIFIED | Source and derivative reuse/retention permissions unresolved |
| Publication readiness | NO-GO | No approved historical method, source evidence or rights clearance |

Repository base: b5dae3fa165b3f94d437597115d9829303754ecc. Research branch only. No public dataset, CBS baseline, GOLD-03 PR #67, ADR-004 or production ETL changed.

Next narrow steps: (1) obtain original NVM/Vastgoedmarkt data dictionary and 1975–1999 records, confirm rights; (2) acquire and pin historical World Bank workbook in authorized isolated environment; (3) identify and pin exact DNB USD/NLG series, quote direction and monthly calendar; (4) rerun independent annual calculation and 1995–1999 overlap with complete source hashes; (5) separate methodology/publication decision.

No real annual price, gold or FX calculations are claimed as verified. No merge or deployment authorized.

---

**Update 2026-10-20 (HIST-03):** the 'Source verification' row above (0 independently replayed World Bank GOLD months) and next step (2) are superseded for GOLD only. Now demonstrated: the World Bank Pink Sheet workbook was acquired in GitHub Actions through the single approved path (`tools.hist_02_acquire.fetch`, run in `hist-03-worldbank-validation.yml`); sheet `Monthly Prices`, column BR (`GOLD`), unit row `($/troy oz)`; 300 of 300 months 1975-01..1999-12 present with no gaps, duplicates or invalid values; the sheet spans 1960-01..2026-09 (801 months); two parsers (stdlib XML and openpyxl) read the same bytes identically; canonical series SHA-256 `283901356b716b4fa455be4e06a3145675f9464385c778b692ee1f3e437c4cf7`. Raw bytes stay ephemeral; only metadata is retained (workbook SHA-256 in the review-only artifact `hist-03-worldbank-gold-summary-review-only`).

NOT demonstrated: a second, independent data source for GOLD (the two parsers prove parser reproducibility on identical bytes, not correctness of the series); historical USD/NLG FX (FRED EXNEUS still times out on response headers); a EUR/NLG gold price; house price expressed in grams of gold; source rights and retention (UNVERIFIED); and the open anomaly that part of the in-range GOLD values are whole numbers (precision statistics are reported, cause unresolved).
