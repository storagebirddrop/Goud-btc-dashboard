# Proposed ADR-004 update — NOT APPROVED

Status: **PROPOSAL ONLY**. The authoritative ADR-004 is unchanged.

## Scope
World Bank Pink Sheet monthly GOLD (USD per troy ounce), ECB EXR.D.USD.EUR.SP00.A daily USD per EUR, CBS monthly average sale price in EUR. January 2000 is the index basis.

## Source definition and comparability
World Bank monthly GOLD historically represents an arithmetic average of daily London afternoon gold fixing prices for 99.5% pure gold. **Beginning June 2025**, the published GOLD definition changes to the average of daily spot prices. This is a benchmark-definition discontinuity and must be annotated on published visualizations. Do not splice or silently rebalance.

## Proposed calculation
For month m, ECB USD-per-EUR monthly FX is the arithmetic mean of all available valid ECB daily observations in that calendar month; no calendar-day denominator, forward fill or inferred rates.

gold_eur_oz[m] = gold_usd_oz[m] / mean_usd_per_eur[m]

gold_eur_gram[m] = gold_eur_oz[m] / 31.1034768

gold_grams_per_house[m] = cbs_house_eur[m] / gold_eur_gram[m]

gold_index[m] = 100 * gold_eur_oz[m] / gold_eur_oz[2000-01]

This ratio of monthly means is **not** the mean of daily EUR gold prices. Approval is required before production activation.

## Data integrity
Historical calendar from 2000-01 through latest observed source month; missing month within a source's published horizon is an error. A source lag beyond its last observed month is pending_publication. Only complete intersections are eligible for calculation. Keep source SHA-256, retrieval timestamp, coverage report, source URL, and provenance; never substitute synthetic history.

## Rights and publication
World Bank Pink Sheet underlying benchmark data may have third-party restrictions. Rights clearance for public raw prices, converted prices, gold index and gold grams per home remains open. **Public export remains blocked**. ECB and CBS attribution remains mandatory under applicable terms. This document does not authorize publication.

## Activation gate
Separate explicit decision required for methodology, rights, and activation. No automatic flag or scheduled publication is permitted in this PR.
