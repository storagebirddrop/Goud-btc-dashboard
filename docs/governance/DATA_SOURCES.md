# DATA_SOURCES — bronregister en acceptatie

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Register
| Reeks | Identificatie / bron | Repo-bewijs | Status voor publieke berekening |
|---|---|---|---|
| `nl_house_avg_eur` | CBS `85773NED`, gemiddelde verkoopprijs bestaande koopwoningen | `etl/sources/cbs.py`, `docs/cbs-ingestion.md`, `data/cbs-housing.csv` | `VERIFIED_REPO` implementatie; live bronvelden, licentie en volledige data-audit nog nodig |
| `nl_hpi` | CBS `85773NED`, prijsindex bestaande koopwoningen, bron vermeldt 2020=100 | dezelfde bestanden | `VERIFIED_REPO` implementatie; geen EUR-bedrag |
| `gold_eur_oz` | **geen goedgekeurde prijsprovider** | `docs/data-sources.md` en JSON-velden `null` | `BLOCKED` |
| `btc_eur` | Coin Metrics Community `ReferenceRateEUR`, kandidaat; CoinGecko als alternatief | `etl/sources/coinmetrics.py`, `docs/coinmetrics-adapter.md` | `BLOCKED` voor productie; alleen read-only adapter en validatie-workflow aangetoond |
| `usd_per_eur` | ECB `EXR.D.USD.EUR.SP00.A` | `docs/data-sources.md`, `etl/sources/ecb.py` (gevonden in repo) | `UNVERIFIED` live dekking, implementatie en voorwaarden |
| `cpi_nl` | CBS CPI exacte tabel en definitie **nog te kiezen** | geen geverifieerde productie-ingestie | `PROPOSED` |

## Bronlinks (verwijzingen zijn geen live API-audit)
- [CBS StatLine 85773NED](https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table) · [CBS OData adapterbasis](https://datasets.cbs.nl/odata/v1/CBS/85773NED)
- [CBS metadata / hergebruik](https://data.overheid.nl/dataset/45084-bestaande-koopwoningen--verkoopprijzen-prijsindex-2020-100) — repo documenteert CC BY 4.0; actuele voorwaarden onafhankelijk toetsen.
- [ECB USD per EUR](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A).
- [Coin Metrics API](https://docs.coinmetrics.io/api/v4) en [CoinGecko API](https://www.coingecko.com/en/api) — alternatieven; historisch bereik, endpointlimieten en redistributie nog onbekend.

## Verplichte registratie per bron
`source_id`, `publisher`, `dataset_id`, `metric_id`, `endpoint`, `retrieved_at_utc`, `observation_period`, `quote_timezone`, `calendar`, `unit`, `currency`, `license_url`, `redistribution_allowed` (expliciet), `revision_policy`, `raw_sha256`, `transformation_version`, `coverage_expected`, `coverage_observed`, `independent_checks`, `approved_by`, `approval_date`.

## Toelatingsproces (`PROPOSED`)
1. Metadata en licentie controleren; vastleggen of we ruwe/afgeleide reeksen mogen publiceren.
2. Test met klein, representatief live datavenster (oud, midden, recent), inclusief paginering en foutresponsen.
3. Vergelijk minimaal drie ankerpunten met officiële publicatie of onafhankelijke provider.
4. Bereken kalenderdekking, afwijkingen, duplicates, revisies en bronbreuken.
5. Bewaar ruwe bronhash en auditrapport; keur bron formeel goed in `DECISIONS.md`.
6. Pas daarna statische publicatie activeren.

## BTC-backfill: zorgvuldig onderscheid
In GitHub is de Coin Metrics adapter en handmatige `.github/workflows/bitcoin-backfill.yml` aanwezig (`VERIFIED_REPO`). De workflow schrijft volgens configuratie een **validatierapport als artifact**, geen koersdata naar public JSON. Eerdere gesprekken meldden geen bruikbare observaties; zonder run-ID, logs en payload is de **specifieke faaloorzaak `UNVERIFIED`**. Niet aannemen dat een 2011-test een actuele dekkingstest vervangt.

## Gegevenshistorie
De repo bevat `data/cbs-housing.csv` en `frontend/public/data/monthly.json`. Hun aanwezigheid is geverifieerd, niet elke observatie of publicatiestatus. De adapter beperkt periodecodes momenteel tot jaren 2000–2099; de bron kan oudere data hebben. De claim '320 complete maanden' moet met een echte telling en bronvergelijking worden bewezen.

## Update v2.1 — BTC-bronregister
- **Primaire kandidaat, niet gepubliceerd:** `storagebirddrop/script-trading-anlytics`, `data/history.csv`, `Asset=BTC`, `Timeframe=1d`, Yahoo Finance `BTC-USD` via `yfinance`, USD/BTC dagelijkse **slotkoers**, 4.409 dagen van 2014-09-17 t/m 2026-10-12; audit [39050246824](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824).
- **FX-kandidaat:** dezelfde dataset, `Asset=EURUSD`, `Timeframe=1d`, Yahoo `EURUSD=X`, notatie **USD per EUR**. 4.368 geldige dagen sinds 2010-01-01; 1.267 BTC-dagen zonder gelijktijdige FX. ECB blijft te onderzoeken als beter gedocumenteerde alternatieve FX-bron.
- **Alternatieve onderzoeksbronnen:** Coin Metrics en CoinGecko blijven voor kruiscontrole en ontbrekende pre-2014-historie; Coin Metrics-catalogusworkflow verwijderd in PR #36, code behouden.
- **Publicatie `BLOCKED`:** Yahoo Finance/yfinance hergebruik-/redistributierechten niet geverifieerd; onafhankelijke ankercontrole, FX-weekendbeleid, datum/tijdsemantiek en licentie moeten vooraf expliciet worden goedgekeurd.

## Update 2026-10-19 — alternatieve historische goudbronnen (onderzoeksfase)
- **Huidige geïmplementeerde bron:** World Bank Pink Sheet maandelijkse `GOLD` USD/troy ounce; ECB `EXR.D.USD.EUR.SP00.A` voor maandelijkse USD-per-EUR-conversie en CBS `85773NED` voor woningprijzen. De goudspecifieke ADR-004 is ACCEPTED; de pipeline is via PR #51 gemerged. **Publicatie blijft HOLD** conform [GOLD_PUBLICATION_DECISION.md](GOLD_PUBLICATION_DECISION.md).
- **Onderzoekskandidaten, niet goedgekeurd:** [DataHub gold-prices](https://datahub.io/core/gold-prices) (onderzoek de feitelijke herkomst van moderne maanden en of de vermelde PDDL daadwerkelijk de inputrechten dekt); [World Gold Council](https://www.gold.org/goldhub/data/gold-prices) (kwaliteit/prijsdefinitie, maar rechten apart beoordelen); [Standard Bullion](https://standardbullion.com/gold-price-api) (API, provenance en voorwaarden nog te toetsen); minstens één onafhankelijke spotprijs- of institutionele bron.
- **Selectiecriteria:** 2000-01 tot laatste complete maand; maandgemiddelde versus maandultimo expliciet; USD/oz of goed gedocumenteerde EUR-prijs; volledige dekking, stabiele herhaalbare toegang, onafhankelijke ankervergelijkingen; expliciete rechten voor publieke interactieve grafieken **én** maandelijkse JSON-distributie. Een vrij toegankelijke API of secundair openlicentielabel volstaat niet als bewijs.
- **Geen impliciete bronwissel:** bronselectie, mogelijke aanpassing van prijsdefinitie/ADR-004 en publieke activatie vereisen afzonderlijke expliciete besluiten. Tot die tijd blijven productie-export en publicatieflags ongewijzigd.
- Eerdere registerregels zijn historische snapshots; dit is de actuele goudstatus, geen retroactieve wijziging van BTC/CPI-bronstatus.

## Historische woning- en gouddekking — onderzoeksnotitie 2026-10-19
- **CBS/Kadaster**: bestaande maandelijkse gemiddelde verkoopprijzen vanaf 1995 volgens brononderzoek; controleer exacte tabel, velddefinitie en eventuele bronbreuken voordat oudere jaren worden opgenomen.
- **NVM via Vastgoedmarkt, Kerncijfers 1974–2024**: kandidaat met jaarlijkse historische gemiddelde verkoopprijzen vanaf circa 1975. `UNVERIFIED` voor een naadloze landelijke CBS-koppeling; controleer 'per ultimo', transactiepopulatie en overlapping 1995–2023.
- **World Bank Pink Sheet GOLD**: bronbeschrijvingen duiden op maandhistorie vanaf 1960; de bestaande adapter filtert vóór 2000. De volledige officiële Excel-kolom en notities vóór 2000 zijn nog niet rechtstreeks geverifieerd. Datasetlicentie CC BY 4.0 is aangetroffen; mogelijke specifieke derdepartijvoorwaarden blijven te controleren. Publicatie-HOLD blijft geldig.
- **Goudprijsregime**: vóór circa 1968 sterk officieel gestuurd; 1968–1973 overgang; vanaf circa 1973 vrijer marktgeprijsd. Interpreteer oude goudvergelijkingen met expliciete regimeannotaties.
- **ECB USD/EUR**: directe referentiereeks begint in 1999; voor eerdere jaren zijn expliciete historische valuta-/guldenmethoden nodig.
- **1900–1974**: geen gevalideerde landelijke reeks gemiddelde Nederlandse woningverkoopprijzen aangetoond; academische regionale indices zijn niet gelijkwaardig aan landelijke gemiddelde koopsommen.
Dit is brononderzoek, geen goedkeuring voor backfill, datasplicing of publieke export.
