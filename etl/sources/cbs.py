"""Read-only CBS StatLine 85773NED adapter. Resolves topic columns from metadata."""
import argparse
import csv
import math
import re
from pathlib import Path

import requests

BASE = "https://opendata.cbs.nl/ODataApi/OData/85773NED"
INDEX_LABEL = "Prijsindex verkoopprijzen"
PRICE_LABEL = "Gemiddelde verkoopprijs"

def fetch_pages(session, endpoint, *, timeout=30):
    url = f"{BASE}/{endpoint}"
    items = []
    while url:
        if not url.startswith(BASE + "/"):
            raise ValueError("Unexpected CBS pagination URL")
        response = session.get(url, timeout=timeout, headers={"Accept": "application/json"})
        response.raise_for_status()
        body = response.json()
        items.extend(body.get("value", []))
        url = body.get("odata.nextLink") or body.get("@odata.nextLink")
        if url and url.startswith("/"):
            url = "https://opendata.cbs.nl" + url
    return items

def resolve_fields(properties):
    found = {}
    for item in properties:
        label = item.get("Title", "").strip().lower()
        key = item.get("Key")
        if label == INDEX_LABEL.lower():
            found["nl_hpi"] = key
        if label == PRICE_LABEL.lower():
            found["nl_house_avg_eur"] = key
    if set(found) != {"nl_hpi", "nl_house_avg_eur"} or len(set(found.values())) != 2:
        raise ValueError("CBS topic fields could not be resolved unambiguously")
    return found

def parse_rows(rows, fields):
    result = {}
    for row in rows:
        period = row.get("Perioden", "")
        if not re.fullmatch(r"20\d{2}MM(?:0[1-9]|1[0-2])", period):
            continue
        month = f"{period[:4]}-{period[-2:]}"
        for series, key in fields.items():
            raw = row.get(key)
            if raw is None or raw == "":
                raise ValueError(f"Missing {series} at {month}")
            value = float(raw)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid {series} at {month}")
            identity = (series, month)
            if identity in result:
                raise ValueError(f"Duplicate CBS observation: {identity}")
            result[identity] = value
    if not result:
        raise ValueError("No monthly CBS observations")
    return sorted((period, series, value) for (series, period), value in result.items())

def fetch_cbs(*, session=None):
    session = session or requests.Session()
    fields = resolve_fields(fetch_pages(session, "DataProperties"))
    return parse_rows(fetch_pages(session, "TypedDataSet"), fields)

def export_csv(rows, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "series", "value"])
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="Fetch CBS monthly housing prices without database writes")
    parser.add_argument("--output", default="data/cbs-housing.csv")
    args = parser.parse_args()
    rows = fetch_cbs()
    export_csv(rows, args.output)
    print(f"Exported {len(rows)} CBS observations to {args.output}")

if __name__ == "__main__":
    main()
