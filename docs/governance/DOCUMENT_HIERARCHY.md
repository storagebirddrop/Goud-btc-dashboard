# Documenthiërarchie en bron van waarheid

## Normatieve status

GitHub `main` is de versiebeheerbare bron van waarheid **na merge**. Een open PR is een voorstel. Documentatie bewijst nooit op zichzelf dat code draait, tests slagen of data publiceerbaar zijn. Het oorspronkelijke v3.0-pakket is een historische distributie; dit register is de repository-integratie.

1. **Harde grenzen:** veiligheid, expliciete eigenaarbesluiten, branch protection en toepasselijke regelgeving.
2. **Operationele instructies:** [AGENTS.md](../../AGENTS.md), [CHANGE_CONTROL.md](CHANGE_CONTROL.md), [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md), [TASK_TEMPLATE.md](TASK_TEMPLATE.md). Deze bepalen *hoe* agenten werken, niet *welke economische methode* is goedgekeurd.
3. **Inhoudelijk normatief, uitsluitend bij `DECIDED`:** [DECISIONS.md](DECISIONS.md), [METHODOLOGY.md](METHODOLOGY.md), [PROJECT_SCOPE.md](PROJECT_SCOPE.md), [DATA_SOURCES.md](DATA_SOURCES.md) en [DATA_CONTRACT.md](DATA_CONTRACT.md). Een `PROPOSED`-paragraaf blijft niet-bindend, ook als de tekst in GitHub staat.
4. **Technische implementatie:** actuele code, tests, workflows en [bestaande technische documentatie](../). Zij bewijzen implementatie, **niet** goedkeuring van economische betekenis. Bij mismatch tussen normatief besluit en code: niet stilzwijgend corrigeren; markeer afwijking en escaleer indien rood.
5. **Historisch bewijs en voortgang:** [VERIFICATION_LOG.md](VERIFICATION_LOG.md), [PROJECT_STATUS.md](PROJECT_STATUS.md), [HANDOVER.md](HANDOVER.md), [CONFLICT_MATRIX.md](CONFLICT_MATRIX.md) en bestaande gedateerde auditrapporten. Statusclaims zijn momentopnamen met bewijs en mogen latere runs niet voorspellen.

## Conflictresolutie

- `DECIDED` versus `PROPOSED`: besluit gaat voor; registreer wijziging via nieuw ADR en `SUPERSEDED`.
- Twee tegenstrijdige `DECIDED`-uitspraken: **stop de inhoudelijk afhankelijke wijziging**, leg bewijs vast, vraag projecteigenaar.
- Code versus besluit: code is implementatiebewijs, geen besluit; maak afwijking zichtbaar.
- Technische handleiding versus governance: behoud handleiding, markeer verouderde aannames; geen ongevraagde codewijziging.
- Gedateerde audit versus actuele status: verifieer run/commit opnieuw. `VERIFIED_REPO` ≠ `VERIFIED_RUN`.
- **Geen impliciete toestemming:** FX-forward-fill, dag-/maandkoersmethodologie, pre-2014 BTC-bronsplicing en publicatie blijven onbeslist totdat expliciet geautoriseerd.

## Wijzigingsprocedure

Voor iedere taak: lees relevante besluiten, inspecteer actuele HEAD en open PR's, registreer bewijs, gebruik [reviewchecklist](REVIEW_CHECKLIST.md), update status/verificatie na daadwerkelijke uitvoering. Alleen `DECIDED`-regels worden normatief toegepast. Zie [CONFLICT_MATRIX.md](CONFLICT_MATRIX.md) voor bestaande inconsistenties.
