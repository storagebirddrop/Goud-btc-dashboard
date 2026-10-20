"""Research-only strict monthly coverage validation; no network or publication."""
import csv
import io
import re
from decimal import Decimal, InvalidOperation

class CoverageError(ValueError):
    pass

def validate_monthly_rows(rows, value_column, *, date_column="DATE", start=1975, end=1999):
    expected = {f"{y}-{m:02d}" for y in range(start, end + 1) for m in range(1, 13)}
    seen = {}
    duplicates = []
    for row in rows:
        if date_column not in row or value_column not in row:
            raise CoverageError("WRONG_SOURCE_COLUMN")
        date = str(row[date_column])
        if not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", date):
            raise CoverageError("INVALID_DATE")
        month = date[:7]
        if month not in expected:
            continue
        if month in seen:
            duplicates.append(month)
        try:
            value = Decimal(str(row[value_column]))
        except (InvalidOperation, ValueError):
            raise CoverageError("INVALID_NUMBER")
        if not value.is_finite() or value <= 0:
            raise CoverageError("INVALID_NUMBER")
        seen[month] = value
    missing = sorted(expected - seen.keys())
    if duplicates or missing:
        raise CoverageError(f"MONTH_COVERAGE_ERROR missing={missing} duplicates={sorted(set(duplicates))}")
    return {"months": len(seen), "first_month": min(seen), "last_month": max(seen),
            "missing_months": [], "duplicate_months": []}

def validate_fred_csv(raw, *, expected_sha256):
    import hashlib
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise CoverageError("HASH_MISMATCH")
    try:
        content = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames not in (["DATE", "EXNEUS"], ["observation_date", "EXNEUS"]):
            raise CoverageError("UNEXPECTED_FRED_SCHEMA")
        return validate_monthly_rows(reader, "EXNEUS", date_column=reader.fieldnames[0])
    except UnicodeDecodeError as exc:
        raise CoverageError("INVALID_ENCODING") from exc
