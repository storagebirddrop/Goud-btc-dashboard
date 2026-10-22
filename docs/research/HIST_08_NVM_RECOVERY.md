# HIST-08 Phase B: NVM / Vastgoedmarkt recovery attempt (research only)

Status: RESEARCH ONLY. Nothing approved or published. Evidence: `tools/hist_08_nvm_probe.py`, workflow `hist-08-nvm-probe.yml` (runs 39600516426 on `ef23136`, 39601340731 on `d70b180`; read-only, no artifacts, no raw bytes stored).

## Measured (CONFIRMED, in CI)

| Fact | Value |
|---|---|
| URL | `https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf` |
| imgix metadata (`?fm=json`) | one image: 5335 x 3001 px, 300 dpi, sRGB, PNG, 158,009 bytes; no page count, no text layer |
| `?page=1` and `?page=2` | byte-identical output (sha256 prefix `edcfb479...`); `?page=3` differs by 16 bytes (`7dd40f0d...`): the `page` parameter does not select distinct pages |
| Rendered at 3000 px / 6000 px | 3000x1688 / 6000x3375; 78% of pixels dark (light-on-dark graphic) |
| OCR (tesseract nld+eng, psm 4/6/11/12, 1x/2x, normal and inverted) | 15-16 characters in every variant: the word "Vastgoedmarkt" only |

## Reading of the evidence

* The URL named `.pdf` is a **single 16:9 raster graphic**, not a multi-page document and not a table. A 158 kB PNG of 16 megapixels is a simple graphic (cover / chart panel), which fits OCR finding only the logo word.
* INFERRED: this file is not the "Kerncijfers 1974-2024" table; it may be a header image or a chart rendered without selectable data. UNRESOLVED: whether the actual table exists elsewhere on the Vastgoedmarkt site.
* I could not view the image myself: the sandbox has no route to the host (CONNECT 403) and no tool returns CI artifacts as images. Therefore no manual transcription was done and **no NVM value is promoted**. This is not a claim that the data do not exist.

## Other recovery routes tried

* Web search (two queries, Dutch): no machine-readable NVM 1974+ table; results only CBS 83906NED/83625NED (from 1995) and a blog. The statement that NVM series start in 1995 is a secondary search summary, UNVERIFIED.
* Earlier tracks (HIST-02/05/06): NVM median in NLG for 1985/1990/1995/1999 (ESB 1999, secondary), 1975 = EUR 47k and 1995 = EUR 105k (quotes), ESB 1981 NBM tables 1976-1980 (text extracted, price concept *kosten koper*), KSS appendix B.10 (index only).

## What would resolve it (next actions, none requires publication)

1. Owner or a person with browser access opens the Vastgoedmarkt Kerncijfers page and the image directly and reports the page URL(s), table heading, statistic (gemiddelde/mediaan, per ultimo?), unit (kEUR) and footnotes; or supplies the original PDF/XLSX.
2. Ask NVM (`nvm.nl` data desk) or Vastgoedmarkt for the historical series with explicit permission (D7).
3. ESB 1981 (NBM, 1976-1980) is already text; a manual transcription of those 5 years is possible from text without OCR and would be the first verified NVM-attributed block (statistic: NBM mean per cell, kosten koper). Not yet done; it needs an independent second reading before any use.
4. Do **not** infer values from neighbouring years, and do not concatenate NVM with CBS.

NVM/CBS overlap: NOT EXECUTED (no NVM series).

## Update (HIST-09, 2026-10-22)

Resolved by the independently verified HIST-09 package: 52 NVM half-year medians 1975-H1..2000-H2 (OTB 2001, Table B3.8) and the CBS 1995-2000 overlap. See `HIST_09_INTEGRATION.md`. The statements above about this imgix image stay true; the data came from another route (the OTB report).
