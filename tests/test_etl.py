from collections import defaultdict
import pytest
from etl.main import month, transform, export_sql

def test_month():
    assert month('2000-01-15') == '2000-01'
    assert month('1999-12-31') is None

def test_gold_daily_average():
    assert transform({('gold_daily_eur_oz', '2000-01-03'): [300], ('gold_daily_eur_oz', '2000-01-04'): [400]})[('gold_eur_oz', '2000-01')] == 350

def test_duplicate_monthly_rejected():
    with pytest.raises(ValueError):
        transform({('nl_hpi', '2000-01'): [100, 101]})

def test_empty_export_rejected(tmp_path):
    with pytest.raises(ValueError):
        export_sql({}, tmp_path / 'upsert.sql')

def test_duplicate_daily_across_files(tmp_path):
    from etl.main import load_csv
    import csv
    merged = defaultdict(list)
    for name in ("one.csv", "two.csv"):
        path = tmp_path / name
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "series", "value"])
            w.writeheader()
            w.writerow({"date": "2000-01-03", "series": "gold_daily_eur_oz", "value": 300})
        for key, values in load_csv(path).items():
            merged[key].extend(values)
    with pytest.raises(ValueError, match="Duplicate daily"):
        transform(merged)

def test_daily_gold_conflicts_with_monthly():
    with pytest.raises(ValueError, match="Conflicting gold"):
        transform({("gold_eur_oz", "2000-01"): [350], ("gold_daily_eur_oz", "2000-01-03"): [300]})
