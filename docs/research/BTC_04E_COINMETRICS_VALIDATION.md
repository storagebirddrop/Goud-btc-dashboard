# BTC-04E — Coin Metrics PriceUSD x ECB x CBS: validation and deterministic replay (research only)

**Status: RESEARCH ONLY. NO PUBLICATION. NO MERGE.** Nothing here is a production ADR, a licence opinion or a release authorization. `monthly.json`, the frontend, accepted gold outputs and the research publication allowlist (empty) are unchanged. Method `CM_PRICEUSD_MONTHMEAN_C1_V1` is conditionally accepted for research by Project Control; this report is the technical validation evidence. Baseline `main` `86621ea0f9aabf8dce540fb4b40ef40fa50caf34`.

## 1. What was built

| Item | File |
|---|---|
| Strict Coin Metrics Community `PriceUSD` adapter (explicit asset/metric, stable canonical query, bounded pagination restricted to the official HTTPS host, retry/backoff incl. `Retry-After`, UTC-midnight timestamp check, canonical Decimal parsing, duplicate/conflict/gap handling) | `tools/btc_04e_cm_replay.py` |
| Model construction on ARCH-02 (monthly mean of complete months only, ECB monthly mean, C1 USD-derived EUR equivalent, BTC and satoshi per CBS mean house) | same, reusing `etl/hist_model.py` unchanged |
| Quality/exception metadata, chart segments, ECB calendar report, stale-run report | same |
| Vintage pins, manifest, private replay snapshot, independent Fraction recalculation | same + `data/fixtures/btc04e/source_pins.json` (hashes only) |
| 56 focused tests | `tests/test_btc_04e_cm_replay.py` |
| Read-only workflow (aggregates artifact only) | `.github/workflows/btc-04e-cm-replay.yml` |

Method (unchanged from the brief): `BTC_USD_month` = mean of every daily PriceUSD of a complete UTC month; `ECB_USD_EUR_month` = mean of valid ECB USD-per-EUR fixings (no weekend/holiday carry-forward); `BTC_EUR_equivalent = BTC_USD_month / ECB_USD_EUR_month`; `BTC_per_house = CBS mean house EUR / BTC_EUR_equivalent`; `sats = BTC x 1e8`. Not a Bitstamp close, not BTC-03 A1; both coexist under different method ids and flags.

## 2. Real-data evidence (GitHub Actions, read-only)

Runs on the PR branch: `39802807352` (head `8484cf5`, first pinless run, vintage `UNPINNED`, pins derived from it) and `39803710812` (head `b750a48`, with pins).

| Item | Result |
|---|---|
| Status | `COMPLETE_RESEARCH`, no missing sources, rebuild identical, private-snapshot replay `IDENTICAL` |
| Coin Metrics PriceUSD | 2010-07-18..2026-10-21, 5,940 daily observations, 0 calendar gaps, 0 provider gaps, 1 page |
| Query | `assets=btc, metrics=PriceUSD, frequency=1d, start_time=2010-07-18, end_time=2026-10-21, page_size=10000` |
| Page SHA-256 (identical in both runs) | `8519daacb6f7978ad124ebce32fb65fbd3601ad5b06c5829555dffdec51b5903` |
| Response id (SHA-256 of page hashes) | `9633cb7249325ea7921701808c671254c782b7126d64eace05a8e270a7f26136` |
| Vintage check against committed pins | `MATCH` for `cm_priceusd_daily` and `ecb_usd_per_eur_daily`, derived values `MATCH` |
| ECB pin | equals the BTC-03 and HIST-10 pin (n 7,082, `0daadfe8…f294`) |
| Monthly series | `cm_priceusd_monthly` 2010-08..2026-09 (194, nulls 2010-07 partial first month, 2026-10 partial current month); `cbs_btc_per_house_cm_c1` and sats 2010-08..2026-08 = **193 months, 0 null** |
| Pins (window 2010-07-18..2026-08-31) | CM n 5,889 sha `d57d692f4953d6b1fbab3a8a71310ba9ca95cd82b932522d0c210e2dea8837e8`; derived values sha `82316fb33a2fd31e49e44d5ef1bd1de363e4254ac400edc8ddb9f8ba879a7c82` (cutoff 2026-08) |
| ECB calendar | 0 weekend fixings; 134 TARGET holidays without fixing; **0 unexpected missing business days** |

## 3. Quality and exceptions (Project Control decisions applied)

Q3 2010-08..2014-01 = 42 months, Q2 2014-02..2016-04 = 27, Q1 candidate 2016-05.. = 124 months with a housing value. Provider-methodology uncertainty is carried as a metadata field for every month.

* **June 2011:** research-only/HOLD (`EXC:HOLD_2011_06`). Coin Metrics has all 30 days, **but 2011-06-19..25 is a 7-day run of the identical value 17.5107167913501**; this coincides with the period where the Mt. Gox archive has a gap in BTC-03. The value is computed and flagged, never published; chart segments are split around it (`2010-08..2011-05` and `2011-07..2026-08`), no interpolation or bridge.
* **Dec 2010 / Jan 2011:** no exclusion for flat prices (as decided). The only stale run of 5+ days in the whole series is the June 2011 run above.
* Kraken 2016-01..03: not used here; its missing months are comparator gaps, not Coin Metrics gaps.

## 4. Independent arithmetic check (same input bytes; exact Fractions; not market validation)

| Month | BTC/EUR equivalent | BTC per house | Satoshi per house | rel. diff |
|---|---|---|---|---|
| 2010-08 | 0.0500 | 4,843,139.1071 | 484,313,910,706,978.81 | 1.6e-34 |
| 2011-06 (HOLD) | 12.5275 | 19,290.5113 | 1,929,051,126,704.31 | 2.3e-34 |
| 2013-01 | 11.7534 | 17,576.3898 | 1,757,638,980,566.18 | 1.5e-34 |
| 2014-02 | 483.0491 | 442.6506 | 44,265,063,254.82 | 1.0e-34 |
| 2016-05 | 409.2920 | 578.3891 | 57,838,906,981.50 | 4.2e-35 |
| 2017-12 | 12,836.9675 | 20.6530 | 2,065,300,859.96 | 4.3e-34 |
| 2026-08 (latest CBS month) | 59,925.6365 | 8.4025 | 840,246,394.25 | 1.5e-34 |

## 5. Corroboration (only existing/cheap sources; no new archive downloads)

Against Bitstamp (live API): CM monthly mean vs Bitstamp USD A1, 181 shared months, mean 0.307 %, max 8.120 % (2011-11). By quality: Q3 (2011-09..2014-01, n 29) mean 1.380 %, max 8.120 %; Q2 (n 27) mean 0.182 %, max 0.584 %; Q1 candidate (n 125) mean 0.085 %, max 1.332 %. CM C1 vs Bitstamp EUR native 2016-05.. (n 125): mean 0.139 %, max 2.090 % (2017-12). 11 months exceed 1 %, 3 exceed 5 % (2011-09 7.26 %, 2011-11 8.12 %, 2011-12 5.83 %); all in the thin 2011-2012 era. Mt. Gox and Kraken archives were **not** re-downloaded; their comparisons remain as recorded in BTC-02/BTC-03.

**Independence caveat:** Bitstamp and Coin Metrics may share underlying exchange data, and both derived series use the same ECB fixings. These comparisons are consistency checks, not independent price confirmation.

## 6. Failure-injection tests (all pass)

Missing UTC day; duplicate same/conflicting values; wrong timestamp; leap February; partial current month; ECB holiday vs unexpected missing business day; wrong FX direction; zero/negative/non-finite/float prices; Decimal context independence and exact satoshi conversion; wrong housing statistic (median refused); unsupported early period; changed old price → `SOURCE_REVISED`; identical input but different derived hash → `DEFECT_DERIVED_DRIFT`; changed method/parser/exception/quality version → `METHOD_CHANGED`; appended data outside the pin window → unchanged; corrupted/truncated/missing snapshot → fail closed; June 2011 HOLD and segment splitting; no public leakage (production hashes, empty allowlist, no BTC strings in public JSON/frontend). Results at the first review head: focused 56 passed; full suite 1,513 passed, 5 skipped (see §8a for the corrected counts).

## 7. Reproducibility limits

* The repository stores **window hashes and a derived-values hash, not the source bytes**. A later run can detect a revision (`SOURCE_REVISED`) but cannot reconstruct the old data. Exact replay works only against the private snapshot written inside the runner (`$RUNNER_TEMP`), which is **not uploaded** and disappears with the runner; its round-trip and fail-closed behaviour is tested. Durable private storage with a rights review is an open decision.
* Coin Metrics returned byte-identical page content in two runs minutes apart; this is a short-horizon stability observation, not evidence about revision policy over time.
* PriceUSD construction before the provider's documented history is not independently documented in this repository.
* The BTC-04B/04C/04D reports referenced in the brief are **not on `main` nor in any PR**; the Project Control decisions in the activation message were applied directly. Any extra BTC-04D evidence was not imported.
* Rights: Coin Metrics Community redistribution terms are UNVERIFIED here.

## 8. Remaining decisions (Project Control / owner)

1. Rights and attribution for Coin Metrics Community derived public values; durable private raw storage (retention, location).
2. Finalize PC-BTC04-4 quality framework (the USD 1 million liquidity heuristic is not used here; the Q boundaries are the dated decisions).
3. Final June 2011 treatment beyond research HOLD, and whether any Q3 start (2010-08) is ever publishable.
4. Whether CM-based and Bitstamp EUR-native series stay separate candidates or one is chosen (never an automatic fallback).
5. Production BTC ADR, data contract, UI labels, release and rollback verification.

## 8a. Project Control review corrections (applied after review of head `5b70caa`)

1. **Vintage enforced.** The tool has an explicit `--mode`. The default `validate` mode finishes `COMPLETE_RESEARCH` only if `vintage_check` is `MATCH`, the private-snapshot replay is `IDENTICAL`, the rebuild is identical and the ECB calendar is clean; every other result (`SOURCE_REVISED`, `DEFECT_DERIVED_DRIFT`, `METHOD_CHANGED`, `UNPINNED`, missing key) ends `VALIDATION_FAILED` with exit code 1. Pin generation needs the separately selected `bootstrap` mode, which reports `BOOTSTRAP_PINS_CANDIDATE` and never `COMPLETE_RESEARCH`. A corrupt pin file still fails closed. The workflow runs `validate` for pull requests and for dispatch unless `bootstrap` is chosen as an input.
2. **June 2011 at the export boundary.** `month_eligibility()` gives every month an explicit state (`RESEARCH_ONLY`, `RESEARCH_ONLY_HOLD`, `RELEASE_ELIGIBLE`, `NONE`); HOLD wins over any approval. `candidate_values()` is the only export selector: it selects nothing by default (`RELEASE_APPROVALS` is empty), and it raises if an approved month is HOLD, null or unsupported. The diagnostic June 2011 value is kept in the research series and metadata; chart segments and candidate values exclude it. No public JSON was created or changed.
3. **ECB calendar integrity.** A month with an unexpected missing ECB business day gets no FX mean (null, so no BTC-per-house value for that month); TARGET holidays and weekends do not block. In `validate` mode any unexpected absence in the validated window (up to 2026-08), or any ECB fixing on a weekend, fails the run. With the real data both counts are 0, so the pinned derived hash is unchanged.

Method, quality periods and source pins are unchanged. Tests: focused 89 passed; full suite 1,546 passed, 5 skipped.

## 9. Merge-readiness

Technically ready for Project Control review: CI green on the validated head (python, frontend, gate, btc-04e, Cloudflare Pages), diff limited to research tooling, tests, one workflow, one hash-only fixture and docs. **No merge or publication is authorized**; open decisions above remain with Project Control and the owner.
