# PROJECT_VISION — doel, onderzoeksethiek en interpretatie

**Versie:** 2.3 · **Peildatum:** 2026-10-19 · **Repository:** [storagebirddrop/Goud-btc-dashboard](https://github.com/storagebirddrop/Goud-btc-dashboard) · **Status:** werkreferentie, geen productiegoedkeuring.

**Bewijslabels:** `VERIFIED_REPO` = rechtstreeks gelezen in GitHub (bewijst aanwezigheid/inhoud, niet dat een run geslaagd is); `DECIDED` = expliciet projectuitgangspunt; `PROPOSED` = nog goed te keuren; `UNVERIFIED` = nog niet onafhankelijk aangetoond; `BLOCKED` = releasevoorwaarde ontbreekt; `SUPERSEDED` = vervangen besluit. Verwijzingen naar GitHub `main` zijn een momentopname, **geen vastgepinde commit**. Raadpleeg `VERIFICATION_LOG.md` voor file-blob-SHA's en auditgrenzen.

## Missie
Onderzoek hoe de relatieve waardering van Nederlandse koopwoningen verandert wanneer dezelfde, expliciet gedefinieerde woningprijs wordt uitgedrukt in nominale euro, euro met constant CPI-prijspeil, gram goud en BTC/satoshi. Maak alle berekeningen herleidbaar en beperk claims tot wat de gegevens ondersteunen.

## Centrale onderzoeksvraag
Hoeveel EUR, gram goud of BTC is op maandbasis nodig voor een **gemiddelde verkochte bestaande koopwoning** volgens de gekozen CBS-prijsmaat, en hoe verandert die verhouding door de tijd?

## Afgeleide vragen
- Hoe verschilt de nominale woningprijs van een CPI-gecorrigeerde reeks?
- Wat is de ontwikkeling van de kwaliteitsgecorrigeerde CBS-prijsindex, apart van het gemiddelde transactiebedrag?
- Hoe beïnvloeden bronkeuze, koersfixing, maandaggregatie, revisies en basisperiode de interpretatie?

## Onderzoeksprincipes (`DECIDED` als redactioneel uitgangspunt)
1. **Geen monetaire conclusie vooraf:** goud en bitcoin zijn alternatieve rekeneenheden, geen intrinsiek constante koopkrachtstandaarden.
2. **Geen categorieverwarring:** CBS-prijsindex is geen eurobedrag; gemiddelde verkoopprijs is geen constante woningkwaliteit.
3. **Geen ongefundeerde betaalbaarheidsclaim:** betaalbaarheid vraagt inkomen, rente, financieringsvoorwaarden, aanbod en andere context.
4. **Geen synthetische historie zonder zichtbare labeling:** nooit missende maanden ongemerkt interpoleren of BTC-prijzen vóór aantoonbare marktdekking verzinnen.
5. **Herleidbaar en falsifieerbaar:** bron, formule, tijdsvenster, dekking, licentie en revisiestatus moeten inspecteerbaar zijn.
6. **Niet voor beleggingsadvies:** het platform is onderzoeks- en educatiemateriaal.

## Aanvullend uitgangspunt v2.3 — brononafhankelijk en publiek reproduceerbaar
De wetenschappelijke vraag en de betekenis van de indicatoren staan centraal, niet de keuze voor één dataleverancier. Geef de voorkeur aan betrouwbare, controleerbare historische prijsreeksen die met passende bronvermelding en aantoonbare gebruiksrechten in **zowel interactieve grafieken als publieke maandelijkse JSON** kunnen worden gebruikt. Beschrijf bronbreuken, tijdsaggregatie en methodologische verschillen zichtbaar; een alternatieve bron mag niet stilzwijgend de betekenis van een bestaande reeks veranderen. Concrete bronkeuze, rechtenstatus, implementatie en publicatiebesluiten horen in `DATA_SOURCES.md`, `DECISIONS.md` en `PROJECT_STATUS.md` en blijven afzonderlijk te beoordelen.

## Acceptatie voor publieke kernclaim (`PROPOSED`)
Een grafiek 'gram goud per woning' of 'BTC per woning' mag pas verschijnen als een echte woningprijs in EUR, een brongecontroleerde assetprijs in EUR, een gedeelde kalenderdefinitie, voldoende dekking, licentierechten en publicatievalidatie aanwezig zijn. Tot dan: duidelijk 'niet beschikbaar', geen nulwaarden.

## Doelgroep (`PROPOSED`)
Onderzoekers, geïnteresseerden in de woningmarkt, monetaire geschiedenis, financiële educatie en datajournalistiek. Toegankelijkheid en doelgroep moeten nog worden vastgesteld.

## Verantwoordelijkheid
Deze documenten zijn een toetsingskader. Feitelijke implementatie en gepubliceerde resultaten worden afzonderlijk gecontroleerd; een geslaagde unit-test is geen economische bronverificatie.
