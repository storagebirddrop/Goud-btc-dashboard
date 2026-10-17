import csv

from etl.trading_history_audit import audit_history


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "Asset", "Timeframe", "Price"])
        writer.writeheader()
        writer.writerows(rows)


def test_audit_reports_overlap_and_gaps(tmp_path):
    path = tmp_path / "history.csv"
    write_csv(path, [
        {"Date": "2026-01-01", "Asset": "BTC", "Timeframe": "1d", "Price": "100"},
        {"Date": "2026-01-03", "Asset": "BTC", "Timeframe": "1d", "Price": "120"},
        {"Date": "2026-01-01", "Asset": "EURUSD", "Timeframe": "1d", "Price": "1.2"},
        {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1w", "Price": "105"},
    ])
    report = audit_history(path)
    assert report["series"]["BTC"]["valid_unique_days"] == 2
    assert report["series"]["BTC"]["missing_days"] == 1
    assert report["btc_fx_same_day_overlap"] == 1
    assert report["btc_days_without_same_day_fx"] == 1
    assert report["publication_approved"] is False


def test_audit_flags_duplicates_and_invalid_values(tmp_path):
    path = tmp_path / "history.csv"
    write_csv(path, [
        {"Date": "2026-01-01", "Asset": "BTC", "Timeframe": "1d", "Price": "100"},
        {"Date": "2026-01-01", "Asset": "BTC", "Timeframe": "1d", "Price": "101"},
        {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1d", "Price": "NaN"},
        {"Date": "2026-01-03", "Asset": "BTC", "Timeframe": "1d", "Price": "-1"},
    ])
    report = audit_history(path)
    assert report["issue_count"] == 3
    assert report["series"]["BTC"]["valid_unique_days"] == 1


def test_audit_rejects_missing_columns(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text("Date,Asset,Price\n")
    try:
        audit_history(path)
    except ValueError as exc:
        assert "columns" in str(exc)
    else:
        raise AssertionError("Expected missing columns to be rejected")
