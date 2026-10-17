# Goud & Bitcoin Dashboard — Project Resources v3.0

**Historische pakketbeschrijving:** de oorspronkelijke distributie bevatte acht v2.1-documenten en aanvullende governancebestanden. Deze repository-integratie bevat gecontroleerde aanvullingen op onder meer status, verificatie en documenthiërarchie; de bestanden zijn daarom niet meer ongewijzigd.

## Oorspronkelijke gebruiksinstructies (historisch, niet normatief voor GitHub)

Onderstaande instructies beschrijven de aangeleverde distributie. De actuele repositorywerkwijze staat in [AGENTS.md](../../AGENTS.md) en [DOCUMENT_HIERARCHY.md](DOCUMENT_HIERARCHY.md).

## In gebruik nemen
1. Voeg de Markdown-bestanden toe aan de ChatGPT-projectresources; plaats `AGENTS.md` ook in de repositoryroot voor agenten die dat bestand ondersteunen.
2. Gebruik `TASK_TEMPLATE.md` voor nieuwe opdrachten. Een doel en enkele acceptatiecriteria volstaan doorgaans.
3. Laat de agent `REVIEW_CHECKLIST.md` gebruiken bij elke betekenisvolle code- of datawijziging.
4. Vul `HANDOVER.md` aan het einde van de sessie in en controleer hem bij de volgende sessie tegen de actuele repository.
5. Maak GitHub branch protection en vereiste CI-checks apart operationeel. Deze ZIP installeert of configureert ze niet.

## Status en auditgrenzen
- De oorspronkelijke v2.1-teksten vormden de basis; deze PR voegt expliciete repositoryverificaties en interpretatienotities toe.
- De vijf nieuwe bestanden zijn governancevoorstellen, niet bewezen repository-instellingen.
- Deze zin gold voor de oorspronkelijke distributie; de repository-integratie heeft GitHub HEAD en CI afzonderlijk geverifieerd in [VERIFICATION_LOG.md](VERIFICATION_LOG.md). Live externe bron- en productiecontroles blijven open.
- Bestaande `PROPOSED`, `DECIDED` en `VERIFIED_REPO` labels behouden hun oorspronkelijke historische betekenis; een nieuwe sessie moet actuele implementatieclaims opnieuw toetsen.

## Volgende technische stap
Controleer bestaande GitHub Actions en branch protection; voeg vervolgens uitsluitend ontbrekende kwaliteitschecks toe, inclusief data-integriteits- en regressietests.
## Repository-integratie
De operationele ingang is [AGENTS.md](../../AGENTS.md). Zie [DOCUMENT_HIERARCHY.md](DOCUMENT_HIERARCHY.md) en [CONFLICT_MATRIX.md](CONFLICT_MATRIX.md). Dit document beschrijft de oorspronkelijke distributie; het is geen bewijs van actuele CI of branch protection.
