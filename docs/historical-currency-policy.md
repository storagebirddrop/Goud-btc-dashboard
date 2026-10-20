# Historische valuta en vergelijkbaarheid

## Doel
Vergelijk Nederlandse huizenprijzen en goud over verschillende monetaire tijdvakken zonder valutaomrekening te verwarren met inflatiecorrectie. Historische bronnen kunnen in NLG, EUR of USD zijn genoteerd.

## Regels voor brondata
- Bewaar altijd de oorspronkelijke numerieke waarneming, valuta, eenheid, datum/frequentie, bron en bronversie. Overschrijf oorspronkelijke waarden niet met omrekeningen.
- Gebruik voor weergave één expliciete **nominale EUR**-reeks naast de originele bronvaluta. Het EUR-bedrag vóór 1999 is een *rekenkundige EUR-equivalent*, niet een destijds verhandelde europrijs.
- Voor NLG → EUR geldt exact de onherroepelijke conversiekoers **1 EUR = 2,20371 NLG**; dus `EUR = NLG / 2.20371`. Deze vaste conversie is geen inflatiecorrectie.
- Voor USD-genoteerd goud gebruik een gedateerde, herleidbare USD/EUR- of historische USD/NLG-koers. Noteer koersrichting en tijdsaggregatie expliciet. De ECB-reeks bestaat niet voor alle historische jaren; vul ontbrekende perioden niet stilzwijgend aan.
- Goudstandaard: **EUR per troy ounce**; 1 troy ounce = **31,1034768 gram**. Bij omrekening naar gram: `EUR/g = EUR/troy oz / 31.1034768`.
- Een index (bijvoorbeeld HPI) is **valutaloos** en mag niet als absolute verkoopprijs worden gepresenteerd.
- Reële EUR (CPI-gecorrigeerd) is een aparte optionele serie met expliciet gekozen basisjaar, CPI-bron en formule.

## Datamodel (beoogd)
Per observatie: `period`, `series`, `original_value`, `original_currency` (indien van toepassing), `original_unit`, `source`, `source_reference`, `frequency`, `methodology`; afgeleide velden `nominal_eur_value`, `conversion_rate`, `conversion_source`, `conversion_period`, `is_derived`.

## Bronnen koppelen
- Verbind verschillende historische indexreeksen alleen na expliciete overlapcontrole, bronkritiek en een gedocumenteerde koppelingsfactor. Markeer breukpunten in de grafiek.
- Gebruik de Herengracht-index niet als landelijk gemiddelde zonder duidelijke waarschuwing.
- Leid een historische absolute huizenprijs niet rechtstreeks uit een index af zonder benoemd ankerjaar en expliciete aannames.
- Geen ontbrekende goud-, huizen- of FX-waarden interpoleren zonder aparte methode, provenance en gebruikersoptie.
- Voor Bitcoin beginnen de waarnemingen pas zodra er verifieerbare marktprijzen beschikbaar zijn.

## Huidige status
De huidige statische JSON bevat CBS-HPI en gemiddelde woningverkoopprijs, met nog lege goudvelden. Dit document specificeert de toekomstige historische uitbreiding; het verandert geen bestaande gepubliceerde waarden.

## Governance-afbakening (2026-10-19; onderzoeksdocument, niet normatief)

- `DECIDED / ACCEPTED`: ADR-004 geldt uitsluitend voor de bestaande maandelijkse goudreeks: World Bank GOLD (maandgemiddelde USD/troy oz) gedeeld door het rekenkundig gemiddelde van geldige dagelijkse ECB USD-per-EUR-koersen in dezelfde kalendermaand; goudindexbasis 2000-01 = 100; geen imputatie. De eerder genoemde EUR/troy-oz-eenheid is **geen alternatieve prijs- of FX-methodologie**.
- `DECIDED`: ADR-011 kiest betrouwbare, vergelijkbare landelijke gemiddelde Nederlandse woningverkoopprijzen als bepalende historische horizon; circa 1900 is onderzoeksambitie, geen goedgekeurde import.
- `PROPOSED`: historische NLG/EUR-, USD/NLG-, CPI-, jaargemiddelde- en bronkoppelingsregels hierboven zijn ontwerp- en onderzoekscriteria, geen wijzigingen aan ADR-004. Voor andere activaprijzen, historische goudregimes of een nieuwe indexbasis is een afzonderlijk besluit vereist.
- `UNVERIFIED`: vergelijkbaarheid NVM/Vastgoedmarkt circa 1975–1994 met CBS/Kadaster, eerdere landelijke woningprijzen en vroege goud/FX-bronnen.
- `BLOCKED`: publieke goudpublicatie blijft HOLD; BTC-maandmethodologie en publieke BTC-publicatie zijn niet goedgekeurd. Geen wijziging aan productie-export of data.

Bij tegenspraak prevaleren `DECISIONS.md` (ADR-004/ADR-011), `METHODOLOGY.md` en `DATA_SOURCES.md` volgens de projectdocumenthiërarchie.
