# HIST-08 closure report (A-H) - research only, nothing published

**A. PR #91 integrity.** `git diff --name-status origin/main...HEAD` against main `0bfc040`: only additions, no modified/renamed/deleted file. The earlier "24" omitted the report itself; GitHub's 25 was correct (since extended by HIST-08 files, all additions). Full suite and governance checks pass; CI green on every earlier head; ARCH-02 is imported only by its own module, checker and tests, its allowlist is empty and the gate denies unlisted/tampered series (tests).

**B. Housing.** NVM/Vastgoedmarkt 1974+ NOT recovered. The `.pdf` URL serves one 5335x3001 px raster (158 kB, `page=` ignored); OCR (normal and inverted) reads only "Vastgoedmarkt". I could not view the image from the sandbox, so no manual transcription; 0 verified NVM observations; NVM/CBS overlap NOT EXECUTED. Evidence and next steps: `HIST_08_NVM_RECOVERY.md`. CBS: 380 monthly observations (60 fixture 1995-1999 + 320 from 2000) bundled and validated, kept as two series.

**C. Gold.** Independent recomputation reproduces HIST-07 to 4 dp; Fed series is NLG per USD; C3 equals C4 exactly in the 36-month overlap (the overlap tests only the FX-mean difference, max 0.31%); aggregation choice (mean vs end of month) dominates (median 1.1%); World Bank whole-dollar rounding <= 0.22% for 1979-98; not a market series before 1971. Recommendation PROPOSED: C1 research candidate (1979-1998 level A, or 1975-1998 with labels). Details and unverified items: `HIST_08_GOLD_VALIDATION.md`.

**D. Bitcoin.** Preferred monthly definition (PROPOSED): mean of daily UTC closes of one venue; month close unusable (mean 8-10%, max 105%); true time-weighted average within 0.34% mean; USD to EUR via ratio of monthly means (0.13% mean vs Bitstamp EUR; matched-day worse); start months 2013-04 (USD-derived) and 2016-05 (Bitstamp EUR), 2014-02 earliest cross-validated; no splice (Mt. Gox vs Bitstamp 3.3% mean venue effect); tolerance 1% investigate / 5% fail. `HIST_08_BTC_DEFINITION.md`.

**E. Decisions D1-D7.** All PROPOSED, none recorded as accepted: `HIST_08_OWNER_DECISIONS.md`.

**F. HIST-08 readiness.** Implemented and tested: CBS bundle (real inputs), generic provenance-enforcing adapter, derived grams/sats over actual overlap (synthetic). Specified, blocked on CI wiring and D2/D3: gold, Bitcoin, NVM bundles (`HIST_08_BUNDLES.md`). New offline tests this phase: 35 gold, 45 Bitcoin, 20 bundle; suite 1315 passed, 5 skipped.

**G. Repo status.** Branch `feat/hist-foundation`, Draft PR #91, not merged; branches `hist-08-gold-validation` and `hist-08-btc-definition` merged into it (merge commits), can be deleted after the PR decision.

**H. Publication safety.** `frontend/public/data/monthly.json` sha256 `1afb0bf9...d8cd` and `data/cbs-housing.csv` sha256 `ad98bba9...22bb` unchanged (asserted by a test); `etl.data_quality` passes; no historical, Bitcoin, NVM or equity data released; `ALLOWLIST == ()`.
