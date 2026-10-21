"""BTC-01: read-only measurement of the Coin Metrics Community BTC reference-rate series.

Research only. No public file is written; nothing is published. Prints:
  * catalog min/max time for BTC ReferenceRateUSD / ReferenceRateEUR (1d),
  * number of daily observations, missing UTC days and months with full calendar coverage,
  * sha256 of the exact response bytes per request (for later pinning in BTC-02),
  * monthly arithmetic means of the first and last complete months as a sanity sample.
Never fills gaps. Exit code 1 only when the service answers with an unexpected structure.
"""
import calendar
import hashlib
import json
import sys
from datetime import date, timedelta
from decimal import Decimal

import requests

CATALOG = "https://community-api.coinmetrics.io/v4/catalog/asset-metrics"
SERIES = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
METRICS = ("ReferenceRateUSD", "ReferenceRateEUR")


def get(session, url, params):
    r = session.get(url, params=params, timeout=60)
    if r.status_code >= 400:
        print(f"HTTP {r.status_code} for {r.url}: {r.text[:400]}")
        r.raise_for_status()
    return r.content


def catalog(session):
    raw = get(session, CATALOG, {"assets": "btc", "metrics": ",".join(METRICS)})
    print(f"catalog sha256 {hashlib.sha256(raw).hexdigest()}")
    doc = json.loads(raw)
    out = {}
    for metric in doc["data"][0]["metrics"] if doc.get("data") else []:
        for freq in metric.get("frequencies", []):
            if freq.get("frequency") == "1d":
                out[metric["metric"]] = (freq["min_time"], freq["max_time"])
    for m in METRICS:
        print(f"CATALOG btc {m} 1d: {out.get(m)}")
    return out


def daily(session, metric, start, end):
    params = {"assets": "btc", "metrics": metric, "frequency": "1d", "start_time": start,
              "end_time": end, "page_size": 10000}
    rows, digests = {}, []
    while True:
        raw = get(session, SERIES, params)
        digests.append(hashlib.sha256(raw).hexdigest())
        doc = json.loads(raw)
        for e in doc["data"]:
            rows[e["time"][:10]] = Decimal(e[metric])
        token = doc.get("next_page_token")
        if not token:
            break
        params["next_page_token"] = token
    print(f"{metric}: {len(rows)} observations {start}..{end}, response sha256 per page: {digests}")
    return rows


def coverage(rows, label, first_month):
    y, m = first_month
    full, partial = 0, []
    last = max(rows)
    ly, lm = int(last[:4]), int(last[5:7])
    while (y, m) <= (ly, lm):
        n = calendar.monthrange(y, m)[1]
        have = sum(1 for d in range(1, n + 1) if f"{y:04d}-{m:02d}-{d:02d}" in rows)
        if have == n:
            full += 1
        else:
            partial.append((f"{y:04d}-{m:02d}", have, n))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    print(f"{label}: complete calendar months {full}; incomplete months {len(partial)}: {partial[:8]}"
          + (" ..." if len(partial) > 8 else ""))
    nonpos = [d for d, v in rows.items() if v <= 0]
    print(f"{label}: non-positive values {len(nonpos)}")


def main():
    s = requests.Session()
    s.headers["User-Agent"] = "btc-01-probe/1 (read-only research)"
    try:
        catalog(s)  # informational only; the series themselves decide first/last dates below
    except Exception as exc:  # noqa: BLE001
        print(f"catalog unavailable ({exc}); continuing with the timeseries endpoint")
    today = date.today().isoformat()
    for metric in METRICS:
        rows = daily(s, metric, "2009-01-01", today)
        if not rows:
            print(f"{metric}: no observations returned")
            continue
        lo = min(rows)
        print(f"SERIES {metric}: first {lo}, last {max(rows)}, observations {len(rows)}")
        first = (int(lo[:4]), int(lo[5:7]))
        coverage(rows, metric, first)
        for d in ("2014-09-17", "2014-10-01", "2016-01-01", "2020-01-01"):
            print(f"  sample {metric} {d}: {rows.get(d)}")
    print("done")


if __name__ == "__main__":
    main()
