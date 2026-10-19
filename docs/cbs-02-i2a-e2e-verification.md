# CBS-02-I2A — onafhankelijke E2E-verificatie (2026-10-19)

**Bewijsstatus:** VERIFIED_REPO (GitHub Actions-uitvoering en joblogs); DERIVED_CHECK (assertions in verificatiescript). **Besluitstatus:** gereed voor governance-review; geen merge- of publicatieautorisatie.

## Vastgepinde uitvoering
- Run: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39270528295
- Job: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39270528295/job/118121290299
- Workflow op main: `a8ea226195e7eaa11e3c5a25b2764b285697e9d0`
- Gecontroleerde I2A-implementatie: `478b95f8658eb73bcc0167365126b914a0f3049a` (de workflow checkt de featurebranch uit en vereist dat deze commit een ancestor is; codepaden `etl/`, `tests/`, `data/` en `frontend/public/data/` zijn ongewijzigd sinds die commit).
- Baseline: `8a05b2be442c529031f4d3da88cca21aacd5668f`
- Artifact: https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/39270528295/artifacts/12194517864 (7 dagen bewaartermijn)

## Vastgestelde resultaten
Alle jobstappen zijn `success`. De logs rapporteren twee geldige geïsoleerde candidate-runs met:
- `months=380`; `historical=60` (1995-01–1999-12); `preserved=320` (2000-01–2026-08)
- exact gelijkblijvende 320 bestaande JSON-records en byte-identieke CSV-suffix
- historische `hpi` en `hpi_index` null; index januari 2000 = 100; goudvelden null
- deterministische CSV, JSON en manifest tussen twee runs
- `published=false`; geen wijzigingen aan publieke data

SHA-256 van de geïsoleerde outputs:
- CSV: `8015c07d92712f5496409d0c25c5aac89548687eabe90c6483dff14d8c613f27`
- JSON: `6507e76d250c18b27eba6018dc1622621e9120488b00c27ae8177716b9aa8c27`
- Manifest: `34414336e5b6b6c41312526feb3d88df36132df803d0819de9d1582dd58973f9`

## Scope en resterende gates
Dit is **geen** bewijs van publicatie, live-updategedrag, productie-integratie, goudmethodologie of BTC-data. I2B, release en publieke goudpublicatie blijven buiten scope/HOLD. PR #57 mag pas na afzonderlijke governance-review, actuele CI en expliciete mergeautorisatie worden gemerged. Het originele `VERIFICATION_LOG.md` van het ChatGPT-project is geen repositorybestand; dit document is het bij PR #57 te reviewen repo-bewijsrecord, niet een stilzwijgende vervanging van dat governance-register.
