# BTC-06 — Data Contract Draft

**Status: PROPOSED — NOT IMPLEMENTED**  
**Project:** Goud & Bitcoin Dashboard · **Datum:** 22 oktober 2026  
**Referentie/main, onafhankelijk gecontroleerd:** `42b32be65f890dba8b327f2c26b6112854e7a4f4`  
**Voorgestelde extensie-ID:** `btc-monthly/1` · **Methode:** `CM_PRICEUSD_MONTHMEAN_C1_V1`  
**BTC-publicatie blijft HOLD.** Dit is een implementeerbaar voorstel, geen nieuwe publieke dataset. Bijbehorende methodologie: `BTC-06_PRODUCTION_METHODOLOGY_ADR_DRAFT.md`; besluiten: `BTC-06_PROJECT_CONTROL_DECISIONS.md`.

Labels: **CONFIRMED** = rechtstreeks gelezen code/payload/bestaand rapport; **INFERRED** = voorgesteld contract/afweging; **UNVERIFIED** = nog niet aangetoond. Voorbeelden hieronder zijn synthetisch en zijn nooit historische observaties of vrijgaven. Productievalidatie mag placeholders niet accepteren.

## 1. Feitelijke huidige implementatie

**CONFIRMED:** het publieke object heeft uitsluitend `data`; 320 opeenvolgende maanden 2000-01..2026-08. De rowkeys zijn, in huidige volgorde:

| Veld | Werkelijk type | Betekenis |
|---|---|---|
| `period` | string `YYYY-MM` | CBS-kalendermaand |
| `gold_eur_oz` | null | Ruwe afgeleide goudprijs blijft uitgesloten |
| `house_eur` | JSON-number | Nominale CBS-gemiddelde verkoopprijs |
| `hpi` | JSON-number | CBS HPI |
| `gold_grams_per_house` | JSON-number | Reeds geautoriseerde afgeleide goudreeks |
| `gold_index` | JSON-number | Reeds geautoriseerde goudindex |
| `hpi_index` | JSON-number | Bestaande herbasering |

Bestand: 53.727 bytes; SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`. De rechtstreeks opgehaalde content is gehasht en parsing/compacte reserialisatie met dezelfde keyvolgorde en één afsluitende LF geeft identieke bytes. Dit is een controle van de repo-payload, geen actuele HTTP-productiemeting.

**CONFIRMED — frontend:** `main.tsx` doet één fetch naar `/data/monthly.json`, controleert `data` en periodevorm, maar is geen volledige contractvalidator. `series.ts` heeft vaste getypeerde veldnamen en `visibleKeys` vereist niet-withheld én minstens één finite waarde. `sat_per_house` is alleen optioneel gereserveerd; er is geen BTC-per-woningkey. Recharts gebruikt al `connectNulls={false}`. De bestaande generieke `fmt` zou een nieuw BTC-kind onbedoeld op één decimaal formatteren als er geen gerichte BTC-formatregel komt.

**CONFIRMED — backend/tests:** `data_quality` controleert exacte root-/rowkeys en bij goud de volledige artifacthash, release-record en codepin. `cbs_historical_update.py` heeft eveneens een exact zevenveldencontract. `tests/test_bitcoin_publication_boundary.py` verbiedt BTC-tekst in publieke JSON en beperkt de frontendmentions; zij bewaken bewust de huidige HOLD. Een additief schema is voor de oude browser grotendeels leesbaar, maar zonder gerichte validator-/testaanpassing niet door de huidige repositorychecks geaccepteerd.

**INFERRED:** er is geen noodzaak aangetoond voor de eerder voorgestelde v2-`metrics`-wrapper, apart bestand, tweede fetch of nieuwe release-infrastructuur. De kleinste bruikbare uitbreiding is twee numbers, één maandmetadatablock en één gedeeld metadatablock. Bron-/methode-ID hoeft niet op elke maand te worden herhaald.

## 2. Twee contracttoestanden

### 2.1 HOLD / legacy

**INFERRED — verplicht tijdens BTC-06C-voorbereiding:** publieke JSON behoudt uitsluitend de huidige root/zeven rowkeys en identieke bestaande waarden. Geen BTC-veld, ook geen nullveld of metadatablock, wordt in de publieke productiepayload geschreven zolang de schema-/publicatieactivatie niet afzonderlijk is geautoriseerd. Publieke BTC-data blijft afwezig; seriesregistry blijft `withheld`.

Private kandidaten en uitsluitend synthetische testfixtures mogen het voorgestelde uitgebreide schema dragen. Zij komen niet in de publiek geüploade artifacts, `frontend/public` of releasebestanden. Metadata/prijsloze checks mogen alleen via expliciete bestaande artifactallowlists.

### 2.2 Geautoriseerde extensie

**INFERRED:** behoud root `data`, alle bestaande rowkeys, volgorde en getalswaarden. Voeg aan elke maandrecord achteraan toe:

1. `btc_per_house`
2. `sat_per_house` — hergebruik van de bestaande frontendnaam, geen extra alias `sats_per_house`.
3. `btc_meta`

Voeg op rootniveau één `btc`-block toe. Geen wijziging van global schema-major of nesting van bestaande reeksen. Exacte rootkeys in actieve toestand zijn `data` en `btc`; exacte rowkeys zijn de zeven bestaande plus drie genoemde. De extensie heeft eigen `contract_version`.

**INFERRED:** rootmetadata is verplicht zodra één van de nieuwe rowkeys voorkomt, ook wanneer alle BTC-waarden null zijn. Omgekeerd vereist root `btc` de drie nieuwe keys op iedere row. Niet mengen binnen een payload; onbekende extensieversie, typefout, incomplete metadata of ongeldige maand is een exportfout. Oude payload zonder extensie blijft ondersteund door de nieuwe frontend en validator in legacy mode. Een oud extern systeem dat exacte keys valideert is niet automatisch compatibel; de repo bezit zulke validators en moet ze bewust aanpassen.

## 3. Velddefinities en null-semantiek

Alle volgende definities zijn **INFERRED — contractvoorstel**.

| Veld | Type/waarden | Eenheid en invariant |
|---|---|---|
| `btc_per_house` | positive finite number of null; booleans/strings verboden | BTC per gemiddeld verkochte woning, `H/(P/F)` |
| `sat_per_house` | positive finite number of null; niet verplicht integer | Satoshi per gemiddeld verkochte woning, `H/(P/F)×1e8`; fracties toegestaan in data |
| `btc_meta.quality` | `Q3`, `Q2`, `Q1_CANDIDATE` of null | Evidenceklasse uit `CM_Q_V1`; geen foutmarge |
| `btc_meta.status` | `PUBLISHED`, `WITHHELD`, `MISSING` | Status voor dit publieke veldpaar, geen algemene juridische rating |
| `btc_meta.missing_reason` | enum hieronder of null | Verplicht bij beide null; null bij twee waarden |
| `btc_meta.flags` | unieke gesorteerde strings, standaard `[]` | Alleen geregistreerde reviewnotities, geen vrije prijsdata of secrets |

Invariant: beide waarden aanwezig of beide null. Eerste releasevoorstel autoriseert beide velden samen; een toekomstige eenveldrelease is een afzonderlijke contract-/productkeuze. `PUBLISHED` vereist twee waarden, geldige kwaliteit, alle gates en null reden. `WITHHELD`/`MISSING` vereisen twee nulls. Geen NaN, Infinity, `"null"`, `0`, lege string of `Number(null)`-conversie. `Q1_CANDIDATE` blijft zo heten bij een goedgekeurde publicatie.

| `missing_reason` | Status | Toepassing |
|---|---|---|
| `RESEARCH_ONLY_HOLD` | `WITHHELD` | Juni 2011; gaat vóór reguliere periode-/qualityselectie |
| `BEFORE_SUPPORTED_MONTH` | `MISSING` | Vóór 2010-08 buiten gevalideerde volledige maanddekking; geen claim dat markt economisch onmogelijk was |
| `NOT_AUTHORIZED_PERIOD` | `WITHHELD` | Ondersteunde geschiedenis buiten exact geautoriseerd profiel/maanden |
| `PUBLICATION_NOT_AUTHORIZED` | `WITHHELD` | Alleen private preview bij ontbrekend releasebesluit; nooit reden om toch uitgebreide publieke JSON uit te rollen |
| `RIGHTS_NOT_CLEARED` | `WITHHELD` | Private kandidaat met onopgeloste toepasselijke rechtenvoorwaarde |
| `INCOMPLETE_PERIOD` | `MISSING` | Gesloten kalendermaand mist vereiste BTC-/FX-input of lopende maand |
| `SOURCE_NOT_PUBLISHED` | `MISSING` | Nog niet verschenen benodigde broninput, indien die maand reeds als CBS-row bestaat |
| `SOURCE_UNAVAILABLE` | `MISSING` | Geen verifieerbare broninput beschikbaar |
| `FAILED_VALIDATION` | `MISSING` | Hash-/valuta-/formule-/kalenderdefect of onverifieerbare kandidaat |

**Prioriteit:** (1) juni-HOLD, (2) vóór ondersteunde aanvang, (3) buiten autorisatie, (4) rechten-/releasegate, (5) concrete input/validatie. Bewaar in private QA alle tegelijk geldende oorzaken; publiceer één deterministische hoofdreden. Een actuele bronfout herschrijft een eerder goedgekeurde historische waarde niet naar null. Zo'n fout stopt de nieuwe kandidaat en laat de vorige publieke payload intact.

`quality=null` vóór 2010-08; vanaf die maand kwaliteit volgens de vaste vensters, ook bij een HOLD/null. Voor bestaande rowperioden na de vastgelegde kandidaat-cutoff mag een kalenderafgeleide klasse alleen als nominale periodeklasse worden gebruikt, niet als maandvalidatie; status blijft MISSING/WITHHELD. Geen publieke row toevoegen uitsluitend om BTC-pending te tonen wanneer de bestaande CBS-kalender die row nog niet heeft.

Voorgestelde vlaggen zijn bijvoorbeeld `EARLY_HISTORY_LIMITED_PROVENANCE`, `REVIEW_2015_05`, `REVIEW_2015_08`, `REVIEW_2017_12`. Exacte mappings worden vanuit bestaande onderzoeksnotities vastgelegd en gereviewd; geen nieuwe anomalie of numerieke afwijking verzinnen. Juni krijgt zijn verplichte reason, niet alleen een optionele flag.

## 4. Gedeelde metadata, provenance en rechten

| Pad binnen root `btc` | Type / eis |
|---|---|
| `contract_version` | Exact `btc-monthly/1` |
| `method_id` | Exact `CM_PRICEUSD_MONTHMEAN_C1_V1` |
| `parser_version` | Exact compatibele versie, momenteel `cm-priceusd-parser/1` |
| `quality_version` / `exception_policy_version` | `CM_Q_V1` / `CM_EXC_V1` tenzij apart gewijzigd besluit |
| `units` | `btc_per_house: BTC/home`, `sat_per_house: satoshi/home`; home = gemiddeld verkochte bestaande koopwoning |
| `coverage` | `supported_from=2010-08`, `default_from=2014-02`, `authorized_from`, `authorized_through`, `early_history_authorized` boolean |
| `release` | reviewed release-ID, exacte eigenaarbesluitreferentie, `publication_authorized` boolean; payload koppelt aan extern exact artifactrecord |
| `provenance.snapshot_format` / `snapshot_id` | Bestaand `btc04e-snapshot/2` en werkelijke snapshot-ID, geen nieuw storageformat |
| `provenance.snapshot_manifest_sha256` | SHA-256 van daadwerkelijke bestaande manifestbytes; hash naast snapshot-ID voorkomt te sterke claim op het verkorte ID |
| `provenance.calculation_git_commit` | Vaste 40-hex codecommit gebruikt voor berekening |
| `provenance.cbs_input_sha256` | Verplichte werkelijke CBS-CSV-bytehash, niet null |
| `provenance.cm_daily_sha256` / `ecb_daily_sha256` | Hash van volledige genormaliseerde inputs uit het snapshot |
| `provenance.source_windows` | Per CM/ECB: first/last/n/hash met bestaand windowhashalgoritme; expliciete grens, geen verwisseling met full-filehash |
| `provenance.derived_values_sha256` / `derived_cutoff` | Bestaande canonieke vijfseries-hash en exact gebruikte cutoff; niet de hash van afgeronde publieke floats |
| `provenance.cm_raw_retention` / `ecb_raw_retention` | Werkelijke toestand; huidige ECB `NOT_RETAINED` eerlijk benoemen |
| `provenance.vintage_reference_utc` / `time_basis` | Referentietijd uit werkelijk snapshot; bijvoorbeeld CM-acquisitietijd met `CM_ACQUISITION_REFERENCE`. Geen bewering van gelijktijdige driebronnenacquisitie |
| `sources` | Eén entry per CM/ECB/CBS met source-ID, metric/series, bronlink, licentie-/voorwaardenlink en attributie |
| `rights` | `assessment=CONDITIONAL`, rights-reviewreferentie, NC-scope, uitgevoerde eigenaarcontractcheck; status is attestatie, geen licentiecertificaat |

Niet ieder publiek metadataveld hoeft alle private HTTP-queries of responsepaginahashes te dupliceren. Detailbewijs blijft in het bestaande private snapshot/QA en gekoppelde PC-records. Publieke provenance bevat geen interne bestandslocaties, accountnamen, tokens of private downloadlinks. Bron-/methodevelden worden per payload geërfd; geen afwijkende maandbron binnen dezelfde indicator.

**CONFIRMED — grenzen BTC-05D:** ECB-originele HTTP-bytes zijn niet bewaard, alleen canonical values. CBS-bytehash is optioneel in de bestaande laag en `replay` accepteert een ontbrekende oude CBS-pin onder bepaalde aanroepen; de CLI voert de actuele CSV-hash aan. Revisies in `run` betreffen CM, niet automatisch alle ECB/CBS-dagen. Snapshot-ID omvat geen volledige authenticiteitsgarantie tegen iemand die manifest en alle hashes bewust herschrijft. Deze grenzen verdwijnen niet door rootmetadata.

**INFERRED — productiekandidaateis:** voor de nieuwe beoordeelde kandidaat CM-rawretentie `RETAINED` eisen en via de bestaande loader verifiëren; ECB `NOT_RETAINED` expliciet als huidige beperking registreren. De wrapper moet CBS-pin verplicht stellen en exact toetsen; snapshotmanifest extern aan het gereviewde kandidaatrecord binden; inputversies/vensters/cutoff expliciet vergelijken. Een huidige replay met `IDENTICAL` is noodzakelijke evidence, geen bewijs van duurzame private vindbaarheid, code-authenticiteit of rechtsgoedkeuring. Geen nieuwe storagearchitectuur: het bestaande opslaggate blijft OPEN totdat een werkelijk herstelbare toegestane kandidaat beschikbaar is.

`data_as_of` mag niet een toekomstige bronpublicatiedatum of de datum van frontenddeployment suggereren. Toon “Gegevensstand gebruikt voor berekening: …; laatste volledige maand: …”. Waar ECB/CBS-acquisitietijden ontbreken, rapporteer onbekend in private evidence en gebruik de genoemde CM-referentiebasis eerlijk; geen tijdstempels fabriceren. Gold-as-of blijft de bestaande eigen datum, niet vervangen door BTC-as-of.

**Licentieinformatie:** CM bron `PriceUSD`, Community-route en CC BY-NC 4.0-link; ECB specifieke reeks/voorwaarden; CBS 85773NED/CC BY 4.0 onder BTC-05A-beperkingen. Publiceer eigen bewerkingen en geen endorsement. `rights.assessment=CONDITIONAL` kan bestaan naast een expliciet geautoriseerde NC-release als voorwaarden zijn afgevinkt en restrisico bewust is aanvaard; “conditioneel” mag geen onopgeloste harde voorwaarde maskeren. Geen uniform CM-label op originele CBS-/ECB-data.

## 5. Schema-voorbeeld — uitsluitend fictieve kandidaat

Dit is een verkort voorbeeld van de **nieuwe velden** plus één volledige synthetische row, geen complete kalender en geen releasebaar bestand. Numerieke waarden zijn rekenfixtures: H=300.000 EUR, P=60.000 USD/BTC, F=1,2 USD/EUR → B=50.000 EUR/BTC → BTC=6, SAT=600.000.000. Zij zijn niet de CBS-/BTC-waarden van februari 2014. Placeholderstrings falen in productie terecht op type/hash-/autoriteitseisen; `publication_authorized=false` maakt dit een private preview.

```json
{
  "data": [
    {
      "period": "2014-02",
      "gold_eur_oz": null,
      "house_eur": 300000,
      "hpi": 80,
      "gold_grams_per_house": 12000,
      "gold_index": 100,
      "hpi_index": 100,
      "btc_per_house": null,
      "sat_per_house": null,
      "btc_meta": {
        "quality": "Q2",
        "status": "WITHHELD",
        "missing_reason": "PUBLICATION_NOT_AUTHORIZED",
        "flags": []
      }
    }
  ],
  "btc": {
    "contract_version": "btc-monthly/1",
    "method_id": "CM_PRICEUSD_MONTHMEAN_C1_V1",
    "parser_version": "cm-priceusd-parser/1",
    "quality_version": "CM_Q_V1",
    "exception_policy_version": "CM_EXC_V1",
    "units": {"btc_per_house": "BTC/home", "sat_per_house": "satoshi/home"},
    "coverage": {
      "supported_from": "2010-08",
      "default_from": "2014-02",
      "authorized_from": null,
      "authorized_through": null,
      "early_history_authorized": false
    },
    "release": {"id": null, "decision_ref": null, "publication_authorized": false},
    "provenance": {
      "snapshot_format": "btc04e-snapshot/2",
      "snapshot_id": "<actual-snapshot-id>",
      "snapshot_manifest_sha256": "<actual-64-hex>",
      "calculation_git_commit": "<actual-40-hex>",
      "cbs_input_sha256": "<actual-64-hex>",
      "cm_daily_sha256": "<actual-64-hex>",
      "ecb_daily_sha256": "<actual-64-hex>",
      "source_windows": {
        "cm_priceusd_daily": {"first": "2010-07-18", "last": "2026-08-31", "n": 5889, "sha256": "<actual-window-hash>"},
        "ecb_usd_per_eur_daily": {"first": "1999-01-04", "last": "2026-08-31", "n": 7082, "sha256": "<actual-window-hash>"}
      },
      "derived_values_sha256": "<actual-five-series-hash>",
      "derived_cutoff": "2026-08",
      "cm_raw_retention": "RETAINED",
      "ecb_raw_retention": "NOT_RETAINED",
      "vintage_reference_utc": "<actual-CM-retrieval-UTC>",
      "time_basis": "CM_ACQUISITION_REFERENCE"
    },
    "sources": [
      {"id": "coinmetrics_community_priceusd", "metric": "btc.PriceUSD.1d", "url": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics", "license_url": "https://creativecommons.org/licenses/by-nc/4.0/", "attribution": "Coin Metrics Community PriceUSD; eigen maandberekening"},
      {"id": "ecb_exr_d_usd", "metric": "EXR.D.USD.EUR.SP00.A", "url": "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A", "license_url": "https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html", "attribution": "ECB; eigen maandgemiddelde en valutaomrekening"},
      {"id": "cbs_85773NED_csv", "metric": "nl_house_avg_eur", "url": "https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table", "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": "CBS StatLine 85773NED; eigen BTC/satoshi-ratio"}
    ],
    "rights": {"assessment": "CONDITIONAL", "review_ref": null, "scope": "NON_COMMERCIAL", "conflicting_contract_check": "UNVERIFIED"}
  }
}
```

**Synthetische rowvarianten voor tests**, pas toe binnen een volledige fixturekalender en de passende private autorisatiefixture:

| Periodetest | `btc_per_house` / `sat_per_house` | `quality` | `status` / `missing_reason` |
|---|---|---|---|
| 2000-01 | null / null | null | MISSING / BEFORE_SUPPORTED_MONTH |
| 2010-08, standaardprofiel | null / null | Q3 | WITHHELD / NOT_AUTHORIZED_PERIOD |
| 2011-06, ook met foutieve brede allowlist | null / null | Q3 | WITHHELD / RESEARCH_ONLY_HOLD |
| 2014-02, synthetisch bevoegd release-record | 6 / 600000000 | Q2 | PUBLISHED / null |
| 2016-05, dezelfde fictieve inputs | 6 / 600000000 | Q1_CANDIDATE | PUBLISHED / null |
| Ontbrekende koersmaand binnen kandidaat | null / null | klasse volgens periode | MISSING / INCOMPLETE_PERIOD; kandidaat niet automatisch vrijgeven |

Actieve productionroot heeft werkelijke release-ID/referentie, geldige hashes, `publication_authorized=true`, werkelijk bereik en afgeronde rechtencheck. Het volledige JSON-schema is de combinatie van de veldtabellen, enums en invarianten; een implementatie mag dit als gerichte validator uitwerken, zonder projectbrede schemaservice.

## 6. Precisie, tolerantie en serialization

**INFERRED — intern:** 34 significante Decimalcijfers, bestaande bewerkingsvolgorde en canonieke decimale tekst; definitie van maandgemiddelden ongewijzigd. Bronstrings niet eerst naar float. Geen quantization van B, BTC of SAT vóór de private waardenhash.

**Publiek:** JSON-number als bestaande goudroute; geen garantie van exacte Decimalweergave. Converteer pas na validatie en test de daadwerkelijk geserialiseerde bytes opnieuw met `parse_float=Decimal`. Eis:

- Beide getallen finite en >0, geen boolean; SAT < 2^53 voor veilige gehele-satoshiweergave in de browser. Een overschrijding geeft hard fail/review, geen clipping.
- `abs(public_BTC_decimal − canonical_BTC) × 1e8 < 0,25` satoshi.
- `abs(public_SAT_decimal − canonical_SAT) < 0,25` satoshi.
- Daardoor publieke BTC/SAT-consistentie binnen **0,5 satoshi**, naast de te verwaarlozen laatste-Decimalcijferafwijking van het bestaande rekenpad. Controleer die laatste intern met 34-cijferige precisietolerantie in plaats van een onhaalbare bitexacte decimale gelijkheid tussen twee onafhankelijk afgeronde bewerkingen.

Deze grenzen controleren representatieverlies; zij zijn geen economische nauwkeurigheidsclaim of bronfoutmarge. Slaagt representatie niet, dan blokkeert de export voor review. Geen stilzwijgende overgang naar strings of integertruncate. UI formatteert BTC met maximaal acht decimalen en SAT op nul decimalen; de waarden blijven intern ongequantized. Geen afgeleide publieke BTC/EUR-prijs of P/F toevoegen: zij zijn niet nodig voor het product en niet afzonderlijk geautoriseerd.

**Hashscope:** bestaande `derived_values_sha256` blijft over vijf canonieke onderzoeksreeksen t/m expliciete cutoff. Voor publieke bytes komt de volledige artifacthash in het bestaande soort externe release-record; niet in datzelfde JSON, om een self-hashcirkel te vermijden. Een afzonderlijke hash van de geselecteerde BTC-values + maandmetadata in het kandidaatrecord voorkomt dat een gelijkblijvende numerieke hash een gewijzigde HOLD/qualityselectie verbergt.

## 7. Releasegate en behoud van bestaande goud/CBS-goedkeuring

### 7.1 Interne kandidaatdimensies

| Dimensie | Voorbeelden van toestand | Verificatie |
|---|---|---|
| Onderzoek | AVAILABLE / MISSING | Broninputs en rekencandidate |
| Economie/kwaliteit | PASS / HOLD / FAILED | Methode, kalender, qualityregels, uitzonderingen |
| Rechten | CONDITIONAL_MET / OPEN / BLOCKED | Gereviewde attestatie met concrete voorwaarden en NC-scope |
| PC-autorisatie | NOT_AUTHORIZED / AUTHORIZED_EXACT_CANDIDATE | Extern eigenaarrecord voor hash/velden/maanden |
| Publieke activering | DISABLED / ACTIVE | Exportpoort én frontendpolicy plus gecontroleerde deployment |

Geen monotoon “groen” label dat de vijf dimensies samenvoegt. Een rechtengrant is geen releasebesluit; een `publication_authorized=true` in door iemand aangeleverde JSON is geen betrouwbare autorisatie.

**INFERRED — hergebruik:** laat een productieadapter de bestaande `candidate_values(..., approved=...)` gebruiken, met identieke allowlist voor beide indicatoren en HOLD als dominante blokkade. `RELEASE_APPROVALS` blijft leeg tijdens voorbereiding. Maak een **voorgesteld** BTC-kandidaat/release-record volgens het bestaande goudrecordpatroon: kandidaat-/publieke hash, snapshotmanifesthash, CBS-inputhash, methode/quality/exceptionversies, geautoriseerde velden, exact maandenbereik plus uitzonderingen, reviewrefs, auteur/datum/besluitref en status. Geen generieke `BTC_ENABLED=true` als voldoende autorisatie.

Tijdens een latere activatie moeten explicit CLI approval, expliciete operationele enable-switch én een geldig exact eigenaarrecord overeenkomen, analoog aan de bestaande goudvoorbereiding. Gecommitte productievalidatie toetst de werkelijke bytes en het geautoriseerde record/codepin; een toevallige ontbrekende CI-env mag een reeds goedgekeurde dataset niet opnieuw vrijgeven of onverklaarbaar autoriseren. Flags openen nooit zelfstandig de gate. Nieuwe maand betekent nieuw kandidaat-/release-record; de defaultallowlist groeit niet met de datum.

### 7.2 Volledige artifacthash is gedeeld

**CONFIRMED:** bestaande goudvrijgave heeft de volledige `monthly.json`-hash in code en record gepind, naast strikte schema-/contentcontroles. Zelfs null-BTC-velden veranderen die hash. Het oude record kan daarom niet ongewijzigd als bewijs voor nieuwe volledige bytes dienen.

**INFERRED — minimale veilige oplossing bij latere activatie:**

1. Houd het bestaande goudrecord en de oude goedgekeurde JSON als onveranderlijk bewijs; geen herlabeling dat het oude besluit nieuwe bytes autoriseerde.
2. Definieer `legacy_projection`: verwijder uitsluitend root `btc` en rowkeys `btc_per_house`, `sat_per_house`, `btc_meta`; behoud alle zeven oude velden, hun waarden, rowvolgorde en canonieke legacyserialization. Bij eerste BTC-release moeten de projectiebytes exact de huidige goedgekeurde goud/CBS-payload herstellen, inclusief hash.
3. Voer de bestaande goud-/CBS-controles uit op deze projectie tegen het ongewijzigde oude goudrecord/codepin. Valideer daarnaast de volledige uitgebreide payload en BTC-selectie tegen een **nieuw exact eigenaar-goedgekeurd samengesteld artifactrecord**. Het nieuwe record bindt volledige JSON-SHA, BTC-kandidaat-SHA en legacyprojectie-SHA. De oude codepin blijft voor legacyprojectie relevant, niet als ongewijzigde pin van het nieuwe volledige bestand.
4. Wijzig de dispatch/validator alleen voor een expliciet ondersteunde BTC-contractversie en geldig nieuw record. Alle onbekende velden of ontbrekende gates blijven hard fail. “Ignore extra keys” zonder controle is niet voldoende.
5. Pas `cbs_historical_update` en boundarytests gericht aan zodat zij deze twee toestanden veilig onderscheiden; geen gaten maken in gold/raw- of BTC-withheld-tests. Bij een volgende wijziging van CBS/goud moet een nieuw passend bestaand bron-/goudbesluit worden gekoppeld; de oude projectiehash kan niet eindeloos worden hergebruikt voor veranderde niet-BTC-data.

Dit is een contract-/validatoraanpassing rond het bestaande artifactrecordpatroon, geen nieuwe release-infrastructuur. Een toekomstige engineeringreview kan expliciete repinning van één gezamenlijk record verkiezen als dat aantoonbaar eenvoudiger en even strikt is; nooit de oude volledige hashcontrole stil verwijderen. Die keuze moet bewijsbaar dezelfde niet-BTC-inhoud beschermen en aan Project Control worden teruggekoppeld.

## 8. Historische selectie en updates

### Initiële historische kandidaat

**INFERRED:** standaard `STANDARD_2014_02`, eindmaand expliciet vastgesteld op basis van de beoordeelde driebronnenvintage. 2026-08 is huidige repo-CBS-cutoff en een **voorbeeld-kandidaatgrens**, geen vrijgave. Geen rows uit bestaande kalender verwijderen: BTC vóór 2014-02 null, juni 2011 expliciet HOLD. Geen Q3-waarden meesturen om pas in UI te verbergen. Geen CBS-/gouddata of perioden vervangen.

Voor optionele vroege historie een apart PC-record met `early_history_authorized=true`, toegestane vroege maanden en prominente Q3-uitleg. Standaardview blijft 2014-02; een toggle is dan uitsluitend presentatie van al afzonderlijk geautoriseerde data. Backendautorisatie kan nooit door querystring, lokale browserstate of toggles worden uitgebreid.

### Toekomstige maandupdates

**INFERRED — proces binnen bestaande Actions:**

1. Bestaande BTC-validatieworkflow handmatig gebruiken voor acquisitie/validatie en bestaande snapshot-/baselineopties hergebruiken. Geen nieuw workflowbestand of automatische releasecron nodig.
2. Bestaande CBS-reviewworkflow blijft review-only. Combineer expliciet gekozen CBS-input met CM/ECB-vintage; nieuwe CBS-invoer moet gelijk zijn aan de publieke teller voor dezelfde goedgekeurde maand.
3. Vergelijk CM én ECB op hun oude vensters en CBS tegen de goedgekeurde CBS-inhoud. BTC-05D's CM-only maandplan is een voorselectie; ECB/CBS moeten apart slagen.
4. Nieuwe complete maand zonder historische revisie → nieuwe private kandidaat. Nog geen gepubliceerd CBS-huisbedrag, ontbrekende fixing of onvolledige BTC-maand → geen nieuw punt. Geen stille actualisering van oude gegevensstand.
5. Historische wijziging in één bron → blokkade, diff en aparte revisieacceptatie. De oude goedgekeurde payload/vintage blijft behouden. Geen historische pinmutatie door de updatejob.
6. Per maandupdate opnieuw exacte velden/maanden/candidatehash en eigenaarvrijgave zolang geen afzonderlijk begrensd delegatiebeleid is goedgekeurd. Geen impliciete autorisatie voor elke toekomstige maand.
7. Herstel/rollback gebruikt bestaande release-/commitwerkwijze en het geautoriseerde exacte bestand; rollbacktest bewijst ook CBS/goud en BTC-HOLD/nullsemantiek. Geen nieuwe `current.json`-architectuur ontwerpen.

**Artifactgrens:** de bestaande workflow uploadt een summarydirectory; de CBS-workflow uploadt reviewkandidaten. Nieuwe volledige BTC-kandidaten/snapshots moeten buiten die geüploade directories blijven. Upload alleen expliciet prijsloze BTC-checkrapporten; geen breed `RUNNER_TEMP/**` of snapshotupload in deze publieke repository.

## 9. UI-databetekenis zonder redesign

**INFERRED — minimale frontendvereisten voor latere activatie:**

- Twee keuzeopties in bestaande “Alternatieve waardering”: “BTC per gemiddeld verkochte woning” en “Satoshi per gemiddeld verkochte woning”. Gelijke economische inhoud, verschillende schaal; geen dubbeltelling als onafhankelijke indicatoren.
- Voeg uitsluitend de noodzakelijke `btc`-formatsoort/typed keys en metadatareading toe. Registry blijft during voorbereiding withheld. Een malformed/unknown BTC-block verbergt/blokkeert alleen BTC met melding; bekende legacydata blijft bruikbaar, backend weigert zo'n productieexport volledig.
- BTC standaard vanaf 2014-02 afbakenen in de BTC-view, niet door globale CBS/gouddata te filteren. Handmatige bredere datumbereiken of de bestaande preset “Alles” geven zonder vroege autorisatie geen Q3-waarden. Bij latere vroege autorisatie vereist uitgebreide historie een expliciete viewkeuze; de standaard mag niet ongemerkt “Alles sinds 2010” worden.
- Toon per geselecteerde maand de kwaliteit en reden van null; tabel toont bijvoorbeeld “Niet gepubliceerd — juni 2011” in plaats van alleen een lege cel. Behoud kalenderrows en `connectNulls=false`; filter niet eerst null-BTC-rows uit de chartdata. Browserproef met punten in mei/juli en null in juni moet twee lijnsegmenten aantonen.
- Maak Q3/Q2/Q1-kandidaat begrijpelijk als bewijsdekking, met vroege onzekerheid; geen bandbreedtes of waarschijnlijkheidspercentages verzinnen. Tooltip/tabel bevat concrete maandstatus en toepasselijke flags.
- Toon bronnen, method-ID/toelichting, NC-/licentielink, eigen bewerkingen, geen endorsement, gegevensstandbasis en laatste volledige maand. Houd goudbronnen/peildatum apart.
- Toon: “Een daling betekent minder BTC per gemiddeld verkochte woning volgens deze referentiemethode; dit zegt niet dat een identieke woning goedkoper is geworden.” Benoem nominale EUR-teller en transactiemix. Geen “betaalbaarheid verbeterd” automatisch genereren.
- Huidige globale tekst “Nog niet beschikbaar: … Bitcoin” blijft tijdens HOLD correct; pas bij echte activering gericht aanpassen. URL-/storage-state mag een withheld registry of niet-geautoriseerde maand niet omzeilen.

Geen visueel redesign, nieuwe pagina of frontendimplementatie in BTC-06A.

## 10. Test- en acceptatiecontract voor BTC-06C

**UNVERIFIED:** dit zijn voorgestelde tests, niet in deze onderzoeksfase uitgevoerd. Hergebruik bestaande `tests/test_btc_04e_cm_replay.py`, static-export-, data-quality-, frontend-series/dashboard-, CBS-safe-update- en publicatieboundarytests. Breid gericht uit, zonder bestaande grensasserties blind te verwijderen.

| # | Type | Test en concrete acceptatie |
|---:|---|---|
| 1 | Unit | H=300000, P=60000, F=1.2 → B=50000, BTC=6; exact Decimalrekenpad |
| 2 | Unit | Zelfde fixture → SAT=600000000; aparte niet-eindig/deelbaar fixture bewijst geen interne integerafronding |
| 3 | Unit | Deel USD/BTC door USD/EUR; vermenigvuldigen en inverse FX worden afgewezen door fixture/eenheidscontrole |
| 4 | Unit | Prijzen 100/200, FX 1/4 → ratio maandgemiddelden 60, dagratio-gemiddelde 75; gekozen pad geeft 60 |
| 5 | Unit | 28/29/30/31 UTC-dagen, schrikkeljaar en timestamps buiten UTC-midnight; missende dag/lopende maand niet compleet |
| 6 | Unit | Weekend/TARGET-dag zonder fixing verwacht; geen synthetische FX-waarden, deling door werkelijk fixingaantal; onverwachte werkdaggap blokkeert |
| 7 | Unit | Ontbrekende input/null blijft null; geen interpolatie, nearest join, fallback of zero-fill |
| 8 | Contract | Bron/methode/parser/quality/exception-ID ontbreekt of wijkt af → hard fail |
| 9 | Unit + contract | Exact Q3 t/m 2014-01, Q2 2014-02..2016-04, Q1_CANDIDATE vanaf 2016-05; geen Q1-auto-upgrade |
| 10 | Unit + contract | Juni 2011 beide null/HOLD, ook bij expliciete foutieve all-month allowlist; selector weigert vrijgave |
| 11 | E2E browser | Synthetische vroege view met mei/juni/juli: juni bestaat als nullrow, twee lijnsegmenten; geen lijn over juni; tooltip/tabel verklaart gat |
| 12 | Contract + E2E | Zonder exact eigenaarrecord/enable alle BTC-publicatie gesloten; vergiftigde JSON/URL/state activeert withheld reeks niet |
| 13 | Regressie contract | Bij eerste BTC-kandidaat legacyprojectie exact huidige 320 rows/sevenfields/hash; goudraw null, goudwaarden/CBS/HPI ongewijzigd |
| 14 | Contract + frontend | Oude payload zonder BTC blijft werken; bekende actieve extensie valideert; partiële metadata/nieuwe onbekende key/version/strings/bools falen |
| 15 | Integratie | Revisie CM, ECB en CBS elk afzonderlijk geïnjecteerd → geen stilzwijgende overschrijving/pinupdate; oude kandidaat intact |
| 16 | E2E | Bronlinks, licentie, C1-uitleg, USD-afgeleid, nominale teller, transactiemix, peildatum en geen endorsement leesbaar; geen rawwaarden in bronblok |
| 17 | Contract | Exact toegestane velden/maanden/cutoff en BTC-blockmetadata in release-record; aangeleverde JSON-bool alleen autoriseert niet |
| 18 | Unit + contract | Float/JSON-roundtrip blijft binnen §6-verliesgrenzen; NaN, Infinity, negatieve getallen en te grote SAT geven fail |
| 19 | Integratie offline | Bestaand snapshot + juiste verplichte CBS-bytehash replay identiek zonder netwerk; missende CBS-pin/mismatch/corrupt snapshot blokkeert |
| 20 | Contract | Numerieke values gelijk maar HOLD/qualitymetadata of bronvintage gewijzigd → hash-/releasecontrole weigert |
| 21 | E2E | BTC default 2014-02, optionele historie alleen apart bevoegd; CBS/goud behoudt bestaande volle bereik/presets |
| 22 | Integratie workflow | Private snapshot/volledige BTC-kandidaat komt niet in publieke artifacts, public directory of logs; synthetische canary bewijst allowlist |
| 23 | Integratie release | Later, na aparte toestemming: verkeerde volledige artifacthash/legacyprojectie of record → reject; rollback exact geautoriseerde oude bytes, geen herberekening uit live API |
| 24 | Regressie HOLD | Tijdens BTC-06C-voorbereiding gecommitte `monthly.json` byte-identiek aan baseline, registry withheld en `RELEASE_APPROVALS` leeg |

Het twee-dagenformulevoorbeeld is een unitfixture voor aggregatievolgorde, geen claim van een complete echte kalendermaand. Volledige-maandtests gebruiken complete synthetische maanden. Echte bronacceptatie kan niet worden vervangen door uitsluitend synthetische passing tests.

## 11. Implementatiegrenzen en resterende verificatie

**INFERRED — afgebakende BTC-06C:** kleine productieadapter/validator rond bestaande CM C1-uitvoer; private kandidaat in dit contract; gericht voorbereide frontendtypes/viewsemantiek onder withheld; hierboven genoemde tests en reviewdocumentatie. Bestaande workflows hergebruiken waar een teststap nodig is. Geen nieuwe storage, ETL-stack, scheduler, publicatiepointer, provider, live BTC-JSON of economische definitie.

**Open gates:** productie-ADR/contract/precisie/profile door PC aanvaarden; contractscope CM; exact reviewbare rekenvintage; praktische private bewaring/herstelbaarheid; gerichte gezamenlijke artifactvalidatie; expliciete eigenaarvrijgave voor toekomstige release. Geen actuele kandidaat-SHA, nieuwe source-measure-ID of rights-reviewref verzonnen. Live CI, frontendbrowser, actuele markt-/CBS-acquisitie en echte replay/restore zijn **NIET UITGEVOERD**.

## 12. Bronnen

Alle code-inspecties op [main `42b32be…`](https://github.com/storagebirddrop/Goud-btc-dashboard/commit/42b32be65f890dba8b327f2c26b6112854e7a4f4), 22-10-2026. De volledige governance-/bronnenlijst staat ook in de ADR-draft; deze contractkeuzes berusten vooral op:

- [static_export.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/static_export.py), [data_quality.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/data_quality.py), [cbs_historical_update.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/cbs_historical_update.py).
- [monthly.json](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/public/data/monthly.json), [series.ts](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/src/series.ts), [main.tsx](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/frontend/src/main.tsx).
- [BTC-05D](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/docs/research/BTC_05D_VINTAGE_REPLAY.md), [btc_04e_cm_replay.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tools/btc_04e_cm_replay.py), [source_pins.json](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/data/fixtures/btc04e/source_pins.json), [hist_model.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/hist_model.py).
- [Goud-release-record](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/data/gold-release-record.json), [goud-codepin](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/etl/gold_publication_candidate.py).
- [Publication boundary tests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_bitcoin_publication_boundary.py), [frontend series tests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_frontend_series.py), [frontend dashboard tests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_frontend_dashboard.py), [static export tests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_static_export.py), [safe CBS update tests](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/tests/test_cbs_safe_update.py).
- [BTC-workflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/.github/workflows/btc-04e-cm-replay.yml), [CBS-workflow](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/42b32be65f890dba8b327f2c26b6112854e7a4f4/.github/workflows/update-static-data.yml).
- BTC-05A-rechtenrapport, lokaal aanwezig en gelezen; geen fictieve GitHub-link. De bron-/licentie-URLs in het schemavoorbeeld volgen dat bestaande rechtenkader, geen nieuwe licentieaudit.
