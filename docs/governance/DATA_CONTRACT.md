# DATA_CONTRACT — JSON v2 ontwerp en validatievoorwaarden

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Belangrijk: v2 is `PROPOSED`, niet het huidige JSON-schema
De bestaande `frontend/public/data/monthly.json` gebruikt een ouder object met `data` en velden zoals `period`, `house_eur`, `hpi`, `gold_eur_oz`, `gold_grams_per_house`, `gold_index`, `hpi_index`. Het onderstaande **nieuwe** contract mag niet als reeds geïmplementeerd worden beschreven. Migratie vereist code, tests en frontend-aanpassing.

## Release-manifest (`PROPOSED`)
```json
{
  "schema_version": "2.0.0",
  "release_id": "example-immutable-id",
  "generated_at_utc": "2026-10-17T12:00:00Z",
  "source_commit": "FULL_40_CHAR_COMMIT_SHA",
  "methodology_version": "2.0",
  "dataset_path": "monthly.json",
  "dataset_sha256": "64_HEX_CHARACTERS",
  "source_snapshots": [
    {"source_id": "cbs-85773NED", "raw_sha256": "64_HEX_CHARACTERS", "retrieved_at_utc": "2026-10-17T12:00:00Z"}
  ],
  "license_status": "approved",
  "coverage": {"start_month": "2000-01", "end_month": "2026-08"}
}
```
De voorbeeldstrings zijn **placeholders, geen geldige SHA's of bewijs van licentiegoedkeuring**.

## Maandobservatie (`PROPOSED`)
```json
{
  "period": "2020-01",
  "metrics": {
    "nl_house_avg_eur": {"value": 315000.0, "unit": "EUR/home", "quality": "OBSERVED", "missing_reason": null, "source_id": "cbs-85773NED"},
    "nl_hpi": {"value": 100.0, "unit": "index_2020_100", "quality": "OBSERVED", "missing_reason": null, "source_id": "cbs-85773NED"},
    "btc_per_avg_sold_home": {"value": null, "unit": "BTC/home", "quality": "MISSING", "missing_reason": "UNVERIFIED_SOURCE", "source_id": null}
  }
}
```
**Alle numerieke waarden in dit voorbeeld zijn fictief en mogen nooit als historische observatie worden geïmporteerd.**

## Validatie-invarianten (`PROPOSED`)
1. `schema_version` verplicht, semver; frontend weigert onbekende major versie.
2. `release_id` immutable; `current.json` verwijst naar exact één release.
3. Dataset-SHA256 moet matchen; manifest bevat commit-SHA en methodeversie.
4. Per `(period, metric)` exact één record; `period` = `YYYY-MM`, chronologisch en uniek.
5. Waarde is finite en positief voor prijzen/ratio's; geen `NaN`, `Infinity`, stringnumeriek of verborgen null-naar-nul conversie.
6. `quality=OBSERVED|DERIVED|MISSING|MODELED`; bij `MISSING` waarde `null` en geldige `missing_reason`.
7. Redenen: `NOT_APPLICABLE`, `NOT_PUBLISHED`, `SOURCE_UNAVAILABLE`, `INCOMPLETE_PERIOD`, `FAILED_VALIDATION`, `LICENSE_BLOCKED`, `UNVERIFIED_SOURCE`.
8. `DERIVED` heeft dependency/source-referenties en formuleversie; geen berekening bij ontbrekende input.
9. Eenheid en valutadimensie per metriek vast; HPI mag nooit als EUR worden gelabeld.
10. Bij dagelijkse aggregatie zijn `expected_days`, `observed_days`, `calendar_id`, `aggregation_method`, `timezone` verplicht in metadata.
11. Alle reeksen binnen één frontendview behoren tot dezelfde `release_id`.
12. Release faalt bij niet-goedgekeurde bronlicentie, bronhashmismatch of ontbrekende vereiste kernserie.

## Migratieplan
- Voeg schema- en fixturetests toe; huidige CSV/JSON-export blijft bestaan tijdens overgang.
- Genereer v2 naast v1; vergelijk overlappende CBS-waarden en totalen.
- Update frontend met release-manifest, statuslabels en null-handling.
- End-to-end test op Cloudflare Pages, inclusief caches, oude release, rollback en pointerconsistentie.
- Schakel pas daarna v1 uit via apart besluit.

## Compatibiliteit
Verander nooit stilzwijgend betekenis van `house_eur` of `hpi`. In de frontend altijd bron en prijsmaat tonen. `release_id` is identificatie, geen tijdstempelgarantie.

## Update v2.1 — BTC audit- en provenance-eisen (`PROPOSED`)
De read-only audit publiceert **geen** koerswaarden. De rapportvelden omvatten `source`, `status=audit_only`, `series.BTC.{daily_rows,valid_unique_days,first,last,missing_days}`, `series.EURUSD`, `btc_fx_same_day_overlap`, `btc_days_without_same_day_fx`, `issue_count`, `publication_approved=false`.

Voor latere prijsreeksen verplicht vastleggen: `source_id`, `source_repository`, `source_ref`/commit, oorspronkelijke quote (`BTC/USD`), dagkoerssemantiek (`daily_close`), FX-bron en notatie (`USD_per_EUR`), observatiedatum/tijdzone, FX-matchregel, bron- en transformatiehash, verwachte/werkelijke kalenderdekking, ontbrekende-dagenreden, `license_status`, `publication_approved`. **Geen nieuwe velden zijn al in de publieke monthly.json geïmplementeerd.**

## Update v2.2 — `btc-monthly/1` (door Project Control aanvaard ontwerp, 2026-10-22; niet gepubliceerd)
**Status:** ontwerp aanvaard (zie ADR-012 in [DECISIONS.md](DECISIONS.md); brondocument `docs/research/btc-06/BTC-06_DATA_CONTRACT_DRAFT.md`, ongewijzigd opgenomen). Implementatie: `etl/btc_contract.py` (validator) en `tools/btc_06c_candidate.py` (private preview), **uitsluitend privé**. De publieke `monthly.json` bevat **geen** BTC-veld en is byte-identiek aan de goedgekeurde goud/CBS-payload (SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`). Dit vervangt niets van het v2-releasemanifest hierboven.

- **Maandvelden** (na de zeven legacyvelden, in deze volgorde): `btc_per_house` (BTC/home), `sat_per_house` (bestaande veldnaam, satoshi/home), `btc_meta`. Beide waarden aanwezig of beide `null`; positieve eindige JSON-numbers; geen strings, booleans, `NaN`, `0`.
- **`btc_meta`** = `{quality, status, missing_reason, flags}` (deze volgorde). `quality`: `Q3`, `Q2`, `Q1_CANDIDATE`, `null` vóór 2010-08. **`status` (publieke enum): `PUBLISHED`, `WITHHELD`, `MISSING`.** `PUBLISHED` vereist twee waarden en `missing_reason=null`; de andere statussen twee nulls en een reden. Private kandidaatstatussen staan uitsluitend in het private zijbestand en nooit in dit veld.
- **`missing_reason` ↔ status:** `RESEARCH_ONLY_HOLD`, `NOT_AUTHORIZED_PERIOD`, `PUBLICATION_NOT_AUTHORIZED`, `RIGHTS_NOT_CLEARED` → `WITHHELD`; `BEFORE_SUPPORTED_MONTH`, `INCOMPLETE_PERIOD`, `SOURCE_NOT_PUBLISHED`, `SOURCE_UNAVAILABLE`, `FAILED_VALIDATION` → `MISSING`. Hoofdreden bij samenloop: juni-HOLD, vóór ondersteunde aanvang, buiten autorisatie, rechten-/releasegate, concrete input.
- **`flags`:** gesorteerde unieke lijst uit het register `EARLY_HISTORY_LIMITED_PROVENANCE` (maanden 2010-08..2014-01), `REVIEW_2015_05`, `REVIEW_2015_08`, `REVIEW_2017_12` (elk alleen op de eigen maand; bewijs in `docs/research/BTC_02_HISTORY.md`). Geen vrije tekst.
- **Juni 2011:** altijd `WITHHELD` / `RESEARCH_ONLY_HOLD`, twee nulls, kwaliteit `Q3`, in de continue kalender (record niet verwijderen); geen autorisatie, allowlist of herlabeling heft dit op.
- **Rootblok `btc`** (exacte sleutels): `contract_version="btc-monthly/1"`, `method_id`, `parser_version`, `quality_version`, `exception_policy_version`, `units`, `coverage` (`supported_from=2010-08`, `default_from=2014-02`, `authorized_from/through`, `early_history_authorized`), `release` (`id`, `decision_ref`, `publication_authorized`), `provenance` (`snapshot_format`, `snapshot_id`, `snapshot_manifest_sha256`, `calculation_git_commit`, `cbs_input_sha256`, `cm_daily_sha256`, `ecb_daily_sha256`, `source_windows`, `derived_values_sha256`, `derived_cutoff`, `cm_raw_retention=RETAINED`, `ecb_raw_retention=NOT_RETAINED`, `vintage_reference_utc`, `time_basis=CM_ACQUISITION_REFERENCE`), `sources` (Coin Metrics, ECB, CBS met licentie- en attributievelden) en `rights` (`CONDITIONAL`, `review_ref`, `scope=NON_COMMERCIAL`, `conflicting_contract_check`). Placeholders, ontbrekende hashes en een onware retentiestatus worden geweigerd; de feitelijke provenancegrenzen (ECB-bytes niet bewaard, geen gelijktijdige driebronnenacquisitie) blijven zichtbaar.
- **Preview versus actief:** `publication_authorized=false` = private preview (alle BTC-waarden `null`, standaardprofielmaanden `WITHHELD` / `PUBLICATION_NOT_AUTHORIZED`, geen release-id of rechtenreview); `true` is alleen geldig samen met een exact eigenaarrecord. De kandidaatwaarden zelf staan in een privé-zijbestand (`private_state` = `CANDIDATE_VALUE`) en nooit in een publiek artifact.
- **Precisie:** canonieke Decimal (34 cijfers); publieke getallen zijn één float-conversie. Per veld verlies < 0,25 satoshi-equivalent, publiek BTC x 1e8 binnen 0,5 satoshi van publiek SAT, SAT < 2^53; export faalt bij overschrijding. Dit is geen economische nauwkeurigheidsclaim.
- **Legacyprojectie en record:** verwijdering van root `btc` en de drie nieuwe rowkeys moet exact de goedgekeurde legacybytes (en hash) herstellen. Een samengestelde release vereist een nieuw eigenaarrecord met hash van het samengestelde bestand, hash van de BTC-selectie (waarden + maandmetadata), legacyprojectiehash, snapshot-manifest- en CBS-hash, versies, geautoriseerde velden en exacte maanden (uitzondering juni 2011), rechtenreferenties en besluitreferentie. Het register is leeg; elke afwijking weigert.
- **Niet uitgevoerd / OPEN:** browser-, restore- en live-releaseproeven; bronrechten en attributie (BTC-05A niet in de repository, geen vrijwaring); duurzame opslag; PC-BTC06-6-voorwaarden; UI-activering.
