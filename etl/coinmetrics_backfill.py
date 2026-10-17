"""Manual BTC history verification. Produces only a coverage report, no price export."""
import json
import os
from datetime import date
from pathlib import Path

from etl.sources.coinmetrics import fetch_reference_rates


def main():
    start = os.environ["START_DATE"]
    end = os.environ["END_DATE"]
    currency = os.environ.get("QUOTE_CURRENCY", "EUR")
    report_path = Path("backfill-report.json")
    report = {"source": "Coin Metrics Community", "asset": "BTC", "currency": currency,
              "start_requested": start, "end_requested": end, "status": "failed"}
    try:
        if date.fromisoformat(start).isoformat() != start or date.fromisoformat(end).isoformat() != end:
            raise ValueError("Dates must use YYYY-MM-DD")
        if currency not in {"EUR", "USD"}:
            raise ValueError("Unsupported currency")
        checked = fetch_reference_rates(start=start, end=end, currency=currency)
        missing = checked["missing_days"]
        report.update({"status": "complete" if not missing else "incomplete",
                       "start_observed": checked["start"], "end_observed": checked["end"],
                       "observations": checked["count"], "missing_days": missing[:100],
                       "missing_days_total": len(missing)})
        if missing or checked["start"] != start or checked["end"] != end:
            raise ValueError("Requested date range is incomplete")
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
