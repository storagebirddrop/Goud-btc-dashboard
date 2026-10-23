# BTC-10 / D07 — Release change-set check (R versus C)

**Conflict found.** The candidate binds `calculation_git_commit = C`, and the calculation identity covers `etl/`. But the two release-only constants physically live inside calculation/frontend files: `ARTIFACT_RECORDS` in `etl/btc_contract.py` and the pin list in `frontend/src/btc.ts`. A plain `git diff C R -- etl` therefore rejects every legitimate release.

**Smallest compatible fix (implemented, tested):** `tools/btc_10_changeset_check.py` makes the identity check precise without weakening it. Command:

`python -m tools.btc_10_changeset_check --repo . --calc-commit C --release-commit R --record RECORD.json`

R may differ from C ONLY in:
1. `etl/btc_contract.py`: the value of `ARTIFACT_RECORDS` (the rest of the module is compared as an AST and must be identical); `()` at C, exactly the one approved record at R.
2. `frontend/src/btc.ts`: the list literal of `BTC_APPROVED_COMPOSITE_SHA256` (the rest of the file must be identical); `[]` at C, exactly `[record.composite_sha256]` at R, hex only.
3. `frontend/public/data/monthly.json`: SHA-256 equals `record.public_payload_sha256`; its legacy projection equals the pinned legacy payload; `composite_release_gate` opens for these exact bytes with the record.
4. Files under `docs/` and `tests/`.

Rejected: any other path (workflows, other frontend files); any other change in the calculation paths (`etl/*`, the four BTC tools, the pins/fixtures); a second record or pin; a record that is PENDING, has an empty approver/date, contains `SYNTHETIC`, has extra/missing fields, differs from the registered one, or is bound to another commit than C. Each case has a regression test (`tests/test_btc_10_d07.py`, 8 mutation cases + 5 record cases + the passing case).

**Residual risks:** `tests/` and `docs/` are free-form (the instruction allows release tests/documentation; the reviewer must read them); the AST comparison ignores comments in `etl/btc_contract.py`.

**Branch discipline:** the release branch is created only after D07/D08 authorization (a branch push triggers a public Cloudflare preview that would show the real values); run this check locally on the release commit before pushing.
