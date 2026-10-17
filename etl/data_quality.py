"""Deterministic checks for committed housing CSV and public JSON.

This module verifies internal consistency, not independent source accuracy.
"""
import argparse
import json
import math
from pathlib import Path

from etl.static_export import build


def validate(csv_path, json_path):
    expected = build(csv_path)
    raw = Path(json_path).read_text(encoding="utf-8")
    payload = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(
        ValueError(f"Non-finite JSON number: {token}")))
    if not isinstance(payload, dict) or set(payload) != {"data"}:
        raise ValueError("Unexpected public JSON schema")
    rows = payload["data"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty or invalid public data")
    if payload != expected:
        raise ValueError("Public JSON differs from validated source CSV or calculated indices")
    if any(set(row) != {"period", "gold_eur_oz", "house_eur", "hpi",
                       "gold_grams_per_house", "gold_index", "hpi_index"} for row in rows):
        raise ValueError("Unexpected monthly record schema")
    for row in rows:
        for key in ("house_eur", "hpi", "hpi_index"):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Invalid numeric type for {key}")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid {key} at {row['period']}")
        for key in ("gold_eur_oz", "gold_grams_per_house", "gold_index"):
            if row[key] is not None:
                raise ValueError(f"Unexpected unverified gold value at {row['period']}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Verify committed CSV/JSON integrity and completeness")
    parser.add_argument("--input", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="frontend/public/data/monthly.json")
    args = parser.parse_args()
    count = validate(args.input, args.output)
    print(f"Validated {count} consecutive months, both CBS series, schema and JSON/CSV parity")


if __name__ == "__main__":
    main()
