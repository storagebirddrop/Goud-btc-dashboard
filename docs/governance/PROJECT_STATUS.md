# PROJECT_STATUS — geauditeerde momentopname en backlog

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Executive status
**Vroege ontwikkeling, niet productie-gereed.** CBS-adapter, historische CSV, statische JSON, CI-definitie en handmatige BTC-validatie-workflow bestaan in GitHub (`VERIFIED_REPO`). Dat bewijst **niet** dat alle CI-runs groen zijn, alle data kloppen of Cloudflare live is.

## Statusmatrix
| Onderdeel | Status | Onderbouwing / volgende stap |
|---|---|---|
| Repo `storagebirddrop/Goud-btc-dashboard`, default `main` | `VERIFIED_REPO` | GitHub repositoryzoekresultaat |
| CBS `85773NED` adapter | `VERIFIED_REPO` | `etl/sources/cbs.py` |
| Twee CBS-reeksen in CSV | `VERIFIED_REPO` (aanwezigheid) | `data/cbs-housing.csv`; complete telling en bron-spotchecks nog `UNVERIFIED` |
| Statische frontend JSON | `VERIFIED_REPO` (aanwezigheid) | `frontend/public/data/monthly.json`; in beginrecords goud `null` |
| CI-workflow en tests | `VERIFIED_REPO` (code/config) | `.github/workflows/ci.yml`; actuele groene run `UNVERIFIED` |
| CBS-update-workflow | `VERIFIED_REPO` (config) | `.github/workflows/update-static-data.yml`; run/deploy `UNVERIFIED` |
| BTC Coin Metrics adapter | `VERIFIED_REPO` (code) | `etl/sources/coinmetrics.py` |
| BTC-backfill uitvoer met bruikbare koersdata | `BLOCKED` voor publicatie | read-only validatie; specifieke eerdere failures `UNVERIFIED` |
| Goudprovider/licentie | `BLOCKED` | bronkeuze en rechten ontbreken |
| CPI-vergelijking | `PROPOSED` | exacte CBS CPI reeks ontbreekt |
| Cloudflare Pages live publicatie | `UNVERIFIED` | deployment-URL en release-audit ontbreken |
| Atomische multi-series releases | `PROPOSED` | nieuw contract en integratietest vereist |

## Kritieke bevindingen uit review v1
- K1: absolute woningprijs en prijsindex gescheiden; **inhoudelijk opgelost in documentatie**, frontend controleren.
- K2: statusclaims gekoppeld aan GitHub bestandsbewijs; **workflow-resultaten nog open**.
- K3: primaire maandratio gedefinieerd; aggregatiekalender/koersfixing **nog te besluiten**.
- K4: versiegebonden releaseontwerp toegevoegd; **implementatie ontbreekt**.
- B1–B7: CPI-beperkingen, pre-market missingness, bronregister, revisies, dekking, JSON-contract en beslislog nu expliciet.

## Geprioriteerde acties
### P0 — blokkades
1. Verifieer CBS veldidentifiers, tabelmetadata, 320-maandenclaim, publicatie-/revisiedata en steekproeven.
2. Audit `main` op commit-SHA, laatste CI-run en refresh-workflowresultaat; leg run-URL's vast.
3. Beslis primaire maandkoersdefinitie en bronkalenders (goud en BTC).
4. Kies juridisch herbruikbare goudbron en valideer onafhankelijke prijsankers.
5. Onderzoek BTC-backfill met workflow-run-ID, gekozen periode, HTTP/status en echte brondekking.
### P1 — betrouwbaarheid
6. Implementeer `DATA_CONTRACT.md` v2 inclusief missing reasons en releaseversies.
7. Bouw atomische release-/rollbackflow en frontend-schemahandshake; test cache/mismatch.
8. Documenteer CPI-serie en herzieningsbeleid; voeg onafhankelijke controles toe.
### P2 — onderhoud
9. Harmoniseer legacy D1-documenten, tests en README.
10. Leg source owners, verificatiedata, SLA en herzieningsprocedure vast.

## Go/no-go
**NO-GO** voor claim 'historische gram goud/BTC per woning is productie-gereed' totdat P0-bron-, licentie- en datavalidatie afgerond zijn. **GO** voor voortzetting van gecontroleerde CBS-scaffold-ontwikkeling.

## Update v2.1 — geverifieerde BTC-audit en Actions
- `VERIFIED_RUN`: [auditrun 39050246824](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824) is geslaagd. BTC/USD 1d: 4.409 unieke geldige dagen, 2014-09-17 t/m 2026-10-12, nul gaten/duplicaten/ongeldige waarden. EURUSD 1d: 4.368 unieke dagen, 2010-01-01 t/m 2026-10-12; 3.142 gelijktijdige BTC/FX-dagen, 1.267 BTC-dagen zonder same-day FX.
- PR #35 is squash-gemerged (`7e9126a99036f2038dc99505c154ded8da85bd54`). PR #36 is squash-gemerged (`aff32f3da65778288677606e37a93c9982e5cd34`); auditbesluit staat in `docs/btc-trading-history-audit-2026-10-17.md`. Coin Metrics-catalogusworkflow is uit Actions verwijderd; adapter/tests behouden.
- `DECIDED`: bestaande tradingdataset is primaire **kandidaat** voor BTC/USD vanaf 2014-09-17; **niet** vrijgegeven voor publicatie. Yahoo-herpublicatierechten, FX-beleid, maandmethodologie, onafhankelijke koerscheck en vroegere historie blijven `BLOCKED`/`PROPOSED`.
- Eerdere tabelregels in dit document die 'actuele groene CI onbekend' of BTC-runresultaten als niet geverifieerd beschrijven zijn historische observaties uit v2.0; de bovengenoemde specifieke runs zijn inmiddels wél geverifieerd. Overige workflow/deployclaims blijven ongeverifieerd.
## Gecontroleerde repositorystatus bij governance-integratie (2026-10-17)
- `VERIFIED_REPO`: main HEAD `ef5a5e1007affe093d6187631e79c28ed4850326` vóór deze governance-PR; GitHub branch listing gecontroleerd.
- `VERIFIED_PR`: #37, #38 en #39 gesloten en gemerged; #40 open en niet gemerged. PR #34, #30, #22 en #21 eveneens open (naast dependency-PR's).
- `VERIFIED_RUN`: [auditrun 39054825172](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39054825172) en [CI-run 39054825208](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39054825208) op main `ef5a5e1` beide `success`; auditjob bevestigd en acht ontbrekende FX-weekdagen in logs gezien.
- `PROPOSED`: PR #40 onderzoekt read-only BTC/EUR maandgevoeligheid; geen goedkeuring van FX-carry-forward, maandaggregatie, bronpublicatie of productie-import.
- Eerdere `UNVERIFIED`-meldingen blijven geldig voor CBS live-broncontrole, Cloudflare deploy, onafhankelijke koersbenchmark en licenties, tenzij afzonderlijk aangetoond. Zie [VERIFICATION_LOG.md](VERIFICATION_LOG.md) voor auditgrenzen.

## v3.1 — integratiestatus (2026-10-17)
- `VERIFIED_REPO`: PR #41 was open/draft op HEAD `7ae264036ef8d5d97277e5095e231181e3fe1d96` vóór v3.1; GitHub PR API gecontroleerd.
- `VERIFIED_RUN`: [run 39057761181](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39057761181) `success` op de eerdere v3.0-HEAD; **niet** geldig voor de v3.1-wijzigingen.
- `UNVERIFIED_ACCESS`: branch protection detail gaf eerder 403. Branch API meldt `protected=false` en rulesets API een lege lijst; daarmee zijn aanvullende eigenaarregels niet bewezen afwezig.
- `PENDING`: v3.1 definitieve CI, review/mergeautorisatie en resource-synchronisatie. PR #40 blijft buiten scope.
