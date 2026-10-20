# GOLD-01 publication readiness: blocker matrix and verdicts

Research only. Nothing here approves publication, lifts the gold publication HOLD, or changes ADR-004, the public gold
fields or the JSON contract. Status date: 2026-10-20, main `3f9aee3`. This page summarizes two detailed reports:
[GOLD_01_RIGHTS.md](GOLD_01_RIGHTS.md) (official terms read, agent L) and
[GOLD_01_TECHNICAL_METHODOLOGY.md](GOLD_01_TECHNICAL_METHODOLOGY.md) (code, runs and method, agent T).
Scope: the two derived indicators the owner already limited on 2026-10-19 (`gold_index`, `gold_grams_per_house`), from
2000-01 on. Raw USD/oz and EUR/oz stay out of scope.

Evidence labels: CONFIRMED FACT (primary text read, or code/test/run), ASSUMPTION, OPEN LEGAL QUESTION, TECHNICAL
DEFICIENCY. This is not legal advice.

## 1. Verdicts (judged separately)

| Dimension | Verdict | Why |
|---|---|---|
| Technically ready | READY WITH CONDITIONS | The candidate pipeline conforms to ADR-004 line by line and is reproducible (GOLD-01 run 39486174734: 320 complete months; GOLD-02 run 39486179684: byte-identical candidate, independent replay PASS, 640 values, max relative deviation 1.89e-16; the replay shares bytes and sources, so it is code-independent only). The publication change itself does not exist and, as is, would break CI: it changes the pinned `APPROVED_PUBLIC_JSON_SHA256` and `BASELINE_JSON_SHA256`, the CBS replay step in `ci.yml` and the default `etl.data_quality` mode, and flips every test that asserts null gold. |
| Legally ready | NOT READY | The Pink Sheet GOLD series carries no gold-specific licence label and the workbook names several commercial providers as sources (Bloomberg, Kitco, IMF IFS, London Bullion Market, Metals Week, Platts, Thomson Reuters Datastream, among others). Whether the World Bank's third-party exception applies is an OPEN LEGAL QUESTION only the World Bank can answer. IBA/LBMA terms require a licence to "obtain, use or redistribute" benchmark data and list a derived-benchmark licence, but nothing read says whether a dashboard ratio counts. |
| Methodologically ready | READY WITH CONDITIONS | The method is decided (ADR-004 ACCEPTED for gold, GOLD-01 limited decision, ADR-011). Open: no independent second source for 2000-2026 (the Bank of England comparison covers 1975-1999 only), World Bank 2000+ rounding unverified, the June 2025 break not quantified, no revision policy, reconstructability stance undecided. |

## 2. Blocker matrix

| # | Blocker | Type | Evidence | Owner | Needed action |
|---|---|---|---|---|---|
| B1 | Is Pink Sheet GOLD under CC BY 4.0 or the third-party exception ("may not be redistributed or reused without the consent of the original data provider")? | OPEN LEGAL QUESTION | Terms text read; workbook Description sheet names several third-party sources, no licence statement | World Bank (data@ / pubrights@) | Written reply naming the rights holder and permission (see section 4) |
| B2 | Does IBA treat the two dashboard indicators as a derived index or as redistribution of LBMA data? | OPEN LEGAL QUESTION | IBA pages read: derived-benchmark licence exists; silent on data reached via the World Bank | IBA licensing, only if B1 fails | Reply on which licence this use needs |
| B3 | Reconstructability: `gold_eur_oz = house_eur x 31.1034768 / gold_grams_per_house` is exact from public fields (tested; floats unrounded); `gold_eur_oz` null is presentational only | OPEN LEGAL QUESTION and owner decision | Test in `tests/test_gold_01_readiness.py`; no term read addresses reconstruction | Lawyer or owner risk acceptance; owner (D3) | Decide: accept, or publish less precision / charts only |
| B4 | Upstream of GOLD since June 2025 is unknown (spot average, source not named) | ASSUMPTION | Workbook notes read | World Bank | Covered by the B1 reply |
| B5 | ECB: reuse requires the source quoted and statistics "not modified"; own modifications must be stated | OPEN LEGAL QUESTION (minor) | ECB policy read | Owner | Keep the explicit "own calculation" statement; confirm aggregation counts as stated modification |
| B6 | CBS table-level reproduction sentence for 85773NED not read (site-wide CC BY 4.0 with mandatory source naming is) | TECHNICAL DEFICIENCY of the evidence | Probe could not extract the sentence | Agent probe follow-up | Re-probe the table page |
| B7 | Publication change does not exist; breaks pins, CI and tests (14-step checklist in the technical report, section 3.3) | TECHNICAL DEFICIENCY | Code references in the technical report | Engineering after owner decisions | Release PR, ROOD per CHANGE_CONTROL |
| B8 | Publication path not chosen (private candidate vs reviewed bytes plus release record); release-record fields are hand-written attestations | TECHNICAL DEFICIENCY (medium) | Technical report T-8 | Owner (D7) | Choose the path and the CI design |
| B9 | World Bank workbook URL is versioned and frozen, but production code does not enforce its hash | TECHNICAL DEFICIENCY (medium) | Same sha in all runs; T-1 | Owner (D2) then engineering | Decide the revision policy and what is pinned |
| B10 | No independent gold source for 2000-2026; World Bank 2000+ precision unverified | TECHNICAL DEFICIENCY (medium) | BoE comparison covers 1975-1999; T-6 | Owner (D1) | Choose a threshold or second source |
| B11 | June 2025 definition break unquantified | Methodology | Workbook: afternoon fixing before, spot average from June 2025 | Owner (D6) | Quantify or keep annotating |
| B12 | Attribution lacks an as-of date and a methodology link; June 2025 wording sits in a collapsed section | TECHNICAL DEFICIENCY (medium) | T-9 | Owner (D8) then engineering | Decide the date field and wording |
| B13 | Docs do not reflect the 2026-10-19 limited decision: `DATA_SOURCES.md` line 47 and `PROJECT_STATUS.md` line 84 describe the gold indicators as HOLD/BLOCKED without that decision (line 12 concerns `gold_eur_oz`, which stays withheld by design) | TECHNICAL DEFICIENCY (docs) | Technical report; lines re-read on main | Owner (governance edit) | Reconcile the documents |
| B14 | Minor: ECB revisions not snapshotted, no minimum ECB days per month, no ECB monthly cross-check, hard-coded "PASS" in the GOLD-02 manifest, no assertions on workbook notes | TECHNICAL DEFICIENCY (low) | T-2 to T-5, T-7 | Engineering | Fold into the release PR |

## 3. Owner decisions (ROOD) that remain

D1 validation threshold or independent check for 2000+; D2 World Bank revision/update policy and pins; D3
reconstructability and published precision; D4 confirm GOLD-01 supersedes the earlier gold source reassessment for this
release; D5 minimum ECB days per month; D6 quantify or only annotate the June 2025 break; D7 release path and CI design;
D8 as-of date and JSON field. Plus the legal clearance in B1 (and B2 if needed).

## 4. Smallest responsible next step

One step, no code and no change to data, ADRs, JSON or the HOLD: the owner sends the single question already drafted in
[GOLD_PUBLICATION_DECISION.md](../governance/GOLD_PUBLICATION_DECISION.md) to the World Bank, sharpened with the new
evidence: the workbook's Description sheet lists several commercial sources for the Commodity Markets data, and no
licence statement. Ask (1) whether the GOLD series is covered by CC BY 4.0 or by the third-party exception, (2) who the
rights holder is if third-party, and (3) whether the two derived monthly indicators from 2000 on may be displayed with the
attribution text on record. A written reply decides whether B2 is needed at all; the technical blockers B7-B14 and the
owner decisions D1-D8 can then be worked in order. No external contact was made by this review.

## 5. Explicit non-claims

No licence conclusion is stated beyond the quoted official text. Nothing here authorizes publication, a release record,
a flag change, a merge or a deployment. The HOLD, ADR-004, the public gold fields and the JSON contract are unchanged.
