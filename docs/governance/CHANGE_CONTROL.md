# CHANGE_CONTROL — besluiten zonder micromanagement

## Principe
Technische keuzes zijn standaard gedelegeerd. Alleen keuzes die de betekenis, scope, veiligheidsgrenzen of onomkeerbare staat wijzigen, vereisen toestemming.

## Classificatie
- **Groen:** technische reparatie zonder gedrags- of semantische wijziging; uitvoeren en rapporteren.
- **Oranje:** compatibele uitbreiding met verhoogd regressierisico; uitvoeren met extra tests, traceerbare review en zo nodig PR-gate.
- **Rood:** wijziging van economische definitie, bronrangorde, tijdaggregatie, publicatiebetekenis, productdoel, destructieve actie of beveiligingsgrens; vraag besluit vóór de risicovolle stap.

## Besluitregistratie
Leg rode keuzes vast in [DECISIONS.md](DECISIONS.md) als voorstel met aanleiding, alternatieven, gevolgen, beslisser, datum en status. Markeer pas `DECIDED` na expliciete bevestiging. Werk gekoppelde methodologie, contracten en tests daarna samen bij.

## Niet escaleren
Gewone compileerfouten, flaky tests, API-timeouts, ontbrekende fixtures en compatibele refactors zijn in beginsel engineeringwerk. Escaleer pas bij hard bewijs van een inhoudelijke of externe blokkade.

## Mergebeleid
Geen automatische merge zonder expliciete delegatie en aantoonbaar geslaagde vereiste checks op de relevante commit. Branch protection blijft leidend. Rood is nooit stilzwijgend gedelegeerd.

## v3.1 — risicoklassen en mergebevoegdheid

| Klasse | Uitvoering | Mergevoorwaarde |
|---|---|---|
| GROEN | Autonoom: bugfixes, tests, documentatie, compatibele kleine refactors | Alleen vooraf expliciet gedelegeerde mergebevoegdheid, geldende checks en repositorybeleid |
| ORANJE | Autonoom met versterkte regressie-, provenance-, rollback- en impactcontrole | Review en merge volgens vooraf vastgesteld beleid; geen impliciete auto-merge |
| ROOD | Analyse en voorstel toegestaan; inhoudelijke wijziging wacht op eigenaar | Expliciet eigenaarbesluit én geldende reviews/checks |

Classificeer op **semantische impact**, niet op extensie of bestandsnaam. CI-bewijs, kritische AI-review, onafhankelijke menselijke review en mergeautorisatie zijn afzonderlijk. Een formele menselijke review is alleen een harde gate als vooraf vastgesteld beleid of repositoryregels dat vereisen; ontbrekend bewijs van beleid is geen bewijs van afwezigheid.

**Toegangsgrens:** HTTP 403 op protection API = `UNVERIFIED_ACCESS`; niet `UNPROTECTED`. Noteer zichtbare branch- en rulesetstatus afzonderlijk. Wijziging van beveiligingsgrenzen is ROOD.

**Geen circulaire autorisatie:** nieuwe delegatie uit een governance-PR kan diezelfde PR niet retroactief autoriseren. Voor PR #41 blijven de vooraf geldende voorwaarden van kracht.
