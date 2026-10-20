# HIST-02 — source pinning and retention

DATA-01B principles are binding: explicit HTTPS source identity and redirect policy, 15,000,000-byte maximum, immutable raw byte hash before parsing, deterministic source identity distinct from retrieved_at_utc, offline replay without network fallback, reject missing bytes/hash mismatch and unapproved source substitutions.

HIST-02 implementation: `tools/hist_02_annual_research.py` contains offline-only `verify_source_bytes(path, expected_sha256)`; no network call, production import or source replacement. Synthetic fixture tests exercise match, mismatch, missing and empty source. This verifies a research interface, **not live source acquisition**.

Original NVM, World Bank historical GOLD and official DNB USD/NLG source bytes: NOT ACQUIRED. Source SHA-256: NOT AVAILABLE. Raw storage: NOT_CONFIGURED. Durable replay: NOT VERIFIED. No raw third-party data is committed or uploaded. Source rights and access remain UNVERIFIED.

Future live acquisition requires approved exact endpoint(s), HTTPS redirect allowlist, explicit data use and retention decision, isolated bounded fetch and raw byte pin, parser provenance, content hash and readback. A hash-only manifest without retained accessible bytes does not prove durable replay.
