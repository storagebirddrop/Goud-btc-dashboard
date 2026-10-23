# BTC-09 — Release readiness matrix

Status: PASS / PASS WITH CONDITIONS / BLOCKED / FAIL / NOT EXECUTED. Authority: TECH = autonomous engineering, OWNER = Project Control.

| ID | Criterion | Status | Evidence | Open action | Authority |
|---|---|---|---|---|---|
| T01 | Source package verified against external anchor | PASS | run 40027551242: TAR SHA-256 = `19abaa9b…d4ce` | none | TECH |
| T02 | Historical candidate reproduced at packing commit | PASS | `616ac933…`, sidecar `a0bcb9ba…` equal | none | TECH |
| T03 | Candidate regenerated under current code, offline | PASS | `5244caab…`, commit `9dba03cc…`, `network_isolated` | repeat at release commit | TECH |
| T04 | Economic values unchanged (151 months) | PASS | sidecar hash identical; 0 value/state/quality diffs | none | TECH |
| T05 | Independent recomputation | PASS | 151/151, tolerance 1e-25 | none | TECH |
| T06 | Scope 2014-02..2026-08, Q2 27 / Q1_CANDIDATE 124, no Q3, 2011-06 withheld | PASS | scope report | owner confirms month set | OWNER |
| T07 | Mandatory release_preflight incl. 14 negative cases | PASS | real inputs, synthetic approval | none | TECH |
| T08 | Frontend/browser acceptance, synthetic | PASS | B01–B11 + B07b | none | TECH |
| T09 | Frontend/browser acceptance, real candidate | PASS | R00–R04, 72/72 total, private CI runner | none | TECH |
| T10 | Production build free of private data/pins | PASS | distribution check + 16 negative tests | none | TECH |
| T11 | Public monthly.json byte-identical; pins/registry empty | PASS | sha `1afb0bf9…`; `[]`, `()` | none | TECH |
| T12 | Rollback logic and runbook | PASS WITH CONDITIONS | synthetic simulation, runbook | real rollback + cache headers NOT EXECUTED | TECH+OWNER |
| T13 | Owner durable copy and restore (disaster-recovery requirement, not a runtime dependency) | NOT EXECUTED | no owner storage reachable; the static site never reads the backup | owner stores TAR, runs `tools/btc_08a_verify_package.py` (historical commit) before the release rebuild | OWNER |
| T14 | Attribution reflects source roles/modifications | PASS | BTC-08B constants + tests + B07/B07b | owner reviews wording | OWNER |
| T15 | Non-commercial operating model documented | PASS WITH CONDITIONS | CM10 owner attestation (private/small circle) | public-site scope amendment (D01) | OWNER |
| T16 | Public deployment authorization | BLOCKED | none exists | exact owner release decision | OWNER |
| T17 | Decision amendment PC-BTC09-A1 | PROPOSED | DECISION_AMENDMENT_PROPOSAL.md | Project Control approval | OWNER |
| T18 | Release preparation sequence | PASS (documented, not executed) | RELEASE_PREPARATION_SEQUENCE.md | execute only after D07/D08 | OWNER |
