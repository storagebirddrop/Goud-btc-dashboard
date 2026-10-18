# Main branch protection — controlled preflight

This is a temporary, documentation-only pull request to validate the existing GitHub Actions CI jobs `python` and `frontend` before enabling repository protection.

- No production code, economic methodology, datasets, or workflow configuration is changed.
- Do **not** merge this pull request.
- No force pushes or branch deletion tests are authorized.
- The repository owner must confirm ruleset recovery access and manually configure and activate the intended ruleset before enforcement tests.
- The existing ruleset was observed as **disabled**, with only `required_linear_history` and no included branch patterns as of the preflight. It must not be activated in this incomplete state.

After CI passes, inspect the exact check names and conclusions, then separately test effective merge restrictions after explicit owner confirmation. An open PR is not authorization to merge.
