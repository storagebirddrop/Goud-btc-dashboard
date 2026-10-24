# HIST-12 — Implementation report (inert historical dashboard)

Status: IMPLEMENTED, **INERT**. Historical publication: HOLD. No historical value exists anywhere in the repository, the build or any preview. Price-free.

## Governance baseline (verified before implementation)
- `main` at start: `106b617d8ccca32ca9ca42b4e5b17fa6706a7374` (HIST-11, PR #111, merged).
- **PR #112 ("docs(governance): approve HIST-11 HD1-HD3 inert UI scope") was still OPEN (draft, not merged)** at implementation time. `docs/governance/DECISIONS.md` on `main` therefore has **no HD1-HD3 record**. The explicit Project Control approvals given in the HIST-12 assignment were used as the authorization; the missing governance integration is reported here and PR #112 was not touched or merged.

## What was built
| Part | Files |
|---|---|
| Publication contract `hist-publication/1` (reuses `hist_model`: canonical JSON, `Series`, `release_hash`, `ReleaseRecord`, `publication_gate`) | `tools/hist_publication.py` |
| Frontend gate (TypeScript counterpart; fail closed, no messages) | `frontend/src/hist.ts` (`HIST_APPROVED_PAYLOAD_SHA256 = []`, `HIST_ALLOW_SYNTHETIC = false`) |
| Only network access, empty pin list = no request | `frontend/src/histLoad.ts` |
| Only URL-hash access (selects the tab, after authorization) | `frontend/src/histNav.ts` |
| Historical view, three panels, tables | `frontend/src/HistoricView.tsx` |
| Tabs Actueel / Historisch, hooks moved unchanged | `frontend/src/main.tsx`, `frontend/src/hooks.ts` |
| Synthetic fixtures and harnesses (test directory only) | `tests/hist12/` (synthetic data, fixtures, browser driver, gate parity) |
| Tests | `tests/test_hist_12_*.py` |
| CI | `ci.yml` (frontend job: TS-vs-Python gate parity), `hist-12-ui-acceptance.yml` (manual, browser) |

## Behaviour
- **Actueel** is the default and unchanged (the BTC synthetic browser acceptance still passes 62/62). **Historisch** exists only after the SHA-256 of the exact `historical.json` bytes is in `HIST_APPROVED_PAYLOAD_SHA256` AND the payload passes the structural gate. With the shipped empty list the file is not even requested.
- Panels (HD2): (1) NVM median per half-year in guilders with an optional converted-euro view (divisor 2.20371, labelled retrospective); (2) CBS monthly mean 1995-01..1999-12, euro, retrospective, ending where the current view begins; (3) NVM/CBS comparison on matching half-years as two separate lines with the median-vs-mean warning, rendered only when the payload block authorizes exactly that scope (HP3 stays undecided: production candidates cannot enable it, `COMPARISON_RELEASES` is empty).
- Not present: gold, grams, index, CPI, Bitcoin, fuel, equity. No interpolation, smoothing or joined series; `connectNulls=false`, linear segments; separate axes and units; accessible tables, text alternatives, keyboard tabs (Arrow/Home/End, roving tabindex), mobile layout.
- Quality and flags are shown in words (bevestigd/voorlopig; handmatig gecontroleerd; retrospectief euro; halfjaargemiddelde gewogen); an undocumented flag or quality refuses the payload.

## Contract gate (Python and TypeScript)
Hash pin; canonical serialization; exact schema and key sets; exact approved series ids, frequency, currency, unit, kind, definition, layer; exact period ranges with no gaps or extras; positive values; documented quality/flags only; provenance complete and lineage resolved; retrospective euro = guilder / 2.20371; comparison disabled or exact scope plus an external HP3 authorization; **authority is external** (`hist_model.ALLOWLIST` record or pin, never the payload); synthetic marker `SYNTHETIC_TEST_ONLY` refused in production and required in test mode.

## Deviations and limits (honest)
- No range presets / month pickers in the historical view (full ranges only; the series are short). Gap statistic of the comparison is not shown (derived value; HP3 undecided).
- The TypeScript gate does not recompute `release_hash` (covered by the exact-bytes pin); the Python gate does. Both agree on every synthetic fixture (parity test).
- The real NVM/CBS research data were deliberately not used; real-data rendering is NOT EXECUTED.
- Cloudflare behaviour for a missing `historical.json` is irrelevant while the pin list is empty (no request); once pinned, a missing file keeps the tab hidden.
