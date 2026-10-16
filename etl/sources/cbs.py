"""Read-only CBS StatLine 85773NED OData v4 housing adapter."""
import argparse
import csv
import math
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://datasets.cbs.nl/odata/v1/CBS/85773NED"
MONTH = re.compile(r"^(20\d{2})MM(0[1-9]|1[0-2])$")
LABELS = {
    "nl_hpi": ("prijsindex", "verkoopprijzen"),
    "nl_house_avg_eur": ("gemiddelde", "verkoopprijs"),
}

def make_session():
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def fetch_pages(session, endpoint, *, params=None, timeout=30):
    url = f"{BASE}/{endpoint}"
    items = []
    visited = set()
    while url:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "datasets.cbs.nl" or not parsed.path.startswith("/odata/v1/CBS/85773NED/"):
            raise ValueError("Unexpected CBS pagination URL")
        if url in visited:
            raise ValueError("CBS pagination loop")
        visited.add(url)
        response = session.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
        response.raise_for_status()
        body = response.json()
        if not isinstance(body.get("value"), list):
            raise ValueError("CBS OData response missing value list")
        items.extend(body["value"])
        url = body.get("@odata.nextLink")
        if url and url.startswith("/"):
            url = "https://datasets.cbs.nl" + url
        params = None
    return items

def resolve_fields(measures):
    found = {}
    for item in measures:
        label = str(item.get("Title", "")).strip().lower()
        code = item.get("Identifier")
        for series, words in LABELS.items():
            if all(word in label for word in words):
                if series in found:
                    raise ValueError(f"Ambiguous CBS measure for {series}")
                if not isinstance(code, str) or not code:
                    raise ValueError(f"Missing CBS measure Identifier for {series}")
                found[series] = code
    if set(found) != set(LABELS) or len(set(found.values())) != 2:
        raise ValueError("CBS measures could not be resolved unambiguously")
    return found

def resolve_period_dimension(dimensions):
    matches = [d.get("Identifier") for d in dimensions if "period" in str(d.get("Identifier", "")).lower()
               or "period" in str(d.get("Title", "")).lower()]
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise ValueError("CBS period dimension could not be resolved")
    return matches[0]

def parse_rows(rows, fields, period_dimension="Perioden"):
    reverse = {code: series for series, code in fields.items()}
    result = {}
    for row in rows:
        series = reverse.get(row.get("Measure"))
        if series is None:
            continue
        period = row.get(period_dimension, "")
        match = MONTH.fullmatch(str(period))
        if not match:
            continue
        month = f"{match.group(1)}-{match.group(2)}"
        raw = row.get("Value")
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
    session = session or make_session()
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    period_dimension = resolve_period_dimension(fetch_pages(session, "Dimensions"))
    # Filter to the two measures; download all periods with OData pagination.
    codes = list(fields.values())
    filter_expr = " or ".join(f"Measure eq '{code}'" for code in codes)
    rows = fetch_pages(session, "Observations", params={"$filter": filter_expr})
    return parse_rows(rows, fields, period_dimension)

def export_csv(rows, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "series", "value"])
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="Fetch CBS OData v4 monthly housing data without database writes")
    parser.add_argument("--output", default="data/cbs-housing.csv")
    args = parser.parse_args()
    rows = fetch_cbs()
    export_csv(rows, args.output)
    print(f"Exported {len(rows)} CBS observations to {args.output}")

if __name__ == "__main__":
    main()
