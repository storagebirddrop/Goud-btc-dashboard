from decimal import Decimal

import pytest

from etl.asset_quality import (
    check_reference_prices, convert_to_eur, house_in_gold_grams,
    house_in_satoshis, monthly_arithmetic_mean, validate_daily_prices,
)


def sample(days=("2026-01-01", "2026-01-02")):
    return [{"date": day, "price": "100", "asset": "BTC",
             "currency": "USD", "source": "fixture"} for day in days]


def test_valid_daily_data_and_missing_days_reported():
    result = validate_daily_prices(sample(("2026-01-01", "2026-01-03")),
                                   asset="BTC", currency="USD", source="fixture")
    assert result["count"] == 2
    assert result["missing_days"] == ["2026-01-02"]


@pytest.mark.parametrize("mutate", [
    lambda x: x.append(dict(x[0])),
    lambda x: x[0].update({"price": "NaN"}),
    lambda x: x[0].update({"price": "-1"}),
    lambda x: x[0].update({"price": "Infinity"}),
    lambda x: x[0].update({"currency": "EUR"}),
    lambda x: x[0].update({"source": "unknown"}),
    lambda x: x[0].update({"date": "2026-02-30"}),
    lambda x: x[0].update({"extra": 1}),
])
def test_rejects_corrupt_prices(mutate):
    records = sample()
    mutate(records)
    with pytest.raises(ValueError):
        validate_daily_prices(records, asset="BTC", currency="USD", source="fixture")


def test_monthly_coverage_gate():
    checked = validate_daily_prices(sample(), asset="BTC", currency="USD", source="fixture")
    with pytest.raises(ValueError, match="coverage"):
        monthly_arithmetic_mean(checked)
    rows = monthly_arithmetic_mean(checked, min_coverage=Decimal("0.06"))
    assert rows[0]["price"] == Decimal("100")
    assert rows[0]["coverage"] == Decimal(2) / Decimal(31)


def test_currency_and_asset_units():
    assert convert_to_eur("220.371", currency="NLG") == Decimal("100")
    assert convert_to_eur("100", currency="USD", eur_per_unit="0.9") == Decimal("90")
    assert convert_to_eur("100", currency="EUR") == Decimal("100")
    assert house_in_gold_grams("100000", "1000") == Decimal("3110.34768")
    assert house_in_satoshis("100000", "50000") == Decimal("200000000")


@pytest.mark.parametrize("kwargs", [
    {"currency": "USD"},
    {"currency": "NLG", "eur_per_unit": "0.5"},
    {"currency": "EUR", "eur_per_unit": "1"},
    {"currency": "USD", "eur_per_unit": "0"},
])
def test_rejects_ambiguous_fx(kwargs):
    with pytest.raises(ValueError):
        convert_to_eur("100", **kwargs)


def test_independent_source_crosscheck():
    assert check_reference_prices("100", "100") == 0
    assert check_reference_prices("103", "100") == Decimal("0.03")
    with pytest.raises(ValueError, match="deviation"):
        check_reference_prices("120", "100")

def test_requested_range_reports_missing_boundaries():
    checked = validate_daily_prices(sample(("2026-01-02", "2026-01-03")),
                                    asset="BTC", currency="USD", source="fixture",
                                    expected_start="2026-01-01", expected_end="2026-01-04")
    assert checked["missing_days"] == ["2026-01-01", "2026-01-04"]
    assert checked["requested_start"] == "2026-01-01"
    assert checked["requested_end"] == "2026-01-04"


def test_requested_range_rejects_out_of_range_observations():
    with pytest.raises(ValueError, match="outside requested"):
        validate_daily_prices(sample(("2026-01-01", "2026-01-03")),
                              asset="BTC", currency="USD", source="fixture",
                              expected_start="2026-01-02", expected_end="2026-01-03")


def test_requested_range_rejects_invalid_boundaries():
    with pytest.raises(ValueError, match="Expected start and end"):
        validate_daily_prices(sample(), asset="BTC", currency="USD", source="fixture",
                              expected_start="2026-01-01")
    with pytest.raises(ValueError, match="Invalid expected date range"):
        validate_daily_prices(sample(), asset="BTC", currency="USD", source="fixture",
                              expected_start="2026-01-04", expected_end="2026-01-01")

def test_monthly_aggregation_rejects_missing_requested_edge_dates():
    checked = validate_daily_prices(sample(("2026-01-02", "2026-01-03")),
                                    asset="BTC", currency="USD", source="fixture",
                                    expected_start="2026-01-01", expected_end="2026-01-04")
    with pytest.raises(ValueError, match="coverage"):
        monthly_arithmetic_mean(checked)
