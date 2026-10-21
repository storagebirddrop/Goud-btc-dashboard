# HIST-08 Phase F: ARCH-02 bundle adapters (research only)

Status: RESEARCH ONLY. `ALLOWLIST` of `etl/hist_model.py` stays empty; nothing is published; no file under `data/`, `frontend/`, `etl/static_export.py` changes. Code: `tools/hist_08_bundle.py`; tests: `tests/test_hist_08_bundle.py` (20 tests, incl. corrupted fixtures).

## Implemented and tested on real committed inputs

| Target bundle | Status | Detail |
|---|---|---|
| (2) CBS monthly housing | **IMPLEMENTED** | `nl_house_avg_eur_1995_1999` (60 obs, fixture `cbs-1995-1999-i1.json`, flags `RETROSPECTIVE_EUR`, `NLG_ORIGINALS_NOT_OBTAINED`, break at 1995-01) and `nl_house_avg_eur_2000` (320 obs, `data/cbs-housing.csv`). Kept as two series, never spliced. 380 observations in total. Source hashes (file sha256) and vintage recorded; `python -m tools.hist_08_bundle cbs --cbs-csv data/cbs-housing.csv --out B.json` is byte-deterministic (bundle sha256 `ca298ca9...` on this HEAD) and `tools/hist_model_check.py` returns OK. |
| generic adapter `source_series` | **IMPLEMENTED** | needs explicit provenance (source id, raw sha256, retrieval time, vintage) and a mandatory per-period quality function; rejects empty input, malformed periods, non-positive / non-finite / float values; a gap stays absent. |
| derived grams / sats per house | **TESTED on synthetic inputs** | restricted to the actual overlap; currency mismatch (NLG gold vs EUR house) raises; sats need a release record naming the restricted series (gate otherwise denies). |

## Specified, not implemented (inputs exist only inside read-only CI runs)

Raw gold / FX / exchange data are never committed, so these adapters cannot run offline on real data. Each is `source_series(...)` plus a CI step that fetches, hashes and feeds the dict; the specification is fixed here so the next milestone is mechanical:

| Bundle | Input and definition | Quality labels | Blocker |
|---|---|---|---|
| (1) gold C1/C4 monthly | C1 1975-01..1998-12 (World Bank whole-USD x Fed NLG/USD, mean of daily; currency NLG per oz, or EUR via NLG/2.20371 as a separate *retrospective* series); C4 1999-01.. observed EUR (`etl/gold_monthly.py`). Series ids `gold_nlg_oz_c1`, `gold_eur_oz_c3_retro`, `gold_eur_oz_c4`; never one unlabelled series. | per `HIST_08_GOLD_VALIDATION.md` levels A-E; publish nothing at C/D | D2 (owner), Fed lineage, aggregation choice |
| (3) NVM annual | none recovered (`HIST_08_NVM_RECOVERY.md`) | n/a | source |
| (4) Bitstamp BTC/EUR from 2016-05 | mean of daily UTC closes, one named venue | Q1 from 2016-05 | D3, archive pinning |
| (5) USD-derived BTC | ratio of monthly means with ECB EUR/USD, from 2013-04 (2014-02 earliest cross-validated) | Q2 | D3 |
| (6) grams per house | `grams_per_house(house, gold)` over the actual overlap; NLG-era needs an NLG house series (not available before 1995) | min of inputs | gold bundle + D2 |
| (7) sats per house | `sats_per_house(house_eur, btc_eur)` over actual overlap | min of inputs | D3; restricted class, release record required |

Overlap of house price (1995-01..) with C1/C3 gold is the 1995-1998 window in retrospective EUR only; with C4 and Bitstamp it starts 1999-01 / 2016-05.

Rules honoured: no annual-to-monthly conversion (`convert_frequency` raises, tested), no splice, no inferred values, original currency and unit kept, source hash and vintage per series, deterministic bundle hash, revisions detectable (`detect_revisions`), publication gate default-deny.
