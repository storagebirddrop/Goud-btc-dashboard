# DATA-01A — append-first update contract (PROPOSED)
**Not an accepted ADR or production JSON-v2 contract.** Applies to prospective review-only monthly gold/BTC data preparation, without changing current public v1 or ADR-004.

## Immutable identities and provenance
- Unique key `(period YYYY-MM, metric_id, approved_source_version)` in staged observations; **one approved observation per (period, metric)** in a release. Enforce ordered contiguous months for the relevant approved publication range. Reject duplicate keys, malformed dates, invalid finite-positive numeric values and unexpected units.
- Every fetched input records exact endpoint, request parameters, response byte SHA-256, byte length, retrieval UTC, HTTP validator metadata when available, upstream revision identifier, access/license status and parser/transformation commit. Store raw bytes only in an access-controlled store with reviewed rights and retention; a hash alone is not reproducible raw evidence.
- Candidate manifest: approved prior dataset SHA, proposed candidate SHA, source byte SHA per input, source versions, transformation commit, method ID, calendar coverage, complete/pending months, overlap diff, change classification, approvals and run/PR references. Manifests are immutable once approved; no overwriting old evidence.
- Deterministic serialization, stable ordering, explicit numeric rounding, strict JSON finite values, no timestamps in the content-addressed *dataset bytes* (timestamps belong in manifest). Rebuild from pinned inputs must reproduce the exact candidate hash.

## State machine and decisions
1. `FETCHED`: fetch each configured source once into isolated bytes; timeout, HTTP errors, empty/invalid payload, entitlement failures → `BLOCKED`, no candidate.
2. `VALIDATED`: independent source parsing, coverage, units, FX direction, duplicate detection, version/hash checks. No forward-fill, interpolation, source substitution or unapproved FX calendar policy.
3. `APPEND_REVIEW`: only **new fully complete** months after approved last month, with every mandatory input present, eligible for candidate review. Current month is `PENDING` even when partial observations exist. A late-published older missing source month may be considered only after complete source set and approved overlap parity.
4. `REVISION_REVIEW_REQUIRED`: any previously approved (period, metric) value differs, source definition changes, pinned response bytes change unexpectedly, or method/source version changes. Generate immutable old/new diff with reason and stop candidate promotion. Distinguish source-byte revision with unchanged normalized values from value revision; neither is silently accepted.
5. `APPROVAL_PENDING`: source rights, methodology, expected period, explicit authorized reviewer, branch-protection checks and baseline hash match required. An automatic PR is a proposal, not authorization.
6. `RELEASED` only via separate approved protected merge and release process. Failure anywhere preserves last approved public dataset and release pointer. Never write to `frontend/public/data/monthly.json` from fetch or validation jobs.

## Policy per case
| Event | Action | Automatic approval? |
|---|---|---|
| New fully sourced month | Append-only candidate, compare full approved history, review | No |
| Current partial month | Pending, report missing inputs and expected publication dates | No |
| Late source publication | Recheck exact missing period, require complete dependencies; preserve old release | No |
| Historical value/source revision | Fail closed, old/new hashes and per-metric diff, independent review and separate owner decision | No |
| Changed benchmark definition | Methodology impact review (e.g. World Bank June 2025); no silent normalization | No |
| Provider outage/rate limit | Failed review run; keep prior approved dataset | No |
| BTC source or FX-calendar switch | Methodology and license decision first | No |

## GitHub guardrails
Review workflows: `contents: read`, no deploy secrets, isolated runner, sanitized report artifact; no write token. Optional bot PR creation in a *later authorized phase* requires scoped credential and normal branch protection, required checks, owner review; never direct push to protected main or approval bypass. Use concurrency and idempotent run keys. GitHub Actions artifact retention is not durable source custody.

## Gold-specific proposed update path
ADR-004 unchanged: World Bank Pink Sheet GOLD monthly USD/troy oz; ECB `EXR.D.USD.EUR.SP00.A` daily **USD per EUR**, arithmetic mean of valid available business-day observations in same calendar month; `gold_eur_oz = gold_usd_oz / monthly_usd_per_eur`, index Jan 2000 = 100, grams per house = `house_eur * 31.1034768 / gold_eur_oz`. No imputation. Align to separately approved CBS month; staggered source release means `PENDING`, not zero. Detect altered workbook hash, overlap changes and benchmark breaks, and preserve approved history. Only `gold_index` and `gold_grams_per_house` are eligible public fields under existing limited decision; `gold_eur_oz` stays null in public v1. No recurring publication implemented here.

## BTC-specific hold
No approved provider, UTC daily fixing/close, EUR FX weekend/holiday mapping, aggregation, licensing or anchor tolerance. BTC update candidates remain audit-only; do not populate public BTC fields or activate JSON-v2.

## Proposed fixtures/tests
Isolated `tools/data_01_review_contract.py` validates staged review rows and hashes without touching repository data; `tests/test_data_01_review_contract.py` tests valid append, incomplete month, missing source, invalid payload, duplicate, FX direction, revision, source switch, hash mismatch, nondeterminism and blocked publication. These are **design-contract tests**, not end-to-end production workflow tests.
