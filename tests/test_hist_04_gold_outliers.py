"""Offline tests with SYNTHETIC data (labelled; they prove code behaviour only, not any real gold price)."""
from datetime import date
from decimal import Decimal

import pytest

from tools import hist_02_acquire
from tools import hist_04_gold_outliers as go

D = Decimal


def test_month_add_wraps_years():
    assert go.month_add("1980-12", 1) == "1981-01"
    assert go.month_add("1980-01", -1) == "1979-12"
    assert go.month_add("1985-03", -3) == "1984-12"


def test_compare_basic_and_missing():
    c = go.compare(D("100"), D("102.5"))
    assert c["diff"] == "-2.5000" and c["abs_diff"] == "2.5000" and c["within_half_usd"] is False
    assert c["pct_of_other"] == "-2.439"
    assert go.compare(D("100"), D("100.4"))["within_half_usd"] is True
    assert go.compare(None, D("1")) is None and go.compare(D("1"), None) is None


def test_context_rows_keep_gaps_absent_no_fill():
    wb = {"1980-11": D("1"), "1980-12": D("2")}
    boe = {"1980-12": D("5")}
    rows = go.context_rows(wb, boe, "1980-12")
    assert len(rows) == 7
    by = {r["month"]: r for r in rows}
    assert by["1980-11"]["boe_monthly"] is None and by["1980-11"]["diff"] is None
    assert by["1981-01"]["wb"] is None


def test_shift_test_detects_month_shift():
    wb = {"1983-07": D("422")}
    boe = {"1983-06": D("422.3"), "1983-07": D("410"), "1983-08": D("400")}
    sh = go.shift_test(wb, boe, "1983-07")
    assert sh["-1"]["within_half_usd"] and not sh["0"]["within_half_usd"] and not sh["1"]["within_half_usd"]
    cl = go.classify(D("422"), sh["0"], sh, {})
    assert cl["class"] == "PROVEN" and cl["reproductions"] == ["month_shift_BoE-1"]


DAILY = {  # synthetic March 1985: Fri 1, Mon 4, Tue 5, Fri 8, Sun 10 (weekend row on purpose)
    date(1985, 3, 1): D("300"), date(1985, 3, 4): D("304"), date(1985, 3, 5): D("306"),
    date(1985, 3, 8): D("310"), date(1985, 3, 10): D("320"), date(1985, 4, 1): D("999"),
}


def test_daily_variants_mean_variants():
    v = go.daily_variants(DAILY, "1985-03")
    assert v["n_days"] == 5 and v["n_fridays"] == 2
    assert v["mean_all"] == D("308")
    assert v["mean_weekdays"] == D("1220") / 4  # Sunday excluded
    assert v["mean_fridays"] == D("305")
    assert v["last_day"] == D("320") and v["first_day"] == D("300") and v["median"] == D("306")
    assert go.daily_variants(DAILY, "1985-02") is None  # absent month: None, not filled


def test_daily_variant_reproduces_wb_proven():
    wb = {"1985-03": D("305")}
    boe = {"1985-03": D("308")}
    r = go.analyse_month("1985-03", wb, boe, {"XTEST": DAILY})
    assert r["classification"]["class"] == "PROVEN"
    assert "XTEST:mean_fridays" in r["classification"]["reproductions"]
    assert r["daily"]["XTEST"]["days_within_half_usd_of_wb"] == []  # no single day within 0.5 of 305
    assert r["rounding_explains"] is False


def test_matching_days_dates_only():
    assert go.matching_days(DAILY, "1985-03", D("306.2")) == ["1985-03-05"]


def test_rounding_explains_is_not_an_outlier():
    r = go.analyse_month("1985-03", {"1985-03": D("308")}, {"1985-03": D("307.6")}, {})
    assert r["rounding_explains"] is True and r["classification"]["class"] == "NOT_AN_OUTLIER"


def test_plausible_and_unverified_bands():
    wb, boe = {"1985-03": D("310")}, {"1985-03": D("300")}
    near = {"X": {"variants": {"mean_all": go.compare(D("310"), D("311.5"))}}}
    assert go.classify(D("310"), go.compare(D("310"), D("300")), go.shift_test(wb, boe, "1985-03"), near)["class"] == "PLAUSIBLE"
    far = {"X": {"variants": {"mean_all": go.compare(D("310"), D("330"))}}}
    cl = go.classify(D("310"), go.compare(D("310"), D("300")), go.shift_test(wb, boe, "1985-03"), far)
    assert cl["class"] == "UNVERIFIED" and cl["best_residual"]["abs_diff"] == "20.0000"


def test_missing_input_unverified_no_fill():
    r = go.analyse_month("1980-12", {}, {"1980-12": D("1")}, {})
    assert r["classification"]["class"] == "UNVERIFIED" and r["wb"] is None


def test_combined_am_pm_common_dates_only():
    am = {date(1985, 3, 1): D("300"), date(1985, 3, 4): D("302")}
    pm = {date(1985, 3, 1): D("304")}
    assert go.combined_daily(am, pm) == {date(1985, 3, 1): D("302")}


def test_is_daily_detects_monthly():
    assert go.is_daily(DAILY) is True
    assert go.is_daily({date(1985, 3, 31): D("1"), date(1985, 4, 30): D("2")}) is False


def test_discover_codes_and_notes_facts():
    html = b"<td>XUDLGPD</td><td>Gold price against US$, daily</td><td>XUMAGPD</td> monthly. " \
           b"Figures are averages of Friday observations. Unrelated sentence here."
    found = go.discover_codes(html)
    assert set(found) == {"XUDLGPD", "XUMAGPD"} and "daily" in found["XUDLGPD"]
    assert any("Friday" in s for s in go.notes_facts(html))
    assert not any("Unrelated" in s for s in go.notes_facts(html))


def test_deviation_ranking():
    wb = {"1985-01": D("1"), "1985-02": D("10"), "1985-03": D("5")}
    boe = {"1985-01": D("1"), "1985-02": D("7"), "1985-03": D("5.2")}
    r = go.deviation_ranking(wb, boe)
    assert r["common_months"] == 3 and r["months_over_half_usd"] == 1 and r["top"][0]["month"] == "1985-02"


def test_register_daily_uses_allowlisted_https_and_rejects_foreign():
    sid = go.register_daily("XUTEST1")
    assert hist_02_acquire.SOURCES[sid][0].startswith("https://www.bankofengland.co.uk/")
    assert "SeriesCodes=XUTEST1" in hist_02_acquire.SOURCES[sid][0]
    hist_02_acquire.validate_url(sid, hist_02_acquire.SOURCES[sid][0])
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url(sid, "https://evil.example/x")
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("boe-gold-unregistered", "https://www.bankofengland.co.uk/")


def test_fail_closed_on_bad_daily_csv():
    from tools import hist_03_second_source as ss
    with pytest.raises(ss.SecondSourceError, match="WRONG_SERIES_COLUMN"):
        ss.parse_points(b"DATE,OTHER\n1985-03-01,300\n", "XUDLGPD")
    with pytest.raises(ss.SecondSourceError, match="DUPLICATE_DATE"):
        ss.parse_points(b"DATE,XUDLGPD\n1985-03-01,300\n1985-03-01,301\n", "XUDLGPD")
