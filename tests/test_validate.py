import csv
import pytest
from etl.validate import validate_file, assert_valid
from etl.main import load_csv

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
    assert load_csv(path)[("gold_eur_oz", "2000-01")] == [250]

def test_duplicate_monthly_values(tmp_path):
    row = {"date": "2000-01", "series": "nl_hpi", "value": "100"}
    path = write_rows(tmp_path, [row, row])
    assert "duplicate observation" in validate_file(path)["errors"][0]
    with pytest.raises(ValueError):
        load_csv(path)

@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_reject_invalid_value(tmp_path, value):
    path = write_rows(tmp_path, [{"date": "2000-01", "series": "gold_eur_oz", "value": value}])
    with pytest.raises(ValueError):
        assert_valid(path)

def test_reject_unknown_series(tmp_path):
    path = write_rows(tmp_path, [{"date": "2000-01", "series": "fake", "value": "123"}])
    with pytest.raises(ValueError):
        assert_valid(path)

def test_daily_gold_multiple_days_allowed(tmp_path):
    path = write_rows(tmp_path, [{"date": "2000-01-03", "series": "gold_daily_eur_oz", "value": "300"}, {"date": "2000-01-04", "series": "gold_daily_eur_oz", "value": "310"}])
    assert load_csv(path)[("gold_daily_eur_oz", "2000-01-03")] == [300]\n    assert load_csv(path)[("gold_daily_eur_oz", "2000-01-04")] == [310]

def test_daily_duplicate_date_rejected(tmp_path):
    row = {"date": "2000-01-03", "series": "gold_daily_eur_oz", "value": "300"}
    path = write_rows(tmp_path, [row, row])
    with pytest.raises(ValueError, match="duplicate observation"):
        load_csv(path)

def test_monthly_date_not_arbitrary_day(tmp_path):
    path = write_rows(tmp_path, [{"date": "2000-01-15", "series": "nl_hpi", "value": "100"}])
    with pytest.raises(ValueError, match="monthly dates"):
        load_csv(path)

def test_pre2000_rejected(tmp_path):
    path = write_rows(tmp_path, [{"date": "1999-12", "series": "nl_hpi", "value": "100"}])
    with pytest.raises(ValueError, match="before 2000"):
        load_csv(path)
