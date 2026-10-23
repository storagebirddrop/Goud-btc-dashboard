# BTC-09 — Frontend and distribution report

## Browser acceptance (run 40027551242, headless Chromium, loopback, temporary pinned build)
- Synthetic B01–B11 plus real-candidate R00–R04: ALL CHECKS PASSED (72/72). R00: payload byte-identical over HTTP (SHA-256 in page and network layer); R01: 151 months, 0 mismatches against the private sidecar in BTC and satoshi; R02: Q2=27, Q1-kandidaat=124; R03: only authorized numeric rows; R04: PRODUCTION build (empty pins) given the real payload shows no Bitcoin text, series, control or chart, and the legacy gold/CBS view renders.
- B07/B07b: source links, licence link, own-calculation, USD-derived and modification notices, non-endorsement, source vintage (snapshot id and capture date from the validated payload).
- Evidence was produced with the real candidate on a CI runner only; no screenshot of a real page, no price in logs or artifacts (details redacted). Uploaded QA: `btc-09-public-qa` (price-free JSON).

## Static distribution (`tools/btc_09_distribution_check.py dist`)
- Production build: no private file names or markers, no raw daily-series lines, no 64-hex literal (no pin), shipped `/data/monthly.json` byte-identical to the committed file and to the pinned legacy payload (`1afb0bf9…91d8cd`), no Bitcoin keys, pin list empty, registry empty. Negative cases in `tests/test_btc_09_distribution.py` (names, markers, daily lines, differing JSON, pin literal).

## Cache and version consistency
- Authorization is bound to the payload BYTES: the page hashes the received body (WebCrypto) and shows Bitcoin only if that hash is in the frontend pin list. Consequences (by design, covered by B10/R04): a stale or foreign JSON with a new frontend, or a new JSON with a stale frontend, yields NO Bitcoin and an intact legacy view. A cache cannot bypass authorization; its worst effect is Bitcoin missing until the stale asset revalidates.
- Cloudflare Pages edge/browser cache headers for `/data/monthly.json`: NOT EXECUTED (no production change allowed; no `_headers` file in the repo, platform defaults apply). Procedure for the authorized window: after deploy, `curl -sI` the JSON and the main JS from two locations, record `cache-control`, `etag`, `age`; require `sha256(body)` of the JSON equal to the release record's public payload hash and the served JS to contain that pin; hard-reload and a clean profile must show identical results; if `age` > 0 with a different etag, purge the Pages cache and repeat.
- Public preview URLs: the branch preview serves the committed legacy JSON only (no Bitcoin data); the real candidate is never deployed.
