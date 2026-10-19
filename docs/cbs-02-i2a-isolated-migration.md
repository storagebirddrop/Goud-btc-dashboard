# CBS-02-I2A — geïsoleerde historische migratie (PR ONLY)

## Governance en grenzen
CBS-01 CLOSED / RESEARCH DATA-GO; CBS-02-I1 MERGED/CLOSED. Deze taak maakt **uitsluitend interne kandidaatbestanden**. Geen publieke data-, frontend-, workflow-, live-adapter-, goud- of BTC-wijzigingen. Januari 2000 blijft de indexbasis. ADR-004, ADR-011 en de goudpublicatie-HOLD blijven gelden. Geen merge of publicatie zonder afzonderlijke governanceautorisatie.

## Vastgepinde bronnen
Baseline op main `8a05b2be442c529031f4d3da88cca21aacd5668f`:
- `data/cbs-housing.csv` SHA-256 `ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6`
- `frontend/public/data/monthly.json` SHA-256 `bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e`
- I1 `historical-prices.json` SHA-256 `0a557dd16fe85e40952dd97edd492d5b3f985f64930d19d960b14307d725c543`
- Oorspronkelijke 85773NED SHA-256 `e621f1828f759c6cd04453eba21ecf76748b3354956fc594cd40527f7d6b40e5`
- Oorspronkelijke 83906NED SHA-256 `e13e13f9969f03944ee93eef417b640447eb7f70230688b29eb04b1eba572338`

**Let op:** bron-CSV's en I1-output zijn niet opgenomen in deze PR. De fixture wordt op verzoek offline gereproduceerd met `python -m etl.cbs_historical_fixture` uit de twee gecontroleerde originele CBS-exports; neem de gegenereerde `historical-prices.json` en `provenance.json` over in een niet-publieke, afgeschermde map. De synthetische tests draaien zonder deze privébestanden. Een echte migratie vereist beide bestanden en de gepinde SHA-256; ontbreken is een harde fout. De I1-provenance is geen onafhankelijke digitale handtekening van CBS.

## Uitvoering (alleen buiten productie)
```bash
python -m etl.cbs_historical_merge \
  --fixture /secure/cbs01/historical-prices.json \
  --provenance /secure/cbs01/provenance.json \
  --baseline-csv data/cbs-housing.csv \
  --baseline-json frontend/public/data/monthly.json \
  --output-csv /tmp/cbs-i2a/candidate.csv \
  --output-json /tmp/cbs-i2a/candidate.json \
  --manifest /tmp/cbs-i2a/manifest.json

python -m etl.data_quality --input /tmp/cbs-i2a/candidate.csv --output /tmp/cbs-i2a/candidate.json
python -m pytest -q tests/test_cbs_historical_merge.py tests/test_cbs_historical_fixture.py tests/test_static_export.py tests/test_data_quality.py tests/test_schema.py tests/test_gold_publication_gate.py
```

De module weigert output in `data/`, `frontend/public/` of `frontend/dist/` en weigert bestaande kandidaatpaden te overschrijven. Er wordt eerst volledig in geheugen gevalideerd; daarna worden drie tijdelijke bestanden gestaged en naar geïsoleerde paden verplaatst. Bij fouten wordt opgeruimd. Meerdere outputbestanden zijn niet één atomische filesystem-transactie; **behandel uitsluitend een complete set met geldig manifest en overeenkomende outputhashes als reviewklaar**.

## Contract
Kandidaat-CSV: `date,series,value` (CRLF), 60 historische `nl_house_avg_eur`-regels vóór de **byte-identieke** bestaande 2000+-CSV-gegevensregels. Kandidaat-JSON: bestaand JSON-v1-object `{"data":[...]}` met dezelfde zeven velden per maand. Historische `house_eur` is positief integer; `hpi`, `hpi_index` en alle drie goudvelden zijn `null`; geen BTC. Bestaande 2000+-JSON-records blijven exact gelijk. HPI is de CBS-prijsindex, `hpi_index` is de eigen 2000-01-genormaliseerde index. Geen historische HPI-extrapolatie.

Manifest bevat input- en outputhashes, I1-provenance-hash, basiscommit, 60 historische maanden, behouden maandtelling en controle-uitkomsten. Geen kloktijd of nondeterministische metadata. Nieuwe CBS-revisies vanaf 2000 of gewijzigde originele bronnen vereisen expliciete herbeoordeling; de initialisatie faalt bewust bij gewijzigde baselinehashes.

## Rollback en CI
De huidige publieke CSV/JSON zijn onaangeroerd en vormen de exacte rollbackreferentie. Kandidaten kunnen veilig worden verwijderd; oorspronkelijke bytes en SHA-256 blijven behouden. CI controleert de synthetische negatieve gevallen zonder privédata. Een afzonderlijke offline echte-fixturerun is vereist vóór enige toekomstige merge-/publicatiebeoordeling; een groene CI alleen bewijst die niet. De live-updateworkflow wordt pas in CBS-02-I2B aangepast, en mag deze I2A-kandidaten niet automatisch publiceren.

## Risico's en scope
- **Bewust niet inbegrepen:** frontendlabels vanaf 1995, live-update historische bescherming, productiepublicatie, bronadapter, algemene ETL, historische HPI, goud en BTC.
- **Risico:** live CBS-updates blijven 2000+-kandidaten produceren totdat I2B is goedgekeurd. I2A publiceert daarom niets.
- **Risico:** baseline is strikt vastgepind; een legitieme latere revisie vereist nieuwe governance-review, geen stille hashupdate.
- **Risico:** JSON-v1 heeft geen `missing_reason`; de nullsemantiek wordt in deze documentatie vastgelegd, niet als ongeautoriseerde schemawijziging.
