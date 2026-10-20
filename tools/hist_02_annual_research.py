"""Offline HIST-02 research math only; synthetic or separately verified inputs.
No network, no publication, no production ETL imports.
"""
from decimal import Decimal
import hashlib
from pathlib import Path

GRAMS_PER_TROY_OUNCE = Decimal("31.1034768")
NLG_PER_EUR = Decimal("2.20371")


class HistoricalInputError(ValueError):
    pass


def verify_source_bytes(path, expected_sha256):
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise HistoricalInputError("INVALID_HASH")
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise HistoricalInputError("SOURCE_UNAVAILABLE") from exc
    if not raw:
        raise HistoricalInputError("EMPTY_SOURCE")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise HistoricalInputError("HASH_MISMATCH")
    return raw


def positive_decimal(value):
    if not isinstance(value, (str, Decimal)):
        raise HistoricalInputError("DECIMAL_STRING_REQUIRED")
    try:
        v = Decimal(value)
    except Exception as exc:
        raise HistoricalInputError("INVALID_NUMBER") from exc
    if not v.is_finite() or v <= 0:
        raise HistoricalInputError("INVALID_NUMBER")
    return v


def gold_nlg_per_ounce(gold_usd_oz, fx_value, quote_direction):
    gold = positive_decimal(gold_usd_oz)
    fx = positive_decimal(fx_value)
    if quote_direction == "NLG_PER_USD":
        return gold * fx
    if quote_direction == "USD_PER_NLG":
        return gold / fx
    raise HistoricalInputError("UNSUPPORTED_FX_DIRECTION")


def annual_gold_nlg(monthly_gold, monthly_fx, quote_direction="NLG_PER_USD"):
    """Require exactly matching January-December months for one calendar year."""
    if set(monthly_gold) != set(monthly_fx):
        raise HistoricalInputError("GOLD_FX_MONTH_MISMATCH")
    keys = sorted(monthly_gold)
    if len(keys) != 12 or len(set(keys)) != 12:
        raise HistoricalInputError("MISSING_OR_DUPLICATE_MONTH")
    year = keys[0][:4]
    if keys != [f"{year}-{m:02d}" for m in range(1, 13)]:
        raise HistoricalInputError("INVALID_MONTH_COVERAGE")
    prices = [gold_nlg_per_ounce(monthly_gold[k], monthly_fx[k], quote_direction) for k in keys]
    return sum(prices) / Decimal(12)


def grams_per_house(house_nlg, gold_nlg_oz):
    return positive_decimal(house_nlg) * GRAMS_PER_TROY_OUNCE / positive_decimal(gold_nlg_oz)


def eur_to_nlg(eur):
    return positive_decimal(eur) * NLG_PER_EUR


def validate_years(year_values, start=1975, end=1999):
    if len(year_values) != end - start + 1 or set(year_values) != set(range(start, end + 1)):
        raise HistoricalInputError("YEAR_COVERAGE_OR_DUPLICATE")
    return True
