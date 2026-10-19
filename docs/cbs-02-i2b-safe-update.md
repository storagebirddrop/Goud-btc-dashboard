# CBS-02-I2B — gecontroleerde CBS-update

Status: PR ONLY. Geen publicatie of merge.

De updater vergelijkt live CBS-maandwaarden met alle bestaande, goedgekeurde waarden vanaf januari 2000. Afwijkende bestaande waarden worden gemeld als `CBS_REVISION_REVIEW_REQUIRED`; kalendergaten, dubbelen en ontbrekende bronbestanden veroorzaken een integriteitsfout. Beide blokkeren de kandidaat. Nieuwe aansluitende maanden worden wel toegelaten.

De historische fixture heeft SHA-256 `0a557dd16fe85e40952dd97edd492d5b3f985f64930d19d960b14307d725c543` en verwijst naar originele CBS 85773NED en 83906NED bronnen via een apart provenancebestand. De ruwe exports zijn niet opgenomen. De fixturemap in deze publieke repository is **niet privé**. Hergebruikvoorwaarden en verplichte bronvermelding moeten voor merge worden bevestigd; anders is een duurzame afgeschermde bronopslag nodig.

## Offline uitvoering

```bash
python -m etl.sources.cbs --output /tmp/cbs-live.csv
python -m etl.cbs_safe_update --live-csv /tmp/cbs-live.csv --output-dir /tmp/cbs-review
python -m etl.data_quality --input /tmp/cbs-review/candidate.csv --output /tmp/cbs-review/candidate.json
python -m pytest -q tests/test_cbs_safe_update.py
```

De uitvoer bevat uitsluitend `candidate.csv`, `candidate.json` en `manifest.json` buiten publieke paden. Het manifest legt input- en outputhashes vast; geen timestamps of autorisatie voor publicatie. Januari 2000 blijft indexbasis 100. Historische HPI- en goudvelden blijven null. JSON-v1 blijft intact. Bij een fout wordt geen kandidaatdirectory gepubliceerd.

## Rollback

Er wordt niets naar de bestaande publieke CSV/JSON geschreven. Verwijder de kandidaatdirectory om de update terug te draaien. Een toekomstige, afzonderlijk geautoriseerde release moet de laatst goedgekeurde Git-commit en SHA-256 als rollbackreferentie gebruiken.

## Open beslissingen

Revisieacceptatie vereist een afzonderlijk governancebesluit met bronvergelijking en nieuwe baseline. De voorwaarden voor publieke herdistributie van de genormaliseerde CBS-prijsfixture vereisen bevestiging. Geen goud- of BTC-publicatiebesluit.
