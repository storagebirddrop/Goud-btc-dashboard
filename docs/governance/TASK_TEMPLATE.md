# TASK_TEMPLATE — resultaatgerichte opdracht

Gebruik dit sjabloon om een taak te starten. Laat de agent het technische plan zelf uitwerken.

## Doel
[Wat moet aantoonbaar werken?]

## Niet onderhandelbare grenzen
- Respecteer goedgekeurde projectmethodologie, scope en datacontracten.
- Geen stilzwijgende semantische of bronwijzigingen.
- Geen destructieve acties of bypass van beschermde checks.

## Acceptatiecriteria
- [Meetbaar gedrag of resultaat]
- [Relevante data-integriteitscontrole]
- [Regressiecontrole]

## Autonomie
Voer analyse, implementatie, debugging, tests en kritische review zelfstandig uit. Stel alleen vragen bij een rood besluit of een blokkade die niet verantwoord technisch oplosbaar is. Lever bewijs, geen uitsluitend narratieve succesclaim.

## Oplevering
Korte samenvatting, gewijzigde bestanden, concrete testcommando's + uitkomst, commit/PR indien gemaakt, resterende risico's en aanbevolen volgende stap.

## Voorbeeld — Bitcoin-backfill
**Doel:** realiseer reproduceerbare BTC-backfill binnen reeds goedgekeurde methodologie.
**Acceptatie:** aantoonbare bronprovenance, expliciete ontbrekende waarnemingen, consistente valuta-/datumconversie, idempotente reruns, falende tests voor corruptie of dubbele datums.
**Escalatie:** alleen bij noodzakelijke wijziging van bronprioriteit, aggregatie of economische definitie.

## v3.1 — taakcontract
- **Risicoklasse:** [GROEN / ORANJE / ROOD en feitelijke impact]
- **Delegatie:** [vooraf verleende uitvoering- en mergebevoegdheid]
- **Merge-gate:** [head-SHA, checks, reviews, beveiligingsstatus en onbekenden]
- **Beslisgrens:** [eigenaarbesluit dat de agent niet zelfstandig mag nemen]
- **Technische beoordeling:** [PASS / PASS WITH CONDITIONS / FAIL]
- **Mergeautorisatie:** [AUTHORIZED / NOT AUTHORIZED / UNKNOWN]

Technische fouten autonoom oplossen; technische kwaliteit nooit als zelfstandige mergeautorisatie beschouwen.
