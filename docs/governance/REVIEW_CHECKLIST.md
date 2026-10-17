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