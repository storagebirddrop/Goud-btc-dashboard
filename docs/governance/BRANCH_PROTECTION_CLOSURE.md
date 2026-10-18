# Branch protection — formal closure (2026-10-18)

**Scope:** repository security baseline for `main`. **Status:** PASS WITH CONDITIONS. This record is evidence of configuration and successful CI, **not** proof of negative enforcement behavior or authorization to merge this PR.

## Active baseline — VERIFIED_REPO

- Repository: [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard).
- Ruleset: [main-baseline-protection, ID 25344164](https://github.com/storagebirddrop/Goud-btc-dashboard/rules/25344164); enforcement **active**.
- Branch selection: `~DEFAULT_BRANCH` (currently `main`); `main.protected=true`.
- Required pull request with **0** required approving reviews; independent human review is **not** technically enforced by this ruleset.
- Required GitHub Actions check contexts: `python` and `frontend` (GitHub Actions integration ID `15368`). Strict up-to-date checks: **false**.
- Linear history required; non-fast-forward pushes and deletion of the protected branch prohibited; no bypass actors.
- Allowed PR merge methods under the ruleset: merge, squash, rebase; repository also enables all three. Do not interpret linear history as squash-only enforcement.
- Repository `main` SHA at verification: `14a3ef3925266aa6c10278337527874b8ee0e3d8`.

## Controlled test and evidence

- [Temporary PR #44](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/44), branch `test/main-protection-preflight`, commit `47c32cca55814b2fbe3a087bcc59aee3bc6f5826`: one documentation-only file `docs/security/main-protection-preflight.md`, no other changed files, **closed without merge**.
- [CI run 39132143800](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39132143800): success; check runs `python` and `frontend` both completed successfully for the test commit. This proves check production, not negative enforcement.
- [CI workflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/.github/workflows/ci.yml) runs on pull requests and pushes to `main` and contains jobs `python` and `frontend`. No CI workflow changes were made as part of this security closure.
- [CBS source audit workflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/.github/workflows/cbs-source-spotcheck.yml) is not a universally required check because its PR trigger is path-filtered.
- The owner confirmed access to change enforcement back to Disabled. This is **OWNER_REPORTED**, not an independently executed rollback test.

## OPEN / UNVERIFIED — negative enforcement

**Open verification item BP-NEG-001:** On the next ordinary, authorized PR, observe whether required checks `python` and `frontend` block merging while pending, missing, or failing; record evidence of GitHub's effective merge conditions before and after successful checks, without actually merging for test purposes. Do not generate artificial failing commits. If unexpected access or merge-blocking behavior occurs, advise owner to restore Disabled and verify recovery; do not change the ruleset without explicit owner approval.

## Governance and disposition

- Security changes are **ROOD** under [CHANGE_CONTROL](CHANGE_CONTROL.md); the owner explicitly authorized controlled activation and confirmed manual rollback access.
- This closure is documentation only and must be reviewed via a **separate PR**. **Do not merge without separate authorization.**
- No force-push or deletion of `main`; no ruleset changes as part of this closure. The temporary test branch may be deleted after confirming its exclusive test scope and closing PR #44; branch deletion is an administrative follow-up if tooling does not permit it.
