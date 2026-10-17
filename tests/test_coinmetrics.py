import pytest

from etl.sources.coinmetrics import fetch_reference_rates, monthly_reference_rates


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class Session:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.pages.pop(0))


def entry(day, value="100"):
    return {"asset": "btc", "time": day + "T00:00:00.000000000Z",
            "ReferenceRateEUR": value}


def test_fetch_valid_daily_and_pagination():
    session = Session([
        {"data": [entry("2026-01-01")], "next_page_token": "next"},
        {"data": [entry("2026-01-02")], "next_page_token": None},
    ])
    result = fetch_reference_rates(start="2026-01-01", end="2026-01-02", session=session)
    assert result["count"] == 2
    assert result["missing_days"] == []
    assert len(session.calls) == 2
    assert session.calls[1][1]["params"]["next_page_token"] == "next"
    assert all(call[1]["timeout"] == 30 for call in session.calls)


def test_missing_day_reported_not_filled():
    session = Session([{"data": [entry("2026-01-01"), entry("2026-01-03")]}])
    result = fetch_reference_rates(start="2026-01-01", end="2026-01-03", session=session)
    assert result["missing_days"] == ["2026-01-02"]


@pytest.mark.parametrize("payload", [
    {},
    {"data": [{"asset": "eth", "time": "2026-01-01T00:00:00Z", "ReferenceRateEUR": "100"}]},
    {"data": [{"asset": "btc", "time": "bad", "ReferenceRateEUR": "100"}]},
    {"data": [{"asset": "btc", "time": "2026-01-01T00:00:00Z"}]},
    {"data": [entry("2026-01-01", "NaN")]},
    {"data": [entry("2026-01-01"), entry("2026-01-01")]},
    {"data": [entry("2025-12-31")]},
])
def test_bad_responses_rejected(payload):
    with pytest.raises(ValueError):
        fetch_reference_rates(start="2026-01-01", end="2026-01-02",
                              session=Session([payload]))


def test_repeated_page_token_rejected():
    session = Session([
        {"data": [entry("2026-01-01")], "next_page_token": "same"},
        {"data": [entry("2026-01-02")], "next_page_token": "same"},
    ])
    with pytest.raises(ValueError, match="Repeated"):
        fetch_reference_rates(start="2026-01-01", end="2026-01-02", session=session)


def test_page_limit_rejected():
    with pytest.raises(ValueError, match="page limit"):
        fetch_reference_rates(start="2026-01-01", end="2026-01-02", max_pages=1,
                              session=Session([{"data": [entry("2026-01-01")],
                                                "next_page_token": "more"}]))


def test_monthly_requires_complete_calendar_month():
    session = Session([{"data": [entry("2026-01-01")]}])
    with pytest.raises(ValueError, match="coverage"):
        monthly_reference_rates(start="2026-01-01", end="2026-01-31", session=session)


def test_invalid_inputs():
    for kwargs in [
        {"start": "2026-02-01", "end": "2026-01-01"},
        {"start": "2026-01-01", "end": "2026-01-02", "currency": "NLG"},
        {"start": "2026-01-01", "end": "2026-01-02", "max_pages": 0},
    ]:
        with pytest.raises(ValueError):
            fetch_reference_rates(session=Session([]), **kwargs)


def test_empty_historical_window_has_actionable_error():
    with pytest.raises(ValueError, match="no BTC/EUR observations"):
        fetch_reference_rates(start="2011-01-01", end="2011-01-31",
                              session=Session([{"data": []}]))
