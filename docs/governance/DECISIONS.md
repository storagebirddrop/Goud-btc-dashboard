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
| ADR-004 | `PROPOSED` | Maandkoers | Gemiddelde van gevalideerde dagelijkse EUR-referentieprijzen; volledige verwachte kalenderdekking |
| ADR-005 | `PROPOSED` | Revisies | Laatst herziene CBS/CPI-data, met raw snapshots per release |
| ADR-006 | `PROPOSED` | Publicatie | Immutable releases + atomische current-pointer |
| ADR-007 | `PROPOSED` | BTC-bron | Coin Metrics testen; CoinGecko vergelijken; alleen na licentie- en kwaliteitsgoedkeuring |
| ADR-008 | `PROPOSED` | Ontbrekende maanden | Geen imputatie; null plus reden en coverage-status |
| ADR-009 | `PROPOSED` | CPI | Exacte CBS CPI-serie en basisjaar later expliciet kiezen |

## Open beslisvragen
1. Is 'gemiddeld verkochte bestaande koopwoning' de gewenste primaire indicator, of willen we een gemodelleerde constante woningkwaliteit als tweede indicator?
2. Welke goudbenchmark, tijdzone en handelskalender zijn geschikt en juridisch herbruikbaar?
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
- **Impact:** ADR-007 (Coin Metrics als primaire testkandidaat) is **SUPERSEDED voor bronprioriteit**, maar niet voor onafhankelijke broncontrole. ADR-004 (maandmethodologie) blijft `PROPOSED`.
- **Open:** FX-weekenden en feestdagen, USD/EUR-dagmatching, bronlicenties, bronvergelijking en publicatiebesluit. Geen forward fill of bronsplicing zonder apart besluit.
- **Bewijs:** [run](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824), [PR #35](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/35), [PR #36](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/36).
## Governance-integratie (2026-10-17)
De opname van dit register in GitHub is **geen nieuw economisch besluit**. ADR-004 en FX-weekend/feestdagbeleid blijven `PROPOSED`/onbeslist. PR #40 is open; scenarioanalyse geeft geen productieautorisatie. Zie [CONFLICT_MATRIX.md](CONFLICT_MATRIX.md).
