# CBS -> D1 staging import (manual, read-only by default)

The command `python -m etl.d1_import --output data/cbs-upsert.sql` downloads live CBS OData v4 history, validates both monthly series, generates deterministic UPSERT SQL, and checks idempotence against an **in-memory SQLite database** using the project schema. It **does not connect to Cloudflare**.

Review the generated SQL, series count, source and coverage before importing. Use a **local** D1 database first:

```sh
cd frontend
npx wrangler d1 migrations apply gold-housing --local --migrations-dir ../db/migrations
npx wrangler d1 execute gold-housing --local --file ../data/cbs-upsert.sql
```

The above is a runbook, not a completed operation. Production and remote staging require explicit approval and Cloudflare credentials; never commit credentials or the downloaded dataset. Do not use synthetic seed data in production.
