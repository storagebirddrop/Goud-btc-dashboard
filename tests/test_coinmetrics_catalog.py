import pytest

from etl.coinmetrics_catalog import parse_catalog


def row(metric, frequency="1d"):
    return {"asset": "btc", "metric": metric,
            "frequencies": [{"frequency": frequency,
                             "min_time": "2014-01-01T00:00:00Z",
                             "max_time": "2026-10-01T00:00:00Z"}]}


def test_complete_catalog():
    report = parse_catalog({"data": [row("ReferenceRateEUR"), row("ReferenceRateUSD")]})
    assert report["status"] == "complete"
    assert report["missing_metrics"] == []
    assert report["metrics"]["ReferenceRateEUR"]["start"].startswith("2014")


def test_missing_eur_metric_blocks_publication():
    report = parse_catalog({"data": [row("ReferenceRateUSD")]})
    assert report["status"] == "incomplete"
    assert report["missing_metrics"] == ["ReferenceRateEUR"]


@pytest.mark.parametrize("payload", [{}, {"data": None}, {"data": [row("ReferenceRateEUR", "1h")]}])
def test_invalid_or_non_daily_catalog_rejected(payload):
    with pytest.raises(ValueError):
        parse_catalog(payload)


def test_duplicate_metric_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_catalog({"data": [row("ReferenceRateEUR"), row("ReferenceRateEUR")]})
