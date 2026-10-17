# Conflictmatrix — Governance v3.0 versus bestaande repository

**Basis:** GitHub `main` `ef5a5e1007affe093d6187631e79c28ed4850326`, geïnspecteerd 2026-10-17; PR #37–#39 merged, PR #40 open. `PROPOSED` is geen autorisatie.

| Onderwerp | Bestaand (repo) | Governance v3.0 | Conflict / doublure | Afhandeling / status |
|---|---|---|---|---|
| Woningmaat | `docs/methodology.md`: CBS gemiddelde transactieprijs, HPI apart | `METHODOLOGY.md` §1: transactiemixgevoelig vs kwaliteitsgecorrigeerde index | Consistent; deels dubbel | Behoud technische uitleg; governance economische definitie; ADR-003 nog `PROPOSED` |
| Maandprijs | `docs/btc-price-methodology.md`: rekenkundig daggemiddelde, 100% kalenderdekking als default | `METHODOLOGY.md` §3 en ADR-004 `PROPOSED` | Technische default klinkt bindender dan formele besluitstatus | Geen productieautorisatie; keuze en fixing open (`BLOCKED`) |
| BTC-koersbron | `docs/btc-source-validation-2026-10.md`: Coin Metrics/CoinGecko onderzoek; `docs/btc-trading-history-audit-2026-10-17.md`: tradingbron kandidaat | ADR-010 `DECIDED` als **onderzoekskandidaat**; ADR-007 superseded voor onderzoeksprioriteit | Verschillende documentmomenten, geen productiebron gekozen | Bestaande docs behouden; historische bronprioriteit expliciet; publicatie `BLOCKED` |
| FX weekenden/feestdagen | `docs/btc-trading-history-audit-2026-10-17.md`: geen carry-forward goedgekeurd | `METHODOLOGY.md` §3: geen forward fill; `DECISIONS.md` open | Consistent, maar PR #39 audit berekent leeftijd en PR #40 onderzoekt hypothetische carry | Onderzoeksberekeningen zijn geen normatieve conversie; **rood besluit open** |
| FX bron | `docs/data-sources.md`: ECB key `EXR.D.USD.EUR.SP00.A`; tradingbron gebruikt Yahoo EURUSD=X | `DATA_SOURCES.md`: ECB onbevestigd, Yahoo kandidaat | Bron- en kalendersemantiek nog niet equivalent bewezen | Onafhankelijke validatie vereist, geen stille vervanging |
| BTC-historie | Tradingbron begint 2014-09-17; CoinGecko/Coin Metrics andere dekking | `PROJECT_SCOPE.md` en `METHODOLOGY.md`: pre-market ≠ nul, geen splice | Consistent; dekking vóór 2014 onbevestigd | `BLOCKED`, expliciet besluit bij broncombinatie |
| Indexbasis | `docs/methodology.md`: first-available voorbeeld, maar waarschuwt voor onvergelijkbare basis | `METHODOLOGY.md`: gedeelde expliciete referentiemaand | Potentieel misleidend voorbeeld in technische documentatie | Geen codewijziging; bij implementatie gemeenschappelijke basis toetsen |
| D1 / runtime | `README.md` en `docs/static-pipeline.md`: statisch zonder D1; `docs/next-phase.md`: staging D1 | ADR-001 `DECIDED`: statische JSON + Pages; legacy D1 blijft | Verouderde technische roadmap | Markeer `docs/next-phase.md` als legacy/voorstel; behoud D1-documentatie |
| Publicatiecontract | `frontend/public/data/monthly.json`: v1 structuur | `DATA_CONTRACT.md`: v2 release-manifest en schema `PROPOSED` | Ontwerp ≠ implementatie | Geen v2-migratie in governance-PR; `BLOCKED` |
| CPI, goud | `docs/data-sources.md`: goudbron onbevestigd, CPI niet productie | `DATA_SOURCES.md`: goud `BLOCKED`, CPI `PROPOSED` | Consistent, incomplete bron-/licentiecontrole | Geen cijfers verzinnen, geen publicatie |
| Status & audit | Bestaande gedateerde BTC-audit en oudere v2.1 statusclaims | `PROJECT_STATUS.md` / `VERIFICATION_LOG.md` v2.1 | Statusregels over CI/audit zijn deels achterhaald | Append-only verificaties V-201–V-205; oudere bewijsclaims blijven historisch |
| CI / branch protection | `.github/workflows/ci.yml` draait Python en frontend | `AGENTS.md`: verplichte checks en merge-gates | CI-run bewijst geen branch-protectionconfiguratie | CI op governance-PR apart verifiëren; branch protection `UNVERIFIED` |
| Terminologie | Technische docs gebruiken soms 'default', 'initial scope' | `DECISIONS.md`: `DECIDED`, `PROPOSED`, `BLOCKED` | Verschil tussen ontwerpintentie en autorisatie | Normatieve status alleen in besluitregister |

## Nog onbevestigde aannames

- Licenties en herdistributierechten voor Yahoo, goud en afgeleide koersdata.
- BTC/USD-slotkoers en EURUSD-fixing qua tijdzone en economische vergelijkbaarheid.
- Werkelijke volledige CBS-dekking, revisies, live bron-spotchecks en Cloudflare deployment.
- Branch protection en vereiste checks op `main`.
- Geschiktheid van een 2-, 3- of 4-dagen FX-leeftijd; PR #40 is niet gemerged en bevat alleen een scenarioanalyse.
- Maandprijsaggregatie en omgang met onvolledige maanden zijn niet inhoudelijk goedgekeurd.

## Reviewbesluit

Documentintegratie kan onafhankelijk van deze **inhoudelijke** open punten worden beoordeeld, zolang zij als `PROPOSED`/`BLOCKED` blijven staan. Geen economische definitie, bronprioriteit of publicatiebeleid wordt met deze PR gewijzigd.

## Onafhankelijke PR #41 audit — aanvullende bevindingen

| ID | Ernst | Bewijs / betrokken bestand | Remediation | Reststatus |
|---|---|---|---|---|
| G-01 | HIGH | `README_GOVERNANCE.md` stelde dat oorspronkelijke documenten ongewijzigd waren en dat geen GitHub-runs waren gecontroleerd, terwijl integratie status/verificatie had aangevuld | Historische pakketclaims expliciet onderscheiden van actuele repository-integratie | Hersteld in PR; CI op definitieve HEAD vereist |
| G-02 | MEDIUM | `scripts/check_governance_docs.py` controleerde alleen governancepaden, niet README en legacy verwijzingen | README/legacy-paden in controle opgenomen; regressietest voor kapotte links | Hersteld, definitieve CI vereist |
| G-03 | HIGH (preventief) | Een `PROPOSED` ADR kon zonder geautomatiseerde detectie `DECIDED` worden gemaakt | Statusbewaking voor ADR-004, ADR-007, ADR-008, ADR-009 plus negatieve regressietest | Baselinebewaking toegevoegd; inhoudelijke autorisatie blijft menselijke beslissing |
| G-04 | MEDIUM | Branch `main` meldt `protected=false` en rulesets API geeft lege lijst; eerdere 403 op protection endpoint | Geen beveiliging gefingeerd; repositoryinstellingen blijven apart in te richten | Open operationeel risico, geen bypass |
| G-05 | LOW | `CHANGE_CONTROL.md` verwees niet klikbaar naar besluitregister | Relatieve Markdown-link toegevoegd | Hersteld |
| G-06 | MEDIUM | Auditcheck op Markdown-links is regex-gebaseerd en dekt geen reference-style links of alle ankers | Scope gedocumenteerd; voor toekomstige uitbreiding overweeg parser of gerichte test | Restbeperking, geen economische wijziging |

**Afbakening:** Dit is een onafhankelijke audit van documentintegratie en PR-diff, niet van CBS- of marktprijsjuistheid. PR #40 is niet gewijzigd. Geen FX-forward-fill, maandaggregatie of publicatieregel goedgekeurd.
