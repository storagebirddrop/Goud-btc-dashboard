# HIST-12 — Security review and negative tests

Adversarial review of the gate. Every attempt below fails closed; no gate was weakened to make a test pass.

## Bypass attempts and results
| Attempt | Result | Evidence |
|---|---|---|
| Valid synthetic file served, production build | no request, no tab | browser H01 (1280 and 375 px) |
| Hostile URL (`?historisch=1&hist=1&view=historisch&tab=historisch#historisch`) | ignored | H01, H06 |
| Seeded localStorage/sessionStorage (`view`, `hist`, `historisch`) | ignored; no code reads storage | H01, H06, `test_hist_12_frontend` |
| Deep link with an invalid or unpinned payload | stays on Actueel | H06 |
| Missing file (404), malformed JSON, unsupported schema | tab hidden, Actueel works, no message | H06 |
| One changed byte; valid-but-other release (unpinned) | tab hidden | H06; Python `test_wrong_or_missing_pin_and_one_changed_byte...` |
| Pinned but structurally invalid: extra series, missing/extra half-year, no provenance, wrong unit, wrong frequency, mean series with median kind, unauthorized comparison scope, missing quality, unresolved quality, missing synthetic marker, euro != guilder / 2.20371, release block not authorized | tab hidden | H06 (18 refusals), gate parity (19 fixtures TS = Python) |
| Synthetic payload in a production candidate / production gate | refused (marker) | Python marker test; TS `allowSynthetic=false` |
| Payload self-authorization (no external record) | refused (`ALLOWLIST` empty) | `test_production_defaults_authorize_nothing` |
| Content changed but hash re-blessed in the payload | refused by the external record | `test_content_changed_but_hash_blessed...` |
| Comparison enabled without external HP3 authorization or with another scope | refused / panel absent | Python + H05 |
| Frequency conversion (half-year to month) | impossible: periods are validated per series; the model refuses conversions | Python periods tests |
| Floats, non-canonical bytes, extra fields | refused | Python serialization test |
| XSS through source titles | text nodes only (React escaping) | review |
| Information leak in errors | no message is produced on any failure | `catch{return null}`, H06 asserts no "niet beschikbaar" and no historical text |
| Raw research data or fixtures in the bundle | none; production output scanned for the fixture hash, the synthetic source id and a gold series id | H01 bundle scan, `test_no_historical_data_exists...` |

## Defects found and corrected during review
1. The initial deep-link and fetch code lived in `main.tsx`, which is guarded against URL/storage state and extra fetches (BTC publication boundary). Moved into two dedicated modules (`histNav.ts`, `histLoad.ts`) so the guard stays unchanged; each module's scope is asserted by tests.
2. The TypeScript gate accepted extra keys on a series object; tightened to the exact model key set and break entries.
3. Existing guards (research artifacts out of the frontend, model out of production files, single data target) were narrowed with explicit, test-asserted exemptions for the approved HD2/HD3 files only; no guard was removed.

## Counts
- Python contract and gate: 30 tests, all pass (all but two positive cases assert a refusal).
- Frontend static: 6 tests; TS-vs-Python parity: 19 fixtures, accepted exactly `valid` and `valid_nocmp`, closed in all four negative modes (production, empty pins, wrong hash, null hash).
- Browser acceptance: 50/50 checks (18 refusal scenarios, production inertness at 2 widths, valid view, deep link, keyboard, mobile, tables, units, comparison on/off).
