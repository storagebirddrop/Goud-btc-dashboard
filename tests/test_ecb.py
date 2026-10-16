import pytest
from etl.sources.ecb import parse_ecb_csv, export_csv, fetch_ecb, SERIES_KEY

def test_parse_rates():
    rows = parse_ecb_csv("KEY,TIME_PERIOD,OBS_VALUE\n"+SERIES_KEY+",2000-01-04,1.03\n"+SERIES_KEY+",2000-01-03,1.02\n")
    assert rows == [("2000-01-03", 1.02), ("2000-01-04", 1.03)]

@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_invalid_rate(value):
    with pytest.raises(ValueError):
        parse_ecb_csv(f"TIME_PERIOD,OBS_VALUE\n2000-01-03,{value}\n")

def test_duplicate_day():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_ecb_csv("TIME_PERIOD,OBS_VALUE\n2000-01-03,1.02\n2000-01-03,1.03\n")

def test_export_csv(tmp_path):
    path = tmp_path / "fx.csv"
    export_csv([("2000-01-03", 1.02)], path)
    assert "2000-01-03,1.02" in path.read_text()

def test_fetch_uses_explicit_ecb_series(monkeypatch):
    class Response:
        text = "TIME_PERIOD,OBS_VALUE\n2000-01-03,1.02\n"
        def raise_for_status(self): pass
    def fake_get(url, *, params, timeout, headers):
        assert url.endswith("/EXR/D.USD.EUR.SP00.A")
        assert params["format"] == "csvdata"
        assert timeout == 30
        return Response()
    monkeypatch.setattr("etl.sources.ecb.requests.get", fake_get)
    assert fetch_ecb() == [("2000-01-03", 1.02)]
