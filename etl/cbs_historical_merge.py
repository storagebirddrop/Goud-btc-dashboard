"""CBS-02-I2A: offline, isolated historical candidate migration (never publish)."""
import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from etl.cbs_historical_fixture import EXPECTED, SOURCES, VERSION as I1_VERSION
from etl.static_export import build

BASELINE_CSV_SHA256 = "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
BASELINE_JSON_SHA256 = "bc15f3bd1c2101df6fd6a8e18b60f62ff2fc3032eb0b71009bb6b44704c5c78e"
FIXTURE_SHA256 = "0a557dd16fe85e40952dd97edd492d5b3f985f64930d19d960b14307d725c543"
BASELINE_COMMIT = "8a05b2be442c529031f4d3da88cca21aacd5668f"
VERSION = "CBS-02-I2A/1"
FIELDS = {"period", "gold_eur_oz", "house_eur", "hpi", "gold_grams_per_house", "gold_index", "hpi_index"}
GOLD = ("gold_eur_oz", "gold_grams_per_house", "gold_index")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    return json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant: {x}")),
                      object_pairs_hook=_unique_pairs)


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"Duplicate JSON key: {key}")
        out[key] = value
    return out


def verify_fixture(raw, provenance_raw, *, expected_fixture_hash=FIXTURE_SHA256):
    if digest(raw) != expected_fixture_hash:
        raise ValueError("I1 fixture SHA-256 mismatch")
    fixture, provenance = strict_json(raw), strict_json(provenance_raw)
    if not isinstance(fixture, dict) or set(fixture) != {"data"} or not isinstance(fixture["data"], list):
        raise ValueError("Invalid I1 fixture schema")
    if not isinstance(provenance, dict) or provenance.get("output_sha256") != digest(raw):
        raise ValueError("Missing or incorrect I1 provenance")
    if provenance.get("converter_version") != I1_VERSION or provenance.get("observations") != 60:
        raise ValueError("Invalid I1 provenance version/count")
    if (provenance.get("period_start"), provenance.get("period_end")) != (EXPECTED[0], EXPECTED[-1]):
        raise ValueError("Invalid I1 provenance period")
    expected_sources = [{"table_id": k, "filename": SOURCES[k][0], "sha256": SOURCES[k][1],
                         "period_column": "Perioden", "price_column": "Gemiddelde verkoopprijs (euro)"}
                        for k in ("85773NED", "83906NED")]
    if provenance.get("sources") != expected_sources:
        raise ValueError("I1 provenance source mismatch")
    rows = fixture["data"]
    if len(rows) != 60 or [r.get("date") for r in rows if isinstance(r, dict)] != list(EXPECTED):
        raise ValueError("Invalid I1 historical coverage/order/duplicates")
    for row in rows:
        if set(row) != {"date", "series", "value"} or row["series"] != "nl_house_avg_eur" or type(row["value"]) is not int or row["value"] <= 0:
            raise ValueError("Invalid I1 historical observation")
    return rows


def _baseline(csv_raw, json_raw, csv_hash, json_hash):
    if digest(csv_raw) != csv_hash or digest(json_raw) != json_hash:
        raise ValueError("Pinned baseline SHA-256 mismatch")
    if not csv_raw.startswith(b"date,series,value\r\n") or b"\r\n" not in csv_raw:
        raise ValueError("Unexpected baseline CSV header/newline contract")
    text = csv_raw.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != ["date", "series", "value"]:
        raise ValueError("Invalid baseline CSV columns")
    seen = set()
    for row in reader:
        if None in row or any(x is None for x in row.values()):
            raise ValueError("Malformed baseline CSV")
        key = (row["date"], row["series"])
        if key in seen or row["date"] < "2000-01":
            raise ValueError("Baseline already extended or duplicated")
        seen.add(key)
    baseline = strict_json(json_raw)
    if not isinstance(baseline, dict) or set(baseline) != {"data"} or not isinstance(baseline["data"], list):
        raise ValueError("Invalid baseline JSON schema")
    for row in baseline["data"]:
        if set(row) != FIELDS or row["period"] < "2000-01":
            raise ValueError("Invalid baseline JSON record")
    return baseline


def without_derived_gold(rows):
    """Copy of baseline rows with the published derived gold indicators blanked.

    The approved public JSON (GOLD-03) carries gold_index / gold_grams_per_house for 2000+;
    this CBS-only review candidate is built from CSV alone and never carries gold, so the
    exact 2000+ comparison covers every non-derived field. gold_eur_oz must already be null."""
    out = []
    for row in rows:
        if row["gold_eur_oz"] is not None:
            raise ValueError("Approved baseline exposes gold_eur_oz")
        out.append({**row, "gold_grams_per_house": None, "gold_index": None})
    return out


def _same_exact(a, b):
    return json.dumps(a, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        b, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def make_candidate(fixture_raw, provenance_raw, baseline_csv_raw, baseline_json_raw, *,
                   csv_hash=BASELINE_CSV_SHA256, json_hash=BASELINE_JSON_SHA256,
                   fixture_hash=FIXTURE_SHA256):
    rows = verify_fixture(fixture_raw, provenance_raw, expected_fixture_hash=fixture_hash)
    baseline = _baseline(baseline_csv_raw, baseline_json_raw, csv_hash, json_hash)
    header = b"date,series,value\r\n"
    prefix = b"".join(f'{r["date"]},nl_house_avg_eur,{r["value"]}\r\n'.encode("ascii") for r in rows)
    csv_candidate = header + prefix + baseline_csv_raw[len(header):]
    if csv_candidate[len(header)+len(prefix):] != baseline_csv_raw[len(header):]:
        raise ValueError("2000+ CSV suffix changed")
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "candidate.csv"
        source.write_bytes(csv_candidate)
        candidate = build(source)
    old_rows, new_rows = baseline["data"], candidate["data"]
    if len(new_rows) != len(old_rows) + 60 or [r["period"] for r in new_rows[:60]] != list(EXPECTED):
        raise ValueError("Candidate historical calendar mismatch")
    old_rows = without_derived_gold(old_rows)
    if not _same_exact(new_rows[60:], old_rows):
        raise ValueError("2000+ JSON records changed")
    if new_rows[60]["period"] != "2000-01" or new_rows[60]["hpi_index"] != 100:
        raise ValueError("2000-01 index anchor changed")
    for original, candidate_row in zip(old_rows, new_rows[60:]):
        if not _same_exact(original, candidate_row):
            raise ValueError("2000+ record changed")
    for original, candidate_row in zip(rows, new_rows[:60]):
        if set(candidate_row) != FIELDS or candidate_row["house_eur"] != original["value"]:
            raise ValueError("Historical price or JSON v1 schema mismatch")
        if candidate_row["hpi"] is not None or candidate_row["hpi_index"] is not None or any(candidate_row[k] is not None for k in GOLD):
            raise ValueError("Unauthorized historical series")
    if any(any(r[k] is not None for k in GOLD) for r in new_rows):
        raise ValueError("Gold publication HOLD violation")
    json_candidate = (json.dumps(candidate, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    manifest = {
        "version": VERSION, "baseline_commit": BASELINE_COMMIT,
        "baseline_csv_sha256": csv_hash, "baseline_json_sha256": json_hash,
        "i1_fixture_sha256": fixture_hash, "i1_provenance_sha256": digest(provenance_raw),
        "i1_source_sha256": {k: SOURCES[k][1] for k in ("85773NED", "83906NED")},
        "historical_months": 60, "preserved_months": len(old_rows),
        "candidate_csv_sha256": digest(csv_candidate), "candidate_json_sha256": digest(json_candidate),
        "checks": {"historical_i1": "PASS", "csv_2000_plus_bytes": "PASS",
                   "json_2000_plus_exact": "PASS", "index_2000_01": "PASS", "gold_hold": "PASS"},
        "publication_authorized": False,
    }
    manifest_raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return csv_candidate, json_candidate, manifest_raw


def _check_output(path):
    target = Path(path).resolve()
    repo = Path(__file__).resolve().parents[1]
    forbidden = (repo / "data", repo / "frontend" / "public", repo / "frontend" / "dist")
    if any(target == d or d in target.parents for d in forbidden):
        raise ValueError(f"Refusing production/public output path: {target}")
    if target.exists():
        raise ValueError(f"Refusing to overwrite existing candidate: {target}")
    return target


def write_candidates(outputs):
    paths = [_check_output(p) for p, _ in outputs]
    if len(set(paths)) != len(paths):
        raise ValueError("Output paths must be distinct")
    staged, created = [], []
    try:
        for target, raw in zip(paths, (b for _, b in outputs)):
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".cbs-i2a-", delete=False) as handle:
                staged.append(Path(handle.name))
                handle.write(raw)
        for target, temp in zip(paths, staged):
            if target.exists():
                raise ValueError("Candidate appeared concurrently")
            os.replace(temp, target)
            created.append(target)
    except Exception:
        for path in created + staged:
            path.unlink(missing_ok=True)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline CBS-02-I2A candidate; never write public data")
    for name in ("fixture", "provenance", "baseline-csv", "baseline-json", "output-csv", "output-json", "manifest"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args(argv)
    out = (args.output_csv, args.output_json, args.manifest)
    for path in out:
        _check_output(path)
    if len(set(map(lambda x: x.resolve(), out))) != 3:
        p.error("Outputs must be distinct")
    payloads = make_candidate(args.fixture.read_bytes(), args.provenance.read_bytes(),
                              args.baseline_csv.read_bytes(), args.baseline_json.read_bytes())
    write_candidates(list(zip(out, payloads)))
    print("Validated isolated CBS-02-I2A candidates; NOT PUBLISHED")


if __name__ == "__main__":
    main()
