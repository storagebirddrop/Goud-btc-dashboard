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
