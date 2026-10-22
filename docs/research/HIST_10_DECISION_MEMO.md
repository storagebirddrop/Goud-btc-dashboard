# HIST-10 methodology decision memo for Project Control (all PROPOSED, nothing decided)

Research only. None of the items below is accepted; ADR-004 is unchanged; nothing is published. Evidence: `HIST_10_GOLD_HOUSING.md`.

| # | Decision | Options | Quantified effect | Recommendation | Needed from Project Control |
|---|---|---|---|---|---|
| 1 | Half-year gold aggregation | M1 mean of monthly local prices; M2 ratio of half-year means; M3/M4 end/start of half | M2 within 0.34% of M1 (max), M3 up to 17.5%, M4 up to 21.7% (mean 4.0-4.5%) | M1 as the research rule; M2 as the sensitivity; reject end/start values as primary | Choose M1 or M2 |
| 2 | FX sampling | monthly mean (ADR-004 style) vs last or first day of the month | mean abs. 0.65-0.76%, max 2.70% (1985-H2) | monthly mean | Confirm |
| 3 | Eras and 1998/1999 | separate NLG-era and observed-EUR series, retrospective EUR as captioned third series; or one unlabelled EUR series | retro and NLG routes identical in grams (8e-34); gold step -0.83%, NVM grams +8.22% at the boundary, definitional part unquantifiable | separate series with an explicit break | Decide presentation and break marking |
| 4 | Start of the research range | 1975-01 (level B 1975-78, rounding up to 0.45%) or 1979-01 (level A) | rounding 0.45% / 0.22% worst case | 1975 with quality labels | Decide |
| 5 | NVM and CBS | separate always; optional side-by-side view 1995-2000 only | gap +9.64% (1995-H1) to -0.09% (2000-H2) in grams = in price | keep separate; never a combined homogeneous series | Decide whether a side-by-side view may ever be public |
| 6 | Weighting for the CBS comparison | M1 gold vs transaction-weighted gold (M5) | at most 0.354% | M1; M5 documented as sensitivity | Confirm |
| 7 | Monthly FX completeness | at least 50% of calendar days (provisional) | no effect on 1971-1998 or 1999-2026 except the partial month 2026-10 | keep, record | Confirm or set another threshold |
| 8 | Scope of gold publication before 2000 | stay research-only, or a future ADR to extend ADR-004 backwards | ROOD item: changes publication meaning and period | stay research-only until rights (World Bank, Fed, NVM) are decided | Decide separately; not requested now |
| 9 | Storage of the derived dataset | workflow artifact only, or small hash-pinned derived CSV in Git (D5) | derived values only, no raw third-party values | decide with D5 | Decide |
