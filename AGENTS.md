# AGENTS — Autonomous Engineering Governance v3.0

Status: operationele agentinstructies na merge in main; methodologische voorstellen blijven onbeslist.

## Missie
Werk autonoom aan het Goud & Bitcoin Dashboard binnen de vastgelegde scope, economische definities, databronregels en datacontracten. Minimaliseer overleg; maximaliseer controleerbaar bewijs.

## Start iedere taak
1. Inspecteer actuele branch, git status, relevante code, workflows en tests. Rapporteer geen verificatie die niet is uitgevoerd.
2. Lees de relevante secties uit docs/governance/PROJECT_SCOPE.md, docs/governance/METHODOLOGY.md, docs/governance/DATA_SOURCES.md, docs/governance/DATA_CONTRACT.md, docs/governance/DECISIONS.md, docs/governance/ARCHITECTURE.md, docs/governance/PROJECT_STATUS.md en docs/governance/VERIFICATION_LOG.md. Lees niet blind alles als alleen specifieke delen nodig zijn.
3. Definieer in maximaal 8 regels: doel, grenzen, bewijs/acceptatiecriteria, risico en gekozen werkwijze.
4. Behandel `PROPOSED` nooit als `DECIDED`, en documentatieclaims `VERIFIED_REPO` nooit als bewijs van de huidige HEAD zonder hercontrole.

## Voorrang en conflicten
- Veiligheid, expliciete gebruikersinstructies en repositorybescherming zijn harde grenzen.
- Vastgelegde goedgekeurde economische besluiten (docs/governance/DECISIONS.md) en methodologische invarianten (docs/governance/METHODOLOGY.md) begrenzen implementatie; scope (docs/governance/PROJECT_SCOPE.md) begrenst functionaliteit.
- docs/governance/DATA_CONTRACT.md is normatief uitsluitend voor onderdelen die expliciet zijn goedgekeurd; voorgestelde schema's zijn niet stilzwijgend productiecontract.
- De werkelijke repository is bron van waarheid voor wat **geïmplementeerd** is, niet voor wat **bedoeld** of methodologisch correct is.
- Bij tegenstrijdigheid: leg bewijs en impact vast, ga verder met niet-geblokkeerde werkzaamheden, escaleer alleen de inhoudelijke keuze.

## Autonomieklassen
**Groen — zelfstandig:** lokale bugfixes, robuuste foutafhandeling, gerichte tests, documentatiecorrecties, compatibele kleine refactors, CI-debugging. Werk uit, test en rapporteer.
**Oranje — zelfstandig onder versterkte verificatie:** compatibele schema-extensies, backfill, bronadapters, performance, dependency-upgrades en beperkte architectuurwijzigingen zonder semantische wijziging. Vereis expliciete regressie-, provenance- en rollbackcontrole; maak PR in plaats van direct te mergen indien de risico's relevant zijn.
**Rood — expliciete toestemming:** nieuwe of gewijzigde economische definities, prijs- of tijdaggregatieregels, bronprioriteit met inhoudelijke gevolgen, gewijzigde scope, historische datavervanging zonder traceerbaarheid, destructieve acties, secrets, productiepublicatie met betekenisvolle impact en omzeilen van beschermde checks.

## Autonome uitvoering
Analyseer -> kies minimale wijziging -> implementeer -> voer gerichte tests uit -> debug -> regressietests -> onafhankelijke kritische review -> rapporteer. Herstel gewone fouten zonder tussenkomst. Stop niet na één mislukte test. Herhaal dezelfde mislukte aanpak niet zonder nieuwe hypothese.

## Dataintegriteit
Geen stilzwijgende interpolatie, backfill, forward-fill, bronwisseling of FX-aanname. Ontbrekende data blijft herkenbaar ontbrekend. Controleer tijddekking, eenheden, valuta, referentiedata, provenance, dubbelen, outliers en reproduceerbaarheid. Leg aannames vast en voeg testcases toe.

## Git en vrijgave
Werk op een taakbranch tenzij anders opgedragen. Commit alleen beoordeelde wijzigingen. Push en open PR wanneer toegestaan; merge alleen als expliciet gedelegeerd, vereiste checks slagen en repositoryregels dat toelaten. Squash nooit om een mislukte CI-run te verhullen. Geen gefingeerde hashes, URLs, testresultaten of tooluitvoer.

## Escalatieformat (alleen rood of echte blokkade)
**Beslissing nodig:** [1 zin]. **Waarom:** [bewijs]. **Opties:** [maximaal 2-3]. **Advies:** [keuze met impact]. **Wat zelfstandig doorgaat:** [restwerk].

## Eindrapport (maximaal 12 regels)
Doel; wijzigingen; bestanden/commit/PR (indien werkelijk aanwezig); uitgevoerde tests met uitkomst; datacontroles; afwijkingen en risico's; open beslissingen; volgende stap. Gebruik `NIET UITGEVOERD` waar bewijs ontbreekt.
## Documenthiërarchie
Zie [docs/governance/DOCUMENT_HIERARCHY.md](docs/governance/DOCUMENT_HIERARCHY.md). Bij conflicten geldt de goedgekeurde besluitstatus; historisch auditbewijs is geen autorisatie. PR #40 blijft onafhankelijk en mag niet stilzwijgend worden gemerged.

## v3.1 — risicogestuurde autonomie en release-gate
- Classificeer op **feitelijke semantische impact** als GROEN, ORANJE of ROOD volgens [CHANGE_CONTROL.md](docs/governance/CHANGE_CONTROL.md); niet uitsluitend op bestandsnamen.
- GROEN: autonoom repareren, testen en PR voorbereiden. Merge alleen bij **vooraf** expliciet gedelegeerde bevoegdheid en geslaagde geldende checks.
- ORANJE: autonoom implementeren met extra regressie-, provenance-, rollback- en impactcontrole; review en merge uitsluitend volgens vooraf vastgesteld beleid.
- ROOD: alleen onderzoek/voorstel zonder inhoudelijke uitvoering totdat de eigenaar expliciet beslist.
- Maak onderscheid tussen technische CI, kritische AI-review, onafhankelijke menselijke review, expliciete mergeautorisatie en geldende repositorybeveiliging.
- Een HTTP 403 bij branch protection betekent `UNVERIFIED_ACCESS`, niet `UNPROTECTED`. `protected=false` en een lege zichtbare rulesetlijst bewijzen niet dat alle andere reviewvereisten ontbreken.
- Wijzigingen aan mergebeleid zijn **niet retroactief**: deze v3.1-regels kunnen PR #41 niet zelfstandig autoriseren. Het vooraf geldende mergebeleid blijft gelden.
- Na een geldige merge: verifieer de commit op `main` en markeer ChatGPT-projectresources als te synchroniseren. Claim geen synchronisatie vóór uitvoering.
