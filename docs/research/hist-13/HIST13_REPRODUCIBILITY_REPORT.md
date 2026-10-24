# HIST-13 — Reproducibility report

Builder: `tools/hist_13_candidate.py` (tests: `tests/test_hist_13_candidate.py`). Environment: the Claude session sandbox, **not** an owner-controlled machine. Private storage or restoration is **not claimed**: the candidate files existed only in the ephemeral session directory.

## Candidate identity (private files; hashes only here)
| File | SHA-256 |
|---|---|
| `historical.candidate.json` (release block PENDING / unauthorized) | `e35a28946feb2612cf994fbc78cdffd70815af63740c9314dfb036ab01ba2d51` |
| content hash of the four series (`release_sha256`, `hm.release_hash`) | `99e6f998b3d8ed7f10099110b48b0d87a9da2fba7367212527577ffb86be95c0` |
| `historical.provenance.json` | `3d9f69010924ca7e2bc6d603e5a4150806336614c4431587344fa6c95d394089` |
| `historical.manifest.json` | `bbd27572948662cc16bcf2d229086e7428d048b394c297566a0f173409f82b5f` |
| `historical.release-record.template.json` | `236f66384ea156f0d857f01f34fc0c0b5c369a4810baae960cfb49a5f7961000` |
| `historical.validation-report.json` | `239d03843ddd5eeba80e0020fbdf54e3501808b7cc36c48fa1889cb9b1bbfdc5` |

**The final payload hash is NOT AVAILABLE.** The contract embeds the owner's authorizer, date and decision reference in the payload; the pin therefore exists only after those fields are supplied (assembled privately). The two preflight payloads below carry a TEMPORARY non-owner authorization and are never an approved release: comparison off `1dd15d1c281f256a23b1e10736f406c3199509d72e1effeb8f69b53ad9a15011`, comparison on `8e60807363630ac85a6253620678879d556f7ad5860c2c7bc154b45cb6db3d3e`.

## Checks (all executed)
- 52/52 NVM half-years (1975-H1..2000-H2), 60/60 CBS months (1995-01..1999-12), 12/12 comparison half-years (1995-H1..2000-H2); all periods consecutive, no gaps, no extras, no 2000 monthly values republished.
- **Independent recalculation** from the raw pinned csv/zip with Fractions (no `hist_model`, `hist_09_bundle` or `hist_publication`): NVM guilders equal; euro = guilder / 2.20371 to 1e-30; 60 CBS months equal the original export; 12 half-year weighted means recomputed from monthly price and registered sales to 1e-30; periods aligned; median and mean series kept separate. Reconciliation: the 12 CBS months of 2000 equal the current dataset (read-only check).
- **Determinism:** two builds in separate processes give byte-identical files (all five documents and both preflight payloads).
- Source integrity: package manifest, validation JSON and both pinned hashes verified before any read; a tampered csv byte or a missing zip blocks the build (tests).

## Limits
- "Source vintage VERIFIED" means the pinned bytes and their hashes; whether CBS has revised the live table since the 2026-09-22 export was not checked (no live access used by design). Exact reproducibility therefore holds from the pinned package, not from the live source.
- The CBS export time comes from the file name.
