"""GOLD-02: fail-closed, review-only release bundle built on GOLD-01 calculations.

No raw gold/FX data are persisted; no public assets are modified.
"""
import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from etl.gold_monthly import ECB, acquire, build_candidate, parse_ecb, parse_housing
from etl.gold_publication_candidate import (
    APPROVED_CBS_SHA256, APPROVED_PUBLIC_JSON_SHA256, render, sha,
)
from etl.sources.worldbank_gold import URL, parse_xlsx


def make_bundle(housing_path, baseline_path, gold_candidate, *,
                wb_sha256, ecb_sha256, commit, run_id, generated_at):
    housing_raw, baseline_raw = housing_path.read_bytes(), baseline_path.read_bytes()
    # GOLD-01 render performs the pinned baseline, calendar, formula and schema gates.
    candidate_raw, gold01_manifest_raw = render(
        housing_raw, baseline_raw, gold_candidate, housing_path=housing_path,
        gold_source_sha256=wb_sha256, ecb_source_sha256=ecb_sha256)
    candidate = json.loads(candidate_raw)["data"]
    baseline = json.loads(baseline_raw)["data"]
    if not candidate or len(candidate) != len(baseline):
        raise ValueError("Candidate coverage mismatch")
    if len(candidate) != len({r["period"] for r in candidate}):
        raise ValueError("Duplicate periods")
    allowed = {"gold_index", "gold_grams_per_house"}
    changes = []
    for current, old in zip(candidate, baseline):
        if current["period"] != old["period"] or set(current) != set(old):
            raise ValueError("JSON-v1 contract/period changed")
        if any(current[k] != old[k] for k in old if k not in allowed):
            raise ValueError("Unauthorized public field revision")
        changed = sorted(k for k in allowed if current[k] != old[k])
        if changed:
            changes.append({"period": current["period"], "fields": changed})
        if current["gold_eur_oz"] is not None:
            raise ValueError("Raw-derived EUR/oz cannot be published")
    if len(changes) != len(candidate):
        raise ValueError("Incomplete gold release candidate")
    gold01 = json.loads(gold01_manifest_raw)
    manifest = {
        "schema": "GOLD-02-review-v1",
        "status": "REVIEW_ONLY / NOT_DEPLOYED",
        "release_authorized": False,
        "repository_commit": commit,
        "generated_at_utc": generated_at,
        "github_actions_run": (f"https://github.com/storagebirddrop/Goud-btc-dashboard/actions/runs/{run_id}" if run_id else None),
        "artifact_name": "gold-02-release-candidate-review-only",
        "artifact_id": None,  # Assigned by GitHub only after upload.
        "sources": {
            "world_bank": {"url": URL, "version": "Pink Sheet Monthly Prices GOLD; June 2025 definition change", "sha256": wb_sha256},
            "ecb": {"url": ECB, "version": "EXR.D.USD.EUR.SP00.A", "sha256": ecb_sha256},
            "cbs": {"path": "data/cbs-housing.csv", "sha256": sha(housing_raw)},
            "approved_public_json": {"path": "frontend/public/data/monthly.json", "sha256": sha(baseline_raw)},
        },
        "candidate_json_sha256": sha(candidate_raw),
        "coverage": {
            "first": candidate[0]["period"], "last": candidate[-1]["period"],
            "months": len(candidate), "complete": gold01["gold_complete_months"],
            "pending": gold01["gold_pending_months"],
        },
        "public_gold_fields": sorted(allowed),
        "integrity": {
            "baseline_hashes": "PASS", "gold_formulas": "PASS",
            "january_2000_index": "PASS", "calendar": "PASS",
            "cbs_unchanged": "PASS", "json_v1": "PASS",
            "eur_oz_null": "PASS", "gold_only_diff": "PASS",
        },
        "diff": {"changed_months": len(changes), "changed_fields": sorted(allowed)},
        "source_rights": "Limited owner decision; third-party benchmark reuse uncertainty remains",
    }
    diff = {"status": "REVIEW_ONLY", "changed_months": len(changes), "changes": changes}
    return {
        "monthly.gold-release-review.json": candidate_raw,
        "manifest.json": (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
        "diff.json": (json.dumps(diff, sort_keys=True, indent=2) + "\n").encode(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--housing", type=Path, default=Path("data/cbs-housing.csv"))
    parser.add_argument("--baseline-json", type=Path, default=Path("frontend/public/data/monthly.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = args.output_dir.resolve()
    if output.exists() or any(output == p or p in output.parents for p in
        (root / "frontend", root / "data", root / "etl")):
        raise ValueError("Output exists or is inside protected source/public directory")
    housing_raw = args.housing.read_bytes()
    baseline_raw = args.baseline_json.read_bytes()
    if sha(housing_raw) != APPROVED_CBS_SHA256 or sha(baseline_raw) != APPROVED_PUBLIC_JSON_SHA256:
        raise ValueError("APPROVED_CBS_BASELINE_HASH_MISMATCH")
    wb_raw = acquire(URL)
    sheet, col, gold, invalid, duplicates, header = parse_xlsx(wb_raw)
    if invalid or duplicates or not gold or min(gold) != "2000-01":
        raise ValueError("Invalid World Bank source observations")
    ecb_raw = acquire(ECB)
    fx, counts, days = parse_ecb(ecb_raw)
    homes = parse_housing(housing_raw)
    end = max(homes)
    gold = {m: v for m, v in gold.items() if m <= end}
    fx = {m: v for m, v in fx.items() if m <= end}
    counts = {m: v for m, v in counts.items() if m <= end}
    candidate = build_candidate(gold, fx, homes, counts)
    commit = os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")
    run_id = os.environ.get("GITHUB_RUN_ID")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle = make_bundle(args.housing, args.baseline_json, candidate,
                         wb_sha256=sha(wb_raw), ecb_sha256=sha(ecb_raw),
                         commit=commit, run_id=run_id, generated_at=now)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        for name, raw in bundle.items():
            (Path(staging) / name).write_bytes(raw)
        os.rename(staging, output)
    print("GOLD_02_REVIEW_ONLY", output)
    for name, raw in bundle.items():
        print("OUTPUT_SHA256", name, hashlib.sha256(raw).hexdigest())
    print(bundle["manifest.json"].decode())


if __name__ == "__main__":
    main()
