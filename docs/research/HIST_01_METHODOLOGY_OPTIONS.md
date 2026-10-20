# HIST-01 — methodological options (not accepted)

Annual research indicator: `grams_per_house_y = house_price_nlg_y * 31.1034768 / annual_gold_price_nlg_per_troy_oz_y`, only after proving source comparability, year definition and currency alignment. This is a **ratio of annual prices**. It is not the annual mean of monthly housing/gold ratios, and it is not a monthly point.

Candidate calculation policy (PROPOSED):
1. Pin original NVM/Vastgoedmarkt annual observations and identify whether values represent annual mean, year-end or another measure; distinguish mean from median.
2. Pin World Bank monthly USD/oz and official USD/NLG daily or monthly observations, verify historical coverage and source version.
3. Independently calculate month-aligned local-currency gold quotes, then explicitly documented annual arithmetic average if complete and justified.
4. Use same-year housing measure, original NLG where available. A retrospectively converted EUR house price may be converted to NLG with 2.20371 only when publisher methodology confirms that conversion and rounding.
5. Validate no duplicate/missing year, quote inversion, invalid units, missing FX, mismatched frequency, negative values, and nondeterminism; independent replay and source hashes required.
6. Never splice annual historical series into monthly JSON-v1, never alter ADR-004 index basis January 2000, never overwrite CBS.
7. Show a visible discontinuity between annual historical source and 1995–present CBS monthly observations. Separate annual series is preferable to unvalidated splice.

Alternatives: (A) separated annual historical segment, CONDITIONAL research; (B) statistically validated splice only with owner methodology decision; (C) annual-only exploratory chart; (D) no extension.

Required later tests: calendar continuity 1975–1999, duplicates, troy-ounce factor, fixed NLG/EUR conversion, daily/monthly FX direction, annual averaging vs ratio averaging, overlap 1995–1999, source-break annotations, missing FX fail-closed, deterministic serialization, existing 2000–2026 hash unchanged. No observational fixture values are asserted here.
