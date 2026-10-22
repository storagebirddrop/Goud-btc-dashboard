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

## Update 2026-10-18 — PR #42 en CBS-bronaudit
- `VERIFIED_REPO`: PR #42 squash-merged; `main` commit `e6b5a3b20109683ced7fdc380d1a4b02598a9e7a` wijzigt alleen `etl/static_export.py` en `tests/test_static_export.py`.
- `VERIFIED_RUN`: PR CI [39122777887](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39122777887) success (124 passed, 3 skipped; frontend build success); live CBS smoke [39122777891](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39122777891) success. Post-merge CI [39123914206](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39123914206) en static update [39123914043](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39123914043) success op mergecommit.
- `IN_PROGRESS`: onafhankelijke CBS-bronsteekproeven in afzonderlijke PR #43. Een geslaagde CBS-smoke bewijst contract/dekking, **niet** dat historische committed waarden overeenkomen met live CBS. Resultaten van echte spotchecks blijven `UNVERIFIED` totdat de handmatige read-only auditworkflow daadwerkelijk is uitgevoerd.
- `BLOCKED`: publicatiegoedkeuring voor goud, BTC, FX- en maandmethoden ongewijzigd.

## Historische CBS-dekkingsaudit — 2026-10-18 (PR #43)
- `VERIFIED_RUN`: [full-history CBS run 39124817771](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124817771) geslaagd op `3aa3994b2aa04d002c429e9365f6d5481b27ef52`. Vergelijking huidige officiële CBS OData 85773NED met committed CSV: januari 2000–augustus 2026, 320 maanden, 640 observaties, 640 exact gelijk; geen ontbrekende maanden of verschillen in dit venster.
- `VERIFIED_RUN`: [CI 39124817780](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124817780) geslaagd op dezelfde commit.
- `UNVERIFIED`: CBS-publicatiesnapshots uit eerdere jaren ontbreken voor bewezen historische revisiedatering; de live bronvergelijking is geen onafhankelijke tweede statistische bron. Geen automatische revisie- of publicatiebesluiten.

## Update 2026-10-19 — koerswijziging goudbrononderzoek
- `VERIFIED_MERGE`: [PR #51](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/51) leverde de gated goudpipeline; [PR #52](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/52) accepteerde de goudspecifieke ADR-004; [PR #53](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/53) registreerde de publicatierechtenbeoordeling met HOLD. PR #53 is squash-gemerged als `35bfe320c96249c18942ffaf53ca3f436d760508`.
- `VERIFIED_RUN`: post-merge PR #51 CI [39160997684](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39160997684) en PR #52 CI [39163991143](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39163991143) SUCCESS; PR #53 CI [39165515461](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39165515461) SUCCESS vóór merge.
- `DECIDED` (onderzoeksrichting, niet bronacceptatie): herbeoordeel een kleine shortlist van historische goudprijsbronnen op herkomst, maanddekking vanaf 2000-01, prijsdefinitie, onafhankelijke controles, expliciete rechten voor grafieken én publieke JSON en integratiekosten. Kandidaten zijn onder meer DataHub, World Gold Council en een onafhankelijke spot-/institutionele reeks. De naam of open-licentievermelding van een aggregator bewijst geen sublicentierecht op derdepartijgegevens.
- `BLOCKED` **[voor `gold_index` en `gold_grams_per_house` vervangen door het eigenaarbesluit GOLD-03 van 2026-10-20; historische momentopname]**: publicatie van goudindicatoren onder de huidige World Bank-gebaseerde implementatie blijft HOLD; `gold_eur_oz`, `gold_index` en `gold_grams_per_house` blijven publiek `null` totdat bronkeuze, eventuele ADR-aanpassing en afzonderlijke activatie zijn goedgekeurd.
- `NEXT`: eerst read-only brononderzoek en validatie; daarna expliciet bronselectiebesluit. Geen nieuwe backfill, productiecode, publieke JSON, publicatieflags of automatisch implementatie-PR in deze documentatiesynchronisatie.
- Eerdere secties zijn historische momentopnamen. Deze update vervangt hun inmiddels achterhaalde goudstatusclaims, maar wijzigt geen BTC-, CPI- of Cloudflare-besluiten.

## Update 2026-10-20 — GOLD-03: HOLD opgeheven voor twee afgeleide indicatoren
- `DECIDED`: de projecteigenaar heeft de goudpublicatie-HOLD opgeheven voor uitsluitend `gold_index` en `gold_grams_per_house` vanaf 2000-01; schriftelijke World Bank-toestemming is geen verplichte projectgate meer. Het rechtenrisico (derdepartij-uitzondering, IBA/LBMA, terugrekenbaarheid van `gold_eur_oz`) is als restrisico geregistreerd, niet als opgelost; zie [DECISIONS.md](DECISIONS.md) (GOLD-03) en [GOLD_PUBLICATION_DECISION.md](GOLD_PUBLICATION_DECISION.md).
- `UNCHANGED`: ADR-004 blijft de goedgekeurde methodologie; `gold_eur_oz` blijft `null`; geen ruwe goudprijzen of bronworkbooks; Bitcoin en satoshi's blijven `withheld`.
- `IN PREPARATION`: de technische implementatie (publieke JSON met de twee indicatoren, herpinning van hashes, CI, bronvermelding en browsercontrole) staat in een Draft PR en is **niet gemerged en niet live**. Merge, deployment en release vereisen een afzonderlijke expliciete toestemming van de projecteigenaar voor de exacte kandidaat.
- Eerdere goud-`BLOCKED`/HOLD-regels in deze en andere documenten zijn voor deze twee indicatoren vervangen en blijven als historische momentopname staan.

## Historische dekking — update 2026-10-19 (`DECIDED` ambitie, uitvoering open)
- `DECIDED`: streef naar de oudste betrouwbaar vergelijkbare landelijke gemiddelde Nederlandse woningverkoopprijzen, idealiter vanaf circa 1900; januari 2000 is geen projectgrens.
- `VERIFIED_REPO`: de huidige World Bank GOLD-adapter en statische export bevatten een 2000-01 filter/grens; huidige productiedata blijven onveranderd.
- `PROPOSED/UNVERIFIED`: NVM/Vastgoedmarkt-jaarreeks circa 1975–1994 als historische uitbreiding; toets definitie en overlap met CBS/Kadaster 1995–heden.
- `DOCUMENTED/UNVERIFIED`: World Bank GOLD heeft volgens bronbeschrijvingen historie vanaf 1960; GOLD-specifieke Excel-notities en volledige vroege data nog niet end-to-end gecontroleerd.
- `OPEN`: landelijke gemiddelde woningprijzen vóór 1975, historische valutaomrekening, verschillende aggregatiefrequenties en goudprijsregimes.
- `BLOCKED`: publieke goudactivatie blijft uit; geen code, dataset of ADR gewijzigd door dit documentatiebesluit.

## Update 2026-10-21 — GOLD-04: live verificatie productie
- `VERIFIED_RUN`: productie (`goud-btc-dashboard.pages.dev`, na herstel van de Cloudflare-GitHub-koppeling, productiecommit `cbc385f`) serveert de geautoriseerde GOLD-03-release: JSON sha256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`, 320 maanden, `gold_index` en `gold_grams_per_house` 320/320, `gold_eur_oz` `null`, CBS-velden ongewijzigd, bronnen en juni-2025-uitleg zichtbaar, desktop en mobiel (live-run 39577148435: 27/27 HTTP, 68/68 browser). Details in VERIFICATION_LOG.md (V-GOLD-04).
- `VERIFIED_RUN`: BTC-publicatiebescherming: geen BTC-/satoshi-veld in de publieke JSON, `sat_per_house` blijft `withheld`, geen selecteerbare Bitcoin-reeks of -grafiek, geen omzeiling via URL of vergiftigde JSON. Alleen de statische zin "Nog niet beschikbaar: reële EUR en Bitcoin." noemt Bitcoin (productbeslissing van de eigenaar of die blijft).
- `PENDING`: formele afsluiting van GOLD-04 na merge van PR #87 (verificatietooling, grenscontrole en regressietests); geen wijziging aan data, ADR-004 of applicatiecode.


## Project Control actuele status — 2026-10-22 (vervangt achterhaalde operationele conclusies hierboven)

**VERIFIED_REPO / VERIFIED_MERGE:** GitHub `main` HEAD is `4758e251ac1c5ad0216da38a8d1cc0abca7ac4cd`, na de squash-merges van [PR #91](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/91) (HIST-09/ARCH-02, `b9b28832e450ee19fd8357eb827866f286554557`), [PR #92](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/92) (HIST-10, `d5cac04d1bb9f34785f060ddb067d72da4c99eab`) en [PR #93](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/93) (BTC-03, `4758e251ac1c5ad0216da38a8d1cc0abca7ac4cd`). Alle vereiste PR-checks waren groen vóór de betreffende merges; dit is **geen claim** dat huidige post-merge productiechecks opnieuw zijn uitgevoerd.

**GEVALIDEERDE ONDERZOEKSBASIS (niet gepubliceerd):**
- HIST-09: NVM/OTB 52 halfjaren 1975-H1..2000-H2, mediane verkoopprijzen NLG; officiële CBS 85773NED 72 maanden 1995-01..2000-12; 12 NVM/CBS-overlap-halfjaren, apart gehouden. Geen NVM/CBS-splice.
- HIST-10: goud per woning voor NVM vanaf 1975 en CBS vanaf 1995 (research only). Onderzoeksmethode `HIST10_M1_V1`, expliciete valuta-eras en kwaliteit, SHA-256-bronvenster-pins. Bronrechten voor uitgebreide historische publicatie onbeslist.
- BTC-03: CBS-prijzen in BTC en satoshi's met gescheiden Mt. Gox-, USD-afgeleide Bitstamp- en EUR-native Bitstamp-segmenten. Onderzoeksmethode `BTC03_A1_C1_V1`; A1/C1 geaccepteerd **voor onderzoek**, Q1 EUR-native 2016-05+, Q2 USD-afgeleid 2013-07+ onder voorlopige liquiditeitsheuristiek, Q3 eerder/thin/archive research only. NVM eindigt in 2000-H2: **geen** BTC-overlap, dus geen NVM/BTC-reeks. Bronvenster-pins zijn vastgelegd; hashes alleen bewaren geen oude bronbytes.
- Bestaande publieke goudstatus blijft GOLD-03/GOLD-04: uitsluitend `gold_index` en `gold_grams_per_house` vanaf 2000-01 geautoriseerd/live; `gold_eur_oz` blijft null. BTC/satoshi, nieuwe historische goud- en woningprijsreeksen zijn **NIET** voor publicatie geautoriseerd. Onderzoeksallowlist blijft leeg volgens mergechecks.

**OPEN / RELEASE-GATES (niet vervallen door succesvolle CI):**
1. Juridisch en feitelijk hergebruik per BTC/NVM/historische goudbron, inclusief derived-data rechten en attributie; CBS-export vermeldt CC BY 4.0.
2. Bronkwaliteit/segmentkeuze voor eventuele publieke BTC-grafieken: Q1/Q2/Q3-verschillen, de voorlopige liquiditeitsdrempel en onafhankelijke bronvalidatie; BTC-methodologie is nog niet als productie-ADR aanvaard.
3. Definities/presentatie: CBS gemiddelde vs NVM mediaan apart, bronbreuken expliciet, 1975-1978 goudkwaliteitslabel, 1998/1999 valuta-overgang en 2016 BTC EUR-native overgang.
4. Nieuwe publicatie vereist afzonderlijke expliciete eigenaarbesluiten en tests voor data-contract, release-gate, frontend, browser en rollback. Een onderzoek-PR-merge is **nooit** publicatieautorisatie.

**NEXT (Project Control):** een afgebakende publicatie-readiness matrix uitwerken met per voorgestelde grafiek reeks, jaarrange, kwaliteit, rechtenstatus, methodologisch besluit, technische releaseafhankelijkheden en voorstel `GO/HOLD`. Geen code-publicatie, source-splice of ADR-statuswijziging in deze documentatiesynchronisatie. `docs/governance/HANDOVER.md` bevat de sessieoverdracht. De oudere momentopnamen hierboven zijn historisch, geen huidige blokkadestatus.

## Project Control-status — BTC-04F synchronisatie (2026-10-22; actueler dan eerdere BTC-momentopnamen)

- **VERIFIED_MERGE:** [PR #95](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/95), `research/btc-04e-coinmetrics-replay`, is na expliciete eigenaarautorisatie **squash-gemerged** op `main`: `64b078ee8a80d9f50b14536ba2e081892d6ef1c2`. De PR-HEAD was `c9828d754d8fed252a2ebcdc6921de33e95ed93f`; vóór merge zijn de vijf vereiste checks op precies die HEAD als `SUCCESS` gecontroleerd. Dat is geen nieuwe claim over live BTC-publicatie.
- **DECIDED / CONDITIONALLY ACCEPTED:** PC-BTC04-1 t/m PC-BTC04-4-F7 in [DECISIONS.md](DECISIONS.md). Coin Metrics Community `PriceUSD` + ECB is de primaire **onderzoek-/productiekandidaat**, met methode `CM_PRICEUSD_MONTHMEAN_C1_V1` en vroege onderzoeksambitie 2010-08.
- **Onderzoeksuitkomst:** Q3 2010-08..2014-01; Q2 2014-02..2016-04; Q1-kandidaat vanaf 2016-05. Standaardgrafiek-richting 2014-02; optionele Q3-historie vanaf 2010-08; **juni 2011 blijft research-only HOLD** wegens onbewezen prijsversheid. Geen automatische fallback/splice.
- **TECHNISCH RESEARCH-ONLY:** PR #95 heeft adapter, tests, read-only workflow en hash-only bronpins gemerged; de validatie rapporteert 193 onderzochte CBS-maanden t/m 2026-08, een `MATCH`-vintage, tijdelijke runner-replay `IDENTICAL` en expliciete niet-publiceerbare status. Deze interne maandwaarden, inclusief een diagnostisch berekende 2011-06, zijn **niet** gelijk aan 193 goedgekeurde publieke maandpunten.
- **OPEN / RELEASE-GATES:** (1) bronrechten/attributie, (2) toegestane duurzame raw-vintageopslag en revisiebeleid, (3) BTC-productie-ADR/datacontract, (4) UI en maandselectie inclusief juni-gat, (5) release-/rollbackvalidatie en afzonderlijke eigenaarautorisatie. BTC/satoshi-publicatie en frontendactivatie blijven **HOLD**.
- **NEXT:** BTC-04F governance-PR beoordelen en na afzonderlijke mergeautorisatie verwerken; daarna per open gate een afgebakend voorstel. Deze aanvulling wijzigt geen productiecode, `monthly.json`, goudautorisaties of historische onderzoekspins.

## Project Control-status — BTC-06C productiekandidaat en datacontract (2026-10-22; actueler dan eerdere BTC-momentopnamen)

- **DECIDED / ACCEPTED (Project Control):** PC-BTC06-1 t/m 7; **PC-BTC06-6 uitsluitend voorwaardelijk** (openstaande voorwaarden nog niet in de repository overgenomen). Productiemethodologie `CM_PRICEUSD_MONTHMEAN_C1_V1` (ADR-012) en het ontwerp `btc-monthly/1` zijn aanvaard als methodologische definitie respectievelijk datacontractontwerp; zie [DECISIONS.md](DECISIONS.md) en [DATA_CONTRACT.md](DATA_CONTRACT.md).
- **TECHNISCH (Draft PR `feature/btc-06c-production-candidate`, niet gemerged):** private kandidaatadapter op de BTC-05D-snapshot, contractvalidator, verplichte CBS-hash- en snapshotprovenancecontrole, revisiecontroles voor CM, ECB en CBS, exacte legacyprojectie op de vastgepinde goud/CBS-hash, inerte frontendtypes en tests. Alles blijft privé; geen upload van kandidaatwaarden, geen publieke wijziging.
- **PUBLICATIE-HOLD (ongewijzigd):** BTC/satoshi `withheld`; `RELEASE_APPROVALS` en artifactregister leeg; `monthly.json` byte-identiek; juni 2011 absolute HOLD; geen numerieke vroege geschiedenis vóór 2014-02.
- **OPEN / RELEASE-GATES:** (1) overname van de PC-BTC06-6-voorwaarden; (2) bronrechten en attributie (BTC-05A is nog niet in de repository en niet als vrijgave gebruikt); (3) duurzame toegestane opslag van historische bronbytes; (4) reconciliatie met de BTC-06A-conceptdocumenten (24 acceptatievoorstellen niet beschikbaar); (5) UI-activering, browser-, restore- en live-releaseproeven (niet uitgevoerd); (6) afzonderlijke eigenaarautorisatie en een exact artifactrecord voor elke publicatie.
