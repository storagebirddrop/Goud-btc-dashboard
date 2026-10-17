from datetime import datetime, timezone

import pytest

from etl.sources.coingecko import fetch_daily_prices, monthly_prices


def stamp(day, hour=0):
    return int(datetime.fromisoformat(day + f"T{hour:02}:00:00+00:00").timestamp() * 1000)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload)


def test_valid_prices_and_parameters():
    session = Session({"prices": [[stamp("2026-09-01", 12), 200],
                                  [stamp("2026-09-01", 0), 100],
                                  [stamp("2026-09-02"), 300]]})
    result = fetch_daily_prices(start="2026-09-01", end="2026-09-02", session=session)
    assert result["count"] == 2
    assert result["missing_days"] == []
    assert session.calls[0][1]["params"]["vs_currency"] == "eur"
    assert session.calls[0][1]["timeout"] == 30


def test_missing_day_is_not_filled():
    result = fetch_daily_prices(start="2026-09-01", end="2026-09-03",
                                session=Session({"prices": [[stamp("2026-09-01"), 100],
                                                            [stamp("2026-09-03"), 200]]}))
    assert result["missing_days"] == ["2026-09-02"]


@pytest.mark.parametrize("payload", [
    {}, {"prices": []}, {"prices": [["bad", 100]]},
    {"prices": [[stamp("2026-09-01"), -1]]},
    {"prices": [[stamp("2026-09-01"), "NaN"]]},
])
def test_invalid_payload_rejected(payload):
    with pytest.raises((ValueError, TypeError)):
        fetch_daily_prices(start="2026-09-01", end="2026-09-02",
                           session=Session(payload))


def test_monthly_rejects_incomplete_month():
    with pytest.raises(ValueError, match="coverage"):
        monthly_prices(start="2026-09-01", end="2026-09-30",
                       session=Session({"prices": [[stamp("2026-09-01"), 100]]}))


def test_invalid_inputs():
    for kwargs in [
        {"start": "2026-09-03", "end": "2026-09-01"},
        {"start": "2026-09-01", "end": "2026-09-02", "currency": "NLG"},
    ]:
        with pytest.raises(ValueError):
            fetch_daily_prices(session=Session({"prices": []}), **kwargs)
