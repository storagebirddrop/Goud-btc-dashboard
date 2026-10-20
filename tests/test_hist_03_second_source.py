"""Offline tests with SYNTHETIC data (labelled; they prove code behaviour only, not any real gold price)."""
from datetime import date
from decimal import Decimal

import pytest

from tools import hist_02_acquire
from tools import hist_03_second_source as ss


def csv(rows, header="DATE,XUMAGPD"):
    return (header + "\n" + "\n".join(rows) + "\n").encode()


def test_parse_ok_iso_and_boe_dates():
    pts, missing = ss.parse_points(csv(["1975-01-02,100.5", "03 Jan 1975,101"]), "XUMAGPD")
    assert pts == {date(1975, 1, 2): Decimal("100.5"), date(1975, 1, 3): Decimal("101")} and missing == 0


def test_missing_markers_counted_not_filled():
    pts, missing = ss.parse_points(csv(["1975-01-02,100", "1975-01-03,.", "1975-01-06,"]), "XUMAGPD")
    assert list(pts) == [date(1975, 1, 2)] and missing == 2


@pytest.mark.parametrize("rows,err", [
    (["1975-01-02,100", "1975-01-02,101"], "DUPLICATE_DATE"),
    (["1975-01-02,abc"], "INVALID_VALUE"),
    (["1975-01-02,0"], "NON_POSITIVE_VALUE"),
    (["1975-01-02,-5"], "INVALID_VALUE"),
    (["1975-01-02,1e3"], "INVALID_VALUE"),
    (["02 Jan 75,100"], "UNPARSEABLE_DATE"),
    (["1975-13-02,100"], "INVALID_DATE"),
    (["1975-01-02,100,7"], "UNEXPECTED_COLUMN_COUNT"),
    ([], "NO_OBSERVATIONS"),
])
def test_parse_rejects(rows, err):
    with pytest.raises(ss.SecondSourceError, match=err):
        ss.parse_points(csv(rows), "XUMAGPD")


def test_wrong_series_or_header():
    with pytest.raises(ss.SecondSourceError, match="WRONG_SERIES_COLUMN"):
        ss.parse_points(csv(["1975-01-02,1"], header="DATE,XUMAGPS"), "XUMAGPD")
    with pytest.raises(ss.SecondSourceError, match="UNEXPECTED_HEADER_SHAPE"):
        ss.parse_points(csv(["1975-01-02,1"], header="DATE,A,B"), "XUMAGPD")
    with pytest.raises(ss.SecondSourceError, match="EMPTY_FILE"):
        ss.parse_points(b"", "XUMAGPD")


def test_aggregate_monthly_mean_and_day_counts_no_filling():
    daily = {date(1975, 1, 2): Decimal("100"), date(1975, 1, 3): Decimal("102"),
             date(1975, 3, 5): Decimal("90"), date(2000, 1, 3): Decimal("1")}
    monthly, counts = ss.aggregate_monthly(daily)
    assert monthly == {"1975-01": Decimal("101"), "1975-03": Decimal("90")}
    assert counts == {"1975-01": 2, "1975-03": 1}
    assert "1975-02" not in monthly  # empty month stays absent
    assert ss.coverage(monthly)["missing_count"] == 300 - 2
    assert ss.days_statistics(counts)["max_days"] == 2


def test_monthly_from_points_duplicate_month_fails():
    pts = {date(1975, 1, 31): Decimal("1"), date(1975, 1, 1): Decimal("2")}
    with pytest.raises(ss.SecondSourceError, match="DUPLICATE_MONTH"):
        ss.monthly_from_points(pts)
    assert ss.monthly_from_points({date(1975, 1, 31): Decimal("1")}) == {"1975-01": Decimal("1")}


def test_allowlist_refuses_unapproved_source_and_registers_candidates():
    with pytest.raises(hist_02_acquire.AcquisitionError, match="UNAPPROVED_SOURCE"):
        hist_02_acquire.fetch("lbma-gold-pm")
    assert "boe-gold-usd-monthly-average" in hist_02_acquire.SOURCES
    with pytest.raises(hist_02_acquire.AcquisitionError, match="UNAUTHORIZED_ENDPOINT_OR_REDIRECT"):
        hist_02_acquire.validate_url("boe-gold-usd-monthly-average", "https://example.org/x")


def test_compare_candidate_synthetic_monthly(monkeypatch):
    wb = {"1975-01": Decimal("100"), "1975-02": Decimal("110")}
    cfg = ss.CANDIDATES["boe-gold-usd-monthly-average"]
    res = ss.compare_candidate(wb, "boe-gold-usd-monthly-average", cfg, csv(["1975-01-31,101", "1975-02-28,109"]))
    assert res["common_months"] == 2 and res["coverage"]["present"] == 2
