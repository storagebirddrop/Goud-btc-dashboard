# HIST-01 — decision report

**Research recommendation: CONDITIONAL GO for further evidence acquisition and isolated annual prototype; NO-GO for historical publication or CBS/NVM splice.**

Base repository commit: `4badeb9bcb9a8d45856d83d5aa77778582f79d5d`. Existing governance, ADR-004, GOLD-03 PR #67 and public data remain untouched.

## Questions answered
1. **Earliest evidenced historical annual housing year:** 1975 in Vastgoedmarkt's published compiled table (1975: 47 x EUR 1,000), **not established as original NVM series**. NVM-original earliest year: UNVERIFIED.
2. **Historical gold coverage:** World Bank historical monthly workbook known from project; exact 1975–1999 contents NOT VERIFIED in this research. No raw bytes or SHA obtained.
3. **FX:** official DNB USD/NLG historical series is a research candidate, not yet a verified downloaded time series. ECB fixed EUR/NLG 2.20371 is VERIFIED but not substitute for historical USD/NLG.
4. **NVM/CBS comparability:** NOT ESTABLISHED. CBS national Kadaster population and historical NVM sample differ; mean/median and year-end/annual timing potentially differ.
5. **1975 annual grams-per-house:** formula is dimensionally valid; **numerical 1975–1999 calculation NOT YET REPRODUCIBLE** without verified annual housing definitions, World Bank history and aligned USD/NLG FX.
6. **Breaks:** source/population and frequency NVM-vs-CBS; annual-vs-monthly; mean-vs-median; pre-euro NLG-vs-EUR; gold benchmark changes including June 2025 (outside historical interval).
7. **Potential later publication:** only licensed, independently pinned derived annual indicator with explicit source break, separate schema/view and owner decision. No automatic JSON-v1 extension.
8. **Blocking risks:** NVM-original attribution and sample metadata; annual average/year-end definition; official USD/NLG observation coverage; World Bank historical raw-byte replay; redistribution rights; independent overlap study and governance approval.

## Minimum next phase
- Acquire NVM original annual series and written methodology/licence, including 1975 proof.
- Pin World Bank 1975–1999 workbook bytes and validate GOLD cells and benchmark.
- Obtain and pin DNB historical USD/NLG rates, quote direction and time frequency.
- Independently compute 1995–1999 overlap and 1975–1999 annual prototype in an isolated review artifact with negative tests.
- Separate owner decision for method, rights and visualization. No publication or merge from this research PR.

**No historical numerical series was generated; no source bytes were committed; no new source hash claimed.**
