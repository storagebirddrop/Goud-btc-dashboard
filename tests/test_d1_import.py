import sqlite3
import pytest
from etl.d1_import import build_sql, verify_local

ROWS = [("2000-01", "nl_hpi", 60.0), ("2000-01", "nl_house_avg_eur", 175000.0)]

def test_deterministic_idempotent_sql():
    sql = build_sql(ROWS)
    assert sql == build_sql(list(reversed(ROWS)))
    assert verify_local(sql) == 2

def test_duplicate_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        build_sql(ROWS + ROWS[:1])

@pytest.mark.parametrize("rows", [
    [("2000-01", "nl_hpi", 60)],
    [("2000-01", "other", 60)] + ROWS,
    [("2000-13", "nl_hpi", 60)] + ROWS,
    [("2000-01", "nl_hpi", float("nan"))] + ROWS,
])
def test_invalid_rows_rejected(rows):
    with pytest.raises(ValueError):
        build_sql(rows)

def test_sql_roundtrip_and_upsert():
    sql = build_sql(ROWS)
    assert verify_local(sql) == 2
