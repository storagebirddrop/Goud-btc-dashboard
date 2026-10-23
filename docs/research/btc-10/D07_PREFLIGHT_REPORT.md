# BTC-10 / D07 — Preflight report

Executed on the genuine private inputs (run 40033193216). The approval used is a SYNTHETIC in-memory one (`approved_by` = `SYNTHETIC-D07-PREFLIGHT-NOT-AN-OWNER`) built from the exact template; it is never persisted, registered or published. A green preflight is not owner authorization.

## Positive path (EXECUTED)
Exact 30-key schema; composite bytes and public payload hash equal; candidate and sidecar identity; byte-identical independent regeneration; 151 months; Q2/Q1_CANDIDATE mapping; complete provenance; pinned legacy rollback target; no gate bypass. Result: PASS.

## Negative battery on the proposed identity (EXECUTED, 14/14 refused)
PENDING private hash; owner not approved; extra field; missing field; fewer months; wrong quality scope; wrong month→quality hash; other snapshot id; other calculation commit; other private candidate bytes; other private sidecar bytes; wrong rollback bytes; mutated-but-hash-consistent payload (the public gate alone accepts it; only regeneration refuses it); non-canonical payload.

## Template (EXECUTED)
`owner_approval=PENDING`, `approved_by=""`, `approved_on=""`; unapproved template never opens the gate (test). See D07_RELEASE_RECORD_TEMPLATE.json.

## NOT EXECUTED
Preflight against an owner-approved record (none exists); against the owner's durable copy.
