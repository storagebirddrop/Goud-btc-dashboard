# HIST-13 — Publication readiness

Technical: PASS WITH CONDITIONS. Publication: **HOLD**. Technical validity of a candidate is not a publication authorization.

| Item | Status | Evidence | Open |
|---|---|---|---|
| Source bytes and hashes | PASS | pinned HIST-09 package verified | live revision status of the CBS table not checked |
| NVM 52/52, CBS 60/60, comparison 12/12 | PASS | counts, consecutive periods | - |
| Independent numerical recalculation | PASS | raw csv/zip, Fractions, 1e-30 | - |
| Deterministic rebuild | PASS | separate processes, byte-identical | - |
| Contract validation and negatives | PASS | 21/21 + control | - |
| Private browser | PASS (session sandbox) | 16/16 | owner-side run |
| NVM source rights (HP1) | HOLD | UNVERIFIED; rows already in public Git fixtures since HIST-09 | owner decision |
| CBS attribution/labels (HP2) | HOLD | CC BY 4.0; wording pending | owner decision |
| NVM/CBS comparison (HP3) | HOLD | payload block off; `COMPARISON_RELEASES` empty | owner decision |
| Page-135 values (HP4) | PASS WITH CONDITIONS | 41 values flagged and shown as "handmatig gecontroleerd" | accept label or supply image |
| Final payload identity (HP5) | NOT AVAILABLE | owner fields (authorizer, date, decision ref) are embedded in the payload | owner supplies; assemble privately |
| Permanent storage of the derived dataset (HP6) | HOLD | not stored anywhere; private outputs were ephemeral | owner decision |
| Production preservation | PASS | monthly.json, cbs csv, gold, BTC D07 identity/pins/registry, allowlists, frontend pins unchanged | - |
