# BTC-06 — Project Control Decisions

**Status: PROPOSED — NO IMPLEMENTATION OR PUBLICATION AUTHORIZED**  
**Datum:** 22 oktober 2026 · **Project:** Goud & Bitcoin Dashboard  
**Onafhankelijk geverifieerde main:** `42b32be65f890dba8b327f2c26b6112854e7a4f4`  
**Bijlagen:** `BTC-06_PRODUCTION_METHODOLOGY_ADR_DRAFT.md` (`PROPOSED — NOT ACCEPTED`) en `BTC-06_DATA_CONTRACT_DRAFT.md` (`PROPOSED — NOT IMPLEMENTED`).

## 1. Aanbevolen kleinste wijziging

**INFERRED — advies:** hergebruik CM C1, BTC-05D-snapshot/replay en de bestaande statische export. Bereid een optionele uitbreiding van dezelfde `monthly.json` voor met `btc_per_house`, `sat_per_house`, compacte maandstatus en één gedeeld BTC-metadatablok. Geen nieuwe ETL, opslagarchitectuur, workflowfamilie of immutable-release-v2-migratie. Houd publiek JSON en frontendactivering ongewijzigd tot een apart exact releasebesluit.

**CONFIRMED — materiële compatibiliteitsvoorwaarde:** de huidige goudcontrole hasht de volledige payload; extra BTC-velden veranderen die bytes. Het voorstel combineert daarom een streng gecontroleerde legacyprojectie voor ongewijzigde goud/CBS-inhoud met een nieuw exact record voor het samengestelde bestand. Oude goudautorisatie wordt niet voorgesteld als goedkeuring van nieuwe bytes. Validators en tests hebben bewust exacte velden; die mogen niet simpelweg worden versoepeld.

## 2. Reeds geautoriseerd versus nog open

| Onderwerp | Bestaande autorisatie / bewijs | Wat nog ontbreekt |
|---|---|---|
| Bron en rekenbasis | **CONFIRMED:** PC-BTC04-1/2 kiest CM Community PriceUSD + ECB, C1 research-accepted | Definitieve productieaanvaarding en exacte release |
| Kwaliteit | **CONFIRMED:** Q3 2010-08..2014-01, Q2 2014-02..2016-04, Q1_CANDIDATE vanaf 2016-05 | Geen automatische Q1-promotie; maand-/releasegeschiktheid apart |
| Juni 2011 | **CONFIRMED:** RESEARCH_ONLY_HOLD | Geen opheffing gevraagd; null en grafiekgat verplicht |
| Weergavestart | **CONFIRMED:** 2014-02 standaard en 2010-08 optioneel als ontwerprichting | Exact numeriek publicatieprofiel; vroege historie afzonderlijk autoriseren |
| Techniek | **CONFIRMED:** BTC-05D-code/doc op main; lokaal snapshot en fail-closed replay | Productieadapter, contracttests, ECB/CBS-revisiecontrole, duurzame private bewaring |
| Rechten | **CONFIRMED:** BTC-05A beschikbaar lokaal, conditional GO als onderzoeksoordeel | Concrete voorwaardencheck, aanvullend contractfeit en releaseacceptatie |
| Goud/CBS | **CONFIRMED:** bestaande payload/velden/goedkeuringen | Geen nieuw economisch besluit nodig voor behouden inhoud; samengestelde bytes vereisen wel nieuwe technische vrijgave |

Bewijslabels: **CONFIRMED** = gelezen code/bestaande stukken/opdracht; **INFERRED** = voorgestelde keuze; **UNVERIFIED** = nog te bewijzen. Dit rapport heeft geen besluiten namens Project Control genomen.

## 3. Nieuwe beslispunten

Alle keuzes hieronder zijn **INFERRED — conceptbesluiten**. De acceptatievragen zijn voor de review door Project Control; er is geen impliciet akkoord of uitvoeringsopdracht.

### PC-BTC06-1 — productie-ADR

- **Voorgestelde keuze:** aanvaard `CM_PRICEUSD_MONTHMEAN_C1_V1` als productiebetekenis, met volledige UTC-prijsmaand, gemiddelde geldige ECB-fixings en CBS-gemiddelde nominale verkoopprijs; houd releaseautorisatie apart.
- **Alternatief:** researchstatus aanhouden tot aanvullende methodologische vragen zijn opgelost. Een andere bron/dagratio-methode is geen onderdeel van deze opdracht.
- **Motivering:** continuïteit met aanvaarde onderzoeksbasis, zonder ongemerkte definitiewijziging.
- **Technische impact:** gerichte registratie en productieadapter; rekenpad hergebruiken.
- **Publicatierisico:** referentiewaardering kan worden aangezien voor EUR-handelsprijs of betaalbaarheid; verplichte toelichting en qualitylabels.
- **Expliciete acceptatievraag:** aanvaardt Project Control de bijgevoegde ADR-inhoud als productievoorstel, met alle publicatiegates nog gesloten?

### PC-BTC06-2 — minimale JSON-uitbreiding en getalsweergave

- **Voorgestelde keuze:** dezelfde flat `data` behouden; velden `btc_per_house`, `sat_per_house`, `btc_meta` en root `btc` met extensie-ID `btc-monthly/1`. Intern Decimal34; publiek JSON-numbers met strikte representatieverliescontrole, UI maximaal acht BTC-decimalen en hele satoshiweergave.
- **Alternatieven:** alleen SAT exporteren en BTC client-side berekenen; of decimal-strings met een bredere frontendwijziging. Geen aangetoonde noodzaak voor projectbrede v2.
- **Motivering:** beide gevraagde indicatoren direct leesbaar, bestaande frontendnaam voor SAT benutten, metadata éénmaal delen.
- **Technische impact:** types/formatting, gerichte validators en contracttests; bestaande zeven velden en waarden behouden.
- **Publicatierisico:** floatrepresentatie is niet exact Decimal34; export faalt bij verlies ≥0,25 satoshi-equivalent per veld. Quality/autoriteit mag niet uit een los JSON-label worden afgeleid.
- **Expliciete acceptatievraag:** accepteert Project Control deze veldnamen, null-/HOLD-semantiek, precision en compatibiliteitsroute volgens het datacontract?

### PC-BTC06-3 — initieel profiel en vroege geschiedenis

- **Voorgestelde keuze:** bereid `STANDARD_2014_02` voor; eindmaand pas vastleggen bij de werkelijk beoordeelde kandidaat. Vroege Q3-waarden niet in publieke JSON opnemen zonder apart besluit; juni 2011 blijft ook dan null en onverbonden.
- **Alternatieven:** eerste release pas 2016-05; of vroege historie tegelijk afzonderlijk autoriseren met Q3-caveats. Geen van deze opties is nu een vrijgave.
- **Motivering:** sluit aan op bestaande ontwerprichting en scheidt standaardgebruik van onzeker vroege historie.
- **Technische impact:** BTC-specifiek viewbereik en exacte maandallowlist, geen globale CBS/goudfilter.
- **Publicatierisico:** in JSON aanwezige vroege waarden zijn al publiek, ook als de grafiek ze verbergt. Q1_CANDIDATE blijft een evidenceklasse.
- **Expliciete acceptatievraag:** mag de eerste kandidaat standaard vanaf 2014-02 worden voorbereid, met vroegere numerieke historie standaard uitgesloten en afzonderlijk te autoriseren?

### PC-BTC06-4 — bescherming gezamenlijke artifactvrijgave

- **Voorgestelde keuze:** oude goud/CBS-JSON en goedkeuring behouden; de eerste BTC-kandidaat moet exact naar die legacybytes projecteren. Een nieuw eigenaarrecord bindt volledige nieuwe artifacthash, BTC-kandidaat en legacyprojectiehash. Geen impliciete repinning of uitschakeling van huidige hashchecks.
- **Alternatief:** één nieuw gezamenlijk record met expliciete repinning en even sterke content-/regressiecontrole. Alleen kiezen na engineeringreview die dezelfde bescherming aantoont.
- **Motivering:** huidige volledige goudhash kan niet tegelijk de andere bytes van een BTC-extensie identificeren.
- **Technische impact:** beperkte opt-in dispatch in `static_export`/`data_quality`, CBS-reviewvalidator en boundarytests; legacy mode blijft ongewijzigd.
- **Publicatierisico:** brede veldtolerantie of oude goedkeuring hergebruiken zonder exacte nieuwe bytes kan onbedoeld data publiceren.
- **Expliciete acceptatievraag:** aanvaardt Project Control de beschreven tweeledige validatie als voorkeursroute voor de latere gezamenlijke kandidaat, zonder de bestaande goud/CBS-besluiten inhoudelijk te wijzigen?

### PC-BTC06-5 — bronrevisies en toekomstige maanden

- **Voorgestelde keuze:** elke nieuwe volledige maand blijft een nieuwe reviewkandidaat; CM-, ECB- én CBS-revisies binnen goedgekeurde historie blokkeren vervanging tot afzonderlijke acceptatie. Geen automatische maandpublicatie en geen automatisch groeiende allowlist.
- **Alternatief:** later een begrensd delegatiebeleid voor uitsluitend nieuwe maanden vaststellen; dat is nu niet aangevraagd of aangetoond.
- **Motivering:** BTC-05D's CM-only maandplan is nog geen driebronnenreleasebeleid.
- **Technische impact:** bestaande generieke revisiehelper/vensterhash op ECB toepassen, CBS-safe-update hergebruiken; bestaande Actions blijven review-only.
- **Publicatierisico:** een stille CBS-/FX-revisie verandert dezelfde maandratio zonder zichtbare methodewijziging.
- **Expliciete acceptatievraag:** bevestigt Project Control expliciete kandidaatvrijgave per maandupdate en afzonderlijke historische revisieacceptatie als eerste productiebeleid?

### PC-BTC06-6 — rechten- en replaygates

- **Voorgestelde keuze:** BTC-05A conditional GO als kader gebruiken; eigenaarcontractcheck en exacte attributie vóór release afvinken. Een werkelijk bewaarde en terugvindbare BTC-05D-kandidaat plus exact passende CBS-input is een releasegate; duurzame bewaring blijft OPEN en wordt niet in BTC-06C herontworpen.
- **Alternatief:** voorbereiding met synthetische fixtures voortzetten en echte kandidaat/release uitstellen totdat rechten en praktische bewaring zijn opgelost.
- **Motivering:** lokaal IDENTICAL bewijst geen later herstel of volledige bron-/contractprovenance. ECB raw blijft NOT_RETAINED, geen fictieve full-rawclaim.
- **Technische impact:** wrapper vereist CBS-hash en bindt snapshotmanifest; geen nieuwe infrastructuur.
- **Publicatierisico:** aanvullend CM/Talos-contract en duurzame vindbaarheid zijn **UNVERIFIED/OPEN**; niet reduceren tot een ongecontroleerde boolean.
- **Expliciete acceptatievraag:** accepteert Project Control deze afzonderlijke releasevoorwaarden en de eerlijke huidige provenancegrenzen, zonder ze door ontwerpgoedkeuring als opgelost te markeren?

### PC-BTC06-7 — afgebakende BTC-06C-opdracht

- **Voorgestelde keuze:** na inhoudelijke review uitsluitend technische voorbereiding onder gesloten publicatiegate autoriseren, volgens §5 hieronder.
- **Alternatief:** eerst één of meer conceptbesluiten aanpassen en daarna engineering autoriseren.
- **Motivering:** productievoorbereiding is mogelijk zonder nieuwe economische keuzes of publicatie.
- **Technische impact:** beperkte adapter/contractvalidator, private kandidaten, withheld frontendvoorbereiding en tests.
- **Publicatierisico:** een voorbereidingsmerge mag geen artifactupload met BTC-data of feitelijke activering veroorzaken; gecommitte publieke JSON blijft exact gelijk.
- **Expliciete acceptatievraag:** autoriseert Project Control apart de beschreven BTC-06C-voorbereiding met behoud van HOLD, zonder merge-/deploy-/releasebevoegdheid?

## 4. Huidige uitkomst en bewijsgrenzen

**INFERRED — GO voor besluitvorming over methode/contract; CONDITIONAL GO voor later afgebakende engineering na expliciete opdracht; HOLD voor BTC-publicatie.**

**CONFIRMED — uitgevoerd:** actuele GitHub-HEAD en verplichte governance gelezen, BTC-04E/05D-code en documenten geïnspecteerd, daadwerkelijke payload geteld/gehasht, exporter/validator/frontend en relevante testdefinities gelezen, BTC-05A hergebruikt. De payload heeft 320 maanden; het mogelijke standaardbereik 2014-02..2026-08 telt 151 maanden. Dit is geen bewijs van 151 vrijgegeven BTC-punten.

**NIET UITGEVOERD:** implementatie, bronacquisitie, huidige CI, echte driebronnenkandidaatberekening, browser-/rollback-/duurzame hersteltests, repo-/pinwijziging, branch/PR/merge/deployment of Claude-activatie. Bestaande BTC-05D-meetresultaten zijn documentatie-evidence, niet hier opnieuw uitgevoerde tests.

## 5. Aanbevolen toekomstige Claude-opdracht — BTC-06C

**Conceptbrief, nog niet gegeven of uitgevoerd:**

> Controleer actuele main, AGENTS en de expliciet geaccepteerde PC-BTC06-besluiten. Implementeer alleen de goedgekeurde minimale productievoorbereiding: adapter van bestaande CM C1/BTC-05D-uitvoer naar private `btc-monthly/1`-kandidaat; verplichte CBS-hash, snapshot-/methode-/quality-/exceptionprovenance; exact maandselectiebeleid; CM/ECB/CBS-revisiecontroles; gerichte contract-/formule-/null-/boundarytests. Bereid frontendtypes, formattering, BTC-viewbereik, bron-/qualityuitleg en juni-gat voor onder `withheld`, met synthetische fixtures. Hergebruik bestaande rekenfuncties, snapshotformat en workflows. Werk de samengestelde artifactvalidatie alleen achter expliciet gesloten activation gates uit; huidige publieke JSON blijft byte-identiek, `RELEASE_APPROVALS` leeg en BTC niet selecteerbaar. Lever gerichte regressie- en reviewevidence volgens de 24 voorgestelde acceptatietests. Markeer niet uitgevoerde live-/releasechecks. Maak alleen branch/PR wanneer de latere opdracht dat toestaat; geen merge, deploy of BTC-publicatie. Stop bij Project Control.

Geen nieuwe storage, secrets, cloudresources, source pins, bronselectie, C1-formule, qualityupgrade, juni-override of geautoriseerde goud/CBS-inhoud wijzigen. Als daadwerkelijke kandidaatbewaring of rechtenbewijs ontbreekt: synthetische voorbereiding afmaken en het ontbrekende releasebewijs expliciet open laten.

**Bronnen:** [geverifieerde main](https://github.com/storagebirddrop/Goud-btc-dashboard/commit/42b32be65f890dba8b327f2c26b6112854e7a4f4), [PC-besluiten](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/DECISIONS.md), [BTC-05D](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/research/BTC_05D_VINTAGE_REPLAY.md), [data_quality](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/data_quality.py), [seriesregistry](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/src/series.ts), lokaal BTC-05A en de twee bijgevoegde BTC-06-concepten met uitgebreide bronnenregisters.

**BTC-PUBLICATIE BLIJFT HOLD.**
