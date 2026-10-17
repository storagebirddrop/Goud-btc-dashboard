"""Read-only FX calendar diagnostics for the trading BTC history.

Never publishes market prices; evaluates same-day FX availability only.
"""
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def diagnose_fx_calendar(path):
    btc, fx = set(), set()
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"Date", "Asset", "Timeframe"}.issubset(reader.fieldnames):
            raise ValueError("Missing history columns")
        for row in reader:
            if row["Timeframe"] != "1d" or row["Asset"] not in {"BTC", "EURUSD"}:
                continue
            day = date.fromisoformat(row["Date"])
            (btc if row["Asset"] == "BTC" else fx).add(day)
    if not btc:
        raise ValueError("No BTC daily observations")
    missing = sorted(btc - fx)
    by_weekday = Counter(WEEKDAYS[d.weekday()] for d in missing)
    by_month = Counter(d.strftime("%Y-%m") for d in missing)
    weekday_missing = [d for d in missing if d.weekday() < 5]
    return {
        "status": "diagnostic_only",
        "btc_days": len(btc),
        "same_day_fx_days": len(btc & fx),
        "missing_same_day_fx_days": len(missing),
        "missing_fx_by_weekday": {name: by_weekday[name] for name in WEEKDAYS},
        "missing_fx_weekdays": len(weekday_missing),
        "missing_fx_months": dict(sorted(by_month.items())),
        "publication_approved": False,
        "note": "No FX carry-forward or conversion applied; weekday gaps require review.",
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m etl.btc_fx_calendar_audit history.csv")
    result = diagnose_fx_calendar(sys.argv[1])
    Path("btc-fx-calendar-report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
