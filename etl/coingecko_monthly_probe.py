"""Read-only CoinGecko full-month coverage probe; exports metadata only."""
import json
import os
from calendar import monthrange
from datetime import date
from pathlib import Path

import requests

from etl.sources.coingecko import fetch_daily_prices

def main():
    month = os.environ.get("TARGET_MONTH", "2026-09")
    currency = os.environ.get("QUOTE_CURRENCY", "EUR")
    report = {"source": "CoinGecko", "month": month, "currency": currency,
              "status": "failed", "price_values_exported": False}
    try:
        if len(month) != 7 or month[4] != "-":
            raise ValueError("TARGET_MONTH must be YYYY-MM")
        first = date.fromisoformat(month + "-01")
        if first.strftime("%Y-%m") != month:
            raise ValueError("Invalid month")
        last = first.replace(day=monthrange(first.year, first.month)[1])
        if currency not in ("EUR", "USD"):
            raise ValueError("Unsupported currency")
        session = requests.Session()
        key = os.environ.get("COINGECKO_DEMO_API_KEY")
        if key:
            session.headers["x-cg-demo-api-key"] = key
        print(f"Testing CoinGecko BTC/{currency} for {first}..{last}; key present: {bool(key)}", flush=True)
        checked = fetch_daily_prices(start=first.isoformat(), end=last.isoformat(),
                                     currency=currency, session=session)
        missing = checked["missing_days"]
        report.update({"observations": checked["count"], "expected_days": last.day,
                       "missing_days": missing, "status": "complete" if not missing and checked["count"] == last.day else "incomplete"})
        print(f"Coverage: {checked['count']}/{last.day}; missing days: {missing}", flush=True)
        if report["status"] != "complete":
            raise ValueError("Incomplete calendar-month coverage")
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        report["error"] = f"CoinGecko HTTP {code}"
        print(f"CoinGecko HTTP {code}; check historical window and API plan", flush=True)
        raise
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        Path("coingecko-monthly-report.json").write_text(json.dumps(report, indent=2) + "\n")

if __name__ == "__main__":
    main()
