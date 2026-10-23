# PC-BTC07D-CM10 — Eigenaarbesluit over Community-datagebruik en restrisico

**Project:** Goud & Bitcoin Dashboard  
**Besluit-ID:** `PC-BTC07D-CM10-2026-10-23`  
**Beslisdatum:** 2026-10-23  
**Beslisser:** Project Control (projecteigenaar)  
**Status:** `DECIDED — OWNER_ACCEPTED_RESIDUAL_RISK`  
**Bevoegdheidsgrens:** eigenaarbesluit over risicobehandeling; geen juridische vrijwaring en geen publicatieautorisatie.

## 1. Aanleiding en beslisvraag

BTC-07D-R01 vond een expliciet gedocumenteerde CC BY-NC 4.0-basis voor de Coin Metrics Community API, maar liet onder **CM-10** onzekerheid bestaan over eventuele aanvullende API-/servicevoorwaarden en de verhouding tot algemene Coin Metrics-/Talos-voorwaarden. De beoogde indicatoren en JSON kunnen onderliggende maandelijkse BTC-prijzen vrijwel exact terugrekenbaar maken.

**Beslisvraag:** moet een afzonderlijke schriftelijke goedkeuring of scopebevestiging van Coin Metrics/Talos een verplichte voorwaarde zijn om met het project verder te gaan?

## 2. Eigenaarverklaringen — `OWNER_ATTESTED`

Project Control verklaart:

- Dashboard en datagebruik zijn uitsluitend **niet-commercieel**: geen advertenties, affiliate-inkomsten, betaalde toegang, abonnementen, diensten of commerciële promotie.
- De beoogde verspreiding is **privé of beperkt tot een kleine kring**; geen actieve brede verspreiding.
- Alle databronnen worden correct benoemd in de notes, inclusief toepasselijke licentielinks, eigen bewerkingen en wijzigingsvermeldingen.
- Er bestaat **geen afzonderlijke overeenkomst** met Coin Metrics of Talos.
- Project Control aanvaardt bewust de resterende onzekerheid rond CM-10 en de mathematische terugrekenbaarheid.

**Afbakening:** een publiek bereikbare website of downloadbare JSON blijft potentieel openbare verspreiding, ook zonder promotie. Werkelijke toegangscontrole moet afzonderlijk technisch worden vastgesteld.

## 3. Alternatieven

1. Schriftelijke rechtenhoudersbevestiging verplicht stellen voordat verdere voorbereiding of publicatiebeoordeling kan plaatsvinden.
2. **Gekozen:** restrisico expliciet aanvaarden en geen externe goedkeuring als generieke projectgate eisen; geldende licentievoorwaarden blijven toepassen.
3. BTC-data niet meer gebruiken — niet gekozen.

## 4. Besluit — `DECIDED`

1. **CM-10 wordt niet langer als verplichte externe goedkeuringsgate behandeld.** Geen afzonderlijke Coin Metrics-/Talos-e-mail, toestemming of overeenkomst als standaardvoorwaarde voor BTC-07E.
2. De door R01 gedocumenteerde **Coin Metrics Community CC BY-NC 4.0** is werkuitgangspunt voor de geïdentificeerde Community-bron, behoudens een aantoonbaar toepasselijke aanvullende bepaling.
3. Project Control accepteert juridisch interpretatierestrisico en technische terugrekenbaarheid van referentieprijzen uit samengestelde indicatoren.
4. De website/notes en eventuele JSON moeten relevante bronvermelding, licentie-informatie, verwijzingen, eigen berekeningen, wijzigingsmelding en niet-endorsementverklaring bevatten.
5. **BTC-07E private real-candidate-verificatie mag doorgaan** met ADR-012, zonder externe goedkeuringsvraag als blokkade. Overige technische en veiligheidsvoorwaarden blijven gelden.
6. **Geen autorisatie** voor publieke BTC-data, releasepins, productiedatawijziging, merge, deployment of andere ongeautoriseerde repositoryaanpassingen.

## 5. Bewijskwalificatie en resterende grenzen

| Onderdeel | Classificatie | Gevolg |
|---|---|---|
| Niet-commerciële exploitatie, distributie-intentie, geen apart contract | `OWNER_ATTESTED` | Verklaard uitgangspunt |
| Community CC BY-NC 4.0 | `DOCUMENTED_IN_R01` | Bron/licentie bij release verifiëren |
| Aanvullende API-/servicevoorwaarden (CM-10) | `UNVERIFIED / OWNER_ACCEPTED_RESIDUAL_RISK` | Geen generieke externe toestemmingsgate; nieuw materieel bewijs herbeoordelen |
| Private BTC-07E-verificatie | `DECIDED` | Toegestaan binnen bestaande grenzen |
| Publieke dashboard-/JSON-verspreiding | `NOT_AUTHORIZED` | Exact afzonderlijk eigenaarbesluit vereist |
| Goud-/CBS-rechten en release-HOLD | `NO_CHANGE` | Geen impliciete herlicentiëring of activatie |

Een eigenaarbesluit kan een toepasselijk contractueel verbod of wettelijke beperking niet opzijzetten. **Bij een concrete strijdige bepaling moet de relevante handeling vóór uitvoering opnieuw worden beoordeeld.** CC BY-NC 4.0 garandeert niet dat iedere bron, endpoint of distributievorm eronder valt.

## 6. Acceptatiecriteria BTC-07E en BTC-08

**BTC-07E:** bronidentiteit en Community-entitlement vastleggen; uitsluitend private kandidaatbytes, bronvintage en offline herstel; geen publieke prijsuitvoer; conceptattributie controleren; reproduceerbaarheid en beveiligingsgates behouden.

**BTC-08:** exacte distributievorm vastleggen (werkelijk privé of publiek bereikbare website/JSON); bron- en licentietekst voor de werkelijke kandidaat vastleggen; volledige attributie en wijzigingsmelding testen; expliciet artifacthash, releasepins, rollback en publicatie goedkeuren of HOLD handhaven.

## 7. Governance-integratie

Dit document legt het eigenaarbesluit vast; opname in de repository verleent **geen nieuwe release- of mergeautorisatie**. BTC-07D-R01 blijft inhoudelijke onderbouwing; eerdere bevindingen worden niet overschreven. De eerdere aanbeveling om altijd schriftelijke Coin Metrics-/Talos-scopebevestiging te verkrijgen vervalt als generieke projectgate; geaccepteerde methodologie, werkelijke voorwaarden en formele publicatie-HOLD blijven ongewijzigd.

**Besluitbron:** expliciete Project Control-verklaringen op 2026-10-23 en BTC-07D-R01/CM-10-review.

**Eindstatus:** CM-10 `OWNER_ACCEPTED_RESIDUAL_RISK`; BTC-07E PRIVATE PREPARATION GO; **BTC-PUBLICATIE HOLD**.
