"""CBS-02-I2B: fail-closed, review-only CBS live update candidates.

Never modifies the checked-in CSV/JSON. A changed overlap is a source revision
requiring human approval, not a silently accepted refresh.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path

from etl.cbs_historical_merge import (
    BASELINE_CSV_SHA256, BASELINE_JSON_SHA256, FIXTURE_SHA256,
    digest, strict_json, verify_fixture, without_derived_gold,
)
from etl.data_quality import validate as validate_data_quality
from etl.static_export import build

VERSION = "CBS-02-I2B/1"
FIXTURE = Path("data/fixtures/cbs-1995-1999-i1.json")
PROVENANCE = Path("data/fixtures/cbs-1995-1999-i1.provenance.json")
CSV_BASE = Path("data/cbs-housing.csv")
JSON_BASE = Path("frontend/public/data/monthly.json")
FIELDS = {"period", "gold_eur_oz", "house_eur", "hpi",
          "gold_grams_per_house", "gold_index", "hpi_index"}


class SourceRevision(ValueError):
    """An otherwise well-formed CBS observation differs from approved history."""

    def __init__(self, report):
        self.report = report
        super().__init__("CBS_REVISION_REVIEW_REQUIRED: " + json.dumps(report, sort_keys=True, separators=(",", ":")))


class IntegrityError(ValueError):
    """Missing, malformed, inconsistent or unauthorized input."""


def months_between(first, last):
    y, m = map(int, first.split("-"))
    result = []
    while f"{y:04d}-{m:02d}" <= last:
        result.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return result


def read_rows(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        if reader.fieldnames != ["date", "series", "value"]:
            raise IntegrityError("Unexpected CBS CSV columns")
        result = {}
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise IntegrityError("Malformed CBS CSV row")
            month, series = row["date"], row["series"]
            if len(month) != 7 or month[4] != "-" or not month[:4].isdigit() or not month[5:].isdigit():
                raise IntegrityError("Invalid month code")
            if not 1 <= int(month[5:]) <= 12 or series not in ("nl_hpi", "nl_house_avg_eur"):
                raise IntegrityError("Invalid month/series")
            try:
                from decimal import Decimal
                number = Decimal(row["value"])
            except Exception as exc:
                raise IntegrityError("Invalid CBS numeric value") from exc
            if not number.is_finite() or number <= 0:
                raise IntegrityError("Invalid CBS numeric value")
            key = (month, series)
            if key in result:
                raise IntegrityError("Duplicate CBS observation")
            result[key] = number
    except (UnicodeError, csv.Error) as exc:
        raise IntegrityError("Invalid CBS CSV encoding/structure") from exc
    dates = sorted({month for month, _ in result})
    if not dates or dates[0] != "2000-01" or dates != months_between("2000-01", dates[-1]):
        raise IntegrityError("Missing or unexpected CBS months")
    if any((m, s) not in result for m in dates for s in ("nl_hpi", "nl_house_avg_eur")):
        raise IntegrityError("Missing CBS price or HPI")
    return result, dates


def generate(fixture_raw, provenance_raw, baseline_csv_raw, baseline_json_raw, live_csv_raw,
             *, baseline_csv_hash=BASELINE_CSV_SHA256,
             baseline_json_hash=BASELINE_JSON_SHA256, fixture_hash=FIXTURE_SHA256):
    if digest(fixture_raw) != fixture_hash:
        raise IntegrityError("I1 fixture SHA-256 mismatch")
    try:
        history = verify_fixture(fixture_raw, provenance_raw, expected_fixture_hash=fixture_hash)
    except (ValueError, KeyError, TypeError) as exc:
        raise IntegrityError("Invalid I1 fixture/provenance") from exc
    if digest(baseline_csv_raw) != baseline_csv_hash or digest(baseline_json_raw) != baseline_json_hash:
        raise IntegrityError("Approved production baseline SHA-256 mismatch")
    old, old_dates = read_rows(baseline_csv_raw)
    live, live_dates = read_rows(live_csv_raw)
    if live_dates[-1] < old_dates[-1]:
        raise IntegrityError("Live CBS history truncated")
    revisions = [
        {"period": month, "series": series, "approved": str(old[(month, series)]),
         "observed": str(live[(month, series)])}
        for month in old_dates for series in ("nl_house_avg_eur", "nl_hpi")
        if old[(month, series)] != live[(month, series)]
    ]
    if revisions:
        raise SourceRevision({"status": "CBS_REVISION_REVIEW_REQUIRED",
                              "source": "CBS StatLine 85773NED",
                              "reason": "Approved observation changed; separate source revision review required",
                              "approved_csv_sha256": digest(baseline_csv_raw),
                              "live_csv_sha256": digest(live_csv_raw),
                              "revisions": revisions})
    if live_dates != months_between("2000-01", live_dates[-1]):
        raise IntegrityError("Live CBS calendar gap")
    try:
        baseline = strict_json(baseline_json_raw)
    except (ValueError, TypeError) as exc:
        raise IntegrityError("Invalid approved JSON") from exc
    if set(baseline) != {"data"} or len(baseline["data"]) != len(old_dates):
        raise IntegrityError("Invalid approved JSON coverage")
    if [r["period"] for r in baseline["data"]] != old_dates:
        raise IntegrityError("Approved JSON order/coverage mismatch")
    # GOLD-03: the approved JSON carries the two derived gold indicators; raw EUR/oz stays null.
    if any(set(r) != FIELDS or r["gold_eur_oz"] is not None for r in baseline["data"]):
        raise IntegrityError("Approved JSON schema/gold gate mismatch")
    if baseline["data"][0]["hpi_index"] != 100:
        raise IntegrityError("January 2000 index basis changed")
    if not baseline_csv_raw.startswith(b"date,series,value\r\n"):
        raise IntegrityError("Approved CSV newline/header contract changed")
    header = b"date,series,value\r\n"
    historic = b"".join(
        f'{r["date"]},nl_house_avg_eur,{r["value"]}\r\n'.encode("ascii") for r in history
    )
    suffix = baseline_csv_raw[len(header):]
    # Use the original approved bytes for all existing 2000+ records.
    additions = b"".join(
        f"{month},{series},{live[(month, series)]}\r\n".encode("ascii")
        for month in live_dates[len(old_dates):]
        for series in ("nl_house_avg_eur", "nl_hpi")
    )
    candidate_csv = header + historic + suffix + additions
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "candidate.csv"
        path.write_bytes(candidate_csv)
        candidate = build(path)
        candidate_json = (json.dumps(candidate, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False) + "\n").encode("utf-8")
        json_path = Path(temp) / "candidate.json"
        json_path.write_bytes(candidate_json)
        validate_data_quality(path, json_path)
    rows = candidate["data"]
    if len(rows) != 60 + len(live_dates) or [r["period"] for r in rows[:60]] != [
            h["date"] for h in history]:
        raise IntegrityError("Historical coverage changed")
    if rows[60:60 + len(old_dates)] != without_derived_gold(baseline["data"]):
        raise IntegrityError("Approved JSON observations changed")
    if candidate_csv[len(header) + len(historic):][:len(suffix)] != suffix:
        raise IntegrityError("Approved CSV bytes changed")
    if rows[60]["period"] != "2000-01" or rows[60]["hpi_index"] != 100:
        raise IntegrityError("January 2000 index basis changed")
    if any(r["hpi"] is not None or r["hpi_index"] is not None or
           any(r[k] is not None for k in ("gold_eur_oz", "gold_grams_per_house", "gold_index"))
           for r in rows[:60]):
        raise IntegrityError("Unauthorized historical series")
    if any(set(r) != FIELDS or any(r[k] is not None for k in
           ("gold_eur_oz", "gold_grams_per_house", "gold_index")) for r in rows):
        raise IntegrityError("JSON v1 or gold publication gate changed")
    report = {
        "status": "PASS_REVIEW_CANDIDATE_NOT_AUTHORIZED_FOR_PUBLICATION",
        "version": VERSION,
        "historical_months": 60,
        "approved_months_unchanged": len(old_dates),
        "new_months": len(live_dates) - len(old_dates),
        "total_months": len(rows),
        "revision_count": 0,
        "revision_policy": "BLOCK_ON_ANY_EXISTING_OBSERVATION_CHANGE",
        "historical_fixture_sha256": digest(fixture_raw),
        "historical_provenance_sha256": digest(provenance_raw),
        "approved_csv_sha256": digest(baseline_csv_raw),
        "approved_json_sha256": digest(baseline_json_raw),
        "live_cbs_csv_sha256": digest(live_csv_raw),
        "candidate_csv_sha256": digest(candidate_csv),
        "candidate_json_sha256": digest(candidate_json),
        "publication_authorized": False,
    }
    return candidate_csv, candidate_json, (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_review(output_dir, files):
    root = Path.cwd().resolve()
    destination = Path(output_dir).resolve()
    for forbidden in (root / "data", root / "frontend" / "public", root / "frontend" / "dist"):
        if destination == forbidden or forbidden in destination.parents:
            raise IntegrityError("Review output must not be in a public/production directory")
    if destination.exists():
        raise IntegrityError("Review output directory already exists (no overwrite)")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".cbs-i2b-", dir=destination.parent))
    try:
        for name, raw in zip(("candidate.csv", "candidate.json", "manifest.json"), files):
            (stage / name).write_bytes(raw)
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail-closed CBS historical update (review only)")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--baseline-csv", type=Path, default=CSV_BASE)
    parser.add_argument("--baseline-json", type=Path, default=JSON_BASE)
    parser.add_argument("--live-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        files = generate(args.fixture.read_bytes(), args.provenance.read_bytes(),
                         args.baseline_csv.read_bytes(), args.baseline_json.read_bytes(),
                         args.live_csv.read_bytes())
    except SourceRevision as exc:
        # Fail closed: only a deterministic diagnostic, never a candidate.
        report_path = Path(str(args.output_dir) + "-revision-review")
        if report_path.exists():
            raise IntegrityError("Revision review directory already exists") from exc
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=report_path.parent) as tmp:
            (Path(tmp) / "revision-report.json").write_text(
                json.dumps(exc.report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            os.rename(tmp, report_path)
        raise
    write_review(args.output_dir, files)
    print("Validated review-only CBS candidate:", args.output_dir)


if __name__ == "__main__":
    main()
