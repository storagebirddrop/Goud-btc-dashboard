import csv
import hashlib
import io
import pytest
from tools.hist_02_coverage import CoverageError, validate_monthly_rows, validate_fred_csv

def rows():
    return [{"DATE": f"{year}-{month:02d}-01", "EXNEUS": "2.50"}
            for year in range(1975, 2000) for month in range(1, 13)]

def test_300_months():
    assert validate_monthly_rows(rows(), "EXNEUS")["months"] == 300

def test_missing_month():
    with pytest.raises(CoverageError, match="MONTH_COVERAGE_ERROR"):
        validate_monthly_rows(rows()[:-1], "EXNEUS")

def test_duplicate_month():
    with pytest.raises(CoverageError, match="duplicates"):
        validate_monthly_rows(rows() + [rows()[0]], "EXNEUS")

@pytest.mark.parametrize("bad", ["", ".", "NaN", "Infinity", "-1", "0"])
def test_invalid_fx(bad):
    data = rows()
    data[0]["EXNEUS"] = bad
    with pytest.raises(CoverageError, match="INVALID_NUMBER"):
        validate_monthly_rows(data, "EXNEUS")

def test_wrong_column():
    with pytest.raises(CoverageError, match="WRONG_SOURCE_COLUMN"):
        validate_monthly_rows(rows(), "GOLD")

def test_fred_hash_mismatch():
    with pytest.raises(CoverageError, match="HASH_MISMATCH"):
        validate_fred_csv(b"DATE,EXNEUS\n", expected_sha256="0" * 64)

def test_fred_schema_rejected():
    raw = b"DATE,USD_PER_NLG\n"
    with pytest.raises(CoverageError, match="UNEXPECTED_FRED_SCHEMA"):
        validate_fred_csv(raw, expected_sha256=hashlib.sha256(raw).hexdigest())

def test_fred_csv_verified():
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["DATE", "EXNEUS"])
    writer.writeheader()
    writer.writerows(rows())
    raw = out.getvalue().encode()
    assert validate_fred_csv(raw, expected_sha256=hashlib.sha256(raw).hexdigest())["months"] == 300
