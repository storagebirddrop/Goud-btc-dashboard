# BTC-09 — Decision-record amendment (PROPOSAL)

Status: `PROPOSED`. Not applied to DECISIONS.md. Nothing below is DECIDED or ACCEPTED until Project Control expressly approves it. Implementation (release record, pin, deployment) is separate and stays NOT AUTHORIZED.

## Proposed amendment text (Dutch, for DECISIONS.md after approval)
> **PC-BTC09-A1 — Release-uitgangspunten Bitcoinreeksen (voorgesteld).**
> 1. **Restrisico bronrechten (CM-10).** Het in PC-BTC07D-CM10 aanvaarde restrisico geldt ook voor de beoogde persoonlijke, informatieve en niet-commerciële, publiek bereikbare website (geen advertenties, affiliate-inkomsten, betaalde toegang, diensten of promotie). De publieke bereikbaarheid van de JSON en de daaruit volgende terugrekenbaarheid van maandreferentieprijzen worden bewust aanvaard. Geen juridische vrijwaring; bij concreet strijdige voorwaarden of een wijziging van het niet-commerciële gebruik volgt herbeoordeling. Geen afzonderlijke Coin Metrics-/Talos-toestemming vereist.
> 2. **Bronvintage.** Uitsluitend snapshot `btc04e-e11c2538168b2bde` (bron-TAR SHA-256 `19abaa9b47c8172924920249304009bbea47e1c612b190666dfa28991b80d4ce`). Een andere vintage vereist een nieuw besluit en een nieuw releaserecord; vintages worden nooit gemengd.
> 3. **Dekking.** Standaardprofiel 2014-02 t/m 2026-08 (151 aaneengesloten maanden). Q3-maanden en 2011-06 (`RESEARCH_ONLY_HOLD`) blijven buiten publicatie; geen interpolatie of aanvulling.
> 4. **Kwaliteitspresentatie.** Q2 (27 maanden) en Q1_CANDIDATE (124 maanden) worden getoond met behoud van het voorlopige onderscheid; Q1_CANDIDATE wordt nergens als definitief Q1 gepresenteerd.
> 5. **Bronvermelding.** De bestaande BTC-08B-teksten (bronrollen, wijzigingsvermelding, bronstand, geen onderschrijving door Coin Metrics, ECB of CBS) gelden als definitieve attributie voor de release.
> 6. **Herstelkopie (D05).** Een privé-eigenaarkopie van de bron-TAR is een **disaster-recovery-eis**, geen operationele afhankelijkheid: de publieke website is statisch en leest tijdens runtime geen back-up. De TAR is wel de bouwinvoer voor de herbouw van de kandidaat; een gecontroleerde herstelrun (`REAL_OWNER_RESTORE_PASS`) is vereist vóór die herbouw.
> 7. **Geen publicatieautorisatie.** Dit besluit autoriseert geen releaserecord, geen frontend-hashpin, geen `ARTIFACT_RECORDS`-vermelding, geen deployment en geen publieke activering. Die vereisen een afzonderlijk, exact besluit over artefactidentiteit en deployment (D07/D08).

## Why each item can be approved now (evidence, all price-free)
1. Source use: CM-10 text already records non-commercial attestation; this only extends its stated scope from private/small-circle to a publicly reachable site (CM-10 itself flags this boundary). No new conflicting term was found in BTC-09.
2. Vintage: restore + anchor + historical candidate reproduced (run 40027551242).
3. Coverage: 151/151 months contiguous, independent recomputation 151/151 (tolerance 1e-25).
4. Quality: counts Q2 27 / Q1_CANDIDATE 124 verified; labels shown in the UI by the existing acceptance (R02).
5. Attribution: browser checks B07/B07b.
6. Static release independent of the backup: the site reads only `/data/monthly.json` (guarded by `tests/test_static_architecture.py`); the shipped build contains no snapshot, TAR or candidate file (`tools/btc_09_distribution_check.py dist`, 16 negative tests). Loss of the backup after release cannot affect the running site; it would only block a future rebuild or independent re-verification.

## Not part of this proposal
Exact composite SHA-256, release id, approver identity, record contents, pin value, deployment window (D07/D08). BTC publication remains HOLD.
