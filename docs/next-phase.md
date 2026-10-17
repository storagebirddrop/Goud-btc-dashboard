> **Historical/legacy planning note:** The staging-D1 recommendation below is not the current runtime decision. See [ADR-001](governance/DECISIONS.md) and the [document hierarchy](governance/DOCUMENT_HIERARCHY.md). This file is retained for implementation history, not as an instruction to deploy D1.

# Next phase: verified historical ingestion

1. Choose and document licensed gold daily data and exact ECB EUR/USD series.
2. Identify CBS dataset codes for existing-home price index and average transaction prices.
3. Build source-specific downloaders with timeouts, retry policies, attribution, and raw-data hashes.
4. Validate coverage and manual spot-checks, then add common-base indexed series.
5. Use staging D1 for migration and API integration tests before production deployment.

No remote data ingestion or Cloudflare deployment is enabled in this branch.
