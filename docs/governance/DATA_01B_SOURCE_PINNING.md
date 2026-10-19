# DATA-01B — source pinning and durable evidence

**Scope:** technical read-only foundation, no production data update or source/methodology decision. Based on main `61e35a1eaed1de2428939d3b39822b390e1c4212` (DATA-01A squash merge). See DATA_01_SOURCE_AUDIT.md, DATA_01_UPDATE_CONTRACT.md, DATA_01_BTC_DECISION.md, DATA_01_IMPLEMENTATION_PLAN.md and DECISIONS.md. JSON-v2 remains PROPOSED.

## Implemented and testable
- `tools/data_01_source_pin.py`: explicit one-shot acquisition returns **exact received bytes** and a manifest; hashes are computed over original bytes **before** source format inspection. No import of production parsers. Callers may subsequently pass those same bytes to existing World Bank, ECB or BTC research adapters. No new price calculation, FX or aggregation.
- Source-specific HTTPS host/path allowlist and version/parameter checks prevent unapproved substitution. Only `world-bank-gold`, `ecb-usd-per-eur`, `coinmetrics-btc-research` recognized. BTC always research only; inclusion in allowlist is not source approval.
- `manifest.identity` is deterministic and content-addressed: source/version/endpoint/request parameters/parser and transform version/rights status/raw SHA-256/byte size, plus canonical identity SHA-256. `manifest.operations` contains UTC retrieval time, HTTP status/selected headers, ephemeral storage reference, retention, validation results and publication authorization=false. Timestamps intentionally do not change identity SHA.
- `replay(raw,manifest)` is **offline**; refuses missing or changed bytes, unexpected source/version, identity tampering and failed validation. No network fallback. A hash-only manifest without bytes cannot replay.
- `write_metadata_only` rejects all writes inside repository root and existing target paths; never writes raw external source bytes.
- The manual `data-01b-source-evidence.yml` workflow runs offline fixtures and regression tests, checks public files and uploads only a minimal status JSON; read-only GitHub token, no deployment or external acquisition. **It does not claim live source retrieval.**

## Storage classes, availability and retention
| Class | GitHub-first candidate | Current evidence / limitations |
|---|---|---|
| A — approved derived data | Versioned protected Git commit with commit+SHA and owner-reviewed PR; optionally immutable release tag/asset **after authorization** | **PROPOSED**, no DATA-01B durable object created or read-back proven. Existing Git tracks CBS/public v1; no permission to add derived prices here. |
| B — third-party raw bytes | Restricted private versioned object store or separately authorized encrypted private storage, with source terms and retention schedule | **NOT CONFIGURED / BLOCKED**. Do not put raw World Bank/ECB/BTC bytes into public Git history, public GitHub Releases, or public Actions artifacts. GitHub Actions ephemeral runner memory/disk is not durable custody. |
| C — safe metadata/audit proof | Reviewed Git commits containing source manifests and hash evidence without raw data or secrets; immutable commit references | **TECHNICAL INTERFACE IMPLEMENTED**. Permanent repository commit is possible subject to owner review; no live source manifest committed in DATA-01B. |

GitHub Releases in a public repository and public Git objects/assets are not private raw-source storage. GitHub Actions artifacts expire and may be accessible to repository readers; not durable. Protected branches and versioned tags provide traceability but do not prove legal rights, retention permanence, immutable object-lock, or actual deployment. Existing Cloudflare deployment config does not establish a restricted evidence store. No paid infrastructure provisioned. **Storage rights, retention and read-back remain NOT VERIFIED.**

## Source acquisition safety
The acquisition API deliberately does **not** persist raw responses, upload them or retry with another provider. Network acquisition must be invoked explicitly by a separately reviewed caller with approved endpoint, access rights and retention policy. The workflow deliberately uses controlled synthetic fixtures rather than live World Bank/ECB/BTC source bytes. No production workflow has been rewired to use this module.

## Open decisions
Owner approval needed before any durable raw-source custody, external live fetch with persistent evidence, Bitcoin price source/fixing and reuse rights, automatic monthly release integration or public gold/BTC activation. GOLD-03 PR #67 and ADR-004 untouched.
