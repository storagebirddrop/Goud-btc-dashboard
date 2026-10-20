# HIST-02 — FX series full coverage verification (2026-10-20)

**PARTIALLY VERIFIED: source metadata and selected table rows; complete 300-month row-by-row verification NOT EXECUTED. Original response bytes NOT VERIFIED.**

Authoritative table: https://fred.stlouisfed.org/data/EXNEUS (Federal Reserve Bank of St. Louis, EXNEUS, *Netherlands / U.S. Foreign Exchange Rate (DISCONTINUED)*). The table explicitly defines frequency **Monthly**, units **Dutch Guilder to One U.S. Dollar**, unadjusted, date range **1971-01 to 2001-12**, last update 2006-03-08. The stated series date range covers **1975-01 through 1999-12** (300 expected months), but no independent row-by-row 300-month completeness test has been executed. The 300-month coverage therefore remains **NOT VERIFIED**. Examples: 1975-01 2.4565, 1998-12 1.8816, 1999-01 1.9012, 1999-12 2.1797. No interpolation or reconstructed values used.

**Critical distinction:** browser-accessible metadata establishes the source's reported date range and quote direction, **not** a cryptographically pinned original CSV response. A direct attempt to retrieve `https://fred.stlouisfed.org/graph/fredgraph.csv?id=EXNEUS` in the isolated container failed DNS resolution. Consequently: original source bytes NOT ACQUIRED; SHA-256 NOT AVAILABLE; offline original-byte replay NOT VERIFIED; durable retention NOT_CONFIGURED. Do not misrepresent a web-rendered table or these examples as a pinned raw source.

**1999 methodological warning:** guilder was replaced by euro in accounting from January 1999; EXNEUS continues to report a synthetic guilder-equivalent quotation. Explicit confirmation of its underlying construction and alignment with the historical housing-price denomination is needed before accepting 1999 annual values.

**Gold:** World Bank original workbook still inaccessible to the web text reader (XLSX unsupported); container DNS unavailable. 0 original World Bank months byte-verified.

**Housing:** Vastgoedmarkt table is a secondary compilation attributed to NVM/NBM. Underlying annual source and statistical metadata remain unavailable.

**Next gate:** obtain original source files through an authorized runner with network access, hash before parsing, retain securely if permitted, independently replay all 300 months and validate housing definition. Until then no historical real-data prototype or public publication.
