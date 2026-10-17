"""Read-only Coin Metrics Community BTC reference-rate adapter.

No network request is made at import time. No production data is written.
See https://docs.coinmetrics.io/api/v4 and community API terms before publishing.
"""
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

import requests

from etl.asset_quality import validate_daily_prices, monthly_arithmetic_mean

BASE_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
METRICS = {"USD": "ReferenceRateUSD", "EUR": "ReferenceRateEUR"}


def parse_page(payload, *, currency):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Malformed Coin Metrics response")
    metric = METRICS[currency]
    records = []
    for entry in payload["data"]:
        if not isinstance(entry, dict) or entry.get("asset") != "btc":
            raise ValueError("Unexpected asset in Coin Metrics response")
        timestamp = entry.get("time")
        if not isinstance(timestamp, str) or len(timestamp) < 10:
            raise ValueError("Missing Coin Metrics timestamp")
        day = timestamp[:10]
        try:
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError
        except ValueError:
            raise ValueError("Invalid Coin Metrics timestamp") from None
        if metric not in entry:
            raise ValueError("Missing Coin Metrics reference rate")
        records.append({"date": day, "price": entry[metric], "asset": "BTC",
                        "currency": currency, "source": "Coin Metrics Community"})
    next_page = payload.get("next_page_token")
    if next_page is not None and (not isinstance(next_page, str) or not next_page):
        raise ValueError("Invalid pagination token")
    return records, next_page


def fetch_reference_rates(*, start, end, currency="EUR", session=None, max_pages=100):
    """Return validated daily observations and explicit missing dates.

    Never silently fill gaps. API pagination is bounded and must stay on the
    official HTTPS endpoint. Caller decides whether data may be redistributed.
    """
    if currency not in METRICS:
        raise ValueError("Unsupported reference-rate currency")
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValueError("Invalid date range") from None
    if start_date.isoformat() != start or end_date.isoformat() != end or start_date > end_date:
        raise ValueError("Invalid date range")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ValueError("Invalid page limit")
    session = session or requests.Session()
    params = {"assets": "btc", "metrics": METRICS[currency],
              "frequency": "1d", "start_time": start, "end_time": end, "page_size": 10000}
    records = []
    tokens = set()
    pages_seen = 0
    for _ in range(max_pages):
        response = session.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        page, token = parse_page(payload, currency=currency)
        pages_seen += 1
        records.extend(page)
        if token is None:
            break
        if token in tokens:
            raise ValueError("Repeated Coin Metrics pagination token")
        tokens.add(token)
        params["next_page_token"] = token
    else:
        raise ValueError("Coin Metrics pagination exceeded page limit")
    if not records:
        raise ValueError(f"Coin Metrics returned no BTC/{currency} observations for {start}..{end} "
                         f"({pages_seen} valid API page(s)); check metric availability in the Coin Metrics catalog")
    checked = validate_daily_prices(records, asset="BTC", currency=currency,
                                    source="Coin Metrics Community", expected_start=start, expected_end=end)
    if checked["start"] < start or checked["end"] > end:
        raise ValueError("Coin Metrics returned observations outside requested range")
    return checked


def monthly_reference_rates(*, start, end, currency="EUR", session=None):
    checked = fetch_reference_rates(start=start, end=end, currency=currency, session=session)
    return monthly_arithmetic_mean(checked)
