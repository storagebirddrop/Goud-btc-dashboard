# HIST-13 — Private browser report

Harness: `tests/hist13/private_browser.py` + `.mjs` (Playwright + Chromium, loopback only, redacted output: pass/fail only, no value printed, no screenshot, nothing stored; temporary frontend copy with temporary pins; the repository sources are not modified).

**Environment:** run locally inside the Claude session sandbox (not public CI, no Cloudflare preview, no network exposure beyond loopback). It is **not an owner-controlled environment**. Classification: **PASS in the session sandbox**; an owner-side run is not executed.

Result: **ALL CHECKS PASSED (16/16)** on the real candidate payloads with a temporary in-memory authorization:
- Production build (empty pins, real payload served, hostile URL): never requested, no tab, no historical text, no errors (1280 and 375 px).
- Authorized payload: Actueel default; Historisch shows three panels; interpretation and median/mean warnings; retrospective-euro text; no synthetic text.
- Tables equal the candidate cell by cell: NVM 52 half-years (original guilders, retrospective euros, quality, flags), CBS 60 months (none after 1999-12), comparison 12 half-years in separate columns.
- Exactly 41 NVM rows carry the page-135 label; source annotations show both sources, the NVM rights status `UNVERIFIED`, CC BY 4.0, quality and flag explanations.
- Unit toggle; switching back to the unchanged Actueel view; comparison panel absent when the payload does not authorize it.
- Refused on the real payloads: the candidate with PENDING owner fields (pinned, structurally unauthorized) and a payload with one flipped byte (unpinned): no tab, Actueel works.
- Mobile 375 px: no horizontal overflow, no errors.

Not covered: a run in an owner-controlled environment; the exact final payload (does not exist until the owner fields are known).
