"""Input quality gates for monthly and daily source observations."""
import csv
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

MONTHLY = {"gold_eur_oz", "nl_house_avg_eur", "nl_hpi"}
DAILY = {"gold_daily_eur_oz"}
EXPECTED = MONTHLY | DAILY

def parse_observation_date(value: str, series: str) -> date:
    if series in MONTHLY:
        if not re.fullmatch(r"\d{4}-\d{2}(?:-01)?", value):
            raise ValueError("monthly dates must be YYYY-MM or YYYY-MM-01")
        return date.fromisoformat(value + "-01" if len(value) == 7 else value)
    if series in DAILY:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("daily dates must be YYYY-MM-DD")
        return date.fromisoformat(value)
    raise ValueError(f"unknown series: {series}")

def read_observations(path: str | Path, *, expected=EXPECTED):
    observations = []
    errors = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"date", "series", "value"}.issubset(reader.fieldnames):
            raise ValueError("CSV must have date,series,value columns")
        for row_num, row in enumerate(reader, start=2):
            try:
                series = (row["series"] or "").strip()
                if series not in expected:
                    raise ValueError(f"unknown series: {series}")
                d = parse_observation_date((row["date"] or "").strip(), series)
                if d.year < 2000:
                    raise ValueError("observation before 2000")
                if d > date.today():
                    raise ValueError("future observation")
                value = float(row["value"])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("value must be finite and positive")
                observations.append((series, d, value))
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"row {row_num}: {exc}")
    return observations, errors

def validate_file(path: str | Path, *, expected=EXPECTED):
    observations, errors = read_observations(path, expected=expected)
    grouped = defaultdict(int)
    for series, d, _ in observations:
        key = (series, d.isoformat() if series in DAILY else d.strftime("%Y-%m"))
        grouped[key] += 1
    for (series, period), count in sorted(grouped.items()):
        if count > 1:
            errors.append(f"duplicate observation: {series}/{period}")
    return {"observations": len(observations), "series": sorted({r[0] for r in observations}), "errors": errors}

def assert_valid(path: str | Path, *, expected=EXPECTED):
    result = validate_file(path, expected=expected)
    if result["errors"]:
        raise ValueError("; ".join(result["errors"]))
    if not result["observations"]:
        raise ValueError("empty dataset")
    return result
