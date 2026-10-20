"""Synthetic-only HIST-02 tests; never assert historical observations."""
import hashlib
from decimal import Decimal

import pytest

from tools.hist_02_annual_research import (
    HistoricalInputError, annual_gold_nlg, eur_to_nlg, gold_nlg_per_ounce,
    grams_per_house, validate_years, verify_source_bytes,
)


def test_pinned_offline_replay(tmp_path):
    p = tmp_path / "source"
    p.write_bytes(b"synthetic")
    digest = hashlib.sha256(b"synthetic").hexdigest()
    assert verify_source_bytes(p, digest) == b"synthetic"
    assert verify_source_bytes(p, digest) == b"synthetic"


@pytest.mark.parametrize("mode", ["missing", "empty", "tampered"])
def test_fail_closed_source(tmp_path, mode):
    p = tmp_path / "source"
    if mode != "missing":
        p.write_bytes(b"" if mode == "empty" else b"tampered")
    with pytest.raises(HistoricalInputError):
        verify_source_bytes(p, hashlib.sha256(b"expected").hexdigest())


def test_fx_quote_direction_and_units():
    assert gold_nlg_per_ounce("100", "2", "NLG_PER_USD") == Decimal("200")
    assert gold_nlg_per_ounce("100", "0.5", "USD_PER_NLG") == Decimal("200")
    with pytest.raises(HistoricalInputError):
        gold_nlg_per_ounce("100", "2", "UNKNOWN")


def test_troy_ounce_and_fixed_currency():
    assert grams_per_house("1000", "100") == Decimal("311.034768")
    assert eur_to_nlg("100") == Decimal("220.371")


def test_annual_aggregation_deterministic():
    gold = {f"1975-{m:02d}": "100" for m in range(1, 13)}
    fx = {f"1975-{m:02d}": "2" for m in range(1, 13)}
    assert annual_gold_nlg(gold, fx) == Decimal("200")
    assert annual_gold_nlg(gold, fx) == annual_gold_nlg(dict(reversed(list(gold.items()))), fx)


def test_missing_fx_and_gold_month():
    gold = {f"1975-{m:02d}": "100" for m in range(1, 13)}
    fx = dict(gold)
    del fx["1975-04"]
    with pytest.raises(HistoricalInputError):
        annual_gold_nlg(gold, fx)
    with pytest.raises(HistoricalInputError):
        annual_gold_nlg(fx, fx)


def test_year_continuity_and_duplicates():
    assert validate_years(list(range(1975, 2000)))
    with pytest.raises(HistoricalInputError):
        validate_years(list(range(1975, 1999)))
    with pytest.raises(HistoricalInputError):
        validate_years([1975] * 25)


def test_bad_number_and_invalid_ounce():
    with pytest.raises(HistoricalInputError):
        grams_per_house("1000", "0")
    with pytest.raises(HistoricalInputError):
        grams_per_house("1000", "NaN")
    with pytest.raises(HistoricalInputError):
        gold_nlg_per_ounce(100.0, "2", "NLG_PER_USD")


def test_annual_vs_year_end_different():
    gold = {f"1975-{m:02d}": str(m * 100) for m in range(1, 13)}
    fx = {k: "2" for k in gold}
    annual = annual_gold_nlg(gold, fx)
    year_end = gold_nlg_per_ounce(gold["1975-12"], fx["1975-12"], "NLG_PER_USD")
    assert annual != year_end
    assert grams_per_house("100000", annual) != grams_per_house("100000", year_end)


def test_indicative_overlap_math_only():
    """Comparison math is valid, but not proof of comparable housing populations."""
    nvm, cbs = Decimal("105000"), Decimal("93750")
    assert nvm - cbs == Decimal("11250")
    assert (nvm - cbs) / cbs == Decimal("0.12")
