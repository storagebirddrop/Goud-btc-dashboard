# REVIEW_CHECKLIST — onafhankelijke kwaliteitsgate

Gebruik bij elke betekenisvolle wijziging. Reviewer moet eigen hypothesen vormen en niet uitsluitend het implementatieverslag herhalen.

## Correctheid
- [ ] Wijziging blijft binnen opdracht en goedgekeurde scope.
- [ ] Bestaande methodologie en besluiten zijn niet stilzwijgend gewijzigd.
- [ ] In- en output, foutpaden en grensgevallen zijn getest.
- [ ] Ontbrekende data wordt niet gemaskeerd of verzonnen.
- [ ] Datums, eenheden, valuta, tijdzones en afronding zijn expliciet.
- [ ] Provenance, revisies en backfill zijn reproduceerbaar waar relevant.

## Engineering
- [ ] Diff is minimaal en begrijpelijk.
- [ ] Bestaande interfaces blijven compatibel of migratie is beschreven.
- [ ] Secrets en credentials zijn niet toegevoegd.
- [ ] CI-configuratie is niet versoepeld om tests groen te krijgen.
- [ ] Rollback of herstelpad bestaat voor impactvolle wijzigingen.

## Bewijs
- [ ] Tests zijn werkelijk uitgevoerd, met commando, resultaat en omgeving.
- [ ] CI-status hoort bij de relevante commit en niet bij een oudere run.
- [ ] Onbewezen claims zijn `UNVERIFIED` gemarkeerd.
- [ ] De reviewer heeft minimaal één plausibel tegenvoorbeeld onderzocht.

## Uitkomst
`PASS` / `PASS WITH RISKS` / `BLOCKED` / `FAIL` — met concrete bevindingen, severity en herstelactie. `PASS WITH RISKS` is geen automatische merge-toestemming.

## v3.1 — bewijs en autorisatie
- [ ] Risicoklasse onderbouwd op feitelijke diff en semantische impact.
- [ ] CI op definitieve head-SHA; geen oudere run als bewijs.
- [ ] AI-review niet als onafhankelijke menselijke review voorgesteld.
- [ ] Reviewplicht vastgesteld op basis van **vooraf** geldend beleid; onbekend expliciet gelabeld.
- [ ] HTTP 403 niet gelijkgesteld aan uitgeschakelde branch protection.
- [ ] Geen nieuwe mergebevoegdheid gebruikt voor de PR die haar invoert.
- [ ] Resource-synchronisatie pas na geverifieerde merge.

**Rapporteer twee afzonderlijke uitkomsten:** technisch `PASS` / `PASS WITH CONDITIONS` / `FAIL` en merge `AUTHORIZED` / `NOT AUTHORIZED` / `UNKNOWN`. Een technische PASS geeft niet automatisch mergebevoegdheid.
