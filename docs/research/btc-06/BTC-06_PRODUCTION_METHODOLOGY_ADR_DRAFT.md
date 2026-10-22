# BTC-06 — Production Methodology ADR Draft

**Status: PROPOSED — NOT ACCEPTED**  
**Voorgesteld ID:** ADR-BTC-PRODUCTION-C1 (definitief ADR-nummer door Project Control te bepalen)  
**Project:** Goud & Bitcoin Dashboard · **Datum:** 22 oktober 2026  
**Gecontroleerde main:** `42b32be65f890dba8b327f2c26b6112854e7a4f4`  
**Uitvoering:** read-only onderzoek en ontwerp. Geen repositorywijziging, publicatie, nieuwe acquisitie, infrastructuur of Claude-opdracht uitgevoerd. **BTC-publicatie blijft HOLD.**

Dit document vormt één pakket met `BTC-06_DATA_CONTRACT_DRAFT.md` en `BTC-06_PROJECT_CONTROL_DECISIONS.md`. Bewijslabels: **CONFIRMED** = rechtstreeks gelezen repository/bestaand rapport of expliciete opdracht; **INFERRED** = afweging/voorstel; **UNVERIFIED** = nog niet bewezen. Alle normatieve productieformuleringen hieronder zijn een voorstel totdat Project Control ze expliciet aanvaardt.

## 1. Aanleiding en kleinste wijziging

**CONFIRMED:** de bestaande applicatie serveert één `/data/monthly.json` met `data` en zeven velden per maand. BTC-04E bevat de onderzoeksberekening; BTC-05D voegt lokaal snapshotformaat `btc04e-snapshot/2`, CM-responsebehoud, offline replay en revisiedetectie toe. Duurzame private bewaring is nog OPEN. De frontend reserveert `sat_per_house` als `withheld`; `btc_per_house` bestaat nog niet in het publieke schema [R1–R7].

**INFERRED — voorgesteld besluit:** promoveer dezelfde berekeningsdefinitie naar een expliciete productie-ADR; voeg later twee afgeleide velden, compacte maandmetadata en één gedeeld BTC-metadatablok toe aan het bestaande JSON. Hergebruik adapter, rekenmodel, snapshot/replay, exporter, validator, seriesregistry en bestaande Actions. Geen v2-migratie, nieuwe ETL, releasepointerarchitectuur of opslagontwerp. De uitbreiding blijft tijdens voorbereiding uitsluitend privé/synthetisch; de publieke payload blijft ongewijzigd tot een exact geautoriseerde release.

## 2. Besluitstatus en voorrang

| Onderdeel | Huidige status | Voorstel voor deze ADR |
|---|---|---|
| CM Community + ECB als bronroute; geen automatische fallback | **CONFIRMED:** PC-BTC04-1, onderzoeks-/productiekandidaat | Bevestigen voor productie, onder rechtenvoorwaarden |
| C1-formule | **CONFIRMED:** PC-BTC04-2, voorwaardelijk research-accepted | Dezelfde formule productiegeschikt verklaren; geen nieuwe prijsdefinitie |
| Q3/Q2/Q1-kandidaat en juni-HOLD | **CONFIRMED:** PC-BTC04-4 | Ongewijzigd overnemen; geen automatische upgrade naar Q1 |
| Start februari 2014, optioneel augustus 2010 | **CONFIRMED:** goedgekeurde ontwerprichting; opdracht vraagt afgebakende publicatieselectie | Eerste releaseprofiel vanaf 2014-02; vroegere numerieke historie apart autoriseren |
| BTC-05D lokale replay | **CONFIRMED:** code/documentatie op huidige main | Hergebruiken met benoemde grenzen |
| Productie-ADR, schema, afronding, exacte releaseperiode | **UNVERIFIED:** geen definitieve productieaanvaarding aangetoond | Nieuwe expliciete besluiten nodig |
| BTC-05A rechtenadvies | **CONFIRMED:** lokaal rapport aanwezig, conditional GO; niet in GitHub | Rechtenreview als aparte releasevoorwaarde, geen juridische vrijwaring |
| Publieke BTC-activering | **CONFIRMED:** HOLD, `RELEASE_APPROVALS` leeg | Blijft HOLD; deze ADR-draft autoriseert niets |

De recente PC-BTC04-sectie in `DECISIONS.md` gaat boven oudere Yahoo-/daily-FX-voorstellen en de oude voorkeur voor EUR-native Bitstamp. De oude `DATA_CONTRACT.md`-v2 en daily-close-metadata zijn voorstellen/historische context, geen verplichting om de geselecteerde CM-referentie onjuist als daily close te etiketteren. Goud-ADR-004, GOLD-03/04, CBS en historische NVM/CBS-besluiten veranderen niet.

## 3. Economische betekenis

**INFERRED — voorgestelde definitie:** de indicator drukt de nominale CBS-gemiddelde verkoopprijs van daadwerkelijk verkochte bestaande koopwoningen uit in Bitcoin, gewaardeerd tegen één maandelijkse, USD-afgeleide BTC/EUR-referentie. Satoshi is een andere rekeneenheid voor dezelfde verhouding: 1 BTC = 100.000.000 satoshi.

Een daling betekent dat het gemiddelde van verkochte woningen in die maand minder BTC vertegenwoordigt onder deze methode. Zij kan voortkomen uit verandering van BTC, EUR/USD, woningprijzen en de mix van verkochte woningen. Zij bewijst niet dat dezelfde woning goedkoper werd, dat inkomens/hypotheeklasten verbeterden, of dat woningen daadwerkelijk met BTC zijn betaald. Het is geen koopkracht-, constante-kwaliteit-, betaalbaarheids- of beleggingsrendementsindex. Er is geen woninggrote uitvoerbare BTC-handelsprijs, slippage of transactiekosten in verwerkt.

## 4. Bronnen en eenheden

| Variabele | Bronidentiteit | Waarneming/eenheid |
|---|---|---|
| `H_m` | CBS StatLine `85773NED`; interne reeks `nl_house_avg_eur` | Nominale gemiddelde verkoopprijs bestaande koopwoningen, EUR per gemiddeld verkochte woning |
| `p_d` | `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics`; `assets=btc`, `metrics=PriceUSD`, `frequency=1d` | Positieve dagelijkse providerreferentiewaarde, USD/BTC; timestamp UTC |
| `f_d` | ECB `EXR.D.USD.EUR.SP00.A` | Geldige dagelijkse referentiefixing, USD per EUR |
| `P_m` | Eigen aggregatie van `p_d` | Rekenkundig kalendermaandgemiddelde, USD/BTC |
| `F_m` | Eigen aggregatie van `f_d` | Rekenkundig gemiddelde geldige ECB-fixings in die kalendermaand, USD/EUR |

**CONFIRMED:** de CBS-adapter resolveert measures via titel/Identifier en weigert ambiguïteit; er is in de gelezen code geen vaste verifieerbare numerieke measure-ID hardcoded. Leg bij een toekomstige kandidaat het daadwerkelijk geresolveerde Identifier en de tabelmetadata vast; verzin geen veldcode. De woninginput is `average_price`, geen HPI, NVM-mediaan of gemodelleerde woning [R8].

**INFERRED:** CM PriceUSD wordt niet hernoemd tot exchangeclose, EUR-native koers, intradag-VWAP of onafhankelijke beurswaarneming. De bekende beperkte vroege reconstructie-/constituentprovenance blijft zichtbaar. Comparatoren Bitstamp/Mt. Gox/Kraken dienen controle; geen automatische bronwisseling of splice.

## 5. Aggregatie, kalender en rekenrichting

Voorgestelde productie-ID blijft **`CM_PRICEUSD_MONTHMEAN_C1_V1`**.

Voor maand `m` met `D_m` kalenderdagen en de verzameling geldige aanwezige ECB-fixings `E_m`:

\[
P_m=\frac{\sum_{d\in m}p_d}{D_m},\quad F_m=\frac{\sum_{d\in E_m}f_d}{|E_m|},\quad B_m=P_m/F_m,
\]
\[
BTC_m=H_m/B_m,\qquad SAT_m=BTC_m\times100{,}000{,}000.
\]

- BTC vereist precies één geldige waarde voor elke UTC-kalenderdag, van de eerste dag 00:00 UTC tot exclusief de eerste dag van de volgende maand. De bestaande adapter accepteert alleen UTC-midnight-timestamps; de maandindeling volgt de providerdatum, niet lokale Nederlandse tijd.
- De maand moet ten opzichte van de vastgelegde acquisitiegrens afgesloten zijn. Geen lopende UTC-dag of onvolledige maand; juli 2010 is geen volledige kandidaatmaand.
- Gelijke bronduplicaten mogen door de bestaande adapter worden gecollapst; conflicterende duplicaten, ongeldige valuta, niet-eindige/niet-positieve waarden of parserproblemen stoppen kandidaatvalidatie.
- ECB gebruikt uitsluitend echte geldige fixings; geen kalenderdagendeler, geen weekend-/feestdag-forwardfill, geen koers 0 en geen dagelijkse BTC/FX-matching. Verwachte TARGET-sluitingsdagen zijn geen datagat.
- **CONFIRMED:** BTC-04E blokkeert maanden met onverwacht ontbrekende ECB-werkdagen, gebruikt daarnaast een minimale coverageheuristiek en controle op een gedeeltelijke laatste maand. **INFERRED:** deze strengere onderzoekscontrole behouden; de 0,5-calendarcoverage is geen zelfstandig bewijs van volledige FX-kwaliteit. Valideer TARGET-kalender en sluitingsdagen per kandidaat met bestaande helper/tests; onverwachte ontbrekende dag → null/blokkade, geen herdeling over een incompleet subset.
- Exacte `YYYY-MM`-join met CBS; geen interpolatie, backdating, automatische kalenderconversie of ontbrekende CBS-maand overslaan.

Een synthetisch onderscheidingsvoorbeeld: twee prijsdagen 100 en 200 USD, FX 1 en 4 USD/EUR. Ratio van gemiddelden = 150/2,5 = **60** EUR/BTC; gemiddelde dagratio = (100/1 + 200/4)/2 = **75**. Deze testgetallen zijn fictief, geen historische koersen. C1 kiest 60. De test moet een fixture gebruiken waarin beide methoden werkelijk verschillen.

## 6. Precisie en presentatie

**CONFIRMED:** `etl/hist_model.py` gebruikt `PREC=34` en lokale Decimalcontexts voor maandgemiddelden, valutaomrekening en huisratio's. Canonieke decimalen hebben geen exponent of overbodige eindnullen. BTC en sats worden momenteel beide direct uit `H/B` afgeleid; zij kunnen op het laatste Decimalcijfer verschillen van het vermenigvuldigen van een reeds afgerond BTC-resultaat [R9].

**INFERRED — voorstel:** behoud 34 significante cijfers en de bestaande bewerkingsvolgorde; geen afronding naar hele satoshi's in de berekening, geen float bij parser/aggregatie/ratio. Leg `ROUND_HALF_EVEN` expliciet vast bij kandidaatvalidatie en bewijs dat de legacywaardenhash gelijk blijft. Afwijking door context/bewerkingsvolgorde is een reviewbare methodische of implementatieafwijking, geen stilzwijgende nieuwe pin.

Voor de bestaande JSON-route: twee finite positieve **JSON-numbers**, net als goudvelden; interne Decimal-vintage blijft de canonieke rekenwaarheid. JSON/binary64 is een gecontroleerde benadering, geen 34-cijferige exactheid. Het contract specificeert verliesgrenzen en weigert niet-veilig representeerbare resultaten. Geen tweede decimal-string-waarde naast hetzelfde publieke getal. Exacte audit gebeurt met private Decimalinputs en hashes.

UI: BTC maximaal acht decimalen, satoshi's zonder decimalen, `nl-NL`; geef afronding aan. Een statistische ratio kan intern fracties van een satoshi hebben; het is geen spendbare transactiehoeveelheid. Voor procentuele verandering gebruik de niet voor weergave afgeronde geladen waarden. Ronding in UI verandert geen bron-/derived-hash.

## 7. Kwaliteit en historie

| Maanden | Label | Betekenis en behandeling |
|---|---|---|
| 2010-08..2014-01 | `Q3` | Indicatieve vroege historie met beperkte provenance/marktspreiding; alleen na afzonderlijke autorisatie als optionele historie |
| 2014-02..2016-04 | `Q2` | Betere comparator-/marktdekking; onzekerheid blijft; geen andere C1-methode |
| Vanaf 2016-05 | `Q1_CANDIDATE` | Sterkere onderzoeksbasis; geen formele Q1-upgrade door CI/replay/publicatie |
| 2011-06 | `Q3` + `RESEARCH_ONLY_HOLD` | Maanduitzondering gaat boven alle algemene kwaliteit/allowlists |

**INFERRED:** dit zijn evidenceklassen, geen betrouwbaarheidsintervallen, foutmarges, statistische ratings of bewezen bronbreuken. Geen oude Bitstamp-USD-volumedrempel importeren. Behoud reviewnotities voor 2015-05/08 en 2017-12 waar de bestaande evidence ze ondersteunt; ze zijn geen automatische uitsluiting en hun magnitude wordt hier niet opnieuw berekend.

Voorgesteld eerste profiel `STANDARD_2014_02`: alleen maanden vanaf februari 2014 t/m een expliciet goedgekeurde cutoff. De huidige repo heeft CBS t/m 2026-08: dat geeft **151 kalendermaanden** in dit profiel. Dit is een telling van de huidige payload, geen 151 gevalideerde of vrijgegeven BTC-waarden. Augustus 2010..2026-08 omvat 193 kalendermaanden; zonder juni 2011 maximaal 192 potentiële punten, niet automatisch toegelaten.

Vroege historie moet afzonderlijk worden geautoriseerd voordat numerieke Q3-waarden in publieke JSON komen. UI verbergen maakt reeds in JSON opgenomen waarden niet privé. Een toekomstige uitgebreide weergave mag alleen geautoriseerde vroege punten tonen; standaard blijft de view vanaf 2014-02. Bestaande CBS-/goudperiodeselectie wordt niet wereldwijd tot 2014 ingekort.

## 8. Ontbrekende en niet-publiceerbare maanden

**INFERRED:** onderzoekswaarde beschikbaar, economische controle, rechtenreview, PC-autorisatie en publieke activering zijn vijf afzonderlijke dimensies. De exporter mag alleen waarden selecteren als alle noodzakelijke dimensies geldig zijn voor exacte kandidaat, velden en maanden. Geen enkele `has_value`, `IDENTICAL`, `Q1_CANDIDATE` of `conditional rights GO` opent de gate.

Bij actieve contractuitbreiding krijgen ontbrekende/niet-toegelaten maanden twee nulls plus reden, geen 0. Voorafgaand aan augustus 2010 betekent `BEFORE_SUPPORTED_MONTH` uitsluitend buiten ondersteunde methodedekking, niet een ongefundeerde economische claim dat Bitcoin toen niet bestond. Binnen ondersteunde historie buiten de autorisatie: `NOT_AUTHORIZED_PERIOD`. Een bronfout, incompleet tijdvak of rechtenblokkade krijgt eigen reden; verlies van al goedgekeurde input mag niet stilzwijgend een nieuwe publieke null-release veroorzaken.

Juni 2011: altijd publiek `null` voor beide waarden, `RESEARCH_ONLY_HOLD`, geen candidate-selectoroverride, geen interpolatie en geen verbonden grafieklijn. De maandrecord blijft in de continue kalender; verwijdering van het record zou een lijn alsnog over het gat kunnen trekken. De bestaande Recharts `connectNulls={false}` hergebruiken en browsermatig bewijzen met een synthetisch vroeg-historiescenario.

## 9. Revisies en updates

**CONFIRMED:** BTC-05D heeft baselinevergelijking voor CM-dagen en blokkeert herzieningen/ontbrekende historie in validate-mode. `monthly_update_plan` identificeert complete nieuwe CM-maanden, maar valideert daarmee niet zelfstandig CBS-, ECB-, rechten- of releasegeschiktheid [R5].

**INFERRED:** één beoordeelde kandidaatvintage met exacte CBS-input, CM/ECB-pins, cutoff, replayresultaat en outputhash. Bewaar reeds goedgekeurde historie; nieuwe volledige maand = nieuwe kandidaat, niet automatische release. CM-, ECB- en CBS-revisies alle drie controleren met bestaande generieke vergelijkingshelper/vensterhashes en CBS-updatecontrole. Een CM-only revisierapport volstaat niet voor een driebronnenproduct.

Beoordeel gewijzigde datums, getroffen maandaggregaten, huisratio's en metadata. Herziening binnen goedgekeurde historie vereist afzonderlijke revisieacceptatie en nieuwe releasehash; oude vintage/pins niet overschrijven. Methode-ID wijzigt bij economische definitiewijziging; parser/quality/exception hebben eigen versievelden. Ook met gelijkblijvende methode kan een nieuwe bronvintage een andere uitkomst hebben.

Bronuitval stopt nieuwe kandidaat; bestaande goedgekeurde publieke release blijft staan. Geen fallback naar Bitstamp/Yahoo/CoinGecko. Bestaande Actions blijven review-only; geen nieuw schema voor automatische maandautorisatie in dit besluit.

## 10. Bronrechten en attributie

**CONFIRMED:** BTC-05A is als lokaal rapport beschikbaar, niet op GitHub. Het adviseert conditional GO voor CM Community CC BY-NC 4.0 + ECB + CBS, onder juiste bronroute, werkelijk NC-gebruik, attributie, bewerkingsmelding en afwezigheid van een conflicterend aanvullend contract. Het onderzoek levert geen definitieve vrijwaring. De contractvraag bij de projecteigenaar blijft **UNVERIFIED**.

**INFERRED — verplichte publieke tekst bij later geautoriseerde BTC-view:**

> Coin Metrics Community, Bitcoin PriceUSD (dagelijkse USD-referentiewaarden; CC BY-NC 4.0), ECB EXR.D.USD.EUR.SP00.A en CBS StatLine 85773NED. Maandgemiddelden, USD/EUR-omrekening en BTC/satoshi per gemiddeld verkochte woning zijn eigen berekeningen. De BTC/EUR-maandreferentie is USD-afgeleid en geen rechtstreeks geobserveerde EUR-handelsprijs. Geen bronorganisatie onderschrijft deze toepassing.

Link bron, licentie en gekozen methodedocument. Toon aanvullende CBS-/ECB-rechteninformatie per bron; presenteer niet alle oorspronkelijke data als CM-licentie. Vaste CC-licentielink: `https://creativecommons.org/licenses/by-nc/4.0/`. Publieke afgeleide JSON heeft dezelfde rechtenreview nodig als grafieken: `H/BTC` of `H×1e8/SAT` maakt de maandreferentie terugrekenbaar. Geen raw-prijzen of dagwaarden als bijvangst exporteren.

## 11. Gates voor productie en publicatie

Alle onderstaande voorwaarden zijn **INFERRED — voorgestelde cumulatieve gates**:

1. Project Control aanvaardt de productie-ADR en het minimale contract; geen `PROPOSED` automatisch als ACCEPTED behandelen.
2. Rechten-/exploitatiecheck voor exacte bronroute en publicatievorm, inclusief aanvullende contractverklaring en attributie.
3. Eén exact geïdentificeerde kandidaat met bronvensterhashes, verplichte CBS-inputhash, snapshotmanifesthash, methode/policy/codeversies en volledige maandselectie.
4. Fail-closed bron-/kalender-/formule-/qualityvalidatie en offline replay; bronrevisies afzonderlijk geaccepteerd.
5. Praktisch terugvindbare, toegestane private kandidaatvintage en bijbehorende CBS-input; duurzame private bewaring is nu nog OPEN. Geen nieuwe opslagarchitectuur in BTC-06A/C; het bestaande opslaggate laten oplossen door Project Control.
6. Exacte outputhash, goedgekeurde velden/maanden, gedeelde-goud/CBS-regressie, browsergrens en rollback bewezen.
7. Expliciete eigenaarautorisatie voor merge/deployment/publieke activering van de exacte kandidaat; gesloten gate is de standaard.

Rechten-, methode-, review- en publicatieautoriteit komen uit gecontroleerde projectrecords; JSON-labels attesteren ze maar creëren die autoriteit niet. Technische verificatie kan een handtekening/besluitreferentie structureren, niet zelfstandig juridische of economische goedkeuring geven.

## 12. Alternatieven en gevolgen

| Alternatief | Oordeel |
|---|---|
| EUR-native Bitstamp of dagelijkse FX-ratio's | Afwijzen voor deze productievoorbereiding: andere bron/semantiek, geen aanleiding om de gekozen C1 opnieuw te vervangen |
| Alleen sats publiceren en BTC in browser afleiden | Minder getallen maar vereist clientberekening en wijkt af van minimaal twee direct interpreteerbare gevraagde indicatoren; niet de voorkeur |
| Volledige immutable-release-v2/schemawrapper | Niet noodzakelijk aangetoond; grotere projectmigratie met extra risico voor bestaande goud/CBS |
| Nieuwe losse BTC-JSON/API | Extra fetch/consistentie- en testoppervlak; huidige enkelvoudige payload kan veilig additief worden uitgebreid |
| Alle vroege waarden toevoegen maar standaard verbergen | Onjuist zonder vroege publicatieautorisatie: verborgen UI is geen JSON-publicatiegate |

**INFERRED:** voordeel van dit voorstel is één gecontroleerde payload met hergebruik van bestaand rekenwerk. Noodzakelijke technische gevolgen blijven: BTC-exportvalidator, compacte metadata, aangepaste strikte veld-/hashcontroles, BTC-specifieke viewselectie en browserchecks. Dit is geen wijziging van de goudformule of CBS-data. De gehele JSON krijgt bij daadwerkelijke BTC-release wel nieuwe bytes en vereist daarom een exact nieuw gezamenlijk artifactrecord.

## 13. Bronnen en verificatiegrenzen

Alle repositorylinks hieronder horen bij de onafhankelijk vastgestelde main-HEAD. Bestandsinspectie bewijst aanwezigheid/gedrag van code, geen actuele groene CI of productie-run.

- **R1:** [Main-commit](https://github.com/storagebirddrop/Goud-btc-dashboard/commit/42b32be65f890dba8b327f2c26b6112854e7a4f4).
- **R2:** [DECISIONS](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/DECISIONS.md), [METHODOLOGY](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/METHODOLOGY.md), [DATA_CONTRACT](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/DATA_CONTRACT.md), [DATA_SOURCES](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/DATA_SOURCES.md).
- **R3:** [BTC-04E-code](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tools/btc_04e_cm_replay.py), [bronpins](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/data/fixtures/btc04e/source_pins.json), [validatiedocument](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/research/BTC_04E_COINMETRICS_VALIDATION.md).
- **R4:** [Static exporter](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/static_export.py), [data_quality](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/data_quality.py), [monthly.json](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/public/data/monthly.json).
- **R5:** [BTC-05D-vintage/replay](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/research/BTC_05D_VINTAGE_REPLAY.md).
- **R6:** [series.ts](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/src/series.ts), [main.tsx](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/src/main.tsx), [publication-boundarytests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_bitcoin_publication_boundary.py).
- **R7:** [BTC-workflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/.github/workflows/btc-04e-cm-replay.yml), [CBS-updateworkflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/.github/workflows/update-static-data.yml), [safe CBS-update](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/cbs_historical_update.py).
- **R8:** [CBS-adapter](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/sources/cbs.py), [CBS-modelinput](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tools/hist_08_bundle.py).
- **R9:** [hist_model.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/hist_model.py), `PREC`, `monthly_mean`, `convert_currency`, `_combine`, `btc_per_house`, `sats_per_house`.
- **R10:** Governance gelezen: [AGENTS](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/AGENTS.md), [DOCUMENT_HIERARCHY](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/DOCUMENT_HIERARCHY.md), [CHANGE_CONTROL](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/CHANGE_CONTROL.md), [PROJECT_STATUS](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/PROJECT_STATUS.md), [ARCHITECTURE](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/governance/ARCHITECTURE.md).
- **R11:** `BTC-05A_SOURCE_RIGHTS_ASSESSMENT.md`, 22 oktober 2026, beschikbaar lokaal en inhoudelijk hergebruikt; **geen GitHub-bestand**. Primaire bron-/licentielinks en juridische beperkingen staan in dat rapport; hier geen nieuwe volledige licentieaudit.

**Aanvullend gelezen:** actuele `docs/governance/PROJECT_SCOPE.md`, `docs/governance/VERIFICATION_LOG.md`, `data/gold-release-record.json` en `etl/gold_publication_candidate.py` op dezelfde HEAD. Het geautoriseerde goudrecord en de codepin bevestigen de hieronder genoemde payloadhash. De oudere PROJECT_STATUS-beschrijving van alleen BTC-04E is niet gebruikt om BTC-05D te ontkennen; de huidige code en het BTC-05D-document zijn daarvoor leidend.

**CONFIRMED:** huidige payload geteld: 320 maanden, 2000-01..2026-08, alleen de bestaande zeven velden; bytehash `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`, 53.727 bytes. **NIET UITGEVOERD:** nieuwe koersacquisitie, huidige CI, echte kandidaatberekening, browser-/rollback-/duurzame restoretests of productievalidatie. Oude onderzoeksrunclaims blijven bestaande evidence, niet opnieuw uitgevoerde tests.
