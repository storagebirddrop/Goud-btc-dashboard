"""Offline synthetic tests for the HIST-07 collector parsers (code behaviour only)."""
import json
from datetime import date
from decimal import Decimal as D

import pytest

from tools import hist_07_collect as c
from tools import hist_07_gold_constructions as hc


def test_parse_bis_keeps_monthly_average_only():
    csv_text = ("KEY,FREQ:Frequency,REF_AREA:Reference area,COLLECTION:Collection,TIME_PERIOD:Time period,OBS_VALUE:Value\n"
                "k,M:Monthly,NL:Netherlands,A:Average,1975-01,1.1146\n"
                "k,M:Monthly,NL:Netherlands,E:End,1975-01,1.2\n"
                "k,M:Monthly,NL:Netherlands,A:Average,1975-02,1.12\n")
    out, combos = c.parse_bis(csv_text.encode())
    assert out == {"1975-01": D("1.1146"), "1975-02": D("1.12")}
    assert combos["M|E|"] == 1


def test_parse_bis_duplicate_month_fails_closed():
    t = "FREQ,COLLECTION,TIME_PERIOD,OBS_VALUE\nM,A,1975-01,1\nM,A,1975-01,2\n"
    with pytest.raises(hc.ConstructionError):
        c.parse_bis(t.encode())


def test_parse_imf_single_series_and_duplicate():
    xml = (b'<m:D xmlns:m="x"><m:Series A="1"><m:Obs TIME_PERIOD="1975-01" OBS_VALUE="2.4565"/>'
           b'<m:Obs TIME_PERIOD="1975-02" OBS_VALUE="2.5"/></m:Series></m:D>')
    out, n = c.parse_imf(xml)
    assert n == 1 and out["1975-01"] == D("2.4565")
    bad = xml.replace(b"1975-02", b"1975-01")
    with pytest.raises(hc.ConstructionError):
        c.parse_imf(bad)


def test_parse_datahub_and_noncolumns():
    out, cols = c.parse_datahub(b"Date,Price\n1950-01,34.73\n1950-02,34.73\n")
    assert out["1950-02"] == D("34.73")
    with pytest.raises(hc.ConstructionError):
        c.parse_datahub(b"a,b\n1,2\n")


def test_parse_cbs_picks_dollar_property_and_skips_annual():
    props = json.dumps({"value": [{"Type": "Topic", "Key": "K1", "Title": "Amerikaanse dollar (per 1)", "Unit": "guldens"}]}).encode()
    data = json.dumps({"value": [{"Perioden": "1975MM01", "K1": 2.46}, {"Perioden": "1975JJ00", "K1": 2.5}, {"Perioden": "1975MM02", "K1": None}]}).encode()
    out, unit = c.parse_cbs(props, data)
    assert out == {"1975-01": D("2.46")} and unit == "guldens"


def test_monthly_mean_no_fill():
    pts = {date(1999, 1, 4): D("1.0"), date(1999, 1, 5): D("2.0"), date(1999, 3, 1): D("3.0")}
    m, n = c.monthly_mean(pts)
    assert m == {"1999-01": D("1.5"), "1999-03": D("3.0")} and n["1999-01"] == 2 and "1999-02" not in m


def test_cov_reports_missing_not_filled():
    r = c.cov({"2000-01": D(1), "2000-03": D(1)}, "2000-01", "2000-03")
    assert r["present"] == 2 and r["missing"] == 1 and r["missing_sample"][0] == "2000-02"


def test_fixture_house_is_60_months_and_hash_stable():
    h, sha = c.fixture_house()
    assert len(h) == 60 and min(h) == "1995-01" and max(h) == "1999-12"
    assert sha == "0a557dd16fe85e40952dd97edd492d5b3f985f64930d19d960b14307d725c543"


def test_collect_all_sources_unreachable_is_incomplete_not_filled(monkeypatch):
    def boom(sid, **k):
        raise c.acq.AcquisitionError("NETWORK_TIMEOUT source=" + sid)
    monkeypatch.setattr(c.acq, "fetch", boom)
    S, rows = c.collect()
    assert S["status"] == "INCOMPLETE"
    assert S["missing_sources"] and "worldbank" not in S
