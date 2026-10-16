"""Quality gates for monthly source observations (no network or writes)."""
import csv
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

EXPECTED = {"gold_eur_oz", "nl_house_avg_eur", "nl_hpi"}

def validate_file(path: str | Path, *, expected=EXPECTED):
    errors = []
    grouped = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"date", "series", "value"}.issubset(reader.fieldnames):
            raise ValueError("CSV must have date,series,value columns")
        for row_num, row in enumerate(reader, start=2):
            try:
                period = row["date"].strip()
                d = date.fromisoformat(period + "-01" if len(period) == 7 else period)
                if d.year < 2000:
                    raise ValueError("observation before 2000")
                if d > date.today():
                    raise ValueError("future observation")
                series = row["series"].strip()
                if series not in expected:
                    raise ValueError("unknown series")
                value = float(row["value"])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("value must be finite and positive")
                grouped[(series, d.strftime("%Y-%m"))].append(value)
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"row {row_num}: {exc}")
    for (series, period), values in sorted(grouped.items()):
        if len(values) > 1:
            errors.append(f"duplicate monthly observation: {series}/{period}")
    return {"observations": len(grouped), "series": sorted({k[0] for k in grouped}), "errors": errors}

def assert_valid(path: str | Path):
    result = validate_file(path)
    if result["errors"]:
        raise ValueError("; ".join(result["errors"]))
    if not result["observations"]:
        raise ValueError("empty dataset")
    return result
