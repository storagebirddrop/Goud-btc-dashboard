import pytest
from etl.sources.cbs import resolve_fields, resolve_period_dimension, parse_rows, fetch_pages, BASE

MEASURES = [{"Title": "Prijsindex verkoopprijzen", "Identifier": "HPI"},
            {"Title": "Gemiddelde verkoopprijs", "Identifier": "AVG"}]
FIELDS = {"nl_hpi": "HPI", "nl_house_avg_eur": "AVG"}

def test_resolve_metadata():
    assert resolve_fields(MEASURES) == FIELDS

def test_missing_metadata_rejected():
    with pytest.raises(ValueError, match="unambiguously"):
        resolve_fields(MEASURES[:1])

def test_resolve_period_dimension():
    assert resolve_period_dimension([{"Title": "Perioden", "Identifier": "Perioden"}]) == "Perioden"

def test_only_monthly_rows():
    rows = [{"Perioden": "2000JJ00", "Measure": "HPI", "Value": 50},
            {"Perioden": "2000MM01", "Measure": "HPI", "Value": 50},
            {"Perioden": "2000MM01", "Measure": "AVG", "Value": 180000}]
    assert parse_rows(rows, FIELDS) == [("2000-01", "nl_house_avg_eur", 180000.0), ("2000-01", "nl_hpi", 50.0)]

def test_duplicate_month_rejected():
    row = {"Perioden": "2000MM01", "Measure": "HPI", "Value": 50}
    with pytest.raises(ValueError, match="Duplicate"):
        parse_rows([row, row], FIELDS)

def test_missing_value_rejected():
    with pytest.raises(ValueError, match="Missing"):
        parse_rows([{"Perioden": "2000MM01", "Measure": "HPI", "Value": None}], FIELDS)

def test_pagination():
    class Response:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body
    class Session:
        def __init__(self): self.urls = []
        def get(self, url, **kwargs):
            self.urls.append(url)
            if len(self.urls) == 1:
                return Response({"value": [{"x": 1}], "@odata.nextLink": BASE + "/Observations?$skip=1"})
            return Response({"value": [{"x": 2}]})
    assert fetch_pages(Session(), "Observations") == [{"x": 1}, {"x": 2}]
