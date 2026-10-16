"""ECB daily USD per EUR exchange-rate adapter. Read-only, explicit fetch."""
import argparse
import csv
import io
import math
from datetime import date
from pathlib import Path

import requests

SERIES_KEY = "EXR.D.USD.EUR.SP00.A"
URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"

def parse_ecb_csv(content: str) -> list[tuple[str, float]]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if not reader.fieldnames or not {"TIME_PERIOD", "OBS_VALUE"}.issubset(reader.fieldnames):
        raise ValueError("ECB response missing TIME_PERIOD or OBS_VALUE")
    observations = {}
    for row in reader:
        if row.get("KEY") and row["KEY"] != SERIES_KEY:
            raise ValueError("Unexpected ECB series key")
        period = row["TIME_PERIOD"]
        d = date.fromisoformat(period)
        value = float(row["OBS_VALUE"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid ECB rate: {period}")
        if period in observations:
            raise ValueError(f"Duplicate ECB date: {period}")
        observations[period] = value
    if not observations:
        raise ValueError("ECB response contained no observations")
    return sorted(observations.items())

def fetch_ecb(*, start="2000-01-01", timeout=30):
    date.fromisoformat(start)
    response = requests.get(URL, params={"startPeriod": start, "format": "csvdata"}, timeout=timeout, headers={"User-Agent": "goud-btc-dashboard/0.1 (research ETL)"})
    response.raise_for_status()
    return parse_ecb_csv(response.text)

def export_csv(rows, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "usd_per_eur"])
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="Fetch ECB USD per EUR daily rates; no database writes")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--output", default="data/ecb-usd-per-eur.csv")
    args = parser.parse_args()
    rows = fetch_ecb(start=args.start)
    export_csv(rows, args.output)
    print(f"Exported {len(rows)} ECB rates to {args.output}")

if __name__ == "__main__":
    main()
