# BTC-09 handover

State: BTC publication HOLD. Pins/registry empty. PR #105 (07E-B, draft, head 933abed) untouched; 08B is based on main 641151b9 and does not depend on its code, but both touch tools/btc_07b_browser.mjs (08B block B07b is isolated; expect a trivial merge).
Sequence for BTC-09 once the owner decides:
1. Owner closes R01/R05/R06 (storage restore, month set, legal clearance).
2. Re-pack the 07E-A snapshot under the final release commit; rebuild candidate; run tools/btc_08a_verify_package.py at that commit.
3. Build composite, run record_template; `release_preflight` MUST pass on the private inputs before the record is registered; owner fills approval fields and private hashes, owner commits the record + frontend pin in a separate authorized change.
4. Run reproduce_composite on private inputs, rollback_target_ok, full CI, real-browser acceptance (private environment only), Cloudflare preview check.
5. Deploy only on explicit authorization; rollback = restore pinned legacy payload.
Do not: create a production record to test, publish from a candidate, mix vintages, or edit pins without the record.
