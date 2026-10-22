# HANDOVER — sessieoverdracht

Dit is een invulbaar sjabloon, **geen actuele projectstatus**. Ververs na elke relevante sessie en controleer opnieuw bij de volgende start.

- Vastgelegd op (UTC): [tijd]
- Repository / branch / HEAD: [gecontroleerde waarden]
- Actieve taak en doel: [tekst]
- Goedkeurde grenzen / relevante ADR's: [verwijzingen]
- Gewijzigde bestanden: [paden]
- Uitgevoerde commando's en uitkomsten: [bewijs]
- CI-run / commit waarop die betrekking heeft: [link of NIET UITGEVOERD]
- Data-integriteitsresultaten: [resultaten]
- Bekende fouten en geteste hypothesen: [kort]
- Openstaande inhoudelijke beslissingen: [alleen echte rode besluiten]
- Eerstvolgende autonome actie: [concreet]
- Status: `IN_PROGRESS` / `BLOCKED` / `READY_FOR_REVIEW` / `DONE`

Bij nieuwe sessie: verifieer branch, HEAD, CI en open PR's; neem dit document niet klakkeloos als actuele waarheid over.

## Sessieoverdracht — 2026-10-18 (audit PR #43)
- `VERIFIED_REPO`: PR #42 merged naar main `e6b5a3b20109683ced7fdc380d1a4b02598a9e7a`.
- `VERIFIED_RUN`: post-merge CI 39123914206 en update-static 39123914043 success.
- Actieve taak: PR #43 read-only CBS live bronsteekproeven, gescheiden van PR #42.
- Nog `UNVERIFIED`: echte historische bronvergelijkingen, eventuele revisies, artifact en PR #43 CI.
- Volgende stap: controleer CI op definitieve PR #43 HEAD, voer handmatige bronsteekproefworkflow uit, analyseer verschillen; geen stille data-update.
- Geen autorisatie om PR #43 te mergen; PR #40 buiten scope.

## Auditvoortgang — 2026-10-18 (PR #43)
- `VERIFIED_RUN`: historische CBS-bronvergelijking 39124817771 en CI 39124817780 geslaagd op `3aa3994b2aa04d002c429e9365f6d5481b27ef52`.
- Diagnose: 320 maanden (2000-01–2026-08), 640/640 exacte matches met actuele officiële CBS OData; geen gaps in gecontroleerd venster.
- Audit bewijst geen historisch revisieverloop zonder oudere CBS-snapshots. Geen productiebronwaarden gewijzigd.
- Volgende stap: einddiff en CI na deze documentatiecommit verifiëren; PR #43 ter review aanbieden, niet mergen zonder aparte autorisatie.

## Sessieoverdracht — 2026-10-22 (na BTC-03 merge)

- Vastgelegd: 2026-10-22; repository `storagebirddrop/Goud-btc-dashboard`; geverifieerde `main` HEAD `4758e251ac1c5ad0216da38a8d1cc0abca7ac4cd`.
- **Status: DONE** HIST-09 (PR #91), HIST-10 (PR #92) en BTC-03 (PR #93) squash-merged met groene PR-CI; uitsluitend onderzoeksfundament. De afzonderlijke merge-SHA's staan in `PROJECT_STATUS.md`.
- **Goedgekeurd voor research, niet productie:** HIST-10 `HIST10_M1_V1` en BTC-03 `BTC03_A1_C1_V1`; BTC-03 Q1 Bitstamp EUR-native vanaf 2016-05, Q2 USD-afgeleid vanaf 2013-07 met voorlopige liquiditeitsdrempel, Q3 vroeg/thin/archive apart.
- **Data-integriteit:** NVM mediane woningprijs 1975-2000 ≠ CBS gemiddelde woningprijs 1995+; geen splice; NVM/BTC-overlap = 0; bronvenster-hashes en methodestatus genoteerd in `data/fixtures/hist10/source_pins.json` en `data/fixtures/btc03/source_pins.json`. Exacte oude bronbytes worden niet door hashes bewaard.
- **Publicatiegrens:** bestaande GOLD-03/04 ongewijzigd; historische goud-, NVM-, BTC- en satoshireeksen niet vrijgegeven. Publicatie-allowlist research leeg. Geen wijziging aan productie-ADR's door deze overdracht.
- **Open besluiten:** source-specific rights, BTC productiebron en kwaliteitsstart, publieke visualisatielabels, data-contract/release-aanpak. `PROJECT_STATUS.md` geeft de actuele gates.
- **Volgende autonome stap:** Project Control maakt een publicatie-readiness matrix, gescheiden voor (a) historische NVM/goud, (b) CBS/goud vóór 2000, (c) CBS/BTC Q1 vanaf 2016-05, (d) oudere BTC Q2/Q3. Advies per reeks GO/HOLD en expliciete eigenaarbesluiten voorbereiden. Geen publicatie of merge zonder autorisatie en groene CI.
- **Deze overdracht:** documentatie-only op een afzonderlijke PR; CI-status van die nieuwe PR moet afzonderlijk worden geverifieerd. Voor gebruik in een andere chat: altijd actuele HEAD en checks opnieuw ophalen.
