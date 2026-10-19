# DECISIONS — expliciete besluiten en voorstellen

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Beslisregels
Een besluit krijgt `ID`, `status`, `datum`, `vraag`, `opties`, `keuze`, `argument`, `gevolg`, `eigenaar`, `bewijs`. `DECIDED` uitsluitend bij expliciete keuze door projecteigenaar of aantoonbaar besluit. Technische aanwezigheid in de repo is **geen** besluit. Nieuwe besluiten vervangen oude met `SUPERSEDED`, niet verwijderen.

| ID | Status | Onderwerp | Keuze / open vraag |
|---|---|---|---|
| ADR-001 | `DECIDED` (eerder projectgesprek) | Runtime | GitHub Actions + statische JSON + Cloudflare Pages; geen D1 als productiedatabase |
| ADR-002 | `DECIDED` (eerder projectgesprek) | Rekeneenheden | Nominale EUR, reële EUR, gram goud, BTC/sats als vergelijkingsdimensies; reële EUR vereist CPI |
| ADR-003 | `PROPOSED` | Woningmaat | Gemiddelde CBS-transactieprijs voor absolute ratio; HPI uitsluitend voor prijsontwikkeling |
| ADR-004 | `PROPOSED` (BTC); `ACCEPTED` (goud, 2026-10-18) | Maandelijkse goudwaardering | World Bank maandgemiddelde USD/oz ÷ maandgemiddelde ECB USD/EUR; vaste basis 2000-01; geen imputatie. Uitsluitend goud; geen BTC-besluit of publicatieautorisatie |
| ADR-005 | `PROPOSED` | Revisies | Laatst herziene CBS/CPI-data, met raw snapshots per release |
| ADR-006 | `PROPOSED` | Publicatie | Immutable releases + atomische current-pointer |
| ADR-007 | `PROPOSED` | BTC-bron | Coin Metrics testen; CoinGecko vergelijken; alleen na licentie- en kwaliteitsgoedkeuring |
| ADR-008 | `PROPOSED` | Ontbrekende maanden | Geen imputatie; null plus reden en coverage-status |
| ADR-009 | `PROPOSED` | CPI | Exacte CBS CPI-serie en basisjaar later expliciet kiezen |

## Open beslisvragen
1. Is 'gemiddeld verkochte bestaande koopwoning' de gewenste primaire indicator, of willen we een gemodelleerde constante woningkwaliteit als tweede indicator?
2. Welke hergebruikrechten gelden voor de World Bank GOLD-benchmark en publieke afgeleide goudindicatoren? De goudmethodologie is besloten; publicatierechten niet.
3. Welke BTC-referentieprijs en bronlicentie voldoen voor publieke herdistributie?
4. Wat is de gekozen CPI-serie en referentiemaand?
5. Welke minimale brondekking en welke afwijking ten opzichte van onafhankelijke ankerpunten accepteren we?
6. Wie mag productiepublicatie en bronwissels goedkeuren?

## Sjabloon
```text
ID:
Status: PROPOSED | DECIDED | SUPERSEDED
Datum:
Beslisser:
Probleem:
Alternatieven:
Besluit:
Argumentatie:
Impact op methodologie/code/schema:
Bewijslink (PR/issue/gespreksbesluit):
Vervangt:
```

## ADR-010 — bestaande tradinghistorie als BTC-bronkandidaat (2026-10-17)
- **Status:** `DECIDED` voor onderzoeksprioriteit; **niet** voor productiepublicatie. **Beslisser:** projecteigenaar, akkoord in gesprek.
- **Keuze:** gebruik `script-trading-anlytics/data/history.csv` (`BTC`, `1d`, `BTC-USD`) als primaire historische **kandidaat** vanaf 2014-09-17; hergebruik bestaande auditworkflow. Coin Metrics/CoinGecko blijven mogelijke referentie-/aanvulbronnen.
- **Argument:** auditrun 39050246824 bevestigt 4.409 opeenvolgende BTC-dagkoersen zonder validatiefouten. Voor 2010–2014-09-16 ontbreekt in deze dataset BTC-historie.
- **Impact:** ADR-007 (Coin Metrics als primaire testkandidaat) is **SUPERSEDED voor bronprioriteit**, maar niet voor onafhankelijke broncontrole. ADR-004 blijft voor BTC-maandmethodologie `PROPOSED`; de goudspecifieke methode is op 2026-10-18 afzonderlijk `ACCEPTED`.
- **Open:** FX-weekenden en feestdagen, USD/EUR-dagmatching, bronlicenties, bronvergelijking en publicatiebesluit. Geen forward fill of bronsplicing zonder apart besluit.
- **Bewijs:** [run](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824), [PR #35](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/35), [PR #36](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/36).
## Governance-integratie (2026-10-17)
De opname van dit register in GitHub op 2026-10-17 was **geen nieuw economisch besluit**. Op die datum bleef ADR-004 `PROPOSED`. **Latere statuswijziging 2026-10-18:** uitsluitend de goudmethodologie is `ACCEPTED`; BTC-FX-weekend/feestdagbeleid blijft `PROPOSED`/onbeslist. De historische scenarioanalyse van PR #40 gaf geen productieautorisatie. Zie [CONFLICT_MATRIX.md](CONFLICT_MATRIX.md).

## ADR-004 — maandelijkse goudwaardering (ACCEPTED, 2026-10-18)

- **ID:** ADR-004. **Status:** `DECIDED / ACCEPTED` uitsluitend voor de goudreeks. **Datum:** 2026-10-18. **Beslisser:** projecteigenaar, expliciete goedkeuring in gesprek. **Vervangt:** eerdere `PROPOSED` goudinterpretatie van ADR-004; BTC-maandmethodologie blijft afzonderlijk onbeslist.
- **Vraag:** welke reproduceerbare maandelijkse goudprijs in EUR en gram goud per gemiddeld verkochte Nederlandse woning gebruikt het dashboard?
- **Alternatieven:** gemiddelde van dagelijkse naar EUR omgerekende goudprijzen; gekozen: verhouding van onafhankelijke maandgemiddelden. Deze methoden zijn niet mathematisch identiek.
- **Besluit:** World Bank Pink Sheet `GOLD` is de maandgemiddelde goudprijs in **USD per troy ounce**. Tot en met **mei 2025** gebaseerd op London afternoon fixing (99,5% goud); **vanaf juni 2025** gemiddelde dagelijkse spotprijzen. De benchmarkdefinitiewijziging moet zichtbaar worden geannoteerd in iedere publieke goudvisualisatie.
- **ECB:** dagelijkse ECB `EXR.D.USD.EUR.SP00.A`, **USD per EUR**. Per kalendermaand het rekenkundig gemiddelde van uitsluitend aanwezige, geldige koersdagen; geen kalenderdagendeler, forward-fill, interpolatie of synthetische waarnemingen.
- **Formules voor maand m:** `monthly_usd_per_eur[m] = mean(valid ECB USD/EUR observations in m)`; `gold_eur_oz[m] = gold_usd_oz[m] / monthly_usd_per_eur[m]`; `gold_eur_gram[m] = gold_eur_oz[m] / 31.1034768`; `gold_grams_per_house[m] = house_price_eur[m] / gold_eur_gram[m]`; `gold_index[m] = 100 * gold_eur_oz[m] / gold_eur_oz["2000-01"]`.
- **Indexbasis:** januari 2000 = 100, onveranderlijk; ontbrekende basis blokkeert berekening/publicatie.
- **Maandkoppeling:** exacte `YYYY-MM` tussen World Bank, ECB en CBS. Alleen volledige historische maanden met geldige observaties in alle drie bronnen. Ontbrekende historische maanden zijn een validatiefout; recente `pending_publication`-maanden zijn bronpublicatieachterstand, geen historisch datagat. Geen stilzwijgend wegvallen van maanden.
- **Semantiek:** `mean(gold_usd_oz) / mean(usd_per_eur)` is **niet** gelijk aan `mean(daily_gold_usd_oz / daily_usd_per_eur)`. De methode is geschikt voor de gekozen maandindicator, niet een reconstructie van dagelijkse EUR-fixings.
- **CBS:** gemiddelde transactieprijs van verkochte bestaande koopwoningen in EUR; gevoelig voor transactiemix, geen constante woningkwaliteit.
- **Technische status:** geïmplementeerd op `main` via [PR #51](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/51), squashcommit `a41539664dd0240b5fd32d8d7d302f1b7342294c`. Post-merge [CI 39160997684](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39160997684) (`python` en `frontend` SUCCESS; 170 tests PASS, 3 SKIPPED) en [statische data 39160997745](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39160997745) SUCCESS. Private backfill: 320 complete maanden 2000-01 t/m 2026-08. Deze tests zijn technische validatie, geen juridische vrijgave.
- **Afzonderlijke besluitpoorten:** (1) economische goudmethodologie **ACCEPTED**; (2) technische implementatie **MERGED / VALIDATED**; (3) rechten voor World Bank GOLD en afgeleide publieke indicatoren **OPEN / NOT CLEARED**; (4) publieke goudpublicatie **NOT AUTHORIZED / DISABLED**. De drie publieke goudvelden blijven `null`. Geen ruwe GOLD-data herdistribueren. Geen wijziging van backend-activatieconfiguratie of publicatie zonder nieuw expliciet besluit.
- **Bronnen:** [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets), [historische maandworkbook](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx), [ECB Data Portal](https://data.ecb.europa.eu/), CBS woningprijzen via bestaande `etl/sources/cbs.py`.

## Onderzoeksbesluit — alternatieve goudbron (2026-10-19)
- **ID:** GOLD-SOURCE-REASSESSMENT-2026-10-19. **Status:** `DECIDED` voor onderzoeksrichting, **niet** voor providerselectie of publicatie. **Beslisser:** projecteigenaar, akkoord in gesprek.
- **Probleem:** de technisch gevalideerde World Bank GOLD-reeks heeft een onopgeloste derdepartij-/benchmarkrechtenvraag voor publieke afgeleide grafieken en JSON. De rechtenbeoordeling in [PR #53](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/53) is als HOLD gedocumenteerd; dit maakt de huidige bron geen automatisch ongeschikte of verboden dataset.
- **Alternatieven:** wachten op specifieke toestemming voor huidige bron, of een beperkte vergelijking van historisch volledige en aantoonbaar herbruikbare alternatieve goudprijsbronnen uitvoeren.
- **Besluit:** prioriteer een praktische, read-only bronvergelijking met data-/rechtenvalidatie; behandel DataHub, World Gold Council, Standard Bullion en een onafhankelijke spot-/institutionele bron uitsluitend als kandidaten. Geen bronselectie vooraf.
- **Argumentatie:** focus op het dashboarddoel, reproduceerbaarheid, voldoende betrouwbare maandgemiddelden vanaf 2000-01, publieke grafieken en JSON; vermijd een disproportioneel open-einde toestemmingsproces. Een aggregatorlicentie heft mogelijke oorspronkelijke rechten niet vanzelf op.
- **Impact:** goudspecifieke ADR-004 blijft `ACCEPTED` voor de huidige World Bank/ECB-definitie; BTC-maandmethodologie blijft `PROPOSED`. Een andere bron/prijsdefinitie kan een beperkte ADR-amendering vereisen. Geen productiecode-, JSON-, flag- of publicatieaanpassing; het bestaande HOLD-besluit blijft gelden totdat het uitdrukkelijk wordt herzien.
- **Bewijs:** [PR #51](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/51), [PR #52](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/52), [PR #53](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/53) en projecteigenaarbesluit van 2026-10-19.
- **Vervangt:** geen bestaande ADR; verandert alleen de onderzoeksprioriteit.

## ADR-011 — historische reikwijdte volgt betrouwbare woningdata (2026-10-19)
- **Status:** `DECIDED` voor projectvisie en onderzoeksprioriteit; **niet** voor productie-implementatie of publicatie. **Beslisser:** projecteigenaar, expliciet akkoord in gesprek.
- **Vraag:** is januari 2000 de projectstartdatum of slechts een bestaande technische grens?
- **Besluit:** de historische vergelijking begint waar de oudste voldoende betrouwbare en vergelijkbare **landelijke gemiddelde Nederlandse woningverkoopprijzen** beschikbaar zijn; streef naar circa 1900 als onderzoekshorizon. Ondersteun in de doelarchitectuur verschillende jaar- en maandfrequenties en data-gedreven bronvensters. Januari 2000 blijft voorlopig de huidige technische grens en ADR-004-indexbasis, **niet** de historische projectambitie.
- **Onderzoeksprioriteit:** toets NVM/Vastgoedmarkt circa 1975–1994 op landelijke dekking, definitie en CBS-overlap; zoek oudere landelijke gemiddelden. World Bank GOLD vanaf 1960 is kandidaat voor oudere goudhistorie; oude goudprijsregimes zichtbaar annoteren.
- **Impact:** documentatiecorrectie; geen wijziging aan ADR-004, bronadapter, publicatiegate of JSON. Bestaande goud-HOLD blijft van kracht.
- **Bewijs:** projecteigenaarbesluit 2026-10-19; codegrenzen `etl/sources/worldbank_gold.py` en `etl/static_export.py`; historische bronreeksen vereisen afzonderlijke validatie.
