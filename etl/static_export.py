"""Build deterministic Pages JSON from reviewed CBS monthly CSV. No cloud access."""
import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

SERIES = {"nl_hpi": "hpi", "nl_house_avg_eur": "house_eur"}

def build(csv_path, *, gold_candidate=None, gold_publication_approved=False):
    if gold_candidate is not None or gold_publication_approved:
        raise PermissionError("Gold publication blocked until separate approval")
    observations = {}
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "series", "value"]:
            raise ValueError("Expected CSV columns date,series,value")
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row at line {row_number}: unexpected column count")
            month, series = row["date"], row["series"]
            if series not in SERIES:
                raise ValueError(f"Unexpected series: {series}")
            try:
                parsed = date.fromisoformat(month + "-01")
            except ValueError as exc:
                raise ValueError(f"Invalid monthly period: {month}") from exc
            if parsed.strftime("%Y-%m") != month or month < "2000-01":
                raise ValueError(f"Invalid monthly period: {month}")
            value = float(row["value"])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid observation: {series}/{month}")
            key = (month, series)
            if key in observations:
                raise ValueError(f"Duplicate observation: {series}/{month}")
            observations[key] = value
    months = sorted({m for m, _ in observations})
    if not months or months[0] != "2000-01":
        raise ValueError("Housing data must start in 2000-01")
    expected = []
    year, month = 2000, 1
    while (year, month) <= tuple(map(int, months[-1].split("-"))):
        expected.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    if months != expected:
        raise ValueError("Gaps in monthly coverage")
    output = []
    for period in months:
        if any((period, series) not in observations for series in SERIES):
            raise ValueError(f"Missing housing series in {period}")
        output.append({
            "period": period,
            "gold_eur_oz": None,
            "house_eur": observations[(period, "nl_house_avg_eur")],
            "hpi": observations[(period, "nl_hpi")],
            "gold_grams_per_house": None,
            "gold_index": None,
            "hpi_index": round(100 * observations[(period, "nl_hpi")] / observations[("2000-01", "nl_hpi")], 10),
        })
    return {"data": output}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="frontend/public/data/monthly.json")
    args = parser.parse_args()
    payload = build(args.input)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Built {len(payload['data'])} monthly records in {destination}")

if __name__ == "__main__":
    main()
