# METHODOLOGY — economische definities en rekenregels

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## 1. De twee woningreeksen zijn **niet uitwisselbaar**
- `nl_house_avg_eur[t]`: CBS gemiddelde verkoopprijs van verkochte bestaande koopwoningen in EUR/transactie; **transactiemixgevoelig**. Dit is de noemer voor een concreet aantal gram/BTC **per gemiddeld verkochte woning**, niet voor een onveranderlijke representatieve woning.
- `nl_hpi[t]`: CBS/Kadaster prijsindex bestaande koopwoningen (bron vermeldt 2020=100); voor kwaliteitsgecorrigeerde **relatieve** prijsontwikkeling. Heeft dimensie indexpunten, niet EUR/woning.
- Een hypothetische woningprijs afgeleid uit een index en anker is alleen toegestaan met expliciet `MODELED` label, anker, aannames en gevoeligheidsanalyse; **niet** stilzwijgend gelijkstellen aan een geobserveerde verkoopprijs.

## 2. Formules
Neem maand `t`, `H_t` = EUR/gemiddeld verkochte woning, `G_t` = EUR/troy ounce, `B_t` = EUR/BTC, `I_t` = CPI, `r` = gekozen referentiemaand.

- Troy ounce = **31.1034768 gram**.
- `gold_eur_g[t] = G_t / 31.1034768`.
- `gold_g_per_avg_sold_home[t] = H_t * 31.1034768 / G_t`.
- `btc_per_avg_sold_home[t] = H_t / B_t`.
- `sats_per_avg_sold_home[t] = (H_t / B_t) * 100_000_000`.
- `house_real_eur_at_r[t] = H_t * I_r / I_t`.
- `index_at_r[t] = 100 * series_t / series_r`, alleen bij **gezamenlijke, expliciet gekozen basismaand** en positieve waarden.
- Bij goud USD/troy oz en ECB `USD per EUR` op dezelfde datum: `gold_EUR_oz[d] = gold_USD_oz[d] / ECB_USD_per_EUR[d]`. Nooit de inverse zonder controle gebruiken.
- NLG historische bedragen: wettelijk vaste conversie `1 EUR = 2.20371 NLG` geldt voor nominale conversie bij euro-introductie; maakt een oud bedrag **niet** automatisch reëel vergelijkbaar. Voor eerdere markt-/FX-regimes aparte herkomst nodig.

## 3. Maandaggregatie (BTC en overige assets: `PROPOSED`; goud: ADR-004 `ACCEPTED` per 2026-10-18)
- Dagkoersen: kies exact bronfixing/referentietijdstip, timezone, handelskalender, UTC dag en eventuele weekenddefinitie per asset.
- **Goud (ADR-004 `ACCEPTED`):** World Bank GOLD USD/troy ounce maandgemiddelde gedeeld door het rekenkundig gemiddelde van beschikbare geldige dagelijkse ECB USD-per-EUR-koersen in dezelfde kalendermaand. De verhouding van maandgemiddelden is niet het gemiddelde van dagelijkse EUR-goudprijzen. Tot en met mei 2025 London afternoon fixing; vanaf juni 2025 gemiddelde dagelijkse spotprijzen, zichtbaar annoteren bij publieke visualisatie. **Overige assets:** dagelijkse EUR-matching/aggregatie blijft `PROPOSED`.
- `H_t / mean(B_d)` is de prijsratio tegen een **gemiddelde referentiekoers**, **niet** `mean(H_t/B_d)`; beide zijn wiskundig verschillend. Leg deze semantiek zichtbaar vast.
- **Goud:** gemiddelde over daadwerkelijk beschikbare geldige ECB-koersdagen (geen kalenderdagendeler en geen imputatie); historische ontbrekende bronmaanden blokkeren, recente nog niet gepubliceerde maanden zijn `pending_publication`. Alleen complete World Bank/ECB/CBS-maandkoppelingen, indexbasis 2000-01 = 100. **Overige assets:** verwachte dagkalender en `PARTIAL`-beleid blijven `PROPOSED`.
- Maand CBS wordt direct aan maand `YYYY-MM` gekoppeld; niet suggereren dat transacties op dezelfde dagen vielen als koersobservaties.
- Geen forward fill, lineaire interpolatie of backdating. Een gedeeltelijke lopende maand apart markeren en standaard uitsluiten.

## 4. Bronbreuken, CPI en revisies
- CPI is een **prijsniveaucorrectie**, geen maat voor woonlasten of hypotheekbetaalbaarheid. Kies exact CBS CPI-reeks, referentie en revisieregels voordat reële EUR verschijnt.
- Kies beleid: `LATEST_REVISED` (voorkeur, voorstel) met snapshotversie; historisch 'as-published' vereist aparte archivering.
- Veranderingen in HPI-basisjaar, CBS-classificatie of benchmarkmethode worden als `BREAK` vastgelegd en niet zonder toelichting aaneengeregen.
- Bronwisseling BTC/goud vereist overlappende periode, vergelijkende afwijkingsanalyse en formeel besluit.

## 5. Missingness en eerlijkheid
`NOT_APPLICABLE` (bv. BTC vóór prijsmarkt), `SOURCE_UNAVAILABLE` (API/bronstoring), `NOT_PUBLISHED` (nog niet beschikbaar), `INCOMPLETE_PERIOD`, `FAILED_VALIDATION`, `LICENSE_BLOCKED`, `UNVERIFIED_SOURCE`. Allemaal `value=null`, met aparte `missing_reason`; nul is een geldige economische waarde **niet** voor een positieve assetkoers.

## 6. Tests en onafhankelijke controles
- Dimensionele controles: EUR/woning ÷ EUR/g = g/woning; EUR/woning ÷ EUR/BTC = BTC/woning.
- Positiviteit, eindigheid, uniekheid `(series, month)`, datumvolgorde, kalenderdekking en bronhash.
- Handmatige steekproef van minstens begin-, midden-, eind- en breukmaanden; check tegen primaire bron.
- Property tests: sats = BTC×1e8; goud in EUR per ounce ↔ gram; reële EUR in referentiemaand = nominale EUR.
- Geen relatieve performancevergelijking met verschillende indexbasissen of overlappende reeksen zonder gedeelde maand.

## 7. Interpretatiewaarschuwing voor elke grafiek
'De reeks toont de prijs van een gemiddeld verkochte bestaande koopwoning uitgedrukt in de gekozen rekeneenheid. De mix van verkochte woningen kan veranderen; de reeks meet geen constante woningkwaliteit of algemene betaalbaarheid.'

## Update v2.1 — BTC/USD-dagkoersen en FX (nog geen productievrijgave)
- De geauditeerde tradingbron bevat Yahoo `BTC-USD` **dagelijkse slotkoersen** en `EURUSD=X` in **USD per EUR**; dit zijn niet per definitie gestandaardiseerde UTC-fixings of daggemiddelden.
- **Rekenrichting:** `btc_eur[d] = btc_usd_close[d] / usd_per_eur[d]` mits koers- en FX-dag expliciet gematcht en bronsemantiek verenigbaar zijn. Voor maandaggregatie eerst elke dag omrekenen, daarna het gemiddelde van dagelijkse EUR-prijzen; **niet** een USD-maandgemiddelde omrekenen tegen één FX-waarde.
- BTC telt 4.409 kalenderdagen vanaf 2014-09-17; slechts 3.142 daarvan hebben dezelfde-dag EURUSD, dus 1.267 ontbrekende FX-matches. **Geen weekend-/feestdag-carry-forward, interpolatie of gedeeltelijke maandpublicatie goedgekeurd.** FX-handelskalender verschilt van BTC-kalender.
- Eerdere BTC-jaren vereisen een tweede gedocumenteerde bron en overlapcontrole; geen nulwaarden of stilzwijgend aan elkaar geplakte methodes.
- Bronrechtelijke controle en onafhankelijke prijsvergelijking blijven blokkades. Zie [audit](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824) en `docs/btc-trading-history-audit-2026-10-17.md`.
## Interpretatie bij opname in GitHub
De goudspecifieke maandaggregatie in §3 is op 2026-10-18 **ACCEPTED** volgens ADR-004 in [DECISIONS.md](DECISIONS.md), maar is **geen autorisatie** voor publieke goudpublicatie of carry-forward. BTC-aggregatie en FX-dagmatching blijven `PROPOSED`. De read-only scenarioanalyse in PR #40 is uitsluitend onderzoeksimplementatie. Bij conflict met historische technische documentatie gelden alleen expliciet goedgekeurde economische besluiten; zie [DOCUMENT_HIERARCHY.md](DOCUMENT_HIERARCHY.md).

## ADR-004-goedkeuring goud (2026-10-18)
De canonieke besluitregistratie staat in [DECISIONS.md](DECISIONS.md), ADR-004. De formule voor goud in EUR/gram is `gold_eur_oz / 31.1034768`; gram per gemiddeld verkochte woning is `house_eur / gold_eur_gram`; de goudindex is `100 * gold_eur_oz[m] / gold_eur_oz[2000-01]`. Alleen volledige historische maanden. De rechtenvraag en publieke activatie zijn afzonderlijk **NIET GOEDGEKEURD**.

## Historische jaarlijkse en maandelijkse reeksen v2.4 (`DECIDED` als onderzoeksprincipe)
Een historische **jaargemiddelde koopsom** is niet automatisch vergelijkbaar met een maandelijkse gemiddelde transactieprijs of een ultimo-waarneming. Valideer populatie, landelijke dekking, valuta, woningtype, definitie, periode en aggregatie vóór koppeling. Vermeng NVM- en CBS-niveaus niet zonder overlapcontrole; een prijsindex is geen geobserveerde gemiddelde koopsom. Construeer geen synthetische maandprijzen uit jaargegevens zonder afzonderlijk besluit en duidelijke modellabels. Goud vóór 1973 moet rekening houden met het vaste officiële prijsregime en de overgang naar een vrije marktprijs (o.a. 1968–1973). De in ADR-004 vastgelegde indexbasis **2000-01=100** blijft voor de huidige maandreeks geldig; een historische jaarindex vergt een expliciete basiskeuze. Geen wijziging van ADR-004 of publicatieautorisatie.
