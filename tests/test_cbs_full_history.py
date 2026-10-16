"""Opt-in live CBS history validation; no Cloudflare writes."""
import os
from datetime import date
import pytest
from etl.sources.cbs import fetch_cbs

pytestmark = pytest.mark.skipif(os.getenv("CBS_FULL_HISTORY") != "1", reason="opt-in network test")

def test_full_history_coverage():
    rows = fetch_cbs()
    by_series = {}
    for month, series, value in rows:
        by_series.setdefault(series, {})[month] = value
    assert set(by_series) == {"nl_hpi", "nl_house_avg_eur"}
    first = date(2000, 1, 1)
    today = date.today()
    expected = []
    year, month = first.year, first.month
    while (year, month) <= (today.year, today.month):
        expected.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    for series, observations in by_series.items():
        assert "2000-01" in observations, f"{series} missing January 2000"
        months = sorted(m for m in observations if m >= "2000-01")
        assert months, f"{series} empty"
        last = months[-1]
        assert last >= f"{today.year - 1:04d}-{today.month:02d}", f"{series} data stale: {last}"
        expected_through_last = [m for m in expected if m <= last]
        missing = sorted(set(expected_through_last) - set(months))
        assert not missing, f"{series} has {len(missing)} missing months: {missing[:12]}"
