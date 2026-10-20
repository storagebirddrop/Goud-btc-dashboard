# Fase 1 — Historische databronnen: onderzoeksrapport (2026-10-17)

Status: **voorlopige bronbeoordeling; geen historische data geïmporteerd**.

## Samenvatting
Een dashboard met Nederlandse woningprijzen versus goud vanaf 1900 is methodologisch mogelijk, maar niet als één uniforme maandelijkse reeks. Tot 1995 is de woningprijsinformatie vooral historisch gereconstrueerd en jaarlijks; vanaf januari 1995 biedt CBS landelijke maandelijkse HPI en gemiddelde verkoopprijzen. De goudprijs vóór 1978 vraagt aanvullende bron- en wisselkoerscontrole. Publicatierechten zijn een afzonderlijke go/no-go-voorwaarde.

## Bronnenmatrix

| Dataset | Bron | Dekking en frequentie | Sterkte | Beperking / rechten | Besluit |
|---|---|---|---|---|---|
| NL HPI en gemiddelde verkoopprijs | CBS StatLine 85773NED | 1995–heden, maandelijks | Officieel, reeds in ETL | Gemiddelde verkoopprijs ≠ zuivere prijsindex | **Behouden; uitbreiding tot 1995 onderzoeken** |
| Historische NL huizenprijsindex | JST Macrohistory R6 | Dataset vanaf 1870, jaarlijks; NL-dekking per variabele verifiëren | Academisch, bronnotities | **CC BY-NC-SA 4.0**, geen onbeperkt commercieel hergebruik; index ≠ gemiddelde prijs | **Kandidaat, niet importeren zonder licentie-/dekkingcheck** |
| Historische goudprijs | MeasuringWorth | Lange historische jaarlijkse reeksen, Londen/VS | Gedocumenteerde prijsdefinities | Niet-winstgericht educatief gebruik; toestemming gevraagd voor publiceren >5 opeenvolgende jaren | **Onderzoek; niet publiek kopiëren** |
| Goudprijs maandgemiddelden | World Gold Council Goldhub | Vanaf 1978, maandelijks in meerdere valuta | Goede frequentie | Afkomst/voorwaarden van onderliggende benchmarkdata en downloadrechten controleren | **Kandidaat, geen automatische ingest vóór licentiecheck** |
| LBMA Gold Price | LBMA / ICE Benchmark Administration | Benchmark, historische data | Marktbenchmark | Historische toegang, gebruik en redistributie licentiegebonden | **Niet automatisch herpubliceren** |
| BTC-marktdata | Coin Metrics | Trades vanaf juli 2010; beschikbare referentiekoersen verifiëren | Reproduceerbare marktdata | Community history, rate limits en licentie voor openbare afgeleide reeks checken | **Kandidaat** |

## Primaire bronlinks
- CBS: https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table
- JST download en licentie: https://www.macrohistory.net/database/
- MeasuringWorth: https://measuringworth.com/datasets/gold/result.php
- World Gold Council: https://www.gold.org/goldhub/data/gold-prices
- LBMA: https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices
- Coin Metrics Community: https://gitbook-docs.coinmetrics.io/packages/coin-metrics-community-data
- Coin Metrics historical trades: https://github.com/coinmetrics/docs-website/blob/master/market-data/market-data-faqs.md

## Rekenregels en ontwerpkeuzes
1. **Bewaar bronwaarden** met originele valuta, bron, periode, frequentie en methode. Voor NLG→EUR is 1 EUR = 2,20371 NLG de vaste conversiefactor; CPI is een afzonderlijke reële-waardeberekening.
2. **Centrale uitkomst**: gram goud per woning, respectievelijk BTC/satoshi per woning. Gebruik woningprijs en activaprijs uit dezelfde periode en in dezelfde valuta.
3. **Jaargegevens blijven jaargegevens**. Geen kunstmatige maandwaarden uit jaarlijkse historische HPI/goudreeksen. In de grafiek onderscheiden: jaarlijkse historische reconstructie versus maandelijkse moderne data.
4. **Historische index ≠ absolute gemiddelde woningprijs**. Een omgerekende historische woningprijs vereist een expliciet modern anker en de aannames/kwaliteitslabel `reconstructed`.
5. **Goudregimes** (goudstandaard, officiële prijzen, vrije markt) zichtbaar annoteren; vermijd de implicatie dat elk historisch koerspunt een vrije marktprijs is.
6. **Geen schijnprecisie**: documenteer aggregatie (maandgemiddelde versus einde maand), FX-matching, herkomst en ontbrekende observaties.
7. **Geen externe data in openbare repository voordat gebruiksrechten zijn bevestigd**.

## Openstaande verificaties / volgende onderzoeksstap
- JST: controleer exacte Nederlandse HPI-jaarobservaties, ontbrekende jaren, definitie, overlap met CBS, en licentie voor beoogd dashboardgebruik.
- Onderzoek alternatieve historische NL-reeksen met minder restrictieve rechten.
- Goud: zoek machineleesbare historische reeksen met expliciete publicatie-/redistributierechten; verifieer 1900–1977 goudregimes en bronkwaliteit.
- FX: vind Nederlandse historische USD/NLG en GBP/NLG koersen, dekking vanaf 1900, officiële versus marktkoersen en gebruiksrechten.
- CPI: verifieer langlopende CBS/andere Nederlandse CPI, basisjaar, kettingmethode en rechten.
- BTC: test de daadwerkelijk toegankelijke vroege BTC/USD- en EUR-data en de licentie voor een publiek statisch JSON-bestand.
- Definieer overgangs- en consistentietests voordat een historische reeks aan de huidige frontend wordt gekoppeld.

## Impact op live dashboard
Geen. Huidige CBS-data, GitHub Actions en Cloudflare Pages blijven ongewijzigd.

## Aanvullende Bitcoin-bronnen (aangedragen door gebruiker)
- **BlockHorizon Charts** — https://charts.blockhorizon.io/ — Bitcoin-analyseplatform. Site bereikbaar; historische prijsdekking, CSV/API-export, methode en herpublicatierechten nog **niet geverifieerd**.
- **Checkonchain** — https://www.checkonchain.com/ en https://charts.checkonchain.com/ — aanbieder van Bitcoin-on-chain- en marktindicatoren. Officiële website verwijst naar een chartportaal; beschikbaarheid van ruwe historische BTC/EUR- of BTC/USD-prijzen, export/API en licentie voor publieke GitHub-JSON nog **niet geverifieerd**.
- **Onderzoekscriterium**: onderscheid originele spotprijsdata van afgeleide on-chain-indicatoren; controleer timestamp, quote currency, exchange/composite methode, oudste punt, gaten, rate limits en commerciële redistributie.
- **Besluit**: beide opnemen op shortlist; geen scraping of kopiëren van chartdata zonder expliciete toestemming/voorwaarden.

## Verdieping Bitcoin-bronnen (2026-10-17)
- **Coin Metrics**: officiële Community API `https://community-api.coinmetrics.io/v4` zonder API-key; 10 verzoeken per 6 seconden per IP. Officiële documentatie beschrijft dagelijkse `ReferenceRateUSD` en `ReferenceRateEUR` via `timeseries/asset-metrics`. De community-reference-rates hebben beperkingen op fijnmazige historie (laatste zeven datapunten); exacte dagelijkse volledige historische dekking moet met een echte API-proef worden bevestigd. Bron: https://gitbook-docs.coinmetrics.io/packages/coin-metrics-community-data en https://gitbook-docs.coinmetrics.io/tutorials-and-examples/tutorials/walkthrough_community
- **Checkonchain**: de officiële site verwijst naar `charts.checkonchain.com`. Een publieke GitHub-repository `checkmatey/checkonchain.com` bevat chart-assets en heeft een MIT-code-licentie, maar **MIT op broncode bewijst geen toestemming voor herpublicatie van onderliggende datasets**. Externe Python-projecten `ocfinance` en `chaindl` beschrijven extractie van chartdata; dat bewijst technische mogelijkheid, niet toegestane herdistributie. Bronnen: https://www.checkonchain.com/ ; https://github.com/checkmatey/checkonchain.com ; https://pypi.org/project/ocfinance/ ; https://chaindl.readthedocs.io/en/latest/
- **BlockHorizon**: officiële chartsite https://charts.blockhorizon.io/ is bereikbaar en heet 'Bitcoin Analytics Platform', maar de publiek uitleesbare pagina documenteert geen verifieerbare export/API of redistributielicentie. Status: nog niet gevalideerd.
- **Voorlopige voorkeursroute**: onderzoek Coin Metrics eerst voor reproduceerbare dagelijkse referentieprijzen; vergelijk steekproefsgewijs met Checkonchain/BlockHorizon. Geen chart-scraping als productiebron zonder toestemming.
- **Acceptatietest**: controleer eerste en laatste datum, dagfrequentie, gaten, prijsdefinitie (UTC-slot vs daggemiddelde), USD/EUR dekking, API-toegang zonder sleutel, rate limiting en schriftelijk toegestane openbare distributie van afgeleide maandwaarden.

## Governance-actualisatie en onderzoeksscope (2026-10-19)

Dit document is een **niet-normatieve bronneninventarisatie**. De oorspronkelijke tabel en bronclaims hierboven zijn onderzoeksnotities en niet automatisch opnieuw gevalideerd.

- `DECIDED / ACCEPTED` — ADR-004: bestaande maandelijkse goudmethodologie gebruikt World Bank GOLD USD/oz maandgemiddelde ÷ ECB USD/EUR maandgemiddelde, indexbasis 2000-01; geen imputatie. Dit document wijzigt die methode niet.
- `DECIDED` — ADR-011: de oudste voldoende betrouwbare, vergelijkbare **landelijke gemiddelde Nederlandse woningverkoopprijs** bepaalt de historische start; circa 1900 blijft een onderzoeksambitie, geen goedgekeurde historische reeks. Jaar- en maandreeksen blijven onderscheidbaar.
- `PROPOSED` — prioriteit 1: NVM/Vastgoedmarkt historische **jaarlijkse gemiddelde verkoopprijzen circa 1975–1994**; controleer landelijke dekking, transactiepopulatie, definities, jaar-/ultimo-karakter, licentie en overlap met CBS/Kadaster. De eerdere claim 'vanaf januari 1995 biedt CBS landelijke maandelijkse HPI en gemiddelde verkoopprijzen' blijft een bronclaim die per tabel en veld moet worden gecontroleerd; niet gelijkstellen aan de momenteel gevalideerde publicatiereeks vanaf 2000.
- `PROPOSED` — prioriteit 2: oudere landelijke woningverkoopprijzen vóór circa 1975. JST/Herengracht-indexen zijn niet zonder anker of representativiteitstoets uitwisselbaar met gemiddelde verkoopprijzen.
- `PROPOSED / UNVERIFIED` — World Bank Pink Sheet GOLD kan volgens bronbeschrijvingen maandhistorie vanaf circa 1960 bevatten; de vroege officiële GOLD-kolom, methodologische breuken en gebruiksrechten zijn nog niet end-to-end gecontroleerd. Historische vaste goudprijsregimes en overgang naar vrije prijsvorming annoteren.
- `DECIDED` — voor BTC-bronprioriteit is de bestaande `script-trading-anlytics/data/history.csv` BTC-USD dagreeks vanaf 2014-09-17 de primaire historische **kandidaat**; Coin Metrics, CoinGecko, Checkonchain en BlockHorizon blijven onafhankelijke onderzoeks-/vergelijkingsbronnen. Geen BTC-methodologie of productiebron goedgekeurd.
- `BLOCKED` — publieke goudpublicatie blijft HOLD; geen historische datasetimport, publieke goud/BTC-activatie of bronwissel op basis van deze onderzoeksnotitie.

Voor besluitstatus en bronverificatie prevaleren `DECISIONS.md`, `METHODOLOGY.md` en `DATA_SOURCES.md`; dit rapport introduceert geen tweede normatieve methodologie.
