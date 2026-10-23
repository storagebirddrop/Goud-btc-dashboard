# BTC-08B — Attribution and source-transparency corrections

Licensing/rights remain UNVERIFIED (no legal clearance; CM-10 is OWNER_ACCEPTED_RESIDUAL_RISK, not a clearance, not a publication authorization). Wording below never claims redistribution rights.

| Item | Before | After | Test |
|---|---|---|---|
| Coin Metrics role | one combined sentence | series PriceUSD named as dated daily USD reference; modification stated; "geen publicatie van of onderschrijving door Coin Metrics" | test_payload_sources_carry_role_and_modification_wording |
| ECB role | EXR series named | "bron: ECB", USD per EUR, modification stated, "geen officiële ECB-publicatie" | same |
| CBS role | named | numerator role, CC BY 4.0, own calculations, "geen CBS-publicatie" | same |
| Modification notice (UI) | absent | BTC_MODIFICATION_TEXT: monthly mean per full UTC calendar month, no interpolation, divided by monthly-mean ECB rate, USD-derived reference, raw daily series not distributed | test_ui_attribution_distinguishes_... |
| Source vintage (UI) | absent | data-btc-vintage (snapshot id) + capture date from the validated payload provenance; later revisions not included | test_ui_shows_the_source_vintage_... ; browser check B07b |
| Frontend gate | no provenance | activateBtc returns null without provenance.snapshot_id / vintage_reference_utc | tsc + browser B01-B11 |
| Non-endorsement | present | explicit "geen publicatie van Coin Metrics, de ECB of het CBS" + "Geen bronorganisatie onderschrijft deze toepassing" | static tests |

Preserved existing wording: "eigen berekeningen", "volledige kalendermaanden (UTC)", "afgeleid uit een USD-referentieprijs", native-EUR disclaimer, interpretation text, no investment advice, quality labels as provisional (Q1 = candidate, not final).
Not corrected (needs owner/legal): whether CC BY-NC 4.0 permits this site's use (commercial status), whether ECB reuse terms need further notice, Bitstamp-era price provenance.
