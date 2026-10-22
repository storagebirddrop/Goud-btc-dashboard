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

## Update v2.2 — `btc-monthly/1` private kandidaat (geaccepteerd ontwerp, 2026-10-22; niet gepubliceerd)
**Status:** het ontwerp is door Project Control geaccepteerd (zie ADR-012 in [DECISIONS.md](DECISIONS.md)); de implementatie is een **private kandidaat**. De publieke `monthly.json` bevat **geen** BTC-veld en is byte-identiek aan de goedgekeurde goud/CBS-payload (SHA-256 `1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd`). Het BTC-06A-conceptdatacontract was niet in de repository beschikbaar; onderstaande vorm volgt de opdrachttekst en de bestaande vocabulaire van dit document en moet door Project Control met dat concept worden gereconcilieerd.

- **Maandvelden** (na de zeven legacyvelden, in deze volgorde): `btc_per_house` (BTC per gemiddeld verkochte woning), `sat_per_house` (bestaande veldnaam; exact `btc_per_house x 100000000`), `btc_meta` = `{status, quality, missing_reason, exception}`.
- **`btc_meta.status`:** `CANDIDATE` (waarde aanwezig), `HOLD` (absolute uitzondering, waarde `null`; alleen 2011-06 met `exception=HOLD_2011_06`), `MISSING` (waarde `null` met verplichte `missing_reason` uit de lijst hierboven). `quality`: `Q3`, `Q2`, `Q1_CANDIDATE` of `null` vóór 2010-08. Numerieke waarden komen uitsluitend voor vanaf 2014-02 (`CANDIDATE` met `Q2`/`Q1_CANDIDATE`); eerdere maanden zijn `null` (`NOT_APPLICABLE` vóór 2010-08, `NOT_PUBLISHED` daarna).
- **Rootblok `btc`:** `contract="btc-monthly/1"`, `status="PRIVATE_CANDIDATE"`, methode-, parser-, uitzonderings- en kwaliteitsversies, `snapshot_id`, `derived_values_sha256`, `source_windows`, `cbs_input_sha256`, `legacy_sha256`, `first_value_month="2014-02"`, `early_history_numeric=false`, `publication_authorized=false`, `release_gate="CLOSED"`, `sources`.
- **Legacyprojectie:** een kandidaat moet terugprojecteerbaar zijn naar exact de zeven legacyvelden; de gereserialiseerde bytes moeten gelijk zijn aan de goedgekeurde payload en aan de vastgepinde hash. Bestaande hashcontroles zijn niet versoepeld.
- **Precisie:** waarden zijn JSON-getallen (één dubbele-precisie-conversie van de exacte Decimal-waarde); de exacte decimalen staan in een privé-zijbestand en `sat_per_house` is daarin exact `btc_per_house x 10^8`. Strings, `NaN`, `Infinity`, booleans en niet-positieve getallen worden geweigerd.
- **Release:** een samengestelde publicatie vereist een exact eigenaar-goedgekeurd artifactrecord (SHA-256 van precies die samengestelde bytes en van de legacyprojectie); het register is leeg, dus de gate is gesloten. Een JSON-veld verleent nooit bevoegdheid.
- **Niet uitgevoerd / OPEN:** browser-, restore- en live-releaseproeven; bronrechten en attributie; duurzame opslag van historische bronbytes; UI-activering. Deze update implementeert niets van het v2-releasemanifest.
