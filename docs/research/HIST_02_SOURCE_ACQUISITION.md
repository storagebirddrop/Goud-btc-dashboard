# HIST-02 — source acquisition register

Base: main b5dae3fa165b3f94d437597115d9829303754ecc. RESEARCH ONLY.

| Candidate | Endpoint | Acquisition | Original bytes SHA | Coverage / definition | Rights |
|---|---|---|---|---|---|
| Vastgoedmarkt historical compilation | https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf | HIST-01 secondary source reference; **no newly pinned PDF bytes** | NOT AVAILABLE | 1975 €47k shown in HIST-01; 1975–1999 underlying NVM provenance, annual mean vs per-ultimo, mix, geographic representativeness, revisions NOT VERIFIED | UNVERIFIED |
| NVM original series | https://www.nvm.nl/ | Original export not located or acquired | NOT AVAILABLE | 0 independently verified original NVM years | UNVERIFIED |
| World Bank Pink Sheet GOLD | https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx | NOT ACQUIRED; raw historical workbook not available for independent replay | NOT AVAILABLE | 0 of 300 months independently verified for 1975–1999 | UNVERIFIED |
| Official DNB historical FX | https://www.dnb.nl/statistieken/ | Specific official USD/NLG endpoint not identified or acquired | NOT AVAILABLE | 0 of 300 required aligned months verified; quote direction, benchmark and calendar unresolved | UNVERIFIED |
| FRED candidate for historical FX | https://fred.stlouisfed.org/ | Investigative candidate only; exact official USD/NLG series identifier not validated | NOT ACQUIRED; local HTTPS attempt failed DNS resolution | NOT AVAILABLE | NOT VERIFIED | UNVERIFIED |
| CBS baseline | repository data/cbs-housing.csv | Existing approved read-only reference, no new extraction in this task | Existing pinned expected SHA ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6, **not independently recomputed here** | Monthly baseline; not proxy for missing NVM years | Existing project policy |

The Vastgoedmarkt secondary series is NOT labelled original NVM. Its 'per ultimo' wording and the distinction between mean/median and price/asking price are unresolved. The retrospective EUR conversion cannot be treated as proven original NLG prices. No complete original 1975–1999 housing source has been pinned. No original observation dataset is committed.

**Acquisition decision:** Do not expand DATA-01B allowlist to unknown hosts or upload third-party raw bytes without separate endpoint, rights and retention review. HTTPS DNS resolution failed in the isolated local environment; absence of exact raw bytes prevents a real historical numeric prototype. Zero externally verified historical source hashes.
