"""Source-agnostic validation for future BTC and gold price feeds.

No provider is contacted, and no unlicensed market data is distributed.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import median

TROY_OUNCE_GRAMS = Decimal("31.1034768")
SATOSHIS_PER_BTC = Decimal("100000000")
NLG_PER_EUR = Decimal("2.20371")


def positive_decimal(value, field):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Invalid {field}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid {field}") from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f"Invalid {field}")
    return result


def validate_daily_prices(records, *, asset, currency, source):
    """Validate chronological daily observations, no duplicates or silent gaps.

    Caller must explicitly identify asset, quote currency and source.
    Missing calendar days are reported, not forward-filled.
    """
    if asset not in {"BTC", "XAU"} or currency not in {"EUR", "USD", "NLG"}:
        raise ValueError("Unsupported asset or currency")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Missing provenance source")
    values = {}
    for row in records:
        if set(row) != {"date", "price", "asset", "currency", "source"}:
            raise ValueError("Unexpected price record schema")
        if (row["asset"], row["currency"], row["source"]) != (asset, currency, source):
            raise ValueError("Mixed price units or provenance")
        try:
            parsed = date.fromisoformat(row["date"])
        except (TypeError, ValueError):
            raise ValueError("Invalid ISO date") from None
        if parsed.isoformat() != row["date"]:
            raise ValueError("Invalid ISO date")
        if parsed in values:
            raise ValueError("Duplicate daily observation")
        values[parsed] = positive_decimal(row["price"], "price")
    if not values:
        raise ValueError("Empty price series")
    ordered = sorted(values)
    missing = []
    from datetime import timedelta
    current = ordered[0]
    while current <= ordered[-1]:
        if current not in values:
            missing.append(current.isoformat())
        current += timedelta(days=1)
    return {"values": values, "missing_days": missing, "start": ordered[0].isoformat(),
            "end": ordered[-1].isoformat(), "count": len(values)}


def monthly_arithmetic_mean(checked, *, min_coverage=Decimal("1")):
    """Monthly average only when the share of covered days reaches threshold.

    Complete interior months require all calendar days; partial boundary months
    are rejected unless the caller explicitly relaxes the threshold.
    """
    from calendar import monthrange
    threshold = positive_decimal(min_coverage, "min_coverage")
    if threshold > 1:
        raise ValueError("Coverage threshold exceeds one")
    grouped = defaultdict(list)
    for day, price in checked["values"].items():
        grouped[(day.year, day.month)].append(price)
    result = []
    for (year, month), prices in sorted(grouped.items()):
        days = monthrange(year, month)[1]
        coverage = Decimal(len(prices)) / Decimal(days)
        if coverage < threshold:
            raise ValueError(f"Insufficient daily coverage: {year:04d}-{month:02d}")
        result.append({"period": f"{year:04d}-{month:02d}",
                       "price": sum(prices) / len(prices),
                       "coverage": coverage})
    return result


def convert_to_eur(price, *, currency, eur_per_unit=None):
    value = positive_decimal(price, "price")
    if currency == "EUR":
        if eur_per_unit is not None:
            raise ValueError("EUR price must not carry FX rate")
        return value
    if currency == "NLG":
        if eur_per_unit is not None:
            raise ValueError("NLG fixed conversion must not be overridden")
        return value / NLG_PER_EUR
    if currency == "USD":
        if eur_per_unit is None:
            raise ValueError("USD conversion requires dated FX rate")
        return value * positive_decimal(eur_per_unit, "eur_per_unit")
    raise ValueError("Unsupported currency")


def house_in_gold_grams(house_eur, gold_eur_per_troy_oz):
    return positive_decimal(house_eur, "house_eur") * TROY_OUNCE_GRAMS / positive_decimal(
        gold_eur_per_troy_oz, "gold_eur_per_troy_oz")


def house_in_satoshis(house_eur, btc_eur):
    return positive_decimal(house_eur, "house_eur") * SATOSHIS_PER_BTC / positive_decimal(
        btc_eur, "btc_eur")


def check_reference_prices(primary, secondary, *, max_relative_deviation=Decimal("0.05")):
    """Cross-source price check; flags rather than silently correcting outliers."""
    limit = positive_decimal(max_relative_deviation, "max_relative_deviation")
    if limit > 1:
        raise ValueError("Deviation limit exceeds one")
    a = positive_decimal(primary, "primary")
    b = positive_decimal(secondary, "secondary")
    deviation = abs(a - b) / b
    if deviation > limit:
        raise ValueError(f"Independent source deviation: {deviation}")
    return deviation
