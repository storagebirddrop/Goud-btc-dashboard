# HIST-12 — Production parity

| Item | State |
|---|---|
| `frontend/public/data/monthly.json` | unchanged; SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd` (= `LEGACY_PUBLIC_SHA256`) |
| `data/cbs-housing.csv` | unchanged; SHA-256 `ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6` |
| Gold/CBS parity | `python -m etl.data_quality` passes (committed CSV = committed JSON) |
| `BTC_APPROVED_COMPOSITE_SHA256` | `[]` |
| `ARTIFACT_RECORDS` | `()` |
| `hist_model.ALLOWLIST` | `()`; `COMPARISON_RELEASES` `()` |
| `HIST_APPROVED_PAYLOAD_SHA256` | `[]`; `HIST_ALLOW_SYNTHETIC` `false` |
| BTC D07 identity | unchanged: calculation paths identical to C `c11f82a83234593ace70369da07ca183c0cc3db3` (`btc_10_d07.calc_identity`); `etl/btc_contract.py`, `etl/hist_model.py`, `frontend/src/btc.ts`, `frontend/src/series.ts` not modified |
| Actueel dashboard | unchanged views/labels/ranges; BTC synthetic browser acceptance 62/62 |
| Public assets | no `historical.json`, no `*hist*` file under `frontend/public` or `data`; synthetic fixtures live only under `tests/hist12/` and a private output directory |
| Production bundle | built with empty pins; scanned: no fixture hash, no synthetic source id, no historical series id |

Why the file is separate: any change to `monthly.json` would change the legacy hash bound into the approved BTC release identity (HIST-11 comparability review s.7). Verification: `tests/test_hist_12_production_parity.py` (also in the manual workflow with full history for the C identity check).

Existing guards adjusted (narrowly, with assertions): `tests/test_static_architecture.py` (second inert fetch target), `tests/test_frontend_series.py` and `tests/test_hist_03_quality_contract.py` (the two view files may name the approved period bounds; research artifacts and numeric arrays remain forbidden), `tests/test_hist_model.py` is unchanged (the contract module lives in `tools/`, outside the BTC calculation paths `etl/`, and complies with the `tools/hist_*` guards).
