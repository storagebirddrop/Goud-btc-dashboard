# HIST-11 — Owner decision pack (Project Control)

Nothing below is decided. Historical publication is HOLD. BTC D08 is separate and unaffected. Recommended defaults are stated; alternatives are listed only where a factual reason exists.

## A. Needed before code implementation (inert code, no data, no visibility)
| ID | Decision | Recommendation | Why |
|---|---|---|---|
| HD1 | UI approach | **Option C** (separate "Historisch" view, "Actueel" stays default and unchanged) | A changes the legacy hash bound into the approved BTC identity and the public contract; B loses the CBS context |
| HD2 | Phase C0 scope: nominal levels only — NVM half-year (NLG original + labelled retrospective EUR), CBS monthly 1995-1999, labelled comparison; **no gold, no index** | approve | gold before 2000 needs an ADR (ROOD); indexes lack an approved base |
| HD3 | Contract `hist-publication/1`: separate `historical.json`, reuse of `hist_model` gate, `HIST_APPROVED_PAYLOAD_SHA256` pin default `[]` | approve; `monthly.json` byte-identical | smallest fail-closed change, no BTC interference |

## B. Needed before publication (exact artifact)
| ID | Decision | Recommendation |
|---|---|---|
| HP1 | NVM/OTB source rights (UNVERIFIED): permission or an explicit owner risk acceptance of the CM-10 type, with attribution wording | owner decision per source; the NVM half-year series cannot go out without it |
| HP2 | CBS 1995-1999 in the separate file under CC BY 4.0 with attribution and "own transformations" wording; retrospective-euro label for values before 2002 | approve |
| HP2b | Optional: add the retrospective-euro note to the **existing** current view for 2000-2001 (production labelling gap) | decide separately; UI-only, ORANJE; not a prerequisite |
| HP3 | Show NVM vs CBS side by side (labelled comparison, gap statistic) or keep strictly separate (HIST-10 decision 5 left it undecided) | show, in its own panel, with the "niet gelijk te stellen" notice |
| HP4 | Page 135: owner supplies the image (removes the flag) or accepts the visible "handmatig gecontroleerd" marker | accept the marker unless the image is available |
| HP5 | Exact release identity: payload SHA-256, release id, decision ref, approver/date; then a separate deployment authorization | after P2 |
| HP6 | Permanent storage of a derived historical dataset in Git/Pages (HIST-10 decision 9 required a provenance and rights assessment) | approve for the C0 payload once HP1/HP2 are settled |

## C. Can remain deferred
| ID | Topic |
|---|---|
| HG1-HG5 | Historical gold and grams: ADR extending ADR-004 backwards (ROOD); rights for World Bank pre-2000, Fed H.10 and ECB own-transformation wording; whole-USD rounding disclosure; Fed->ECB source break wording; quality-level presentation (B/A/E) |
| HI | Any historical index and base policy; Kadaster/NVM index-only 1970-1994 (D4); CPI/real values (D6, ADR-009) |
| HX | Option A (extending the main series) — a separate ROOD decision that would also re-open the BTC release identity |
| HY | Permanence of the 50% FX threshold; private raw-vintage store; pre-1975 horizon |

## Minimum set to start implementation: HD1, HD2, HD3. Minimum set to publish C0: HD1-HD3, HP1, HP2, HP3, HP4, HP5, HP6 and a deployment authorization.

## Technical (no decision needed)
TECH-1 read the CBS table notes for 1995-2000 definition changes (read-only, closes criterion 9 of S3); TECH-2 implement P1/P2 once HD1-HD3 are approved.
