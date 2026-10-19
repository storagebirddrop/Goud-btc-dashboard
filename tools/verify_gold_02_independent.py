"""GOLD-02B pinned-byte acquisition and independent review-only audit.

Independent parser and formula path deliberately import NO production parsers/calculators.
Raw source bytes remain in runner temp, never uploaded or committed.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 28
WORLD_BANK = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
ECB = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2000-01-01&format=csvdata"
GRAMS = Decimal("31.1034768")
# JSON-v1 production exporter uses float() conversion: compare serialized numeric values
# with an a-priori tolerance of 1e-9 absolute OR 1e-12 relative.
ABS_TOL = Decimal("0.000000001")
REL_TOL = Decimal("0.000000000001")
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def acquire_pinned(url, path):
    request = urllib.request.Request(url, headers={
        "User-Agent": "GoldDashboard-PoC/1.0",
        "Accept": "text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
    with urllib.request.urlopen(request, timeout=55) as response:
        raw = response.read(15000001)
        metadata = {"url": url, "final_url": response.url, "http_status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "sha256": digest(raw), "bytes": len(raw)}
    if not raw or len(raw) > 15000000 or metadata["http_status"] != 200:
        raise ValueError("Invalid external source response")
    path.write_bytes(raw)
    if digest(path.read_bytes()) != metadata["sha256"]:
        raise ValueError("Pinned bytes changed on disk")
    return metadata


def independent_world_bank(raw):
    if not raw.startswith(b"PK"):
        raise ValueError("World Bank source is not XLSX")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.findall(".//x:t", NS))
                      for item in root.findall("x:si", NS)]
        wb = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = next(s for s in wb.findall(".//x:sheets/x:sheet", NS)
                     if "monthly prices" in s.attrib["name"].lower())
        relationship = sheet.attrib["{" + NS["r"] + "}id"]
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(x.attrib["Target"] for x in rels if x.attrib["Id"] == relationship).lstrip("/")
        name = target if target.startswith("xl/") else "xl/" + target
        xml = ET.fromstring(archive.read(name))
        rows = []
        for element in xml.findall(".//x:sheetData/x:row", NS):
            row = {}
            for cell in element.findall("x:c", NS):
                col = "".join(c for c in cell.attrib.get("r", "") if c.isalpha())
                value = cell.find("x:v", NS)
                inline = cell.find("x:is", NS)
                v = (value.text or "") if value is not None else (
                    "".join(t.text or "" for t in inline.findall(".//x:t", NS))
                    if inline is not None else "")
                if cell.attrib.get("t") == "s" and v:
                    v = shared[int(v)]
                row[col] = v
            rows.append(row)
    header = next(i for i, row in enumerate(rows)
                  if any(str(v).strip().upper() == "GOLD" for v in row.values()))
    column = next(k for k, v in rows[header].items() if str(v).strip().upper() == "GOLD")
    prices = {}
    for row in rows[header + 1:]:
        date_raw = str(row.get("A", "")).strip()
        if not date_raw:
            continue
        if date_raw.replace(".", "", 1).isdigit():
            month = (datetime(1899, 12, 30) + timedelta(days=float(date_raw))).strftime("%Y-%m")
        elif "M" in date_raw:
            month = datetime.strptime(date_raw[:7], "%YM%m").strftime("%Y-%m")
        else:
            month = datetime.strptime(date_raw[:7], "%Y-%m").strftime("%Y-%m")
        if month < "2000-01":
            continue
        if month in prices:
            raise ValueError("Duplicate World Bank month: " + month)
        val = Decimal(str(row.get(column, "")).strip())
        if not val.is_finite() or val <= 0:
            raise ValueError("Invalid World Bank observation")
        prices[month] = val
    return prices


def independent_ecb(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not {"TIME_PERIOD", "OBS_VALUE"}.issubset(reader.fieldnames or []):
        raise ValueError("Invalid ECB schema")
    daily = set()
    monthly = defaultdict(list)
    for row in reader:
        if row.get("CURRENCY") not in (None, "USD") or row.get("CURRENCY_DENOM") not in (None, "EUR"):
            raise ValueError("Wrong FX direction")
        day = row["TIME_PERIOD"]
        if not row.get("OBS_VALUE"):
            continue
        datetime.strptime(day, "%Y-%m-%d")
        if day in daily:
            raise ValueError("Duplicate ECB daily observation")
        daily.add(day)
        rate = Decimal(row["OBS_VALUE"])
        if not rate.is_finite() or rate <= 0:
            raise ValueError("Invalid ECB rate")
        monthly[day[:7]].append(rate)
    return {m: sum(vals) / len(vals) for m, vals in monthly.items()}


def independent_housing(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if set(reader.fieldnames or []) != {"date", "series", "value"}:
        raise ValueError("Invalid CBS schema")
    houses = {}
    for row in reader:
        if row["series"] != "nl_house_avg_eur":
            continue
        month = row["date"][:7]
        if month in houses:
            raise ValueError("Duplicate CBS observation")
        houses[month] = Decimal(row["value"])
        if not houses[month].is_finite() or houses[month] <= 0:
            raise ValueError("Invalid CBS observation")
    return houses


def independent_compare(world_bank_raw, ecb_raw, cbs_raw, public_raw, candidate_raw):
    gold = independent_world_bank(world_bank_raw)
    fx = independent_ecb(ecb_raw)
    houses = independent_housing(cbs_raw)
    public = json.loads(public_raw)["data"]
    candidate = json.loads(candidate_raw)["data"]
    months = [row["period"] for row in public]
    if months != [row["period"] for row in candidate] or len(set(months)) != len(months):
        raise ValueError("Candidate period mismatch")
    if not months or months[0] != "2000-01":
        raise ValueError("Index basis period missing")
    year, month = 2000, 1
    for period in months:
        if period != f"{year:04d}-{month:02d}":
            raise ValueError("Noncontiguous candidate months")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    if any(m not in gold or m not in fx or m not in houses for m in months):
        raise ValueError("Missing historical source month")
    if any(m <= months[-1] and m >= "2000-01" and m not in months
           for source in (gold, fx) for m in source):
        raise ValueError("Source calendar differs from approved CBS")
    base = gold["2000-01"] / fx["2000-01"]
    stats = {"exact_matches": 0, "within_tolerance": 0, "out_of_tolerance": 0,
             "max_absolute_deviation": "0", "max_relative_deviation": "0",
             "deviations": [], "checked_months": len(months),
             "checked_indicator_values": 2 * len(months),
             "formula_results": {"gold_index": "PASS", "gold_grams_per_house": "PASS"},
             "cbs_parity": "PASS"}
    max_abs, max_rel = Decimal(0), Decimal(0)
    for old, row in zip(public, candidate):
        period = row["period"]
        if set(row) != set(old) or any(row[k] != old[k] for k in old if k not in
             ("gold_index", "gold_grams_per_house")):
            raise ValueError("CBS or JSON schema revision")
        if row["gold_eur_oz"] is not None:
            raise ValueError("EUR/oz public exposure")
        if Decimal(str(old["house_eur"])) != houses[period]:
            raise ValueError("CBS baseline parity")
        eur = gold[period] / fx[period]
        expected = {"gold_index": Decimal(100) * eur / base,
                    "gold_grams_per_house": houses[period] * GRAMS / eur}
        for field, value in expected.items():
            actual = Decimal(str(row[field]))
            difference = abs(actual - value)
            relative = difference / abs(value)
            max_abs = max(max_abs, difference)
            max_rel = max(max_rel, relative)
            if difference == 0:
                stats["exact_matches"] += 1
            elif difference <= ABS_TOL or relative <= REL_TOL:
                stats["within_tolerance"] += 1
            else:
                stats["out_of_tolerance"] += 1
                stats["formula_results"][field] = "FAIL"
                stats["deviations"].append({"period": period, "field": field,
                                            "expected": str(value), "actual": str(actual),
                                            "absolute": str(difference), "relative": str(relative)})
    if Decimal(str(candidate[0]["gold_index"])) != 100:
        raise ValueError("Wrong gold index base")
    stats["max_absolute_deviation"] = str(max_abs)
    stats["max_relative_deviation"] = str(max_rel)
    stats["status"] = "PASS" if stats["out_of_tolerance"] == 0 else "FAIL"
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--old-candidate", type=Path)
    args = parser.parse_args(argv)
    from etl.gold_02_release import make_bundle
    from etl.gold_monthly import build_candidate, parse_ecb, parse_housing
    from etl.sources.worldbank_gold import parse_xlsx
    from etl.gold_publication_candidate import APPROVED_CBS_SHA256, APPROVED_PUBLIC_JSON_SHA256
    root = Path(__file__).resolve().parents[1]
    out = args.output_dir.resolve()
    if out.exists() or any(out == p or p in out.parents for p in
            (root / "frontend", root / "data", root / "etl")):
        raise ValueError("Unsafe or existing output directory")
    cbs = (root / "data/cbs-housing.csv").read_bytes()
    public = (root / "frontend/public/data/monthly.json").read_bytes()
    if digest(cbs) != APPROVED_CBS_SHA256 or digest(public) != APPROVED_PUBLIC_JSON_SHA256:
        raise ValueError("CBS baseline revision; no release candidate")
    with tempfile.TemporaryDirectory(prefix="gold-02b-pinned-") as private:
        pin = Path(private)
        wb_meta = acquire_pinned(WORLD_BANK, pin / "world-bank.xlsx")
        fx_meta = acquire_pinned(ECB, pin / "ecb.csv")
        wb = (pin / "world-bank.xlsx").read_bytes()
        fx = (pin / "ecb.csv").read_bytes()
        # Production and independent auditor consume identical immutable on-disk bytes.
        _, _, gold, invalid, duplicate, _ = parse_xlsx(wb)
        if invalid or duplicate:
            raise ValueError("Production parser found invalid World Bank source")
        monthly_fx, counts, _ = parse_ecb(fx)
        homes = parse_housing(cbs)
        end = max(homes)
        production = build_candidate({m: v for m, v in gold.items() if m <= end},
            {m: v for m, v in monthly_fx.items() if m <= end}, homes,
            {m: v for m, v in counts.items() if m <= end})
        generated = datetime.now(timezone.utc).isoformat()
        bundle = make_bundle(root / "data/cbs-housing.csv",
            root / "frontend/public/data/monthly.json", production,
            wb_sha256=digest(wb), ecb_sha256=digest(fx),
            commit=os.environ.get("GOLD02_SOURCE_SHA") or os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
            run_id=os.environ.get("GITHUB_RUN_ID"), generated_at=generated)
        candidate_raw = bundle["monthly.gold-release-review.json"]
        stats = independent_compare(wb, fx, cbs, public, candidate_raw)
        if stats["status"] != "PASS":
            raise ValueError("Independent formula replay FAIL: " + json.dumps(stats["deviations"][:5]))
        source_manifest = {"world_bank": wb_meta, "ecb": fx_meta,
            "cbs": {"sha256": digest(cbs), "bytes": len(cbs)},
            "public_json": {"sha256": digest(public), "bytes": len(public)},
            "repository_commit": os.environ.get("GOLD02_SOURCE_SHA") or os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")}
        previous = {"status": "NOT_PROVIDED", "previous_candidate_sha256": None}
        if args.old_candidate:
            prior = args.old_candidate.read_bytes()
            previous = {"status": "IDENTICAL" if prior == candidate_raw else "DIFFERENT",
                "previous_candidate_sha256": digest(prior), "new_candidate_sha256": digest(candidate_raw)}
            if prior != candidate_raw:
                before = json.loads(prior)["data"]
                after = json.loads(candidate_raw)["data"]
                previous["changes"] = [{"period": a["period"], "fields": [k for k in a if a[k] != b.get(k)]}
                    for a, b in zip(after, before) if a != b]
        audit = {"status": "PASS", "review_only": True,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "repository_commit": source_manifest["repository_commit"],
            "same_pinned_bytes_for_production_and_auditor": True,
            "world_bank_sha256": digest(wb), "ecb_sha256": digest(fx),
            "candidate_sha256": digest(candidate_raw),
            "independent_comparison": stats,
            "source_definition_change": "2025-06; no correction or splice applied",
            "raw_sources_uploaded": False,
            "historical_comparison": previous}
        bundle["source-manifest.json"] = (json.dumps(source_manifest, sort_keys=True, indent=2) + "\n").encode()
        bundle["independent-audit.json"] = (json.dumps(audit, sort_keys=True, indent=2) + "\n").encode()
        bundle["previous-candidate-diff.json"] = (json.dumps(previous, sort_keys=True, indent=2) + "\n").encode()
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=out.parent) as stage:
            for name, data in bundle.items():
                (Path(stage) / name).write_bytes(data)
            os.rename(stage, out)
        print("GOLD_02B_INDEPENDENT_PASS", json.dumps({
            "candidate_sha256": digest(candidate_raw), "world_bank": wb_meta,
            "ecb": fx_meta, "statistics": stats, "previous": previous}, sort_keys=True))


if __name__ == "__main__":
    main()
