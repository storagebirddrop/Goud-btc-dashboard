import csv

import pytest

from etl.btc_fx_monthly_sensitivity import analyze


def write_rows(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "Asset", "Timeframe", "Price"])
        writer.writeheader()
        writer.writerows(rows)


def test_monthly_sensitivity_and_no_price_export(tmp_path):
    path = tmp_path / "history.csv"
    write_rows(path, [
        {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1d", "Price": "200"},
        {"Date": "2026-01-03", "Asset": "BTC", "Timeframe": "1d", "Price": "300"},
        {"Date": "2026-01-04", "Asset": "BTC", "Timeframe": "1d", "Price": "400"},
        {"Date": "2026-01-05", "Asset": "BTC", "Timeframe": "1d", "Price": "500"},
        {"Date": "2026-01-02", "Asset": "EURUSD", "Timeframe": "1d", "Price": "2"},
        {"Date": "2026-01-05", "Asset": "EURUSD", "Timeframe": "1d", "Price": "2.5"},
    ])
    report = analyze(path)
    m = report["months"][0]
    assert m["btc_days"] == 4
    assert m["scenarios"]["0"]["covered_days"] == 2
    assert m["scenarios"]["1"]["covered_days"] == 3
    assert m["scenarios"]["2"]["covered_days"] == 4
    assert m["scenarios"]["2"]["mean_delta_vs_same_day_pct"] == pytest.approx(15.0)
    assert report["price_values_exported"] is False
    assert "price" not in str(m).lower()


def test_reject_duplicate_prices(tmp_path):
    path = tmp_path / "history.csv"
    write_rows(path, [
        {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1d", "Price": "200"},
        {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1d", "Price": "201"},
        {"Date": "2026-01-02", "Asset": "EURUSD", "Timeframe": "1d", "Price": "2"},
    ])
    with pytest.raises(ValueError, match="duplicate"):
        analyze(path)
