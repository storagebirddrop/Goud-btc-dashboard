"""Build deterministic Pages JSON from reviewed CBS monthly CSV. No cloud access."""
import argparse
import csv
import json
import math
import os
from datetime import date
from pathlib import Path

SERIES = {"nl_hpi": "hpi", "nl_house_avg_eur": "house_eur"}


GOLD_FIELDS = ("gold_eur_oz", "gold_grams_per_house", "gold_index")

def gold_enabled():
    return (os.environ.get("GOLD_PUBLICATION_ENABLED") == "true"
            and os.environ.get("GOLD_PUBLICATION_APPROVAL") == "APPROVED")

def validate_gold(candidate, public_rows):
    from decimal import Decimal
    from etl.gold_monthly import GRAMS, expected_months
    if not isinstance(candidate, dict) or candidate.get("publication_authorized") is not False:
        raise ValueError("Invalid candidate metadata")
    data, coverage = candidate.get("data"), candidate.get("coverage")
    if not isinstance(data, list) or not data or not isinstance(coverage, list) or not coverage:
        raise ValueError("Missing gold data or coverage")
    months = [r.get("month") for r in data]
    if months != expected_months("2000-01", months[-1]):
        raise ValueError("Missing, duplicate or unordered gold months")
    calendar = [r.get("month") for r in coverage]
    if calendar != expected_months("2000-01", calendar[-1]):
        raise ValueError("Invalid coverage calendar")
    if any(r.get("status") not in ("complete", "pending_publication") for r in coverage):
        raise ValueError("Historical gold source gap")
    if months != [r["month"] for r in coverage if r["status"] == "complete"]:
        raise ValueError("Candidate/coverage mismatch")
    result = {}
    base = None
    for r in data:
        month = r["month"]
        if month not in public_rows:
            raise ValueError("Candidate month missing in CBS")
        try:
            usd, fx, eur, gram, grams, idx, house = (
                Decimal(str(r[k])) for k in ("gold_usd_oz", "usd_per_eur", "gold_eur_oz",
                "gold_eur_gram", "gold_grams_per_house", "gold_index", "house_eur"))
            days = r["fx_days"]
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("Malformed gold candidate") from exc
        if any(not x.is_finite() or x <= 0 for x in (usd, fx, eur, gram, grams, idx, house)):
            raise ValueError("Invalid gold numeric value")
        if type(days) is not int or days <= 0:
            raise ValueError("Invalid FX observation count")
        if house != Decimal(str(public_rows[month]["house_eur"])):
            raise ValueError("CBS candidate/public mismatch")
        if base is None:
            base = eur
        def close(a, b):
            return abs(a - b) <= max(Decimal("1e-10"), abs(b) * Decimal("1e-12"))
        if not all((close(eur, usd/fx), close(gram, eur/GRAMS),
                    close(grams, house/gram), close(idx, Decimal(100)*eur/base))):
            raise ValueError("Candidate formula mismatch")
        result[month] = {"gold_grams_per_house": float(grams),
                         "gold_index": float(idx)}
    if result["2000-01"]["gold_index"] != 100:
        raise ValueError("Incorrect index basis")
    return result

def build(csv_path, *, gold_candidate=None, gold_publication_approved=False):
    authorized = gold_enabled() and gold_publication_approved is True
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
            if parsed.strftime("%Y-%m") != month or month < "1995-01":
                raise ValueError(f"Invalid monthly period: {month}")
            value = float(row["value"])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid observation: {series}/{month}")
            key = (month, series)
            if key in observations:
                raise ValueError(f"Duplicate observation: {series}/{month}")
            observations[key] = value
    months = sorted({m for m, _ in observations})
    if not months or months[0] not in ("1995-01", "2000-01"):
        raise ValueError("Housing data must start in 2000-01")
    expected = []
    year, month = map(int, months[0].split("-"))
    while (year, month) <= tuple(map(int, months[-1].split("-"))):
        expected.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    if months != expected:
        raise ValueError("Gaps in monthly coverage")
    output = []
    for period in months:
        if (period, "nl_house_avg_eur") not in observations or (period >= "2000-01" and (period, "nl_hpi") not in observations) or (period < "2000-01" and (period, "nl_hpi") in observations):
            raise ValueError(f"Missing housing series in {period}")
        output.append({
            "period": period,
            "gold_eur_oz": None,
            "house_eur": observations[(period, "nl_house_avg_eur")],
            "hpi": observations.get((period, "nl_hpi")),
            "gold_grams_per_house": None,
            "gold_index": None,
            "hpi_index": (round(100 * observations[(period, "nl_hpi")] / observations[("2000-01", "nl_hpi")], 10) if period >= "2000-01" else None),
        })
    if authorized:
        if gold_candidate is None:
            raise ValueError("Authorized export requires private gold candidate")
        verified = validate_gold(gold_candidate, {row["period"]: row for row in output})
        for row in output:
            if row["period"] in verified:
                row.update(verified[row["period"]])
    return {"data": output}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="frontend/public/data/monthly.json")
    parser.add_argument("--gold-candidate", default=None)
    parser.add_argument("--approve-gold-publication", action="store_true")
    args = parser.parse_args()
    candidate = None
    if args.approve_gold_publication and gold_enabled():
        if not args.gold_candidate:
            raise ValueError("Authorized export requires --gold-candidate")
        candidate = json.loads(Path(args.gold_candidate).read_text(encoding="utf-8"))
    payload = build(args.input, gold_candidate=candidate,
                    gold_publication_approved=args.approve_gold_publication)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Built {len(payload['data'])} monthly records in {destination}")

if __name__ == "__main__":
    main()
