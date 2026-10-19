"""CBS-02-I2B: fail-closed, review-only CBS update candidates.

No public paths are written. Existing 2000+ observations are immutable without
a separately approved CBS revision; new contiguous months are allowed.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from etl.cbs_historical_merge import verify_fixture, FIXTURE_SHA256
from etl.static_export import build
from etl.data_quality import validate

FIXTURE = Path("data/fixtures/cbs-1995-1999-i1.json")
PROVENANCE = Path("data/fixtures/cbs-1995-1999-i1.provenance.json")
FIELDS = {"period", "gold_eur_oz", "house_eur", "hpi",
          "gold_grams_per_house", "gold_index", "hpi_index"}
HEADER = b"date,series,value\r\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    if reader.fieldnames != ["date", "series", "value"]:
        raise ValueError("Invalid CSV columns")
    rows = {}
    for row in reader:
        if None in row or any(x is None for x in row.values()):
            raise ValueError("Malformed CBS CSV")
        key = (row["date"], row["series"])
        if key in rows:
            raise ValueError("Duplicate CBS observation")
        try:
            value = float(row["value"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid CBS numeric value") from exc
        import math
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Invalid CBS numeric value")
        rows[key] = value
    return rows


def _months(start, end):
    y, m = map(int, start.split("-"))
    result = []
    while f"{y:04d}-{m:02d}" <= end:
        result.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return result


def generate(fixture, provenance, baseline_csv, baseline_json, live_csv):
    history = verify_fixture(fixture, provenance, expected_fixture_hash=FIXTURE_SHA256)
    if not baseline_csv.startswith(HEADER):
        raise ValueError("Unexpected approved CSV encoding/newline contract")
    baseline = json.loads(baseline_json)
    if set(baseline) != {"data"} or not isinstance(baseline["data"], list):
        raise ValueError("Invalid approved JSON schema")
    old_rows = baseline["data"]
    if not old_rows or old_rows[0]["period"] != "2000-01":
        raise ValueError("Approved baseline must start at 2000-01")
    if any(set(row) != FIELDS for row in old_rows):
        raise ValueError("Approved JSON-v1 fields changed")
    old = csv_rows(baseline_csv)
    new = csv_rows(live_csv)
    periods = sorted({p for p, _ in new})
    old_periods = [row["period"] for row in old_rows]
    if old_periods != _months("2000-01", old_periods[-1]):
        raise ValueError("Approved baseline has calendar gaps or duplicates")
    if periods != _months("2000-01", periods[-1]) or periods[:len(old_periods)] != old_periods:
        raise ValueError("Live CBS missing, duplicated or reordered months")
    for month in periods:
        if (month, "nl_house_avg_eur") not in new or (month, "nl_hpi") not in new:
            raise ValueError("Missing required live CBS series")
    if set(old) != {(p, series) for p in old_periods for series in ("nl_house_avg_eur", "nl_hpi")}:
        raise ValueError("Approved CSV series mismatch")
    revisions = [{"period": p, "series": s, "approved": old[(p, s)], "live": new[(p, s)]}
                 for p, s in sorted(old) if new[(p, s)] != old[(p, s)]]
    if revisions:
        raise ValueError("CBS_REVISION_REVIEW_REQUIRED: " + json.dumps(revisions, separators=(",", ":")))
    # Retain exact approved CSV lines for all existing months.
    extra = []
    for p in periods[len(old_periods):]:
        for series in ("nl_house_avg_eur", "nl_hpi"):
            extra.append(f"{p},{series},{new[(p, series)]}\r\n".encode("ascii"))
    prefix = b"".join(f"{r['date']},nl_house_avg_eur,{r['value']}\r\n".encode("ascii") for r in history)
    candidate_csv = HEADER + prefix + baseline_csv[len(HEADER):] + b"".join(extra)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.csv"
        path.write_bytes(candidate_csv)
        payload = build(path)
        candidate_json = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()
        json_path = Path(tmp) / "candidate.json"
        json_path.write_bytes(candidate_json)
        validate(path, json_path)
    rows = payload["data"]
    if rows[60:60 + len(old_rows)] != old_rows:
        raise ValueError("Existing approved JSON records changed")
    if rows[60]["period"] != "2000-01" or rows[60]["hpi_index"] != 100:
        raise ValueError("Incorrect January 2000 index base")
    if len(rows) != 60 + len(periods):
        raise ValueError("Candidate length mismatch")
    if any(r["hpi"] is not None or r["hpi_index"] is not None or
           any(r[g] is not None for g in ("gold_eur_oz", "gold_grams_per_house", "gold_index"))
           for r in rows[:60]):
        raise ValueError("Invalid historical null semantics")
    manifest = {
        "status": "REVIEW_ONLY_NOT_PUBLISHED",
        "publication_authorized": False,
        "fixture_sha256": sha(fixture),
        "provenance_sha256": sha(provenance),
        "approved_csv_sha256": sha(baseline_csv),
        "approved_json_sha256": sha(baseline_json),
        "live_cbs_sha256": sha(live_csv),
        "candidate_csv_sha256": sha(candidate_csv),
        "candidate_json_sha256": sha(candidate_json),
        "historical_months": 60,
        "retained_months": len(old_rows),
        "new_months": len(periods) - len(old_rows),
        "total_months": len(rows),
        "revision_count": 0,
        "review_required": True,
    }
    manifest_raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    return candidate_csv, candidate_json, manifest_raw


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build isolated, fail-closed CBS review candidates")
    parser.add_argument("--live-csv", type=Path, required=True)
    parser.add_argument("--baseline-csv", type=Path, default=Path("data/cbs-housing.csv"))
    parser.add_argument("--baseline-json", type=Path, default=Path("frontend/public/data/monthly.json"))
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = args.output_dir.resolve()
    forbidden = [root / "data", root / "frontend" / "public", root / "frontend" / "dist"]
    if any(output == p or p in output.parents for p in forbidden):
        raise ValueError("Refusing public or production output path")
    if output.exists():
        raise ValueError("Output directory already exists: fail closed")
    results = generate(args.fixture.read_bytes(), args.provenance.read_bytes(),
                       args.baseline_csv.read_bytes(), args.baseline_json.read_bytes(),
                       args.live_csv.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        stage = Path(staging)
        for name, raw in zip(("candidate.csv", "candidate.json", "manifest.json"), results):
            (stage / name).write_bytes(raw)
        os.rename(stage, output)
    print("Review-only candidate validated:", output)


if __name__ == "__main__":
    main()
