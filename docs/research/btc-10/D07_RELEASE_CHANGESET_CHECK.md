# BTC-10 / D07 — Release change-set check (three-commit model C -> B -> R)

**Defect (found in review of PR #109, now corrected).** The first version compared the release commit R directly with the frozen calculation commit C. But PR #109 itself adds authorized technical tooling, a workflow and tests between C and any future release, so a legitimate release failed with `unauthorized_paths`. Reproduced deterministically by `test_defect_reproduced_a_legitimate_release_has_technical_changes_between_C_and_R` (a temporary repository with C, an integrated baseline B containing tools/workflow/tests/docs, and R).

**Model.**
- **C** frozen calculation commit `c11f82a83234593ace70369da07ca183c0cc3db3`. The candidate and the release record bind `calculation_git_commit = C`; it is never rebased to B or R.
- **B** integrated technical baseline: the commit on `main` after PR #109 is merged (before the merge, a branch HEAD may be used only to test the model; it is not the final baseline). Its calculation code must equal C and its production state must still be closed.
- **R** the production release commit, a descendant of B.

**Command** (price-free report, exit 0 only if everything holds):

`python -m tools.btc_10_changeset_check --repo . --calc-commit C --baseline-commit B --release-commit R --record RECORD.json`

`--baseline-commit` is mandatory; it is never defaulted to R.

**Checks.**
1. C, B, R resolve; C is an ancestor of B, B an ancestor of R, and B differs from R (`ancestry_C_B_R`).
2. C -> B: no difference in the calculation paths (`CALC_PATHS` of the BTC-08A contract: `etl/`, the four BTC tools, `data/fixtures/btc04e`) (`calc_code_identical_C_to_B`). Technical files elsewhere (tools, workflow, tests, docs) are allowed and counted.
3. The record is approved, has the exact 30 keys, no empty approver or date, no `SYNTHETIC`, and binds **C** — not B, not R (`record_binds_C`).
4. B is the closed legacy state: `ARTIFACT_RECORDS == ()`, pin list `[]`, public payload = pinned legacy payload (`baseline_closed_legacy_state`).
5. B -> R may differ ONLY in: the value of `ARTIFACT_RECORDS` in `etl/btc_contract.py` (rest of the module identical as AST; exactly the one record); the list literal of `BTC_APPROVED_COMPOSITE_SHA256` in `frontend/src/btc.ts` (rest identical; exactly `[record.composite_sha256]`); `frontend/public/data/monthly.json` (SHA-256 = `record.public_payload_sha256`; legacy projection = pinned legacy payload; `composite_release_gate` opens for these bytes); files under `docs/` and `tests/`.
6. Rollback: `record.rollback_ref` equals `{previous_public_sha256: sha256(B public payload), state: LEGACY_GOLD_CBS_NO_BTC}` (`rollback_target_is_B_public_payload`).

**Rejected (each has a regression test in `tests/test_btc_10_d07.py`):** a calculation change C->B (etl, calculation tool, replay tool); a non-closed baseline (registry, pin, payload); invalid ancestry (swapped commits, B==R, R off a side branch, unknown commit); calculation change B->R; unrelated tool, modified or new workflow, other frontend file B->R; a second record or pin, a wrong pin value; a payload that differs from the record; a record bound to B or R, PENDING, unapproved, synthetic, malformed, missing a key, extra key, or with a wrong rollback target.

**Verified on this repository:** C -> HEAD of PR #109 has `calc_code_identical_C_to_B: true` (14 technical files changed outside the calculation paths); the unapproved template is rejected as required.

**Residual risks.** `tests/` and `docs/` are free-form (a reviewer must read them); the AST comparison ignores comments in `etl/btc_contract.py`.

**Branch discipline.** Create the release branch only after D07/D08 authorization; run this check locally on R before pushing (a push publishes a Cloudflare preview).
