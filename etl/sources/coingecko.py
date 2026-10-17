"""Read-only CoinGecko BTC daily market-chart adapter.

Public/demo API historical limits vary by plan. This adapter does not publish
or persist downloaded prices; use only within the permitted access window.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import requests

from etl.asset_quality import validate_daily_prices, monthly_arithmetic_mean

BASE_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"


def parse_market_chart(payload, *, start, end, currency):
    if not isinstance(payload, dict) or not isinstance(payload.get("prices"), list):
        raise ValueError("Malformed CoinGecko market chart response")
    observations = {}
    for pair in payload["prices"]:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Malformed CoinGecko price observation")
        timestamp, value = pair
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("Invalid CoinGecko timestamp")
        try:
            day = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            raise ValueError("Invalid CoinGecko timestamp") from None
        if start <= day <= end:
            price = Decimal(str(value))
            if not price.is_finite() or price <= 0:
                raise ValueError("Invalid CoinGecko price")
            # Range endpoint can include multiple intraday observations.
            # Use the earliest UTC observation of each day, deterministically.
            prior = observations.get(day)
            if prior is None or timestamp < prior[0]:
                observations[day] = (timestamp, price)
    if not observations:
        raise ValueError(f"CoinGecko returned no BTC/{currency} prices for {start}..{end}")
    rows = [{"date": day, "price": str(value), "asset": "BTC",
             "currency": currency, "source": "CoinGecko"}
            for day, (_, value) in sorted(observations.items())]
    return validate_daily_prices(rows, asset="BTC", currency=currency, source="CoinGecko")


def fetch_daily_prices(*, start, end, currency="EUR", session=None):
    if currency not in {"EUR", "USD"}:
        raise ValueError("Unsupported currency")
    try:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError("Invalid date range") from None
    if a.isoformat() != start or b.isoformat() != end or a > b:
        raise ValueError("Invalid date range")
    from datetime import datetime, time, timedelta
    start_ts = int(datetime.combine(a, time.min, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.combine(b + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp()) - 1
    response = (session or requests.Session()).get(
        BASE_URL, params={"vs_currency": currency.lower(), "from": start_ts, "to": end_ts},
        timeout=30)
    response.raise_for_status()
    return parse_market_chart(response.json(), start=start, end=end, currency=currency)


def monthly_prices(*, start, end, currency="EUR", session=None):
    return monthly_arithmetic_mean(fetch_daily_prices(start=start, end=end,
                                                       currency=currency, session=session))
