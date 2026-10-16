import csv
import pytest
from etl.validate import validate_file, assert_valid

def write_rows(tmp_path, rows):
    path = tmp_path / "input.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "series", "value"])
        w.writeheader()
        w.writerows(rows)
    return path

def test_valid_monthly_data(tmp_path):
    path = write_rows(tmp_path, [{"date": "2000-01", "series": "gold_eur_oz", "value": "250"}])
    assert assert_valid(path)["observations"] == 1

def test_duplicate_monthly_values(tmp_path):
    row = {"date": "2000-01", "series": "nl_hpi", "value": "100"}
    path = write_rows(tmp_path, [row, row])
    assert "duplicate monthly" in validate_file(path)["errors"][0]

@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_reject_invalid_value(tmp_path, value):
    path = write_rows(tmp_path, [{"date": "2000-01", "series": "gold_eur_oz", "value": value}])
    with pytest.raises(ValueError):
        assert_valid(path)

def test_reject_unknown_series(tmp_path):
    path = write_rows(tmp_path, [{"date": "2000-01", "series": "fake", "value": "123"}])
    with pytest.raises(ValueError):
        assert_valid(path)
