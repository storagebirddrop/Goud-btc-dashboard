import json
from decimal import Decimal as D
import pytest

from tools.verify_gold_02_independent import independent_ecb, independent_compare


def test_ecb_independent_daily_average_and_direction():
    raw = b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n2000-01-03,1.1,USD,EUR\n2000-01-04,1.3,USD,EUR\n"
    assert independent_ecb(raw)["2000-01"] == D("1.2")
    with pytest.raises(ValueError, match="Wrong FX direction"):
        independent_ecb(raw.replace(b"USD,EUR", b"EUR,USD"))


def test_ecb_invalid_rate_and_duplicate_day_fail_closed():
    raw = b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n2000-01-03,NaN,USD,EUR\n"
    with pytest.raises(ValueError, match="Invalid ECB rate"):
        independent_ecb(raw)
    raw = b"TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM\n2000-01-03,1.1,USD,EUR\n2000-01-03,1.2,USD,EUR\n"
    with pytest.raises(ValueError, match="Duplicate ECB"):
        independent_ecb(raw)
