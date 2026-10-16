import pytest
from etl.sources.cbs import resolve_fields, parse_rows, fetch_pages, BASE

def test_resolve_metadata():
    props = [{"Title": "Prijsindex verkoopprijzen", "Key": "IndexField"},
             {"Title": "Gemiddelde verkoopprijs", "Key": "PriceField"}]
    assert resolve_fields(props) == {"nl_hpi": "IndexField", "nl_house_avg_eur": "PriceField"}

def test_missing_metadata_rejected():
    with pytest.raises(ValueError, match="unambiguously"):
        resolve_fields([{"Title": "Gemiddelde verkoopprijs", "Key": "PriceField"}])

def test_only_monthly_rows():
    fields = {"nl_hpi": "idx", "nl_house_avg_eur": "price"}
    rows = [{"Perioden": "2000JJ00", "idx": 50, "price": 180000},
            {"Perioden": "2000KW01", "idx": 50, "price": 180000},
            {"Perioden": "2000MM01", "idx": 50, "price": 180000}]
    assert parse_rows(rows, fields) == [("2000-01", "nl_house_avg_eur", 180000.0), ("2000-01", "nl_hpi", 50.0)]

def test_duplicate_month_rejected():
    row = {"Perioden": "2000MM01", "idx": 50, "price": 180000}
    with pytest.raises(ValueError, match="Duplicate"):
        parse_rows([row, row], {"nl_hpi": "idx", "nl_house_avg_eur": "price"})

def test_missing_value_rejected():
    with pytest.raises(ValueError, match="Missing"):
        parse_rows([{"Perioden": "2000MM01", "idx": None, "price": 180000}], {"nl_hpi": "idx", "nl_house_avg_eur": "price"})

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
                return Response({"value": [{"x": 1}], "@odata.nextLink": BASE + "/TypedDataSet?$skip=1"})
            return Response({"value": [{"x": 2}]})
    session = Session()
    assert fetch_pages(session, "TypedDataSet") == [{"x": 1}, {"x": 2}]
