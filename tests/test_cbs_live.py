"""Network-enabled CBS OData v4 contract checks."""
import os
import pytest
from etl.sources.cbs import fetch_pages, make_session, resolve_fields, resolve_period_dimension, parse_rows

pytestmark = pytest.mark.skipif(os.getenv("CBS_LIVE_TEST") != "1", reason="dedicated live workflow")

def test_live_metadata_fields():
    session = make_session()
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    assert set(fields) == {"nl_hpi", "nl_house_avg_eur"}
    assert resolve_period_dimension(fetch_pages(session, "Dimensions"))

def test_live_monthly_2000_contract():
    session = make_session()
    fields = resolve_fields(fetch_pages(session, "MeasureCodes"))
    period = resolve_period_dimension(fetch_pages(session, "Dimensions"))
    codes = list(fields.values())
    filt = "(" + " or ".join(f"Measure eq '{code}'" for code in codes) + f") and {period} ge '2000MM01' and {period} le '2000MM12'"
    rows = fetch_pages(session, "Observations", params={"$filter": filt})
    observations = parse_rows(rows, fields, period)
    assert len(observations) == 24, f"Expected 12 months x 2 series, got {len(observations)}"
