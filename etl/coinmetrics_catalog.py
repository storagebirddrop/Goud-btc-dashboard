"""Read-only Coin Metrics catalog availability probe. No prices are persisted."""
import json
from pathlib import Path

import requests

URL = "https://community-api.coinmetrics.io/v4/catalog/asset-metrics"
METRICS = ("ReferenceRateEUR", "ReferenceRateUSD")


def parse_catalog(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Malformed Coin Metrics catalog response")
    found = {}
    for item in payload["data"]:
        if not isinstance(item, dict) or item.get("asset") != "btc":
            continue
        metric = item.get("metric")
        if metric not in METRICS:
            continue
        if metric in found:
            raise ValueError("Duplicate BTC catalog metric")
        frequencies = item.get("frequencies")
        if not isinstance(frequencies, list):
            raise ValueError("Missing catalog frequencies")
        daily = [row for row in frequencies
                 if isinstance(row, dict) and row.get("frequency") == "1d"]
        if len(daily) != 1:
            raise ValueError(f"Missing or ambiguous daily frequency for {metric}")
        record = daily[0]
        start, end = record.get("min_time"), record.get("max_time")
        if not isinstance(start, str) or not isinstance(end, str) or start > end:
            raise ValueError(f"Invalid catalog coverage for {metric}")
        found[metric] = {"start": start, "end": end}
    return {"source": "Coin Metrics Community", "asset": "BTC",
            "status": "complete" if len(found) == len(METRICS) else "incomplete",
            "metrics": found, "missing_metrics": [m for m in METRICS if m not in found]}


def main():
    path = Path("btc-catalog-report.json")
    report = {"source": "Coin Metrics Community", "asset": "BTC", "status": "failed"}
    try:
        entries = []
        for metric in METRICS:
            response = requests.get(URL, params={"assets": "btc", "metrics": metric}, timeout=30)
            if not response.ok:
                try:
                    detail = json.dumps(response.json(), ensure_ascii=True)[:1000]
                except ValueError:
                    detail = response.text[:1000]
                raise ValueError(f"Coin Metrics catalog {metric}: HTTP {response.status_code}; "
                                 f"provider response: {detail}")
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError(f"Malformed catalog response for {metric}")
            entries.extend(payload["data"])
        report = parse_catalog({"data": entries})
        if report["missing_metrics"]:
            raise ValueError("BTC daily reference rate metrics unavailable")
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
