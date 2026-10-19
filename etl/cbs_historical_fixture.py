"""Offline, fail-closed CBS StatLine historical housing-price fixture converter."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

VERSION = "CBS-02-I1/1"
PRICE = "Gemiddelde verkoopprijs (euro)"
PERIOD = "Perioden"
MONTHS = {name: i for i, name in enumerate(("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"), 1)}
EXPECTED = tuple(f"{y:04d}-{m:02d}" for y in range(1995, 2000) for m in range(1, 13))
SOURCES = {
    "85773NED": ("85773NED_SelectieZonderStatSymbol_20261019112844(1).csv", "e621f1828f759c6cd04453eba21ecf76748b3354956fc594cd40527f7d6b40e5"),
    "83906NED": ("83906NED_SelectieZonderStatSymbol_20261019113553.csv", "e13e13f9969f03944ee93eef417b640447eb7f70230688b29eb04b1eba572338"),
}

def parse_export(raw: bytes, *, expected_sha256: str):
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter=";", strict=True)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)) or PERIOD not in fields or PRICE not in fields:
            raise ValueError("Invalid StatLine CSV header or missing price column")
        values = {}
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row width")
            label = row[PERIOD].strip().lower()
            match = re.fullmatch(r"(\d{4}) ([a-z]+)", label)
            if not match:
                if re.match(r"^199[5-9]\s", label):
                    raise ValueError(f"Invalid historical month label: {label}")
                continue
            year, month_name = int(match[1]), match[2]
            if not 1995 <= year <= 1999:
                continue
            if month_name not in MONTHS:
                raise ValueError(f"Invalid historical month name: {month_name}")
            period = f"{year:04d}-{MONTHS[month_name]:02d}"
            if period in values:
                raise ValueError(f"Duplicate historical month: {period}")
            price = row[PRICE].strip()
            if not re.fullmatch(r"[0-9]+", price) or int(price) <= 0:
                raise ValueError(f"Invalid positive integer euro price: {period}")
            values[period] = int(price)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Invalid UTF-8 or CSV structure") from exc
    if set(values) != set(EXPECTED):
        raise ValueError(f"Historical coverage mismatch: missing={sorted(set(EXPECTED)-set(values))}, extra={sorted(set(values)-set(EXPECTED))}")
    return values

def convert(primary: bytes, comparison: bytes, *, hashes=None):
    hashes = hashes or {k: sha for k, (_, sha) in SOURCES.items()}
    first = parse_export(primary, expected_sha256=hashes["85773NED"])
    second = parse_export(comparison, expected_sha256=hashes["83906NED"])
    for month in EXPECTED:
        if first[month] != second[month]:
            raise ValueError(f"CBS source price mismatch in {month}: {first[month]} != {second[month]}")
    return [{"date": month, "series": "nl_house_avg_eur", "value": first[month]} for month in EXPECTED]

def serialize(rows):
    return (json.dumps({"data": rows}, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def main(argv=None):
    p = argparse.ArgumentParser(description="Validate CBS StatLine exports and create offline 1995–1999 price fixture")
    p.add_argument("--primary", required=True, type=Path)
    p.add_argument("--comparison", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    args = p.parse_args(argv)
    for table, path in (("85773NED", args.primary), ("83906NED", args.comparison)):
        if path.name != SOURCES[table][0]:
            p.error(f"Unexpected filename for {table}: {path.name}")
    a, b = args.primary.read_bytes(), args.comparison.read_bytes()
    rows = convert(a, b)
    payload = serialize(rows)
    manifest = {
        "converter_version": VERSION,
        "verification": "CBS-01 RESEARCH DATA-GO; CBS-02-I1 OFFLINE VALIDATED; NOT PUBLISHED",
        "period_start": EXPECTED[0], "period_end": EXPECTED[-1],
        "observations": len(rows), "output_sha256": hashlib.sha256(payload).hexdigest(),
        "sources": [{"table_id": k, "filename": SOURCES[k][0], "sha256": SOURCES[k][1],
                     "period_column": PERIOD, "price_column": PRICE}
                    for k in ("85773NED", "83906NED")],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    args.manifest.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

if __name__ == "__main__":
    main()
