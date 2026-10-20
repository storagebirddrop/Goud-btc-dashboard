"""Synthetic tests (labelled SYNTHETIC: prove code only, not source behaviour)."""
from decimal import Decimal as D
import pytest
from tools.hist_03_precision import deviation_stats, PrecisionError


def test_synthetic_zero_deviation():
    s = {"1975-01": D("100"), "1980-06": D("200")}
    r = deviation_stats(s, dict(s))
    assert r["n"] == 2 and r["mean_signed_diff"] == 0 and r["max_abs"] == 0
    assert r["share_within_0_5_usd"] == 1.0 and r["only_wb"] == 0 and r["only_other"] == 0


def test_synthetic_sign_and_stats():
    wb = {"1975-01": D("101"), "1975-02": D("98"), "1985-03": D("100.5")}
    ot = {"1975-01": D("100"), "1975-02": D("100"), "1985-03": D("100")}
    r = deviation_stats(wb, ot)
    assert r["mean_signed_diff"] == pytest.approx((1 - 2 + 0.5) / 3, abs=1e-6)
    assert r["max_abs"] == 2 and r["median_abs"] == 1
    assert r["share_within_0_5_usd"] == pytest.approx(1 / 3, abs=1e-6)  # only 0.5 qualifies
    assert r["max_rel_pct"] == 2.0
    assert r["subperiods"]["1975-79"]["n"] == 2 and r["subperiods"]["1985-89"]["n"] == 1
    assert r["subperiods"]["1990-94"]["n"] == 0 and r["subperiods"]["1990-94"]["mean_abs"] is None
    assert [t["month"] for t in r["top3_abs_diff"]] == ["1975-02", "1975-01", "1985-03"]
    assert r["top3_abs_diff"][0]["diff"] == -2.0


def test_synthetic_unequal_sets():
    r = deviation_stats({"1975-01": D("1"), "1975-02": D("1")}, {"1975-01": D("1"), "1975-03": D("1"), "1975-04": D("1")})
    assert r["n"] == 1 and r["only_wb"] == 1 and r["only_other"] == 2


@pytest.mark.parametrize("wb,ot", [
    ({}, {}), ({"1975-01": D("1")}, {"1975-02": D("1")}),
    ({"1975-01": D("1")}, {"1975-01": D("0")}),
    ({"1975-01": 1.0}, {"1975-01": D("1")}),
    ({"1975-13": D("1")}, {"1975-13": D("1")}),
    ({"1975-01": D("NaN")}, {"1975-01": D("1")}),
    (None, {}),
])
def test_synthetic_fail_closed(wb, ot):
    with pytest.raises(PrecisionError):
        deviation_stats(wb, ot)
