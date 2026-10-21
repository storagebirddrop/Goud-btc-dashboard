# VERIFICATION_LOG — bewijsregister en auditgrenzen

**Versie:** 2.1 · **Peildatum:** 2026-10-17 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Uitvoering 2026-10-17
Via verbonden GitHub-connector zijn repository en onderstaande bestanden op de standaardbranch gelezen. `VERIFIED_REPO` betekent **bestand/inhoud gezien**, niet live data- of workflow-uitvoering. Er is **geen** workflow-log, live CBS API-resultaat of Cloudflare deploy geverifieerd. File-blob-SHA is **niet** de commit-SHA van de branch.

| Bewijs-ID | Bestand / controle | Blob SHA of resultaat | Wat is bewezen |
|---|---|---|---|
| V-001 | [Repository](https://github.com/storagebirddrop/Goud-btc-dashboard) | default `main`, publiek gevonden | repo bestaat |
| V-002 | [README.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/README.md) | `1a1a12d4fedb9a8857cae6c62a6c05145f64110d` | project is early-development, statische Pages-voorkeur |
| V-003 | [docs/cbs-ingestion.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/cbs-ingestion.md) | `7653ae7eb87b2889862750f8262f8e6ebfb850e4` | repo documenteert CBS `85773NED` en beide maten |
| V-004 | [etl/sources/cbs.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/etl/sources/cbs.py) | `f3308307e9e8b776fa9eddc58adb72d53b27fadb` | OData adapter, maandregex, validatiecode |
| V-005 | [data/cbs-housing.csv](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/data/cbs-housing.csv) | `68a452c2b0ce459a1b0ef3a7f0d3587121dc962b` | CSV aanwezig, beginregels gecontroleerd |
| V-006 | [frontend/public/data/monthly.json](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/frontend/public/data/monthly.json) | `78a7cd63f10b90d739a5cd5c3722808221cd2f5b` | JSON aanwezig, beginrecords en gold-null |
| V-007 | [docs/static-pipeline.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/static-pipeline.md) | `a4e8909fe192b2c78624a7b92fec0ea48d75e3db` | beoogde Pages pipeline |
| V-008 | [.github/workflows/ci.yml](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/.github/workflows/ci.yml) | `77b4ff0c8c50dcd003623131d2dfdbecf415e3e4` | test- en buildstappen geconfigureerd |
| V-009 | [.github/workflows/update-static-data.yml](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/.github/workflows/update-static-data.yml) | `4310a57450c2ad36bb40c650ec1fcaf65ec62b2f` | update-workflow bestaat; triggers geconfigureerd |
| V-010 | [.github/workflows/bitcoin-backfill.yml](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/.github/workflows/bitcoin-backfill.yml) | `797aa8e04cb209957968eb739a4d0f8344be1940` | handmatige BTC validatie, artifact only |
| V-011 | [etl/sources/coinmetrics.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/etl/sources/coinmetrics.py) | `7a9ad61c5ff08d11e9341fb86f6696aa5c0296af` | EUR/USD referentieadaptercode |
| V-012 | [docs/coinmetrics-adapter.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/coinmetrics-adapter.md) | `f1db3c06238cc6866689aa541d2f2005ef75f004` | repo zegt niet productieverbonden |
| V-013 | [docs/data-quality.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/data-quality.md) | `a1d27a531a8322f0ff3d3d5a26f7041d642327c6` | QA-doelen en beperkingen gedocumenteerd |
| V-014 | [docs/methodology.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/methodology.md) | `95ccca7e23a217443e4f1672dce4c4dd611c31a1` | methodologische bronafbakening |
| V-015 | [docs/data-sources.md](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/docs/data-sources.md) | `ed3823d18c6d49ef3d382a7652795a30cac422bc` | CBS/ECB identifiers gedocumenteerd |
| V-016 | [etl/static_export.py](https://github.com/storagebirddrop/Goud-btc-dashboard/blob/main/etl/static_export.py) | `e91468f31a34c7423a3d98fbdfb07e61aae076b3` | exportcode aanwezig |

## Niet geverifieerd — expliciet open
- **Branch commit-SHA** en of alle bovengenoemde blobversies tot exact dezelfde tree behoren.
- **320-maandenclaim**: CSV/JSON bestaan; er is geen volledige telling/vergelijking uitgevoerd.
- Laatste **CI-run** groen/rood; exacte run-ID, joblogs, testsuites, artifact-integriteit.
- CBS API live antwoord, licentievoorwaarden op peildatum, herzieningen en externe ankerpunten.
- Goud- en BTC-data, toegestane herdistributie, end-to-end BTC backfill, Coin Metrics-faaloorzaak.
- Cloudflare Pages deployment, productie-URL, cachegedrag, rollback.
- v2-schema en atomische releases zijn **ontwerpen**, geen implementaties.

## Vereiste volgende verificatie
1. Leg volledige `main` commit-SHA vast en lees workflow runs + joblogs; registreer datum, URL, status en failure.
2. Download volledige committed CSV/JSON; tel per reeks en maand, controleer alle waarden en export-determinisme.
3. Doe CBS live bron-spotchecks (oude, recente en revisiemaand).
4. Run BTC-workflow met gedocumenteerde recente én historische vensters, controleer API payload en coverage.
5. Vergelijk goud/BTC met onafhankelijk geverifieerde bronnen en check licenties.
6. Test publicatie, manifest-hashes, frontend-consistentie en rollback.

## V-NEW — geverifieerde uitvoering en mergehistorie (2026-10-17)
| Bewijs-ID | Bron | Resultaat / grens |
|---|---|---|
| V-101 | [BTC trading-audit, run 39050246824, job 117447184267](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39050246824) | `success`; BTC 4.409 dagelijkse positieve unieke waarden van 2014-09-17 t/m 2026-10-12, 0 ontbrekende kalenderdagen, 0 fouten |
| V-102 | Dezelfde audit | EURUSD 4.368 dagelijkse waarden 2010-01-01 t/m 2026-10-12; 3.142 overlapdagen; 1.267 BTC-dagen zonder dezelfde-dag FX; FX heeft niet dezelfde kalender als BTC |
| V-103 | [PR #35](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/35) | auditcode en handmatige Actions-workflow squash-merged; mergecommit `7e9126a99036f2038dc99505c154ded8da85bd54`; voorafgaande CI: 116 passed, 3 skipped; frontend success |
| V-104 | [PR #36](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/36) | bronbesluit gedocumenteerd, oude Coin Metrics-catalogusworkflow verwijderd; CI `success` run 39050453505; squash-merge `aff32f3da65778288677606e37a93c9982e5cd34` |

**Auditgrens:** rapport is read-only en bevat alleen aggregaten. `publication_approved=false`; geen onafhankelijke koersbenchmark, herpublicatietoestemming of BTC/EUR-productieserie bewezen. De v2.0-verklaring dat *geen enkele* workflow-run geverifieerd was is door deze specifieke bewijsstukken achterhaald, niet door een algemene productievalidatie.
## V-NEW — governance-integratiecontrole (2026-10-17)
| Bewijs-ID | Bron | Resultaat / grens |
|---|---|---|
| V-201 | GitHub `main` branch API | HEAD `ef5a5e1007affe093d6187631e79c28ed4850326` op inspectiemoment; geen garantie voor latere HEAD |
| V-202 | GitHub PR API #37–#40 | #37–#39 merged; #40 open, niet merged |
| V-203 | [CI 39054825208](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39054825208) | push CI success op `ef5a5e1`; geen bewijs van live data of deployment |
| V-204 | [BTC audit 39054825172](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39054825172) | audit success op `ef5a5e1`; log bevat 8 ontbrekende FX-weekdagen en age-cap statistieken; publicatie blijft niet goedgekeurd |
| V-205 | Repository tree en bestaande docs | technische docs onder `docs/`; centrale v3 governancebestanden ontbraken vóór deze PR |

**Verificatiegrens:** De oorspronkelijke V-001–V-104 registraties zijn historische bewijsclaims en worden niet met terugwerkende kracht herzien. Governance-PR CI en branch protection moeten nog afzonderlijk worden gecontroleerd.

## V-301–V-306 — onafhankelijke governance-PR audit (2026-10-17)

| ID | Controle | Feitelijke uitkomst |
|---|---|---|
| V-301 | [PR #41](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/41) files API | 20 bestanden bij initiële audit: 18 toegevoegd, 2 gewijzigd, geen verwijderingen; geen ETL/frontend-productiecodewijzigingen; branch `docs/governance-v3-integration` |
| V-302 | [PR #37](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/37) t/m [#40](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/40) | #37–#39 merged, #40 open en niet gewijzigd door governance-PR |
| V-303 | GitHub branches/main API en rulesets API | `protected=false`, `protection.enabled=false`, lege rulesetslijst; branch protection detail-API gaf 403 (connectorbeperking). Geen verplichte reviews uit publiek zichtbare regels afgeleid; repositorybeheerder kan extra beleid hebben |
| V-304 | [CI-run 39056894346](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39056894346) | `success` op eerdere PR-HEAD `2a4212bf5`; niet geldig als bewijs voor latere commits |
| V-305 | [CI-run 39057613139](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39057613139) | `failure`: letterlijke `\\n` in regressietest veroorzaakte Python `SyntaxError`; gecorrigeerd |
| V-306 | [CI-run 39057669726](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39057669726) | `failure`: letterlijk `\\n` in commentaar schakelde de return/semantische gate uit (`check() is None`); gecorrigeerd |

**Auditstatus:** Bewijs van Python-, frontend- en documentatiecontroles op de **definitieve** HEAD moet afzonderlijk via de laatste CI-run worden vastgelegd. De mislukte runs zijn niet genegeerd of als geslaagd voorgesteld. Geen lokale volledige repositorytest uitgevoerd.

## V-3.1 integratie — nieuwe bewijsgrens (2026-10-17)
- `VERIFIED_REPO`: PR #41 `open`, `draft`, vóór integratie HEAD `7ae264036ef8d5d97277e5095e231181e3fe1d96`; main `ef5a5e1007affe093d6187631e79c28ed4850326`.
- `VERIFIED_REPO`: PR-bestandslijst vóór v3.1: 20 bestanden; geen productiecodewijzigingen.
- `VERIFIED_RUN`: [39057761181](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39057761181) `success` voor v3.0, **niet** voor v3.1.
- `UNVERIFIED_ACCESS`: beschermingdetail-API 403; zichtbare `protected=false`/lege rulesets geen alomvattende garantie.
- `PENDING`: nieuwe definitieve GitHub Actions-resultaten, expliciete mergeautorisatie en resource-sync na merge.

## V-401–V-404 — PR #42 afronding en CBS-bronauditstart (2026-10-18)
| ID | Direct bewijs | Resultaat / grens |
|---|---|---|
| V-401 | [PR #42](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/42), GitHub PR/commit API | `merged=true`, `closed`, squashcommit `e6b5a3b20109683ced7fdc380d1a4b02598a9e7a`; parent `483b06d3f4246372534aa0e9d8821591a14c35b8`; uitsluitend twee CSV-validatie-/testbestanden |
| V-402 | [CI 39122777887](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39122777887) en [smoke 39122777891](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39122777891) | Beide `success` op `3e63aa7e3f19aab7303c85624198023db741725b`; pytest `124 passed, 3 skipped`; frontend geslaagd; drie parametrische CSV-gevallen in code aanwezig; CI toont geen afzonderlijke testnamen |
| V-403 | [Post-merge CI 39123914206](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39123914206), [static update 39123914043](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39123914043) | Beide `success` op `e6b5a3b20109683ced7fdc380d1a4b02598a9e7a`; geen live externe bronsteekproef aangetoond |
| V-404 | [PR #43](https://github.com/storagebirddrop/Goud-btc-dashboard/pull/43) | Aparte read-only CBS-bronaudit in ontwikkeling. Onafhankelijke historische live steekproeven `UNVERIFIED` tot uitvoering workflow en inspectie artifact; geen datawijziging of publicatieautorisatie |

### V-405 — onafhankelijke live CBS-steekproef (2026-10-18)
- `VERIFIED_RUN`: [CBS spot-check run 39124068286](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124068286) `success` op PR #43 commit `e3a3db5c20cf799df1e53432ad3361f2d41416e5`. Job `spotcheck` geslaagd; opdracht `python -m etl.cbs_source_spotcheck --output cbs-source-spotcheck.json` met daadwerkelijke live CBS OData requests uitgevoerd.
- `VERIFIED_RUN`: [diagnostisch artifact 12135690315](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124068286/artifacts/12135690315) geüpload (471 bytes ZIP). Het script faalt als een van de acht geselecteerde observaties afwijkt of ontbreekt; succesvolle run ondersteunt dus `all_match=true` voor januari 2000, 2010, 2020 en 2025, beide reeksen. Artifactinhoud is **nog niet afzonderlijk uitgelezen**; geen exacte bronwaarden of revisieclaims daaruit afgeleid.
- `UNVERIFIED`: alle overige maanden, latere revisies en een tweede **onafhankelijke bron** buiten CBS. Dit is een vergelijking van committed waarden met actuele **primaire CBS-bron**, niet een externe alternatieve prijsbron.

### V-406 — volledige historische CBS-livevergelijking (2026-10-18)
- `VERIFIED_RUN`: [CBS full-history run 39124817771](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124817771) `success` op `3aa3994b2aa04d002c429e9365f6d5481b27ef52`. Het voorafgaande diagnostische [runlog 39124782677](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124782677) vermeldt `checked_months=320`, `checked_observations=640`, `MATCH=640`, `complete=true`, `all_match=true`, `status=PASS`; de run zelf faalde toen door een technische scriptfout, die daarna is hersteld. De geslaagde definitieve run bevestigt de reparatie.
- `VERIFIED_RUN`: [CI 39124817780](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39124817780) `success` op dezelfde SHA. Diagnosevenster 2000-01 t/m 2026-08; 2 CBS-reeksen, geen geconstateerde verschillen. Niet bewezen: historische revisiegeschiedenis, externe alternatieve bron, of toekomstige data.

### V-407 — onafhankelijke PR #43 failure-mode review (2026-10-18)
- `VERIFIED_REPO`: audit-PR `#43` had een fail-open exitpad: `status=DIFFERENCES` gaf proces-exitcode 0 bij gedeeltelijke live CBS-data of waardeafwijking. De code is gecorrigeerd: uitsluitend `PASS` mag exitcode 0 geven; `DIFFERENCES` en `INCOMPLETE` geven nonzero. Rapport blijft beschikbaar via `if: always()` artifact-upload met `if-no-files-found: error`.
- `VERIFIED_REPO`: CLI-regressietests toegevoegd voor CBS-uitval, ontbrekende live-maat en afwijkende live-waarde; controle op nonzero exit, rapportstatus en `publication_approved=false`. Geen bronwaarden of economische methoden gewijzigd.
- `VERIFIED_RUN`: [historische audit 39126588171](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39126588171) `success` op `4efb74375b719da68ea6052fee31186dc716569e`. CI op dezelfde SHA dient apart gecontroleerd te worden; eerdere runs zijn geen bewijs voor later gewijzigde commits.

### V-GOLD-04 — live productieverificatie na GOLD-03 (2026-10-21): NOT VERIFIED
- `VERIFIED_RUN`: [GOLD-04 live-run 39567965613](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39567965613) en [39568067837](https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39568067837) (read-only GET's vanaf een GitHub-runner, circa 7–9 minuten na de merge van PR #86, mergecommit `06b240a9a5ecfd398f8b464f0c222a818ab30884`). De agent-sandbox bereikt `goud-btc-dashboard.pages.dev` niet (netwerkbeleid), daarom is de controle als workflow uitgevoerd.
- `VERIFIED_RUN`: productie serveert **niet** de geautoriseerde release: `monthly.json` is 45.212 bytes met sha256 `bc15f3bd…c78e` (de pre-release null-goud JSON), goudvelden 0/320 gevuld; CBS-velden komen wel overeen met de committed CSV (320 maanden). De geserveerde bundel (`index-CSGmVxEd.js`) bevat de GOLD-03 bronteksten niet en ook niet de DASH-01/DASH-02-interface (`Alternatieve waardering`, `Toon als tabel`); verwachte assetnaam van een verse build is `index-DYIm6jk6.js`.
- `UNVERIFIED`: oorzaak. Geen Cloudflare-deploystatus beschikbaar via GitHub (geen deployment- of check-run van Cloudflare op de commit). Mogelijkheden: build faalt of staat uitgeschakeld in het Cloudflare Pages-project, productiebranch/rootdirectory/buildcommando wijkt af van `docs/static-pipeline.md`, of een vertraagde/vastgelopen deployment sinds vóór DASH-01. Controle in het Cloudflare-dashboard (Deployments, build log) is nodig.
- `RESULT`: GOLD-04 blijft `NOT VERIFIED` tot productie de release `1afb0bf9…91d8cd` serveert en de browsercontrole (desktop 1280 px, mobiel 375 px) slaagt. Het script `tools/gold_04_live_verify.py` met `.github/workflows/gold-04-live-verify.yml` is herhaalbaar.
