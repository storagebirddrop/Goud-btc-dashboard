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
2. Welke hergebruikrechten gelden voor de World Bank GOLD-benchmark en publieke afgeleide goudindicatoren? De goudmethodologie is besloten; publicatierechten niet. **Update 2026-10-20 (GOLD-03):** voor de twee afgeleide indicatoren `gold_index` en `gold_grams_per_house` heeft de projecteigenaar het restrisico expliciet geaccepteerd en is schriftelijke World Bank-toestemming geen projectgate meer; de juridische vraag zelf blijft open en geregistreerd.
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

## GOLD-01 — eigenaarbesluit beperkte goudpublicatie (2026-10-19)

- **Status:** DECIDED door projecteigenaar op 2026-10-19; **technische release:** PR-only / niet gemerged / niet live.
- **Besluit:** de eerdere goudpublicatie-HOLD wordt **uitsluitend voor** de afgeleide indicatoren `gold_index` en `gold_grams_per_house` opgeheven, voor maanden vanaf 2000-01 en alleen na gecontroleerde implementatie en afzonderlijke merge-/deploytoestemming.
- **Uitdrukkelijk uitgesloten:** `gold_eur_oz`, ruwe GOLD USD/oz-prijzen, bronworkbooks, bron-CSV's en goudwaarden vóór 2000; deze blijven niet publiek respectievelijk `null`.
- **Rechten:** het eerdere World Bank/derdepartij-/IBA-onderzoek blijft ongewijzigd als **historische risicoanalyse**. Dit eigenaarbesluit is een bewuste, beperkte publicatierisicoacceptatie, **geen juridisch bewijs** van onbeperkte rechten, sublicenties of benchmarkhergebruik.
- **Methodologie:** ADR-004 blijft ongewijzigd en leidend. Zichtbare bronvermelding World Bank Pink Sheet GOLD, ECB EXR.D.USD.EUR.SP00.A en CBS StatLine 85773NED; vermelding eigen transformaties en definitiebreuk per juni 2025.
- **Publicatiepoort:** geen merge, deploy of live datasetwijziging zonder afzonderlijke expliciete toestemming. Fail-closed controles en de bestaande CBS-publicatie blijven leidend.

## GOLD-03 — eigenaarbesluit opheffing goudpublicatie-HOLD voor twee afgeleide indicatoren (2026-10-20)

- **Status:** `DECIDED` door projecteigenaar op 2026-10-20 (expliciet besluit in projectgesprek). **Technische release:** niet gemerged, niet live; zie Publicatiepoort.
- **Besluit:** de goudpublicatie-HOLD wordt opgeheven voor **uitsluitend** de afgeleide indicatoren `gold_index` (goudprijsindex in EUR, januari 2000 = 100) en `gold_grams_per_house` (gram goud per gemiddelde Nederlandse woning), voor maanden vanaf 2000-01. Een voorafgaande schriftelijke toestemming van de World Bank is **niet langer een verplichte projectgate**.
- **Uitdrukkelijk uitgesloten (ongewijzigd):** `gold_eur_oz` blijft `null`; geen ruwe USD-goudprijzen, geen bronworkbooks of bron-CSV's, geen goudwaarden vóór 2000; Bitcoin en satoshi's blijven `withheld` (ADR-004 voor BTC, ADR-007 en ADR-008 blijven `PROPOSED`).
- **Vervangt (`SUPERSEDED`, alleen voor deze twee indicatoren):** de HOLD-adviezen en de voorwaarde 'HOLD totdat schriftelijke rechtenbevestiging beschikbaar is' in [GOLD_PUBLICATION_DECISION.md](GOLD_PUBLICATION_DECISION.md) (advies 2026-10-18), en de HOLD-formuleringen in [PROJECT_STATUS.md](PROJECT_STATUS.md) en [DATA_SOURCES.md](DATA_SOURCES.md). Die analyses blijven als historische risicodocumentatie bewaard; de eigenaarbesluiten GOLD-01 (2026-10-19) en GOLD-03 gaan voor.
- **Geregistreerd restrisico (niet verzwegen, geen bewezen licentievrijheid):** (1) de World Bank Dataset Terms kennen een uitzondering voor derdepartijdata en de GOLD-reeks draagt geen eigen licentielabel; het werkboek noemt meerdere commerciële bronnen (onder meer Bloomberg, Kitco, Thomson Reuters Datastream) en geen IBA; (2) ICE Benchmark Administration en LBMA hanteren licenties voor gebruik, herdistributie en afgeleide benchmarks; of dit dashboardgebruik daaronder valt is niet beoordeeld en niet beantwoord; (3) `gold_eur_oz` is uit publieke velden exact terug te rekenen (`house_eur` x 31,1034768 / `gold_grams_per_house`), getest; (4) de ECB-voorwaarde 'statistieken niet gewijzigd' vergt expliciete vermelding van eigen bewerkingen; (5) er is geen juridisch advies ingewonnen. Zie `docs/research/GOLD_01_RIGHTS.md` en `docs/research/GOLD_01_PUBLICATION_READINESS.md`.
- **Methodologie:** ADR-004 blijft de goedgekeurde methodologie en blijft ongewijzigd.
- **Transparantie:** het dashboard toont bij de goudgrafieken: World Bank Commodity Markets (Pink Sheet) GOLD met link, ECB-reeks EXR.D.USD.EUR.SP00.A met link, CBS StatLine 85773NED met link, de vermelding dat omrekening, indexering en gram-per-woning eigen berekeningen zijn, de gebruikte gegevensperiode en peildatum van de bronstand, een methodologische toelichting en de definitiewijziging van de World Bank-goudreeks per juni 2025 (zichtbaar geannoteerd). Er worden geen claims gedaan over licentiestatus, goedkeuring of ondersteuning door bronorganisaties.
- **Publicatiepoort:** dit besluit autoriseert uitsluitend de technische voorbereiding (implementatie in een Draft PR). Merge, deployment en daadwerkelijke publieke release vereisen een afzonderlijke expliciete toestemming van de projecteigenaar voor de exacte kandidaat (hash). Fail-closed controles, gepinde hashes en de bestaande CBS-publicatie blijven leidend.
- **Impact:** documentatie in deze PR; de implementatie raakt `monthly.json`, gepinde hashes, CI en frontend en is ROOD/ORANJE volgens [CHANGE_CONTROL.md](CHANGE_CONTROL.md). Geen wijziging van ADR-004.
- **Bewijs:** projecteigenaarbesluit 2026-10-20; onderzoek HIST-03 t/m HIST-05 en GOLD-01 (`docs/research/`); GOLD-01-terms-probe en review-runs 39486174734 (kandidaat 320 maanden) en 39486179684 (byte-identieke replay).


## BTC-01 — voorstel BTC-maandmethodologie (PROPOSED, 2026-10-21)

- **Status:** `PROPOSED`. Geen besluit, geen publicatieautorisatie. ADR-004 (BTC-deel), ADR-007 en ADR-008 blijven `PROPOSED`; Bitcoin en satoshi's blijven `withheld`.
- **Voorstel:** maandwaarde = rekenkundig gemiddelde van alle dagwaarden in de kalendermaand (zelfde familie als de gouddefinitie en passend bij het maandgemiddelde van CBS). Voor USD-bronnen: maandgemiddelde BTC/USD gedeeld door maandgemiddelde ECB USD/EUR (geen FX-carry-forward); een gevalideerde EUR-native bron heeft voorkeur.
- **Bronnen:** tradinghistorie (Yahoo BTC-USD, ADR-010) als onderzoekskandidaat; Coin Metrics `ReferenceRateEUR` als onafhankelijke controle en mogelijke EUR-native bron; CoinGecko Demo alleen als recente controle (365 dagen).
- **Start en formules:** voorgestelde startmaand 2014-10 (eerste volledige maand; eerdere maanden `null`, geen splice zonder besluit). `btc_per_house = house_eur / btc_eur`, `sat_per_house = btc_per_house * 100000000`; Decimal-rekenwerk, afronden alleen bij weergave.
- **Restrisico/open:** `btc_eur = house_eur * 1e8 / sat_per_house` is exact reconstrueerbaar (publicatie van sats is gelijk aan publicatie van de koers); bronrechten (Yahoo, Coin Metrics niet-commercieel) zijn open; externe feiten zijn nog niet uit primaire bronteksten bevestigd. Open besluiten: bronrechten, USD-methode (ratio van gemiddelden, dagomrekening of EUR-native), startmaand/splice, te publiceren velden, tolerantie na meting.
- **Impact:** uitsluitend onderzoek; geen wijziging van code, JSON, vlaggen of publicatiepoorten. Uitwerking en BTC-02-voorstel: `docs/research/BTC_01_METHODOLOGY.md`.
