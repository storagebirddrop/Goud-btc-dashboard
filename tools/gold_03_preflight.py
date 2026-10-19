"""GOLD-03 review-only preflight for an EXACT pinned GOLD-02B derived JSON.

Never calls gold source APIs, production gold formulas or a publication entrypoint.
"""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CANDIDATE_SHA = "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
CBS_SHA = "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
PUBLIC_SHA = "bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e"
GOLD = ("gold_index", "gold_grams_per_house")
SCHEMA = {"period", "house_eur", "hpi", "hpi_index", "gold_eur_oz", *GOLD}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_and_preview(candidate_bytes, public_bytes, cbs_bytes):
    if sha(candidate_bytes) != CANDIDATE_SHA:
        raise ValueError("UNAPPROVED_GOLD_CANDIDATE_SHA")
    if sha(public_bytes) != PUBLIC_SHA or sha(cbs_bytes) != CBS_SHA:
        raise ValueError("CBS_BASELINE_REVISION")
    candidate = json.loads(candidate_bytes)
    public = json.loads(public_bytes)
    if set(candidate) != {"data"} or set(public) != {"data"}:
        raise ValueError("JSON_V1_TOP_LEVEL_SCHEMA")
    new, old = candidate["data"], public["data"]
    if len(new) != len(old) or not new or len(new) != 320:
        raise ValueError("UNAPPROVED_MONTH_COVERAGE")
    changes = []
    for a, b in zip(new, old):
        if set(a) != SCHEMA or set(b) != SCHEMA or a["period"] != b["period"]:
            raise ValueError("JSON_V1_SCHEMA_OR_PERIOD")
        if any(a[k] != b[k] for k in SCHEMA - set(GOLD)):
            raise ValueError("UNAUTHORIZED_CBS_OR_RAW_GOLD_CHANGE")
        if a["gold_eur_oz"] is not None:
            raise ValueError("RAW_GOLD_NOT_NULL")
        if any(not isinstance(a[k], (float, int)) or isinstance(a[k], bool) or
               not (0 < a[k] < float("inf")) for k in GOLD):
            raise ValueError("INVALID_GOLD_VALUE")
        if a["period"] < "2000-01":
            raise ValueError("UNAUTHORIZED_HISTORICAL_GOLD")
        changed = sorted(k for k in GOLD if a[k] != b[k])
        if changed != sorted(GOLD):
            raise ValueError("MISSING_OR_UNAUTHORIZED_GOLD_DIFF")
        changes.append({"period": a["period"], "fields": changed})
    if new[0]["period"] != "2000-01" or new[-1]["period"] != "2026-08" or new[0]["gold_index"] != 100:
        raise ValueError("INDEX_BASIS_OR_COVERAGE")
    year, month = 2000, 1
    for row in new:
        if row["period"] != f"{year:04d}-{month:02d}":
            raise ValueError("NONCONTIGUOUS_MONTHS")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    # The exact validated candidate is already in JSON-v1 public serialization.
    # Do not reserialize and risk an unreviewed byte change.
    diff = {"changed_months": len(changes), "changes": changes,
            "unchanged_cbs_fields": ["period", "house_eur", "hpi", "hpi_index"],
            "changed_fields": sorted(GOLD)}
    return candidate_bytes, diff


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--public", type=Path, default=Path("frontend/public/data/monthly.json"))
    p.add_argument("--cbs", type=Path, default=Path("data/cbs-housing.csv"))
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    out = args.output_dir.resolve()
    if out.exists() or any(out == protected or protected in out.parents for protected in
                           (root / "frontend", root / "data", root / "etl")):
        raise ValueError("UNSAFE_PREVIEW_OUTPUT")
    public_bytes = args.public.read_bytes()
    candidate_bytes = args.candidate.read_bytes()
    cbs_bytes = args.cbs.read_bytes()
    preview, diff = verify_and_preview(candidate_bytes, public_bytes, cbs_bytes)
    # Test rollback from exact baseline bytes, without source fetch or reconstruction.
    with tempfile.TemporaryDirectory(prefix="gold03-rollback-") as rollback_dir:
        target = Path(rollback_dir) / "monthly.json"
        target.write_bytes(preview)
        target.write_bytes(public_bytes)
        if target.read_bytes() != public_bytes or sha(target.read_bytes()) != PUBLIC_SHA:
            raise ValueError("ROLLBACK_BYTES_MISMATCH")
    manifest = {
        "schema": "GOLD-03-preflight-v1",
        "status": "PREPARED / NOT_DEPLOYED",
        "release_authorized": False,
        "repository_commit": os.environ.get("GOLD03_SOURCE_SHA") or os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
        "github_actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_sha256": sha(candidate_bytes),
        "cbs_sha256": sha(cbs_bytes),
        "public_before_sha256": sha(public_bytes),
        "preview_sha256": sha(preview),
        "rollback_file": "rollback.monthly.json",
        "rollback_sha256": sha(public_bytes),
        "coverage": {"first": "2000-01", "last": "2026-08", "months": len(diff["changes"])},
        "changed_fields": sorted(GOLD),
        "preflight": {"candidate_pin": "PASS", "baseline_pin": "PASS",
                      "cbs_parity": "PASS", "json_v1": "PASS",
                      "gold_index_base": "PASS", "no_raw_gold": "PASS",
                      "rollback_byte_identical": "PASS"},
        "deployed_commit": None,
        "deployment_target": None,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as stage:
        for name, data in {
            "preview.monthly.json": preview,
            "rollback.monthly.json": public_bytes,
            "diff.json": (json.dumps(diff, sort_keys=True, indent=2) + "\n").encode(),
            "release-manifest.json": (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
        }.items():
            (Path(stage) / name).write_bytes(data)
        os.rename(stage, out)
    print("GOLD_03_PREFLIGHT_PASS", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
