# BTC-07B P0 — CI-output containment and inventory of existing artifacts

Status: ENGINEERING EVIDENCE — PUBLICATION HOLD. Metadata only: no artifact was downloaded, opened, deleted or modified.
Inventory date: 2026-10-22, repository `storagebirddrop/Goud-btc-dashboard`, main `bf5542fbcbc10849926b97e7113878318539a7a5`.

## 1. Own finding (corrected in this change)

Before P0 the workflow `btc-04e-cm-replay.yml` uploaded the whole directory of the full research summary and printed
sections of it. Verified from code (`tools/btc_04e_cm_replay.py`, `run()`), not from the artifact contents:

| Section of `summary.json` | Price-bearing content in the code path |
|---|---|
| `stale_runs[].value` | the repeated daily USD price of a flat run |
| `independent.<month>` | `btc_eur`, `btc_per_house_exact`, `sats_per_house_exact`, `house_eur`, including the diagnostic month 2011-06 |
| `corroboration.*` | percentage deviations vs Bitstamp (no price level) |
| `quality_metadata_sample`, `june_2011` | month metadata; `value` is null for the sampled months in the code path |
| `source_notes` | free text echoed from provider fetch helpers |

The print step listed `stale_runs` and `independent` in its default key list, so these sections were also written to the
public job log. Whether a given historic artifact/log really contains these values has NOT been verified here.

## 2. Containment implemented (P0)

* `tools/btc_public_report.py`: positive allowlist `public_summary(R)` (reviewed keys only: statuses, counts, dates, hashes,
  booleans) plus an independent backstop `assert_price_free` / `assert_value_free` (no floats, no decimal numbers in text,
  no long digit runs outside hashes, forbidden key names, size cap, fixed top-level schema `btc04e-public-summary/1`).
* `tools/btc_04e_cm_replay.py`: `--summary-out` stays the PRIVATE full summary; `--public-summary-out` writes the allowlisted
  file; `--print-summary` refuses anything that is not a valid public summary; exception text is scrubbed (`safe_text`).
  If the allowlist refuses a document nothing public is written and the run fails.
* `tools/btc_06c_candidate.py`: printed summaries pass `assert_value_free`; exception text scrubbed.
* Workflow: private summary in `$RUNNER_TEMP/btc-04e-private/` (never uploaded); only `$RUNNER_TEMP/btc-04e-public/` is
  uploaded as `btc-04e-public-summary-not-approved` (retention 7 days); the print step reads only the public file with no
  `--keys` override; the old artifact name is no longer produced.
* Tests (`tests/test_btc_07b_p0_containment.py`) are content based: they build a summary with synthetic canary prices in
  `stale_runs`, `independent` (incl. 2011-06), June 2011 diagnostics, corroboration and free text, run the real entry points
  and search every file that would be uploaded and all captured stdout for those values.

Not reproduced in any run: no real-data workflow run happened between the finding and this change.

## 3. Inventory of existing artifacts (metadata via GitHub API; content not inspected)

All artifacts below were `expired: false` at inventory time. Retention is 14 days, so every one of them expires on its own
date; deletion is NOT performed and needs a separate Project Control decision.

### 3.1 Old BTC-04E summary artifacts — name `btc-04e-summary-not-approved` — PRICE-BEARING IN CODE PATH, REVIEW REQUIRED

| Artifact ID | Run | Head SHA (short) | Bytes | Expires |
|---|---|---|---|---|
| 12446705130 | 39824350907 | c9828d7 | 3946 | 2026-11-05 |
| 12436712556 | 39804389201 | 5b70caa | 3924 | 2026-11-05 |
| 12436766458 | 39803710812 | b750a48 | 3924 | 2026-11-05 |
| 12436541593 | 39802807352 | 8484cf5 | 3924 | 2026-11-05 |
| 12454525684 | 39842855388 | b104e9c | 4125 | 2026-11-05 |
| 12454695849 | 39843421744 | 7fc6e65 | 4125 | 2026-11-05 |
| 12454084272 | 39845861319 | d6b9f55 | 4125 | 2026-11-05 |
| 12457687178 | 39851990055 | 99ce333 | 4111 | 2026-11-05 |
| 12458074373 | 39854747404 | 2f7ed47 | 4112 | 2026-11-05 |

Run 39802013473 (first run, failure) produced no artifact. The sizes (about 4 KB) suggest a small JSON document; whether it
contains the `stale_runs`/`independent` values is not verified. The workflow logs of the same runs printed the same sections
(job logs not read here).

### 3.2 Earlier BTC research artifacts — described as aggregates, NOT re-verified

* `btc-03-summary-not-approved`: 12423525260, 12422651856, 12422022448, 12421169398 (5.6 KB each, runs 39771978056, 39770734860, 39770032765, 39769016414).
* `btc-02-*-aggregates` (archives, aggregators, exchanges, terms, yahoo; run 39752519453) and `hist-08-*-aggregates`
  (daily, usd-archives, eur-archives; run 39752519505). BTC-02/HIST-08 daily aggregates may carry monthly or daily price
  statistics; this has not been checked in this phase.
* Runs of BTC-01 (run 39577742740 etc.), `bitcoin-backfill.yml`, `trading-btc-audit.yml`: no artifacts listed for the BTC-01
  run inspected; the 2026-10-17 workflows (backfill 8 runs, trading audit 7 runs) were not inspected for artifacts and any
  artifact from them is likely expired (retention default not verified).

### 3.3 Accessibility

Repository visibility and who can download Actions artifacts/logs (public repo: any authenticated GitHub user can read
logs and download artifacts) were NOT verified in this phase. Treat access as potentially wider than the owner until PC
confirms the visibility settings.

## 4. Decision requested from Project Control (PC-BTC07-5)

1. Review the content of the artifacts and logs in 3.1 (and 3.2 as far as PC considers necessary).
2. Decide separately whether to delete them before the 2026-11-05 expiry or let them expire; this change deletes nothing.
