# ARCHITECTURE — bestaande inrichting en doelarchitectuur

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## 1. Architectuurbesluit (`DECIDED`)
Voorkeursroute: GitHub Actions → gecontroleerde CSV/ETL → statische JSON → React/Vite → Cloudflare Pages. **Geen D1 voor de primaire runtime.** De repository bevat legacy D1-code; aanwezigheid daarvan is geen besluit om D1 in productie te gebruiken.

## 2. Wat in GitHub daadwerkelijk zichtbaar is (`VERIFIED_REPO`)
- `frontend/` React/Vite; `frontend/public/data/monthly.json` is aanwezig met CBS-velden en `gold_*: null` in gecontroleerde beginrecords.
- `etl/sources/cbs.py`: CBS OData v4 adapter voor `85773NED`; filtert maandcodes `20xxMMxx`, haalt gepagineerd op en controleert duplicates/positieve waarden.
- `data/cbs-housing.csv`: maandelijkse `nl_house_avg_eur` en `nl_hpi` records aanwezig.
- `etl/static_export.py` en `etl/data_quality.py`: statische export en kwaliteitscontrole in repository.
- `.github/workflows/ci.yml`: pytest, controle committed CSV/JSON en Vite build; configuratie aangetoond, **geen succesvolle run bewezen**.
- `.github/workflows/update-static-data.yml`: triggers push, maandagcron en handmatig; exacte end-to-end effectiviteit niet getest.
- `.github/workflows/bitcoin-backfill.yml`: handmatige validatie, `contents: read`, artifact `backfill-report.json`; **geen** publieke BTC-export.
- `etl/sources/coinmetrics.py`: Coin Metrics read-only API adapter met EUR/USD referentiemetrics.

## 3. Huidige versus gewenste stroom
```text
BESTAAND (code aantoonbaar):
CBS 85773NED -> cbs-housing.csv -> static_export -> monthly.json -> React/Vite
             -> CI / update-workflow (gedefinieerd, runtime niet geaudit)
Coin Metrics -> handmatige validatie -> rapport-artifact (geen publicatie)

DOEL (`PROPOSED`):
goedgekeurde bronnen -> immutable raw snapshots -> normalisatie -> QA
 -> versiegebonden manifest + dataset -> atomische release -> Pages frontend
```

## 4. Publicatiegarantie (`PROPOSED`, nog NIET bewezen)
- Bouw in staging alle reeksen en manifest; valideer schema, source hashes, volledigheid, licentie en onderlinge consistentie.
- Genereer unieke `release_id` op basis van build/commit en inhoudshashes.
- Publiceer **één onveranderlijke release-directory** `data/releases/<release_id>/` met manifest en data.
- Pas na geslaagde verificatie update een kleine `data/current.json` pointer in dezelfde deployment; frontend leest eerst pointer en vervolgens uitsluitend bestanden van die release.
- Bewaar vorige pointer en rollbackprocedure. Geen deels geüpdatete afzonderlijke datasets tonen.
- **Let op:** Git/Cloudflare deploy-atomiciteit en cachegedrag moeten integraal getest worden; bovenstaande is een ontwerpeis, geen bestaande garantie.

## 5. Security en betrouwbaarheid
- Beperk workflow-permissies; geen secrets in JSON, logs of artifacts.
- API requests met timeouts, retries/backoff, paginatiebegrenzing, responsevalidatie en bron-whitelisting.
- Scheid unit-tests, live smoke-tests en release-tests. Een groene CI zegt niets over bronnauwkeurigheid zonder onafhankelijke checks.
- Publicatie alleen met vooraf goedgekeurde bronlicenties en gecontroleerde attributie.

## 6. Legacy en documentatieconflicten
`README.md` en `docs/static-pipeline.md` noemen statisch Pages zonder D1; `docs/next-phase.md` noemt nog staging-D1. Dit is verouderde/alternatieve informatie. **Vereiste repository-opruiming:** legacy documenten markeren of actualiseren; code niet verwijderen zonder afzonderlijk besluit.

## 7. Ontbrekende bewijzen
Exacte workflow-run-ID's, commit-SHA op moment van succes, volledige public JSON audit, Cloudflare deploy-status, end-to-end release-integriteit en rollbacktest ontbreken. Zie `VERIFICATION_LOG.md`.

## Update v2.1 — kandidaat-BTC-ingestie en Actions
`script-trading-anlytics/data/history.csv` → **read-only** `.github/workflows/trading-btc-audit.yml` → `etl/trading_history_audit.py` → uitsluitend statistisch artifact `trading-btc-audit-report.json`. Deze keten is werkelijk uitgevoerd: [run 39050246824](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824), `success`.

**Geen** automatische BTC-prijsimport naar publieke JSON, geen BTC/EUR-conversieproductie, geen BTC-release. PR #36 verwijderde de verouderde `.github/workflows/btc-catalog-probe.yml`; `etl/coinmetrics_catalog.py` en tests blijven als onderzoekscode. De overige CBS/CI-workflows zijn niet gewijzigd. Voor een toekomstige import: immutable bron-snapshot/hash, datum- en FX-match, QA, licentiepoort en atomische release, pas na goedkeuring.

## Doelarchitectuur historische dekking v2.4 (`DECIDED` ontwerpprincipe; implementatie `PROPOSED`)
Maak de dekking per bron en indicator data-gedreven, zonder universeel hardcoded beginjaar. Ondersteun gescheiden jaar- en maandfrequenties, met expliciete aggregatie, provenance, dekking en ontbrekende waarden. Behoud een aparte langetermijnlaag voor historische woning-/gouddata en de bestaande maandelijkse productielaag zolang bronvergelijkbaarheid niet is aangetoond. De huidige World Bank-adapter en statische export begrenzen de reeks tot 2000-01; dat is technische schuld, geen productvereiste. ADR-004, de bestaande 2000-01 indexbasis en de goudpublicatiegate blijven ongewijzigd.
