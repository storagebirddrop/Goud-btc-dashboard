# HIST-13 — Source manifest (price-free)

Status: PRIVATE CANDIDATE, NOT AUTHORIZED FOR PUBLICATION. Baseline `main` `1458cf5cbbd5987f4d2482a3048a3f78fe428af5` (HIST-12 merged). HD1-HD3 are recorded in `docs/governance/DECISIONS.md` (`PC-HIST11-HD1-HD3`, DECIDED / OWNER_APPROVED, 2026-10-24); the HIST-12 gate is closed (`HIST_APPROVED_PAYLOAD_SHA256 = []`, `hist_model.ALLOWLIST = ()`, `COMPARISON_RELEASES = ()`).

## Inputs (hash-pinned HIST-09 package, `data/fixtures/hist09`; no live or revised data)
| Input | SHA-256 | Role |
|---|---|---|
| `HIST09_NVM_1975_2000_RESEARCH.csv` | `099489a42548f81c009607d464756871d11b8a646bfc54d0a28e687e3d5dffda` | NVM nominal median, NLG, half-year, OTB 2001 table B3.8 (52 values) |
| `85773NED-202609220630.zip` | `01d2aea00c19026e41b18ccd3a17b6beb004cd1b914a8a4a3f6683e15700584f` | owner-supplied CBS StatLine 85773NED export (CC BY 4.0 catalogue licence read in the export) |
| `SHA256_MANIFEST.json` | `f9ca15412b6b6bcabc30fffd94c5495086e45a2a672d4cc83417faa60b8a280a` | package manifest (verified by the adapter before any read) |

Vintage references carried in the candidate: `csv:099489a42548`, `zip:01d2aea00c19`. Acquisition timestamps: NVM `2026-10-22T00:00:00+00:00` (HIST-09 verification date), CBS `2026-09-22T06:30:00+00:00` (taken from the export file name, **not independently verified**).

## Source statuses
- NVM/OTB: rights `UNVERIFIED` (HP1 open). 41 of 52 values (1975-H1..1995-H1) rest on Project Control's page-135 verification (flag kept); the 11 values of page 136 were re-read from the owner screenshot in HIST-09.
- CBS: CC BY 4.0; attribution and own-transformation wording is HP2. Values before 2002 are retrospective euro (NLG originals not obtained).
- **Finding:** the HIST-09 input rows are already committed in this (public) repository under `data/fixtures/hist09` since HIST-09. They are not in any frontend asset or build, but they are publicly readable in Git; relevant for HP1/HP6.

## Series built (contract `hist-publication/1`)
| Series | Periods | Frequency | Statistic / unit | Series SHA-256 |
|---|---|---|---|---|
| `hist_nvm_median_nlg_h` | 1975-H1..2000-H2 (52) | semiannual | median, NLG | `f049e7eb5ed2f80cb8f54adda3540f97aa5528dedd54bee7a6767a556582eeba` |
| `hist_nvm_median_eur_retro_h` | same (52) | semiannual | median, retrospective EUR (= NLG / 2.20371) | `9cd4b0a0baef0b810f99795c162c31ea524f8afcb481497db255c8d34d40533e` |
| `hist_cbs_avg_eur_m` | 1995-01..1999-12 (60) | monthly | mean, retrospective EUR | `8a53e0205eba3aa20b81caed51dfe4eb30430a970ab79bf80d12443eeb0ec8eb` |
| `hist_cbs_avg_eur_h` | 1995-H1..2000-H2 (12) | semiannual | transaction-weighted mean, retrospective EUR | `18082f124aa9cd679037ff50bc930d67fb0ab74d503ae61830b6d44beedabc5f` |

Flags carried: only the contract's documented set. Internal source/review flags (`OTB_2001_B3_8`, `CBS_85773NED`, `REDENOMINATED`, `MONTHS:6/6`, and `VISUAL_P136_SESSION_REVIEW` on the 11 page-136 values) stay in the HIST-09 bundles and are not part of the public contract; the page-135 qualification (`VISUAL_P135_PER_PROJECT_CONTROL`, 41 points in each NVM series) is preserved.
