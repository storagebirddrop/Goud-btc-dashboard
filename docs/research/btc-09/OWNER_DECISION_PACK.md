# BTC-09 — Owner decision pack (Project Control)

Recommended defaults follow existing decisions (ADR-012, PC-BTC04, PC-BTC07D-CM10). Publication stays HOLD until D08.

| ID | Decision | Recommended default | Basis |
|---|---|---|---|
| D01 | Does the accepted CM-10 residual risk also cover the exact public website release? | YES, scoped to a non-commercial, informational public site, with attribution/modification/non-endorsement notices as built; any concrete conflicting provider term re-opens it | CM10 §2 states the attestation was for private / small-circle use and that a public site is potentially public distribution; this is a scope confirmation, not new research or a new written provider permission |
| D02 | Final source vintage | the BTC-07E-A snapshot `btc04e-e11c2538168b2bde`; any newer acquisition = new vintage, new record | reproducible, anchored, 151 months |
| D03 | Authorized months | 2014-02..2026-08 (151); 2011-06 and Q3 stay out | PC-BTC04, STANDARD_2014_02 |
| D04 | Quality presentation | publish Q2 (27) and Q1_CANDIDATE (124), labelled provisional; never call Q1 final | PC-BTC04-F2 |
| D05 | Durable owner copy as disaster-recovery requirement (not a runtime dependency) | keep the TAR (anchor above) in private owner storage; before the release rebuild run `tools/btc_08a_verify_package.py` at commit `641151b9…` on a clean machine and record `REAL_OWNER_RESTORE_PASS`; the public site is static and never reads the backup; artifact 12524137867 expires 2026-10-24T18:51Z, after which the owner copy is the only build input | BTC-08A |
| D06 | Final attribution | approve the BTC-08B texts as built (source roles, modification notice, vintage line, non-endorsement) | tests B07/B07b |
| D07 | Release artifact identity | choose release id, decision ref, rights ref; engineering rebuilds the candidate at the release commit (sidecar must stay `a0bcb9ba…`), builds the composite, runs `release_preflight`, and hands the template record to the owner | BTC-08B contract |
| D08 | Public deployment authorization | separate explicit decision after D01–D07; includes the cache-header procedure and the rollback runbook | change control |

The single combined amendment proposal (status PROPOSED, not applied) is in DECISION_AMENDMENT_PROPOSAL.md; the exact step sequence is in RELEASE_PREPARATION_SEQUENCE.md.
