# HIST-13 — Owner decision pack

Nothing is decided or activated. Candidate identity for review: `historical.candidate.json` SHA-256 `e35a28946feb2612cf994fbc78cdffd70815af63740c9314dfb036ab01ba2d51`, content hash `99e6f998b3d8ed7f10099110b48b0d87a9da2fba7367212527577ffb86be95c0`, proposed release id `HIST-REL-2026-10-001` (PROPOSED).

| ID | Decision | Recommendation |
|---|---|---|
| HP1 | NVM/OTB rights (UNVERIFIED); note that the rows are already public in the repository fixtures | per-source owner decision: permission or an explicit risk acceptance with attribution; also decide whether the fixtures should stay in Git |
| HP2 | CBS 1995-1999 attribution wording (CC BY 4.0, own transformations) and the retrospective-euro label | approve |
| HP3 | Show the NVM/CBS comparison (separate panel, warning) | show, own panel, warning kept |
| HP4 | Page-135 values | accept the visible "handmatig gecontroleerd" label unless the image is supplied |
| HP5 | Release identity: authorizer, date, decision reference; then the payload is assembled privately, its SHA-256 pinned in the frontend, a `ReleaseRecord` added to the allowlist (and the HP3 entry if approved) in a separate release PR with a change-set check; then deployment authorization | after HP1-HP4 |
| HP6 | Permanent storage of the derived dataset (HIST-10 decision 9) | approve for this payload once HP1/HP2 are settled |

Technical note for HP5: because the contract embeds the owner fields, the final hash cannot be pre-computed; the builder reproduces the candidate byte-identically on demand (`python -m tools.hist_13_candidate --inputs data/fixtures/hist09 --out-dir <private dir>`).
