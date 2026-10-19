# CBS-02-I1 — offline historische prijsfixture

**Scope:** uitsluitend 60 gemiddelde CBS-verkoopprijzen van bestaande koopwoningen, 1995-01 t/m 1999-12. **Geen productie-integratie, HPI, goud, BTC, JSON-v1-wijziging of publicatie.** CBS-01 Fase 5: CLOSED / RESEARCH DATA-GO; deze converter is een technische verificatie, geen aanvullende bronautorisatie.

## Invoercontract

Twee oorspronkelijke CBS StatLine CSV-exportbestanden, met exact de in `etl/cbs_historical_fixture.py` gepinde namen en SHA-256-waarden:

- Primair: `85773NED_SelectieZonderStatSymbol_20261019112844(1).csv`, SHA-256 `e621f1828f759c6cd04453eba21ecf76748b3354956fc594cd40527f7d6b40e5`.
- Vergelijking: `83906NED_SelectieZonderStatSymbol_20261019113553.csv`, SHA-256 `e13e13f9969f03944ee93eef417b640447eb7f70230688b29eb04b1eba572338`.

Bestanden zijn **niet** in Git opgenomen. Het gaat om de door de projecteigenaar aangeleverde CBS-01-exportbytes, niet om een nieuwe live download. Bronidentiteit is inhoudelijk geverifieerd maar niet cryptografisch onafhankelijk door CBS ondertekend. De converter verifieert eerst beide hashes. CSV: UTF-8 (optionele BOM), puntkomma, eerste rij kolomnamen, kolommen `Perioden` en exact `Gemiddelde verkoopprijs (euro)`; overige CBS-statistieken worden genegeerd. Perioden `YYYY nederlandse_maandnaam`, case-insensitive, met expliciete maandwoorden. Alleen 1995–1999. Positieve gehele eurobedragen zonder duizendtalseparator; 60 unieke, volledige maanden per bron; beide prijsreeksen moeten exact overeenkomen. Jaarregels en perioden buiten het venster worden niet gepubliceerd.

## Uitvoering

Vanaf repositoryroot, Python 3.12 of nieuwer:

```bash
python -m etl.cbs_historical_fixture \
  --primary '/secure/cbs/85773NED_SelectieZonderStatSymbol_20261019112844(1).csv' \
  --comparison '/secure/cbs/83906NED_SelectieZonderStatSymbol_20261019113553.csv' \
  --output '/tmp/cbs02-i1/historical-prices.json' \
  --manifest '/tmp/cbs02-i1/provenance.json'
python -m pytest -q tests/test_cbs_historical_fixture.py
```

Gebruik een niet-publieke lokale map voor de originele exports. Geen netwerkverbinding nodig. Fouten in hash, kolommen, CSV-rijbreedte, periode, maandnaam, prijs, volledigheid of cross-source-overlap geven een expliciete `ValueError` en stoppen vóór schrijven van output. De bestanden worden pas na succesvolle validatie aangemaakt; voer de tool uit in een schone outputmap om oude artefacten niet voor nieuwe resultaten aan te zien.

## Uitvoercontract

`historical-prices.json` bevat uitsluitend `{"data":[{"date":"1995-01","series":"nl_house_avg_eur","value":88991},...]}` met precies 60 chronologisch gesorteerde records tot `1999-12`. `value` is integer EUR, zonder HPI/goud/BTC. JSON heeft vaste UTF-8-serialisatie, LF en geen timestamps. `provenance.json` bevat afzonderlijk tabel-ID's, originele namen, SHA-256's, gebruikte kolommen, window, count, converterversie `CBS-02-I1/1`, verificatiestatus en output-SHA-256. De outputbytes zijn bij identieke inputs en converterversie identiek; de manifestbytes eveneens. Geen wijzigingen aan `data/cbs-housing.csv` of `frontend/public/data/monthly.json`.

## Reproduceerbaarheid en vervolg

De synthetische tests draaien zonder privébestanden. Met `CBS01_PRIVATE_SOURCE_DIR=/secure/cbs` voert de optionele test een echte CBS-01-cross-source-check uit. De vastgepinde bronhashes voorkomen stille bronvervanging: een nieuwe export of CBS-revisie vereist expliciete beoordeling en nieuwe provenance.

**CBS-02-I2 (niet uitvoeren in I1):** besluit over HPI-null vóór 2000, gecontroleerde join met bestaande 2000+-CSV, vaste januari-2000-indexbasis, aanpassing van statische export/validatie, frontend en CI-updategate, rollback en afzonderlijke publicatieautorisatie. Goud-HOLD blijft gelden.
