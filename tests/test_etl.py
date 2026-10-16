from collections import defaultdict
import pytest
from etl.main import month, transform, export_sql

def test_month():
    assert month('2000-01-15') == '2000-01'
    assert month('1999-12-31') is None

def test_gold_daily_average():
    assert transform({('gold_daily_eur_oz', '2000-01'): [300, 400]})[('gold_eur_oz', '2000-01')] == 350

def test_duplicate_monthly_rejected():
    with pytest.raises(ValueError):
        transform({('nl_hpi', '2000-01'): [100, 101]})

def test_empty_export_rejected(tmp_path):
    with pytest.raises(ValueError):
        export_sql({}, tmp_path / 'upsert.sql')
