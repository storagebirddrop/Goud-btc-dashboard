# HIST-09 — Final source validation and CBS/NVM overlap

**Project Control status: Research verification PASS; publication NOT AUTHORIZED.**

## Evidence
- NVM OTB table B3.8: 52/52 text matched; page 135 visually checked in preceding execution, and page 136 screenshot supplied by owner on 2026-10-22. The 11 price values shown on page 136 (1995-H2 to 2000-H2) exactly match the research CSV. Original NLG values are retained.
- NVM source price measure is nominal median sale price of existing houses in the NVM/Vastgoed/published-report source population, expressed in thousands of NLG in the source. It is not the national CBS mean.
- Official CBS StatLine 85773NED downloadable export `85773NED-202609220630.zip`, uploaded by owner, contains 72 monthly average sale prices (measure M001534), transactions (M001532_2), and total sale value (M001535), Jan 1995–Dec 2000, all positive and complete.
- CBS 12 semiannual means reconstructed using transaction-weighted monthly published averages: sum(price * sales)/sum(sales). Full integer transaction counts agree with all 24 official quarterly aggregates and all 6 official yearly aggregates. Semiannual monthly-weighted means differ from independently quarter-weighted means by at most EUR 0.49; annual means differ from official yearly figures by less than EUR 0.42 (source rounding).
- Fixed redenomination used only for unit comparability: NVM_EUR = NVM_NLG / 2.20371; NOT a current purchasing power adjustment.

## Main findings
- 12/12 complete half-year comparisons 1995-H1 to 2000-H2.
- NVM nominal medians exceed CBS means in 11/12 half years; the sole negative gap is 2000-H2.
- Mean signed NVM/CBS relative gap: +7.1273%; median: +7.2640%; range: -0.0885% to +10.5214%.
- Small deviations in weighted aggregation are explained by the publication rounding of the monthly and quarterly means, NOT evidence of identity of NVM/CBS methodologies.

## Interpretation and boundaries
The two sources differ in statistical measure (median vs mean) and population (NVM broker-related transactions vs CBS registered sales). The 12-observation overlap cannot prove statistical equivalence or justify a stitched homogeneous historical series. Keep separate labelled research series; do not interpolate annual or semiannual observations to monthly.

**No GitHub changes, no production data changes, no publication.** Use this review bundle for subsequent owner decision on ARCH-02 research ingestion and the historical gold-valuation methodology.

## Reproduction
Run: `python hist09_finalize.py --cbszip /path/to/85773NED-202609220630.zip --nvm HIST09_NVM_1975_2000_RESEARCH.csv --out /path/to/output`
This bundle includes normalized CBS monthly data, the overlap CSV with growth rates, SHA-256 manifest and validation output. The uploaded original CBS ZIP is not repackaged; its SHA-256 is pinned in the validation JSON.
