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
