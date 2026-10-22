# BTC-05D — minimal local vintage snapshot, offline replay and revision detection (research only)

**Status: RESEARCH ONLY. BTC publication HOLD. Durable storage OPEN.** Implements the restricted PC-BTC05B-REV1 scope as a small extension of `tools/btc_04e_cm_replay.py`. The BTC-05A rights assessment is **not available in the repository**; no rights conclusion is drawn here. Nothing in this change touches `monthly.json`, the frontend, gold, source pins, the method `CM_PRICEUSD_MONTHMEAN_C1_V1`, secrets, schedules or the release gate (`RELEASE_APPROVALS` stays empty; June 2011 stays `RESEARCH_ONLY_HOLD`).

## 1. Technical inventory (phase A, BTC-04E at `main` `0fc635d`)

| Question | Finding before BTC-05D |
|---|---|
| Source data the adapter can keep | Only hashes: per-page SHA-256 and a response id. The response bytes were discarded after parsing. |
| Original API response bytes | Available in memory during acquisition (`r.content`), not kept. **Now kept** (CM pages). ECB response bytes are not exposed by the existing ECB helper; only the normalized values are available. |
| Normalized daily values | `cm_priceusd_daily`, `ecb_usd_per_eur_daily` (canonical `day:value`). |
| Runner snapshot | Normalized files + a minimal manifest under `$RUNNER_TEMP`, hash-checked only; no versions, no canonical-hash cross-check, no original bytes. |
| Pins | Window hashes of both daily series and the derived-values hash in `data/fixtures/btc04e/source_pins.json`. |
| Offline replay | Possible for the runner snapshot, but weakly verified. |
| Minimal change needed | Keep the CM response bytes; make import verify everything; add an explicit offline replay entry point. |
| Unchanged | Method, adapter parsing rules, quality periods, June 2011 rule, candidate selector, pins, vintage statuses, `--mode`. |

**Three different things, never to be conflated**

- *Source verification*: today's source compared with stored hashes (`check_pins`: `MATCH` / `SOURCE_REVISED` / …).
- *Deterministic calculation*: identical input, identical derived values (`rebuild_identical`).
- *Historical vintage replay*: re-processing the exact bytes used earlier without the current provider (`--replay-snapshot`). **A hash file alone is not sufficient for this**; only a stored snapshot is. A freshly downloaded response is never called the original vintage unless its bytes provably match.

## 2. Storage decision

The repository `storagebirddrop/Goud-btc-dashboard` is **public** and no private storage exists in it (Actions artifacts of a public repository are publicly readable; no secrets or private repository are authorised). Therefore: **local export/import only; durable storage is OPEN.** No claim is made that durable historical replay is operational.

## 3. Snapshot format (`btc04e-snapshot/2`, ~365 kB for the full history)

Directory chosen explicitly (`--export-snapshot DIR`, refused if it already holds a snapshot; default on a runner is a private temp directory that is not uploaded):

| File | Content | Size in the real run |
|---|---|---|
| `cm_priceusd_daily.txt` | normalized `day:value` lines (5,940 days) | 164,264 B |
| `ecb_usd_per_eur_daily.txt` | normalized ECB values (7,120 days) | 127,388 B |
| `raw/cm_priceusd_page_000.json.gz` | original Coin Metrics response bytes (gzip, mtime 0) | 70,571 B |
| `snapshot_manifest.json` | snapshot id, source identity, endpoint + canonical query, UTC acquisition time, period and counts, source/response/canonical hashes, method/parser/exception/quality versions, git commit, derived hash and cutoff, CBS input hash, `ecb.raw: NOT_RETAINED` | 2,410 B |

Total 364,633 B. The snapshot id (`btc04e-…`) is a hash of versions, canonical input hashes and derived hash — not of timestamps.

## 4. Replay guarantees and limits

`load_snapshot` fails closed (`SnapshotError`) with codes `MISSING`, `CORRUPT`, `SOURCE_HASH_MISMATCH`, `NORMALIZED_HASH_MISMATCH`, `METHOD_CHANGED`, `EXISTS`. It checks: manifest/format; method, parser, exception and quality versions against the running code; file hashes and counts; canonical daily hashes; response pages vs recorded hashes and response id; raw pages re-parsed with the current parser must reproduce the stored normalized values; snapshot id. `replay` and `--replay-snapshot` use only the snapshot (no provider request, no live fallback); result `IDENTICAL` / `DIFFERENT` / `CBS_INPUT_DIFFERS`.

Real-data result (run on the PR head): export of the live acquisition, then replay from that export: `IDENTICAL`, derived hash `82316fb3…7c82`, raw CM bytes `RETAINED_AND_VERIFIED`; vintage against the committed pins `MATCH`.

Limits: replay is proven only for a snapshot that is still available locally; the ECB response bytes are not retained (only normalized values); nothing proves yet that a stored snapshot can be retrieved later from a durable location; a hash in the repository still cannot reconstruct data.

## 5. Revision detection and monthly update

`revision_report(stored, current)` classifies `UNCHANGED_HISTORY`, `NEW_OBSERVATIONS_ONLY`, `HISTORICAL_REVISION` (changed or newly appearing day inside the stored window) and `MISSING_HISTORICAL` (wins). It returns day lists and counts only, never prices, and never replaces stored values. With `--baseline-snapshot DIR` the run loads the baseline first (a bad baseline stops the run before any request), reports the classification, and in `validate` mode fails on `HISTORICAL_REVISION` / `MISSING_HISTORICAL`. `monthly_update_plan` lists the complete calendar months a monthly update could add when history is unchanged; pins are never written, the new vintage gets its own snapshot id, and the release gate stays closed. No workflow schedule or publication behaviour was changed.

## 6. Tests

Added to `tests/test_btc_04e_cm_replay.py` (119 tests there; 1,576 passed, 5 skipped in the full suite): byte-identical export/import, no overwrite, offline replay with network and live acquisition forbidden, CLI exit codes, missing/corrupt snapshot, source and normalized hash mismatch (both directions), method/parser/policy/quality version mismatch, snapshot id semantics, revision categories (unchanged, new observations, revised, missing, inserted), validate-mode failure on revisions, monthly update plan, bad baseline stops before any request, June 2011 HOLD after replay, unsuitable months blocked by the candidate selector, no raw data tracked in git / uploaded / present in public JSON.

## 7. Not operational / open

Durable private storage and retention (OPEN); BTC-05A rights conclusions (not available); ECB response-byte retention; automated monthly job (not created, not authorised); BTC publication (HOLD).
