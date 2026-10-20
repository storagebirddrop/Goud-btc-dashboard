"""HIST-05 CBS/Kadaster house-price probe: offline tests with SYNTHETIC fixtures (prove parser code only)."""
import json
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from tools import hist_02_acquire
from tools import hist_05_cbs_kadaster as m

PROPS = {"value": [
    {"Type": "TimeDimension", "Key": "Perioden", "Title": "Perioden"},
    {"Type": "Topic", "Key": "Prijs_1", "Title": "Gemiddelde verkoopprijs", "Unit": "euro"},
    {"Type": "Topic", "Key": "Index_2", "Title": "Prijsindex bestaande koopwoningen", "Unit": "2020 = 100"},
    {"Type": "Topic", "Key": "Mut_3", "Title": "Mutatie ten opzichte van een jaar eerder", "Unit": "%"},
]}


def rows(extra=None):
    base = [
        {"ID": 0, "Perioden": "1995MM01", "Prijs_1": 88991, "Index_2": 41.5, "Mut_3": None},
        {"ID": 1, "Perioden": "1995MM02", "Prijs_1": 89741, "Index_2": None, "Mut_3": -1.5},
        {"ID": 2, "Perioden": "1995MM04", "Prijs_1": 89808, "Index_2": 42.5, "Mut_3": 0.5},
        {"ID": 3, "Perioden": "1995KW01", "Prijs_1": 90000, "Index_2": 42.0, "Mut_3": None},
        {"ID": 4, "Perioden": "1995JJ00", "Prijs_1": 92000, "Index_2": 43.0, "Mut_3": 3.1},
        {"ID": 5, "Perioden": "1995X000", "Prijs_1": 1, "Index_2": 1, "Mut_3": 1},
    ]
    return {"value": base + (extra or [])}


def doc(d):
    return m.load_json(json.dumps(d).encode())


def test_all_candidates_registered_https_and_exact():
    assert len(m.CANDIDATES) >= 40
    for sid, (url, _, _) in m.CANDIDATES.items():
        assert url.startswith("https://") and hist_02_acquire.SOURCES[sid][0] == url
        hist_02_acquire.validate_url(sid, url)
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("cbs3-85773NED-data", "https://opendata.cbs.nl/ODataApi/OData/85773NED/UntypedDataSet")
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("kadaster-home", "http://www.kadaster.nl/")


def test_period_codes():
    assert m.parse_period("1995MM01") == ("M", "1995-01")
    assert m.parse_period("1995MM12 ") == ("M", "1995-12")
    assert m.parse_period("1995KW04") == ("Q", "1995-Q4")
    assert m.parse_period("1995JJ00") == ("A", "1995")
    assert m.parse_period("1950") == ("A", "1950")
    for bad in ("1995MM13", "1995MM00", "1995KW05", "1995JJ01", "1995X000", "1995HJ01", "95MM01", ""):
        assert m.parse_period(bad) is None


def test_periods_between_complete_sequences():
    assert m.periods_between("M", "1995-11", "1996-02") == ["1995-11", "1995-12", "1996-01", "1996-02"]
    assert m.periods_between("Q", "1995-Q3", "1996-Q1") == ["1995-Q3", "1995-Q4", "1996-Q1"]
    assert m.periods_between("A", "1990", "1992") == ["1990", "1991", "1992"]


def test_measure_classification():
    assert m.classify_measure("Gemiddelde verkoopprijs", "euro")["kind"] == "PRICE_LEVEL"
    assert m.classify_measure("Gemiddelde verkoopprijs", "euro")["currency"] == "EUR"
    c = m.classify_measure("Gemiddelde verkoopprijs", "gulden")
    assert c["kind"] == "PRICE_LEVEL" and c["currency"] == "NLG"
    i = m.classify_measure("Prijsindex bestaande koopwoningen", "2015 = 100")
    assert i["kind"] == "INDEX" and i["base"] == "2015=100"
    assert m.classify_measure("Mutatie", "%")["kind"] == "CHANGE_PCT"
    assert m.classify_measure("Aantal verkochte woningen", "aantal")["kind"] == "COUNT"


def test_typed_parse_missing_stays_none_and_unsupported_counted():
    props = m.parse_props(doc(PROPS))
    assert props["period_key"] == "Perioden" and props["dimensions"] == [] and set(props["topics"]) == {"Prijs_1", "Index_2", "Mut_3"}
    series, unsupported = m.parse_typed(doc(rows()), props)
    idx = series[("Index_2", ())]["M"]
    assert idx["1995-02"] is None and idx["1995-01"] == Decimal("41.5")
    assert series[("Prijs_1", ())]["Q"]["1995-Q1"] == Decimal("90000")
    assert series[("Prijs_1", ())]["A"]["1995"] == Decimal("92000")
    assert unsupported == {"1995X000": 1}
    assert not any("1995-03" in fm.get("M", {}) for fm in series.values())  # no filling


def test_summary_gaps_nulls_and_hash():
    props = m.parse_props(doc(PROPS))
    series, uns = m.parse_typed(doc(rows()), props)
    s = m.table_summary(series, uns, props["topics"])["measures"]
    mon = s["Prijs_1"]["shown"][0]["frequencies"]["M"]
    assert mon["observations"] == 3 and mon["first"] == "1995-01" and mon["last"] == "1995-04"
    assert mon["gap_count"] == 1 and mon["gaps_head"] == ["1995-03"] and "canonical_sha256" not in mon
    assert s["Index_2"]["shown"][0]["frequencies"]["M"]["null_values"] == 1
    assert s["Index_2"]["kind"] == "INDEX" and s["Index_2"]["base"] == "2020=100"
    full = m.series_facts({"M": {"1995-01": Decimal(1), "1995-02": Decimal(2)}}, "PRICE_LEVEL")
    assert len(full["M"]["canonical_sha256"]) == 64


def test_duplicate_period_is_hard_error():
    props = m.parse_props(doc(PROPS))
    with pytest.raises(m.Hist05Error, match="DUPLICATE_PERIOD"):
        m.parse_typed(doc(rows([{"ID": 9, "Perioden": "1995MM01", "Prijs_1": 5}])), props)


@pytest.mark.parametrize("bad", ["n.v.t.", "12,5", True])
def test_invalid_numeric_is_hard_error(bad):
    props = m.parse_props(doc(PROPS))
    with pytest.raises(m.Hist05Error, match="INVALID_NUMERIC"):
        m.parse_typed(doc(rows([{"ID": 9, "Perioden": "1995MM09", "Prijs_1": bad}])), props)


def test_non_positive_level_or_index_is_hard_error_but_change_may_be_negative():
    props = m.parse_props(doc(PROPS))
    series, uns = m.parse_typed(doc(rows([{"ID": 9, "Perioden": "1995MM09", "Prijs_1": 0}])), props)
    with pytest.raises(m.Hist05Error, match="NON_POSITIVE"):
        m.table_summary(series, uns, props["topics"])
    ok = m.parse_typed(doc(rows()), props)  # negative Mut_3 value above is fine
    assert m.table_summary(ok[0], ok[1], props["topics"])["measures"]["Mut_3"]["kind"] == "CHANGE_PCT"


def test_dimensions_make_separate_series_and_cap_shown_combos():
    p = {"value": PROPS["value"] + [{"Type": "GeoDimension", "Key": "RegioS", "Title": "Regio's"}]}
    props = m.parse_props(doc(p))
    assert props["dimensions"] == ["RegioS"]
    data = {"value": [{"Perioden": "1995MM01", "RegioS": f"R{i:02d}  ", "Prijs_1": 100 + i} for i in range(6)]
            + [{"Perioden": "1995MM02", "RegioS": "R00  ", "Prijs_1": 101}]}
    series, uns = m.parse_typed(doc(data), props)
    assert len([k for k in series if k[0] == "Prijs_1"]) == 6
    s = m.table_summary(series, uns, props["topics"])["measures"]["Prijs_1"]
    assert s["dimension_combinations"] == 6 and len(s["shown"]) == 4 and s["shown"][0]["dimensions"] == ["R00"]
    assert m.single_series(series, "Prijs_1", "M") is None  # ambiguous: never silently pick one region


def test_v4_observations_parse_and_duplicates():
    obs = [{"Id": 1, "Measure": "M1", "Perioden": "1995MM01", "Value": 88991.0},
           {"Id": 2, "Measure": "M1", "Perioden": "1995MM02", "Value": None},
           {"Id": 3, "Measure": "M1", "Perioden": "1995JJ00", "Value": 90000}]
    series, uns = m.parse_observations_v4(m.load_json(json.dumps(obs).encode()))
    assert series[("M1", ())]["M"]["1995-02"] is None and series[("M1", ())]["A"]["1995"] == Decimal("90000")
    with pytest.raises(m.Hist05Error, match="DUPLICATE_PERIOD"):
        m.parse_observations_v4(obs + [obs[0]])
    with pytest.raises(m.Hist05Error, match="MISSING_MEASURE"):
        m.parse_observations_v4([{"Perioden": "1995MM01", "Value": 1}])


def test_load_json_and_value_array_errors():
    with pytest.raises(m.Hist05Error, match="NOT_JSON"):
        m.load_json(b"<html>blocked</html>")
    with pytest.raises(m.Hist05Error, match="MISSING_VALUE_ARRAY"):
        m.value_list({"odata.metadata": "x"})


def test_compare_series_descriptive_only():
    a = {"1999-11": Decimal(100), "1999-12": Decimal(110), "2000-01": None}
    b = {"1999-11": Decimal(100), "1999-12": Decimal(100), "2000-01": Decimal(5), "2000-02": Decimal(1)}
    r = m.compare_series(a, b)
    assert r["common_periods"] == 2 and r["exact_equal"] == 1 and r["max_abs_diff"] == "10" and r["max_abs_diff_period"] == "1999-12"
    assert m.compare_series({"1990-01": Decimal(1)}, {"1991-01": Decimal(1)}) == {"common_periods": 0}


def test_level_continuity_and_unavailable():
    mon = {f"1999-{i:02d}": Decimal(100 + i) for i in range(1, 13)}
    mon["2000-01"] = Decimal("120")
    r = m.level_continuity(mon)
    assert r["status"] == "COMPUTED" and r["window_months"] == 11 and Decimal(r["boundary_change_pct"]) > 7
    assert m.level_continuity({"1999-12": Decimal(1)}) == {"status": "NOT_AVAILABLE"}


def test_fixture_loads_60_months_and_matches_repo_pin():
    fx = m.load_fixture()
    assert len(fx) == 60 and min(fx) == "1995-01" and max(fx) == "1999-12"


def test_catalog_rows_and_discovery_filter():
    cat = {"value": [
        {"Identifier": "70001NED", "Title": "Woningvoorraad; 1975 - 1999", "Period": "1975 - 1999", "Frequency": "Jaar"},
        {"Identifier": "70002NED", "Title": "Consumentenprijzen; prijsindex 1900=100", "Period": "1900 - 2000"},
        {"Identifier": "70003NED", "Title": "Koopwoningen; prijzen 1965", "Period": "1965 januari - 1999 december"},
        {"Identifier": "85773NED", "Title": "Bestaande koopwoningen", "Period": "1995 januari - 2026 augustus"},
        {"Identifier": "80004NED", "Title": "Nieuwe woningen", "Period": "2005 - 2026"},
        {"Identifier": "bad id!", "Title": "x"}, {"Title": "no id"}]}
    rows_ = m.catalog_rows(doc(cat))
    assert [r["id"] for r in rows_] == ["70001NED", "70002NED", "70003NED", "85773NED", "80004NED"]
    assert rows_[2]["start_year"] == 1965 and rows_[2]["end_year"] == 1999
    picked = m.pick_discovered(rows_, exclude=["85773NED"])
    assert [r["id"] for r in picked] == ["70003NED", "70001NED"]  # oldest first; CPI and post-2000 excluded
    assert m.pick_discovered(rows_, [], limit=1) and len(m.pick_discovered(rows_, [], limit=1)) == 1


def test_register_table_validates_and_allowlists():
    m.register_table("70003NED")
    assert hist_02_acquire.SOURCES["cbs3-70003NED-data"][0].endswith("/70003NED/TypedDataSet")
    with pytest.raises(m.Hist05Error):
        m.register_table("../evil")
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("cbs3-70003NED-data", "https://opendata.cbs.nl/ODataApi/OData/OTHER/TypedDataSet")


def test_page_facts_rights_quote_and_links():
    html = (b"<html><title>Copyright</title><body><script>var a=1;</script><p>The re-use of the content of this site is permitted, "
            b"provided Statistics Netherlands is cited as the source.</p><a href='/nl/woningmarkt/prijzen'>x</a><a href='/other'>y</a></body></html>")
    f = m.page_facts(html)
    assert f["html_title"] == "Copyright" and "var a" not in " ".join(f["rights_quotes"])
    assert any("cited as the source" in q for q in f["rights_quotes"])
    assert f["matching_links"] == ["/nl/woningmarkt/prijzen"]
    assert m.rights_level({"status": "FETCHED", "page": f}) == "OFFICIAL_TEXT_READ"
    assert m.rights_level({"status": "UNREACHABLE"}) == "NOT_RETRIEVED"
    assert m.rights_level({"status": "FETCHED", "page": {"rights_quotes": []}}) == "NOT_RETRIEVED"


class _Resp:
    status = 200

    def __init__(self, body, url):
        self.body, self.url = body, url
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.url

    def read(self, n):
        return self.body[:n]


def test_fetch_status_ok_and_unreachable_variants():
    sid = "cbs3-85773NED-info"
    url = hist_02_acquire.SOURCES[sid][0]
    raw, e = m.fetch_status(sid, opener=lambda req, timeout=None: _Resp(b'{"value":[]}', url))
    assert raw and e["status"] == "FETCHED" and len(e["sha256"]) == 64 and e["http_status"] == 200

    def boom(req, timeout=None):
        raise HTTPError(url, 403, "Forbidden", {}, None)
    raw, e = m.fetch_status(sid, opener=boom)
    assert raw is None and e["status"] == "UNREACHABLE" and "HTTP_STATUS_ERROR" in e["error"]

    raw, e = m.fetch_status(sid, opener=lambda req, timeout=None: _Resp(b"x", "https://evil.example/"))
    assert raw is None and e["status"] == "UNREACHABLE" and "UNAUTHORIZED" in e["error"]


def _routes(overrides=None):
    props = json.dumps(PROPS).encode()
    data = json.dumps({"value": [{"Perioden": f"1995MM{i:02d}", "Prijs_1": 88000 + i, "Index_2": 40 + i, "Mut_3": None} for i in range(1, 13)]}).encode()
    info = json.dumps({"value": [{"Title": "T", "Period": "1995 - 1995", "Frequency": "Maand"}]}).encode()
    table = {"info": info, "props": props, "data": data}

    def fake(sid, opener=None):
        entry = {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0]}
        body = (overrides or {}).get(sid, "default")
        if body == "default":
            for k, v in table.items():
                if sid.startswith("cbs3-85773NED-") and sid.endswith(k):
                    body = v
        if body in ("default", None):
            entry.update(status="UNREACHABLE", error="HTTP_STATUS_ERROR", http_status=403)
            return None, entry
        entry.update(status="FETCHED", http_status=200, bytes=len(body), sha256="0" * 64)
        return body, entry
    return fake


def test_main_all_unreachable_exits_zero_with_missing_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "fetch_status", _routes())
    out = tmp_path / "s.json"
    # nothing but a synthetic 85773NED answers; everything else is unreachable
    assert m.main(["--summary-out", str(out)]) == 0
    s = json.loads(out.read_text())
    assert s["defects"] == [] and s["nothing_approved"] is True and s["publication_authorized"] is False
    assert "kadaster-home" in s["missing_sources"] and "cbs3-83906NED-data" in s["missing_sources"]
    t = [r["table_analysis"] for r in s["results"] if "table_analysis" in r and r["table_analysis"]["table_id"] == "85773NED"][0]
    assert t["status"] == "OBTAINED"
    assert s["comparisons"]["fixture_1995_1999_vs_85773NED"]["common_periods"] == 12


def test_main_integrity_defect_exits_one(tmp_path, monkeypatch):
    bad = json.dumps({"value": [{"Perioden": "1995MM01", "Prijs_1": 1}, {"Perioden": "1995MM01", "Prijs_1": 2}]}).encode()
    monkeypatch.setattr(m, "fetch_status", _routes({"cbs3-85773NED-data": bad}))
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out)]) == 1
    s = json.loads(out.read_text())
    assert any("DUPLICATE_PERIOD" in d for d in s["defects"])


def test_main_html_instead_of_json_is_a_finding_not_a_defect(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "fetch_status", _routes({"cbs3-85773NED-data": b"<html>captcha</html>"}))
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out)]) == 0
    s = json.loads(out.read_text())
    t = [r["table_analysis"] for r in s["results"] if "table_analysis" in r and r["table_analysis"]["table_id"] == "85773NED"][0]
    assert t["status"] == "FORMAT_NOT_USABLE"


def test_report_lines_compact_and_report_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(m, "fetch_status", _routes())
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out)]) == 0
    lines = m.report_lines(json.loads(out.read_text()))
    assert any(l.startswith("TAB 85773NED v3 OBTAINED") for l in lines) and any(l.startswith("  M Prijs_1|") for l in lines)
    assert any(l.startswith("CMP ") for l in lines) and lines[-1] == "DEFECTS []"
    assert m.main(["--report", str(out)]) == 0
    assert "TAB 85773NED" in capsys.readouterr().out
