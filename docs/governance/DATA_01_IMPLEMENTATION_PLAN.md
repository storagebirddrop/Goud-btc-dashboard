# DATA-01A — staged implementation plan
**Status: PROPOSED / DESIGN REVIEW ONLY.** No production updater, schema migration, publication, merge or deployment is authorized.

| Phase | Scope | Acceptance evidence | Gate |
|---|---|---|---|
| DATA-01B | Read-only source snapshot manifest: exact fetched bytes hashed *before* parsing, pinned URL/version/commit, retention and rights policy; deterministic metadata-only audit | Fixture-based replay and SHA mismatch tests; verified restricted storage/retention | No raw licensed inputs in public artifacts |
| DATA-01C | Append-first observation validator shared by gold/CBS and future BTC research; classify new, late, revised, incomplete | All negative fixtures, independent overlap diff, no public file writes | No automatic revision approval |
| DATA-01D | Review-only gold monthly candidate on approved ADR-004, using pinned WB/ECB and approved CBS; delayed-source and benchmark-change tests | Independent 100% month replay, two allowed gold indicators, hashes, CBS parity | No release until GOLD-03 owner authorization |
| DATA-01E | BTC research gate: source terms, UTC fixing, FX calendar, monthly method, historical coverage and independent anchors | Signed owner decision, source rights evidence, no splice, negative fixtures | **BLOCKED pending owner decisions** |
| DATA-01F | Protected GitHub candidate PR and release gate: review evidence, immutable candidate and rollback snapshot, deployed commit/served hash | Branch-protection checks, approved reviewer, rollback byte identity, deployment verification | Separate release authorization required |
| DATA-01G | Optional JSON-v2 parallel fixture only after explicit schema approval | v1/v2 parity, frontend backward compatibility and atomic release pointer | JSON-v2 remains PROPOSED |

## Audit conclusions
- GitHub version-controls committed public build inputs but existing scheduled CBS flow produces **ephemeral review artifacts only**, not an approved monthly auto-commit.
- The June 2025 World Bank definition break is a methodological annotation, not permission to rescale/normalize source values.
- Review artifacts expire and must not be mistaken for permanent evidence. Design durable candidate storage separately from raw-source custody.
- Existing GOLD-02B candidate and GOLD-03 Draft PR #67 are out of scope; no changes to them.
- Current `main` baseline is commit `2069a4fea4b528300916967719a21ea15683c9b8`; all test results must bind to DATA-01A branch HEAD.

## Owner decisions before any implementation beyond review-only design
BTC reference source and daily fixing; FX weekend/holiday rule; BTC history start/splice policy; public rights and independent anchor tolerance; durable source/candidate custody and retention; approval/merge/deployment actor policy. Do not infer these decisions from green CI.
