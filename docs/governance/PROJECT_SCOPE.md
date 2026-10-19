# PROJECT_SCOPE — afbakening, fasering en acceptatie

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Bevestigde huidige repository-scope (`VERIFIED_REPO`)
De README noemt een **vroege ontwikkelfase**, initieel goud versus Nederlandse woningprijzen, maandbasis vanaf 2000; React/Vite frontend, Python ETL, statische JSON en Cloudflare Pages als voorkeursroute. De repository bevat al een CBS CSV/JSON-scaffold; dit is **niet** hetzelfde als een productieklare goud-/BTC-grafiek.

## MVP-fasen (`PROPOSED`; geen impliciete feature-goedkeuring)
| Fase | Oplevering | Vrijgavevoorwaarde |
|---|---|---|
| M0: betrouwbare woningbasis | CBS gemiddelde transactieprijs + apart CBS HPI, bron en waarschuwing over samenstelling | CBS bron/velden en maanddekking geverifieerd; frontend correct gelabeld |
| M1: goudvergelijking | gram goud per gemiddelde verkochte woning + nominale EUR | goudbron/licentie, FX, dagmatching, dekking en spot-checks akkoord |
| M2: bitcoinvergelijking | BTC en sats per gemiddelde verkochte woning | onafhankelijke BTC broncheck, volledige backfill of expliciete gaps, licentie |
| M3: CPI-context | reële EUR (gekozen basismaand/jaar) | CPI-reeks, formule en revisiebeleid akkoord |
| M4: verrijking | andere goederen/landen, scenario's | apart besluit |

**Belangrijk:** M0 kan bestaan zonder goud- of BTC-data. De volgorde is een voorstel, niet een claim dat alle onderdelen al beschikbaar zijn.

## Binnen scope
- Historische maandreeksen, bronmetadata, kwaliteitspoorten, backfills, statische versies en transparante visualisaties.
- Nominale EUR, HPI, gram goud, BTC/sats en later CPI-gecorrigeerde EUR; duidelijke onderscheidende labels.
- Reproduceerbare scripts en controleerbare releases.

## Buiten scope (huidige fase)
- Handelsadviezen, portefeuilleoptimalisatie, voorspellingen, real-time koersen, persoonlijke financiële gegevens, D1-productiedatabase.
- 'De gemiddelde woning' presenteren als identieke woning door de tijd; algemene koopkracht gelijkstellen aan goud/BTC.
- Automatisch bijschatten van ontbrekende data.

## Tijddekking
- CBS adapter verwijst naar tabel `85773NED`; repo-code accepteert momenteel **alleen maandcodes vanaf 2000** (`20\d{2}`), hoewel bronhistorie eerder kan beginnen. Dit is een implementatiebeperking, geen economische begindatum.
- `2000-01` tot `2026-08` telt rekenkundig 320 maanden; feitelijke volledige dekking vereist CSV/JSON-audit.
- Bitcoin pas vanaf bewezen koershistorie; pre-market is `NOT_APPLICABLE`, geen API-fout.
- Laatste onvolledige maand wordt niet stilzwijgend als volledige maand getoond.

## Definition of Done (`PROPOSED`)
Een fase is gereed als: (a) beslissingen geregistreerd, (b) bronlicentie en dataset-ID vastgesteld, (c) tests en onafhankelijk gecontroleerde ankerpunten geslaagd, (d) versieerbaar datacontract nageleefd, (e) frontend-labels juist, (f) release en rollback getest, (g) verificatielog bijgewerkt.

## Expliciete blokkades
`BLOCKED`: geen vrijgave van goud/BTC-indicator zonder gevalideerde bronprijzen en publicatierechten. `UNVERIFIED`: exacte CI- en Cloudflare deploy-status.

## Update v2.1 — BTC-tijddekking
De tradingrepository is nu een **geverifieerde kandidaat** voor dagelijkse BTC/USD-slotkoersen van **2014-09-17 t/m 2026-10-12** (4.409 opeenvolgende kalenderdagen, auditrun 39050246824). Dit is de bewezen dekking van **die bron**, niet de economische startdatum van Bitcoin en niet de dekkingsgarantie voor een publieke BTC/EUR-maandreeks. De periode vóór 2014-09-17 en de 1.267 BTC-dagen zonder dezelfde-dag FX vereisen expliciete methodologische keuzes. M2 blijft `BLOCKED` voor publicatie wegens FX, licentie en onafhankelijke broncontrole.

## Historische reikwijdte v2.4 (`DECIDED`, 2026-10-19)
Het project streeft naar een zo lang mogelijke vergelijking, idealiter vanaf circa 1900, **afhankelijk van de oudste aantoonbaar betrouwbare gemiddelde Nederlandse woningverkoopprijs**. De huidige 2000-01 grens is uitsluitend technisch. Onderzoek jaarlijkse historie naast recente maanddata; presenteer perioden zonder vergelijkbare woningprijzen niet als gram-goud-per-woning. De gevonden NVM/Vastgoedmarkt-reeks vanaf circa 1975 is `PROPOSED/UNVERIFIED` als aansluitende landelijke reeks; CBS/Kadaster vanaf 1995 is de bestaande operationele bron. Historische bron- en frequentieverschillen vereisen expliciete validatie.
