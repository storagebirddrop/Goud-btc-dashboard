# BTC-08B — Publication-readiness matrix and unresolved decision register

Statuses: PASS / PASS WITH CONDITIONS / BLOCKED / FAIL / UNVERIFIED. Authority: OWNER (Project Control decision) or TECH (autonomous). BTC-ADR-004 (gold) gives no BTC authorization.

## A. Readiness matrix
| ID | Criterion | Status | Evidence | Remaining action | Authority |
|---|---|---|---|---|---|
| R01 | Source vintage defined and bound | PASS WITH CONDITIONS | snapshot_id/manifest/provenance bound in record; 07E-A package hashes | owner durable storage + REAL_OWNER_RESTORE_PASS; re-pack under release commit | OWNER (storage), TECH (re-pack) |
| R02 | Price methodology (ADR-012) | PASS WITH CONDITIONS | DECIDED per DECISIONS.md; method_id bound | PC-BTC06-6 open conditions remain | OWNER |
| R03 | Calendar/FX (monthly mean, no carry-forward) | PASS | method tests, 151 contiguous months | none | - |
| R04 | Quality selection (F2 windows) | PASS WITH CONDITIONS | qualities explicitly bound and scoped; Q1 = candidate | quality overrides / final labels open | OWNER |
| R05 | Coverage 2014-02..2026-08 (151) | PASS WITH CONDITIONS | contiguity check in 07E-B | owner decides authorized months | OWNER |
| R06 | Licensing/rights | UNVERIFIED / BLOCKED | CM-10 residual-risk acceptance only | legal clearance of CC BY-NC 4.0 use, ECB terms | OWNER/LEGAL |
| R07 | Attribution and modification notices | PASS | tests + browser B07/B07b | owner review of wording | OWNER |
| R08 | Distribution form (static JSON, byte-identical) | PASS | reproduce_composite, 62/62 browser | none | - |
| R09 | Authorization record schema | PASS | btc-release-record/2, exact key set | owner creates real record | OWNER |
| R10 | Fail-closed gate | PASS | 1823 passed, negative suite | none | - |
| R11 | Rollback | PASS WITH CONDITIONS | rollback_target_ok; B11 | real deploy/cache rollback NOT EXECUTED | TECH+OWNER |
| R12 | No private data in CI/artifacts/previews | PASS WITH CONDITIONS | synthetic only; redaction in REAL mode | Cloudflare preview exposure check NOT EXECUTED | TECH |
| R13 | Activation (pin + record) | BLOCKED | pins and registry empty by design | explicit owner release authorization | OWNER |

## E. Open decisions (owner) — format: Decision / Evidence / Options / Recommendation / Continues autonomously
1. Legal/rights clearance for CC BY-NC 4.0 data on this site. Evidence: CM-10 acceptance is not clearance. Options: obtain written clearance; relicense/replace source; keep HOLD. Recommendation: written clearance before any release. Autonomous: all technical preparation.
2. Quality labelling/overrides (Q1_CANDIDATE as final? Q3/2011-06 stay out). Recommendation: publish only Q2 + Q1_CANDIDATE labelled provisional.
3. Authorized month set and early-history (pre-2014-02) policy. Recommendation: 2014-02..2026-08, hold 2011-06.
4. Source vintage to release (07E-A snapshot vs a newer acquisition). Recommendation: 07E-A snapshot; any new vintage needs a new record.
5. Durable owner storage + REAL_OWNER_RESTORE_PASS (08A open).
6. Real release authorization, approver identity and pin/registry change (separate from merge).

## Technical actions (no owner decision needed)
Re-pack/rebuild candidate under release commit; Cloudflare preview/cache exposure check on the final PR; real-data preflight in authorized private environment.
