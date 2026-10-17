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