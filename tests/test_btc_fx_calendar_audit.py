import csv

from etl.btc_fx_calendar_audit import diagnose_fx_calendar


def test_fx_gap_breakdown_by_weekday_and_month(tmp_path):
    path = tmp_path / "history.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Date", "Asset", "Timeframe", "Price"])
        writer.writeheader()
        writer.writerows([
            {"Date": "2026-01-02", "Asset": "BTC", "Timeframe": "1d", "Price": "1"},
            {"Date": "2026-01-03", "Asset": "BTC", "Timeframe": "1d", "Price": "1"},
            {"Date": "2026-01-04", "Asset": "BTC", "Timeframe": "1d", "Price": "1"},
            {"Date": "2026-01-05", "Asset": "BTC", "Timeframe": "1d", "Price": "1"},
            {"Date": "2026-01-02", "Asset": "EURUSD", "Timeframe": "1d", "Price": "1"},
        ])
    report = diagnose_fx_calendar(path)
    assert report["btc_days"] == 4
    assert report["same_day_fx_days"] == 1
    assert report["missing_same_day_fx_days"] == 3
    assert report["missing_fx_by_weekday"]["Saturday"] == 1
    assert report["missing_fx_by_weekday"]["Sunday"] == 1
    assert report["missing_fx_by_weekday"]["Monday"] == 1
    assert report["missing_fx_weekdays"] == 1
    assert report["missing_fx_weekday_dates"] == ["2026-01-05"]
    assert report["missing_fx_age_days"] == {"1": 1, "2": 1, "3": 1}
    assert report["unmatched_btc_days_by_max_prior_fx_age"] == {"0": 3, "1": 2, "2": 1, "3": 0, "4": 0, "7": 0}
    assert report["missing_fx_months"] == {"2026-01": 3}
    assert report["publication_approved"] is False
