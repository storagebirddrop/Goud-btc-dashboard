"""GOLD-03 one-off (temporary, removed after use): write the reviewed GOLD-02B candidate
bytes to the public JSON and derive the release record from the bundle by code.

No value is typed by hand: artifact hash/size/period range, source hashes and the review
run all come from the bundle and the runner. Methodology/authorization fields are
attestations. Raw World Bank/ECB data are never read or written here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from etl.data_quality import validate_gold_release_record_preflight

AUTH = {
    "status": "NOT_AUTHORIZED",
    "authorized_by": None,
    "authorized_at": None,
    "reference": ("GOLD-03 owner decision 2026-10-20 lifts the publication HOLD for gold_index and "
                  "gold_grams_per_house and authorizes PREPARING the release only; merge/deploy "
                  "authorization is pending (status stays NOT_AUTHORIZED until the owner sets it)"),
}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--csv", type=Path, default=Path("data/cbs-housing.csv"))
    p.add_argument("--public", type=Path, default=Path("frontend/public/data/monthly.json"))
    p.add_argument("--record", type=Path, default=Path("data/gold-release-record.json"))
    p.add_argument("--review-run", required=True)
    a = p.parse_args(argv)
    candidate = (a.bundle / "monthly.gold-release-review.json").read_bytes()
    manifest = json.loads((a.bundle / "manifest.json").read_bytes())
    audit = json.loads((a.bundle / "independent-audit.json").read_bytes())
    sha = hashlib.sha256(candidate).hexdigest()
    cbs = hashlib.sha256(a.csv.read_bytes()).hexdigest()
    if not (manifest["candidate_json_sha256"] == audit["candidate_sha256"] == sha):
        raise ValueError("Bundle candidate hash mismatch")
    if audit["status"] != "PASS" or audit["raw_sources_uploaded"] is not False:
        raise ValueError("Independent audit is not PASS")
    if manifest["sources"]["cbs"]["sha256"] != cbs or manifest["release_authorized"] is not False:
        raise ValueError("Bundle CBS hash/authorization mismatch")
    rows = json.loads(candidate)["data"]
    record = {
        "schema_version": 1,
        "artifact": {"sha256": sha, "months": len(rows),
                     "first_period": rows[0]["period"], "last_period": rows[-1]["period"]},
        "fields_published": ["gold_index", "gold_grams_per_house"],
        "methodology": {"adr": "ADR-004", "status": "ACCEPTED"},
        "sources": {"worldbank_workbook_sha256": manifest["sources"]["world_bank"]["sha256"],
                    "ecb_sha256": manifest["sources"]["ecb"]["sha256"], "cbs_csv_sha256": cbs},
        "candidate_validation": {"candidate_sha256": sha, "review_run": a.review_run, "result": "PASS"},
        "release_authorization": AUTH,
    }
    a.public.write_bytes(candidate)
    a.record.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = validate_gold_release_record_preflight(a.csv, a.public, a.record)
    print("MATERIALIZED", json.dumps({"public_sha256": sha, "months": len(rows),
          "world_bank_sha256": record["sources"]["worldbank_workbook_sha256"],
          "ecb_sha256": record["sources"]["ecb_sha256"], "preflight_months": report["months"]}))


if __name__ == "__main__":
    main()
