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
