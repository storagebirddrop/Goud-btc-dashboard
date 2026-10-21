# Historical data foundation: work index (research only)

Status: **RESEARCH. Nothing here is approved, published or a decision.** No change to production gold/CBS data, ADR-004, the JSON contract or the Bitcoin/equity withholding. Created 2026-10-21 from `main` `0bfc040`.

Mission: the longest *defensible* historical base for comparing Dutch house prices with gold, Bitcoin and (later) the S&P 500 and AEX. A series is never extended beyond its defensible coverage; no splice, interpolation or forward fill.

## Naming (to avoid confusion with earlier work)

The repository already holds HIST-01..HIST-05 research (`docs/research/HIST_0*.md`, `tools/hist_0*.py`). This assignment builds on that work and uses new identifiers:

| Track | ID | Report | Builds on |
|---|---|---|---|
| Dutch housing 1975+ (NVM, CBS/Kadaster, overlap, currency, pre-1975) | HIST-06 | `HIST_06_HOUSING.md` | HIST-01, HIST-02, HIST-05 (NVM, CBS) |
| Gold before 2000 and NLG/EUR constructions, grams per home | HIST-07 | `HIST_07_GOLD_NLG.md` | HIST-03, HIST-04, HIST-05 (gold per home) |
| Bitcoin history from the earliest credible market | BTC-02 | `BTC_02_HISTORY.md` | BTC-01 |
| S&P 500 and AEX feasibility | EQ-01 | `EQ_01_EQUITY_FEASIBILITY.md` | new |
| Historical data model, validators, publication-layer separation | ARCH-02 | `HIST_ARCH_02_MODEL.md` | ARCHITECTURE.md, DATA_CONTRACT.md |

Final deliverables of this branch (index, coverage matrix, executive report): see the sections below, filled when the tracks are complete.

## Rules for every track

- Raw third-party bytes are not committed; CI artifacts and logs carry aggregates, hashes and metadata only. Every claim is labelled CONFIRMED (primary text or measurement), PROPOSED, INFERRED or UNRESOLVED.
- Original nominal values, derived EUR values and inflation-adjusted values stay separate. Annual data is never turned into monthly data.
- Production-affecting choices (source priority, aggregation, FX, scope, publication) are ROOD (`CHANGE_CONTROL.md`): research and propose only.
