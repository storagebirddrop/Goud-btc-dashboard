"""Read-only audit of the trading repository's BTC-USD and EURUSD daily bars.

No prices are written to artifacts or dashboard outputs.
"""
import csv
import json
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from etl.asset_quality import validate_daily_prices

SOURCE = "Trading repository (Yahoo Finance via yfinance)"
REQUIRED = {"Date", "Asset", "Timeframe", "Price"}


def audit_history(path):
    counts = Counter()
    dates = {"BTC": set(), "EURUSD": set()}
    prices = {"BTC": {}, "EURUSD": {}}
    issues = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("Missing required history.csv columns")
        for line, row in enumerate(reader, start=2):
            asset = row.get("Asset")
            if asset not in prices or row.get("Timeframe") != "1d":
                continue
            counts[asset] += 1
            day = row.get("Date", "")
            try:
                parsed = date.fromisoformat(day)
                if parsed.isoformat() != day:
                    raise ValueError("Noncanonical date")
                value = Decimal(row.get("Price", ""))
                if not value.is_finite() or value <= 0:
                    raise ValueError("Nonpositive or nonfinite price")
            except (ValueError, InvalidOperation, TypeError) as exc:
                issues.append({"line": line, "asset": asset, "reason": "invalid date or price"})
                continue
            if day in dates[asset]:
                issues.append({"line": line, "asset": asset, "reason": "duplicate daily date"})
                continue
            dates[asset].add(day)
            prices[asset][day] = str(value)
    series = {}
    for asset, currency in (("BTC", "USD"), ("EURUSD", "USD per EUR")):
        rows = prices[asset]
        summary = {"daily_rows": counts[asset], "valid_unique_days": len(rows),
                   "first": min(rows) if rows else None, "last": max(rows) if rows else None}
        if rows:
            if asset == "BTC":
                normalized = [{"date": day, "price": value, "asset": "BTC",
                               "currency": "USD", "source": SOURCE} for day, value in rows.items()]
                checked = validate_daily_prices(normalized, asset="BTC", currency="USD",
                                                source=SOURCE)
                summary["missing_days"] = len(checked["missing_days"])
                summary["missing_day_examples"] = checked["missing_days"][:10]
            else:
                start, end = date.fromisoformat(min(rows)), date.fromisoformat(max(rows))
                summary["calendar_span_days"] = (end - start).days + 1
                summary["missing_calendar_days"] = summary["calendar_span_days"] - len(rows)
                summary["note"] = "FX trades weekdays; weekends are not necessarily missing data."
        series[asset] = summary
    overlapping = dates["BTC"] & dates["EURUSD"]
    report = {"source": SOURCE, "status": "audit_only", "series": series,
              "btc_fx_same_day_overlap": len(overlapping),
              "btc_days_without_same_day_fx": len(dates["BTC"] - dates["EURUSD"]),
              "issue_count": len(issues), "issue_examples": issues[:20],
              "publication_approved": False,
              "caveats": ["Yahoo Finance redistribution terms not verified",
                          "BTC close is not a daily arithmetic mean",
                          "EURUSD is USD per EUR; convert BTC/USD to EUR by division",
                          "Weekend FX conversion policy requires explicit approval"]}
    return report


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m etl.trading_history_audit path/to/history.csv")
    report = audit_history(sys.argv[1])
    Path("trading-btc-audit-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["series"]["BTC"]["valid_unique_days"] == 0 or report["issue_count"]:
        raise SystemExit("BTC audit failed: missing BTC or malformed/duplicate records")


if __name__ == "__main__":
    main()
