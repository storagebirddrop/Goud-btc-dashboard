"""Read-only monthly BTC/EUR FX carry sensitivity; exports aggregates only."""
import csv
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

CAPS = (0, 1, 2, 3, 4, 7)


def analyze(path):
    series = {"BTC": {}, "EURUSD": {}}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"Date", "Asset", "Timeframe", "Price"}.issubset(reader.fieldnames):
            raise ValueError("Missing required history columns")
        for row in reader:
            asset = row["Asset"]
            if asset not in series or row["Timeframe"] != "1d":
                continue
            day = date.fromisoformat(row["Date"])
            value = Decimal(row["Price"])
            if not value.is_finite() or value <= 0 or day in series[asset]:
                raise ValueError("Invalid or duplicate daily price")
            series[asset][day] = value
    btc, fx = series["BTC"], series["EURUSD"]
    if not btc or not fx:
        raise ValueError("BTC and EURUSD daily observations required")
    latest_day = None
    latest_value = None
    rows = defaultdict(lambda: defaultdict(list))
    ages = defaultdict(lambda: defaultdict(list))
    for day in sorted(set(btc) | set(fx)):
        if day in fx:
            latest_day, latest_value = day, fx[day]
        if day not in btc:
            continue
        month = day.strftime("%Y-%m")
        for cap in CAPS:
            if latest_day is not None and (day - latest_day).days <= cap:
                rows[month][cap].append(btc[day] / latest_value)
                ages[month][cap].append((day - latest_day).days)
    result = []
    for month in sorted({d.strftime("%Y-%m") for d in btc}):
        total = sum(d.strftime("%Y-%m") == month for d in btc)
        baseline = rows[month][0]
        month_record = {"month": month, "btc_days": total, "scenarios": {}}
        for cap in CAPS:
            vals = rows[month][cap]
            mean = sum(vals) / len(vals) if vals else None
            base_mean = sum(baseline) / len(baseline) if baseline else None
            delta = (mean / base_mean - 1) * 100 if mean is not None and base_mean is not None else None
            month_record["scenarios"][str(cap)] = {
                "covered_days": len(vals),
                "coverage_pct": round(100 * len(vals) / total, 4),
                "max_fx_age_days": max(ages[month][cap]) if vals else None,
                "mean_delta_vs_same_day_pct": round(float(delta), 6) if delta is not None else None,
            }
        result.append(month_record)
    return {
        "status": "audit_only",
        "source": "Trading repository BTC/USD close and EURUSD USD-per-EUR",
        "method": "daily BTC/EUR = BTC/USD divided by latest prior or same-day EURUSD; arithmetic mean of eligible daily observations",
        "warning": "Scenarios have different day coverage; mean differences mix FX carry and sample composition effects.",
        "publication_approved": False,
        "price_values_exported": False,
        "months": result,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m etl.btc_fx_monthly_sensitivity history.csv")
    report = analyze(sys.argv[1])
    Path("btc-fx-monthly-sensitivity-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "months": len(report["months"]), "publication_approved": False}))


if __name__ == "__main__":
    main()
