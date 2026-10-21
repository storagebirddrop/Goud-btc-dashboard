# GOLD-03 frontend notes (draft, preparation only)

Status: PR-only preparation for the owner decision of 2026-10-20 (gold hold lifted for `gold_index` and `gold_grams_per_house` from 2000-01). Not a release. No change to the JSON contract, the ETL or governance documents.

## What changed (frontend/src)
- `series.ts`: new pure constants and helpers for gold transparency: `GOLD_SOURCE_ASOF`, `METHODOLOGY_URL`, `GOLD_SOURCE_LINKS` (World Bank, ECB EXR.D.USD.EUR.SP00.A, CBS 85773NED), `GOLD_OWN_CALC_TEXT`, `GOLD_METHOD_TEXT`, `GOLD_BREAK_TEXT`, `isIsoDate`, `viewHasGold`, `goldPeriod`. Registry mechanism, `publication: 'gated'` and `viewAnnotations` are unchanged. Gold card source strings now name all sources.
- `main.tsx`: component `GoldSources`, always visible directly under the chart, rendered only when the current view contains a gold series (`viewHasGold`). It shows the three sources with links, the own-calculation and non-endorsement statement, the data period of the gold series (first and last month with finite values, from the loaded rows), the source reference date, the method in Dutch with the methodology link, and the full June 2025 definition change. The collapsed "Bronnen & methode" section now also holds the method, the methodology link, the as-of date and the break text (the same constants, so no contradiction).
- `style.css`: `.gold-src` block styles.
- The chart annotation "jun 2025: bronwijziging goud" is unchanged (gold views only).

## The as-of constant
The JSON has no date field and must not get one. `GOLD_SOURCE_ASOF` in `series.ts` holds `{date, note}`. The date is the "peildatum bronstand" shown in both places. It is currently `2026-10-19` (date of the source files of the reviewed candidate). At every release (data refresh) the person publishing the gold values must set it to the date of the source files used (World Bank Pink Sheet workbook, ECB rates, CBS table). Tests only check that it is a valid ISO date, defined once, and rendered; they cannot check that it is correct.

## Wording guard
No text claims licence status, approval, authorization or endorsement. The only statement about the sources' stance is negative ("Geen van de bronorganisaties onderschrijft deze toepassing"). `tests/test_frontend_gold_sources.py` checks a forbidden-phrase list over the UI text. Third-party-rights uncertainty remains a registered residual risk and is deliberately not mentioned in the UI.

## Tests
- New `tests/test_frontend_gold_sources.py` (8 tests): block only for gold views, links/series id/statements/method/break text, collapsed section consistency, as-of constant validity and use, period derived from data, forbidden phrases, sat and raw gold stay hidden, card units and sources.
- `tests/test_frontend_series.py`: the "committed JSON has no gold" assertion is now state-tolerant (gold_eur_oz null everywhere; only the two gated columns may hold values, then complete and finite from 2000-01; CBS columns positive; 320 rows 2000-01..2026-08). After G1's data lands it can be tightened to "complete".
- Result at time of writing: full `python -m pytest -q` passed except one bug in my own `isIsoDate` which was fixed (then the frontend tests passed, also with `CI=true`); final full run and `npm run build` are recorded in the PR.

## Browser check (headless Chromium via DevTools protocol)
Synthetic JSON (gold_index, gold_grams_per_house for 2000-01..2026-08, plus a present-but-withheld `sat_per_house`) served from a copy of `frontend/dist` outside the repo. Desktop 1280 px and mobile 375 px:
- Gold views (index January 2000 = 100, gram goud per woning): block present 12 px under the chart, 4 working links (3 sources + methodology), annotation "jun 2025: bronwijziging goud" drawn.
- Nominal and CBS 2020 views: no gold block, no annotation.
- No text matching `sat`/`satoshi` anywhere; horizontal overflow 0 px in all views; all links in the block are focusable by keyboard.
- Period text rendered "januari 2000 t/m augustus 2026 (320 maanden)".
Screenshots are not committed.

## For the lead to decide
1. Set `GOLD_SOURCE_ASOF.date` at release (set to 2026-10-19 for this release).
2. Owner review of the Dutch wording (method text, "eigen berekeningen", break text).
3. The break text is shown in full in the block and in the collapsed section, plus the short chart label. The GOLD_PUBLICATION_DECISION annotation text is slightly different in wording; ours follows the task brief (full statement of the World Bank definition change).
4. Tighten the series test once the real gold data is committed.
