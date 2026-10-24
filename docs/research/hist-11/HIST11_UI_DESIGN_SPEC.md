# HIST-11 — UI design specification (proposal; nothing implemented)

Status: design for Project Control approval. The current dashboard (`frontend/src/main.tsx`, `series.ts`) stays recognizable and unchanged for users who never open the historical view. The dashboard remains a static Cloudflare Pages application; no backend.

## 1. Options

| | A: extend the main chart | B: separate historical view (NVM only) | C: combined interface with explicit series separation |
|---|---|---|---|
| What | prepend CBS 1995-1999 months to the existing series | one new page for the NVM half-year series | a second top-level view next to the existing one, holding NVM, CBS 1995-2000 and the labelled comparison |
| Usability | best continuity for the primary measure; but 60 months where 3 of 4 series are empty, "Alles" preset and cards change meaning | clear but isolated; no CBS context | clear separation, comparison available, one navigation element |
| Implementation | high: `monthly.json`, export strictness, `data_quality`, `Point` type, pins, presets | low | medium: new payload + loader + one view, `series.ts` untouched for current series |
| Methodology risk | high: reads as one continuous accepted series incl. retrospective euro and unlabelled 2000-2001 | low | low-medium: risk is only a misread comparison, mitigated by separate panels |
| Mobile | unchanged layout, longer axis | single panel | stacked panels, no dual axis |
| Release safety | **worst**: changes the legacy hash bound into the approved BTC release (comparability review s.7) | good | **best**: `monthly.json` byte-identical |

**Recommendation: Option C**, delivered inertly first (code behind an empty hash-pin list), nominal data only.

## 2. Navigation
- A segmented control (role `tablist`) at the top: **Actueel** (default, today's dashboard, unchanged) | **Historisch**. Deep link `#historisch`.
- The "Historisch" tab is **not rendered** unless the loaded historical payload's SHA-256 is in the frontend pin list (same pattern as Bitcoin, `activateBtc`); an unapproved, missing or malformed file leaves the current dashboard exactly as it is.
- In the historical view a persistent link "Naar actuele reeks (vanaf 2000)" and a text note that the current view starts where the NVM series ends.

## 3. Historical view layout (Phase C0: nominal levels only)
1. Notice block (always visible, not collapsible): "Historische reeksen zijn niet gelijk te stellen met de actuele reeks. NVM geeft een mediaan, CBS een gemiddelde; NVM is halfjaarlijks, CBS maandelijks. Er is niets aangevuld of geïnterpoleerd."
2. **Panel 1 — NVM mediane verkoopprijs, halfjaar, 1975-H1..2000-H2.** Unit toggle: "Gulden (origineel)" (default) / "Euro, omgerekend (÷ 2,20371)". Series is one line with markers per half-year.
3. **Panel 2 — CBS gemiddelde verkoopprijs, maand, 1995-01..1999-12** (euro, "omgerekend vóór 2002"). Ends at 1999-12; the continuation is the current view (no line to it).
4. **Panel 3 — Vergelijking NVM vs CBS, halfjaar 1995-H1..2000-H2** (only if HP3 is approved): two lines, both in euro, distinct colour and dash, plus a gap row ("NVM ligt gemiddeld 7,1% hoger"). Never one combined line.
5. Source and method block under each panel, quality legend, "Toon tabel" toggle (accessible table with every plotted value).

## 4. Axes, scales, ranges
- X axis: half-year category labels (`1975 H1`) in panels 1 and 3, month labels in panel 2. Ticks every 5 years; no shared x-axis between panels.
- Y axes: one axis per panel, linear, labelled with unit and currency ("ƒ" for guilders, "€ (omgerekend)" for retrospective euro); no dual axes, no log scale in C0; no index chart in C0.
- Default ranges: panel 1 full 1975-H1..2000-H2; panel 2 full 1995-01..1999-12; panel 3 full 1995-H1..2000-H2. Presets: "Alles", "1975-1994", "1995-2000". The existing month pickers are not reused (they are monthly); half-year selects are provided.
- Lines connect only consecutive points of the same series; a null breaks the line (`connectNulls=false`); no trend, regression or smoothing overlays.

## 5. Labels and tooltips (Dutch)
- Series labels: "NVM, mediane verkoopprijs bestaande koopwoningen (halfjaar)", "CBS, gemiddelde verkoopprijs bestaande koopwoningen (maand)".
- Tooltip (all panels): period, statistic ("mediaan" / "gemiddelde"), value with unit, **original** and **omgerekend** value for NVM, source and layer ("gemeten" / "afgeleid"), quality badge and flag text (for example "handmatig gecontroleerd"), for panel 3 both values and the gap in percent.
- Raw internal flags (`VISUAL_P135_PER_PROJECT_CONTROL`, `RETROSPECTIVE_EUR`) are mapped to fixed Dutch phrases; no flag may be shown unmapped and no value may be shown without its quality.

## 6. Quality indicators
NVM points: badge "bevestigd" plus marker "handmatig gecontroleerd" on the 41 flagged half-years. Gold (later phase): badges "B", "A", "E" with the legend of the HIST-08 thresholds and the rounding note (whole USD). A point without quality is not rendered.

## 7. Source disclosures (per panel)
- NVM: "Bron: OTB 2001, tabel B3.8 (NVM-makelaars/Vastgoedmarkt/persberichten); nominale mediaan; rechten per bron door Project Control beoordeeld" (exact wording after HP1).
- CBS: "CBS StatLine 85773NED (CC BY 4.0); halfjaargemiddelde en omrekening eigen berekening; bedragen vóór 2002 zijn door het CBS in euro omgerekend" (wording after HP2).
- Statement of own transformations, source vintage date, and the break list B1-B7 as a short list under the charts (not only inside the chart), so mobile users see it.
- No claim of endorsement by any source organisation.

## 8. Mobile
Single column; charts at least 280 px high; breaks and quality legend rendered as lists below the chart (no overlay labels); tooltips on tap; segmented control wraps without horizontal scroll; tables scroll inside their own container; 16 px side gutters as in the current layout.

## 9. Not in scope of this design
Historical gold and grams (Phase C1, after HG decisions), any index chart, real (CPI) values, pre-1975 data, any change to the Actueel view's series, cards or annotations (except the optional HP2b label for retrospective euro 2000-2001).
