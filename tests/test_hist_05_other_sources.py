"""HIST-05 other-sources probe: offline tests with SYNTHETIC fixtures (prove parser code only, not real data)."""
import csv
import io
import json
import zipfile
from decimal import Decimal

import pytest

from tools import hist_02_acquire
from tools import hist_05_other_sources as m

LONG = """FREQ,REF_AREA,VALUE,UNIT_MEASURE,TITLE_TS,TIME_PERIOD,OBS_VALUE,OBS_STATUS
Q,NL,N,628,Netherlands - Residential property prices - nominal - Index 2010=100,1970-Q1,10.5,A
Q,NL,N,628,Netherlands - Residential property prices - nominal - Index 2010=100,1970-Q2,,M
Q,NL,N,628,Netherlands - Residential property prices - nominal - Index 2010=100,1970-Q4,11.0,A
Q,NL,R,628,Netherlands - real - Index 2010=100,1970-Q1,50,A
Q,DE,N,628,Germany - Index 2010=100,1970-Q1,99,A
"""


def _scan(text):
    return m.scan_sdmx_csv(csv.reader(io.StringIO(text)))


def test_all_candidates_registered_https_and_exact():
    for sid, (url, _, _, _) in m.CANDIDATES.items():
        assert url.startswith("https://") and hist_02_acquire.SOURCES[sid][0] == url
        hist_02_acquire.validate_url(sid, url)
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("bis-spp-q-nl", "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.DE?format=csv")


def test_parse_period_variants_and_errors():
    assert m.parse_period("1975")[0] == "A"
    assert m.parse_period("1975-Q3")[:3] == ("Q", 1975, 3)
    assert m.parse_period("1975:Q3")[0] == "Q" and m.parse_period("1975Q3")[0] == "Q"
    assert m.parse_period("1975-12")[:3] == ("M", 1975, 12)
    for bad in ("1975-13", "75", "1975-Q5", "1975-01-01", "abc"):
        with pytest.raises(m.HousingSourceError):
            m.parse_period(bad)


def test_long_csv_filters_nl_keeps_missing_null_and_reports_gaps():
    res = _scan(LONG)
    assert res["nl_series_count"] == 2  # nominal and real, Germany excluded
    nom = next(s for s in res["nl_series"] if s["real_or_nominal"] == "NOMINAL")
    assert nom["n_obs"] == 2 and nom["missing_markers"] == 1
    assert nom["first"] == "1970-Q1" and nom["last"] == "1970-Q4"
    assert nom["gap_count"] == 2 and nom["gaps_first5"] == ["1970-Q2", "1970-Q3"]  # gaps stay gaps
    assert nom["unit_class"] == "INDEX" and nom["base_period"] == "2010"
    assert nom["n_obs_1975_1999"] == 0 and nom["years_up_to_1999"] == ["1970"]
    assert any(s["real_or_nominal"] == "REAL" for s in res["nl_series"])


def test_duplicate_and_invalid_numeric_are_hard_errors():
    with pytest.raises(m.HousingSourceError, match="DUPLICATE"):
        _scan(LONG + "Q,NL,N,628,Netherlands - Residential property prices - nominal - Index 2010=100,1970-Q1,12,A\n")
    with pytest.raises(m.HousingSourceError, match="INVALID_VALUE"):
        _scan(LONG.replace("11.0", "11.0x"))
    with pytest.raises(m.HousingSourceError, match="INVALID_VALUE"):
        _scan(LONG.replace("11.0", "Infinity"))
    with pytest.raises(m.HousingSourceError, match="INVALID_PERIOD"):
        _scan(LONG.replace("1970-Q4", "1970-Q9"))


def test_mixed_frequency_in_one_series_is_defect():
    with pytest.raises(m.HousingSourceError, match="MIXED_FREQUENCY"):
        _scan(LONG + "Q,NL,N,628,Netherlands - Residential property prices - nominal - Index 2010=100,1971,12,A\n")


def test_wide_layout_and_bis_style_headers():
    cols = ",".join(str(y) for y in range(1990, 2002))
    text = ("FREQ:Frequency,REF_AREA:Reference area,UNIT_MEASURE:Unit of measure," + cols + "\n"
            "A:Annual,NL:Netherlands,Index 2015=100," + ",".join(str(50 + i) for i in range(12)) + "\n"
            "A:Annual,FR:France,Index 2015=100," + ",".join("1" for _ in range(12)) + "\n")
    res = _scan(text)
    assert res["layout"] == "wide" and res["nl_series_count"] == 1
    s = res["nl_series"][0]
    assert s["frequency"] == "A" and s["n_obs"] == 12 and s["base_period"] == "2015" and s["n_obs_1975_1999"] == 10


def test_unrecognised_layout_fails_closed():
    with pytest.raises(m.HousingSourceError, match="LAYOUT"):
        _scan("a,b\n1,2\n")
    with pytest.raises(m.HousingSourceError, match="EMPTY"):
        _scan("\n")


def test_zip_scan_and_bad_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x.csv", LONG)
    assert m.scan_zip_bytes(buf.getvalue())["nl_series_count"] == 2
    with pytest.raises(m.HousingSourceError, match="BAD_ZIP"):
        m.scan_zip_bytes(b"not a zip")


def test_unit_classification_level_index_rate_and_no_level_from_index():
    assert m.classify_unit({"UNIT": "Index, 2010 = 100"}) == "INDEX"
    assert m.classify_unit({"UNIT": "Euro, price level"}) == "LEVEL"
    assert m.classify_unit({"UNIT": "Year-on-year changes, in per cent"}) == "RATE"
    assert m.classify_unit({"x": "foo"}) == "UNDETERMINED"
    assert m.detect_base({"t": "Real index 2015=100"}) == "2015"
    assert m.detect_base({"t": "nothing"}) is None


def _xlsx(rows, sheet="HPI"):
    def cell(ref, v):
        return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    body = ""
    for ri, row in enumerate(rows, 1):
        body += f'<row r="{ri}">' + "".join(cell(f"{chr(65 + ci)}{ri}", v) for ci, v in enumerate(row)) + "</row>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        zf.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        zf.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>')
    return buf.getvalue()


def test_xlsx_country_scan_quarterly_missing_and_duplicates():
    rows = [["Real house price index, 2005=100"], ["Date", "Belgium", "Netherlands"], ["1975:Q1", "1", "40.1"],
            ["1975:Q2", "1", "NA"], ["1975:Q3", "1", "41"], ["note"]]
    res = m.scan_xlsx_country(_xlsx(rows))
    s = res["nl_series"][0]
    assert s["frequency"] == "Q" and s["n_obs"] == 2 and s["missing_markers"] == 1 and s["gap_count"] == 1
    assert s["sheet_notes"] and res["sheet_names"] == ["HPI"]
    with pytest.raises(m.HousingSourceError, match="DUPLICATE"):
        m.scan_xlsx_country(_xlsx(rows + [["1975:Q1", "1", "42"]]))
    with pytest.raises(m.HousingSourceError, match="INVALID_VALUE"):
        m.scan_xlsx_country(_xlsx([["Date", "Netherlands"], ["1975:Q1", "abc"]]))
    with pytest.raises(m.HousingSourceError, match="BAD_XLSX"):
        m.read_xlsx_sheets(b"nope")


PDF_TEXT = ("Kerncijfers\nGemiddelde verkoopprijs bestaande woningen per ultimo x 1000 euro\n"
            + "\n".join(f"{y}   {40 + (y - 1975)}" for y in range(1975, 2001)) + "\n1975   99\n")


def test_year_value_table_parse_stops_at_repeat_and_unparsed_is_not_defect():
    tab = m.parse_year_value_table(PDF_TEXT)
    assert tab["status"] == "PARSED" and tab["values"][1975] == Decimal("40") and len(tab["values"]) == 26
    s = m.summarize_year_table(tab["values"])
    assert s["first"] == "1975" and s["gap_count"] == 0 and s["years_up_to_1999"] == ["1975-1999"] and s["anchors"]["1995"] == "60"
    assert m.parse_year_value_table("no heading here")["status"] == "HEADING_NOT_FOUND"
    assert m.parse_year_value_table("Gemiddelde verkoopprijs bestaande woningen\n1975 40\n")["status"] == "FORMAT_UNPARSED"


def test_growth_comparison_no_splice_and_annualization():
    q = {y * 4 + i: Decimal(100 + (y - 2000) * 10) for y in (2000, 2001, 2002) for i in range(4)}
    ann = m.annualize(q, "Q")
    assert ann == {2000: 100, 2001: 110, 2002: 120}
    part = {k: v for k, v in q.items() if k != 2001 * 4}
    assert 2001 not in m.annualize(part, "Q")  # incomplete year is dropped, never filled
    cbs = {"nl_hpi": {f"{y}-{mo:02d}": Decimal(50 + (y - 2000) * 6) for y in (2000, 2001, 2002, 2003) for mo in range(1, 13)}}
    ann[2003] = Decimal(130)
    res = m.compare_growth(ann, m.annual_from_cbs(cbs["nl_hpi"], "mean"), "a", "b")
    assert res["common_growth_years"] == 3 and Decimal(res["pearson_r"]) <= 1
    assert m.compare_growth({2000: Decimal(1)}, {2000: Decimal(1)}, "a", "b")["status"] == "TOO_FEW_COMMON_YEARS"


def test_overlap_skips_real_rate_and_undetermined():
    assert m.overlap_with_cbs("k", {"unit_class": "INDEX", "real_or_nominal": "REAL"}, {}, "A", {})["status"] == "NOT_COMPARED_REAL_SERIES"
    assert m.overlap_with_cbs("k", {"unit_class": "RATE", "real_or_nominal": "NOMINAL"}, {}, "A", {})["status"] == "NOT_COMPARED_UNIT_RATE"


def test_licence_quotes_and_ckan_facts():
    html = b"<html><body><p>All content is licensed under CC BY-NC-SA 4.0 for non-commercial reuse only.</p><p>Short.</p></body></html>"
    q = m.licence_quotes(html)
    assert q and "CC BY-NC-SA" in q[0]
    assert m.ckan_facts(json.dumps({"result": {"count": 1, "results": [{"title": "T"}]}}).encode())["titles"] == ["T"]
    assert m.ckan_facts(b"<html>")["status"] == "NOT_JSON"


def _fake_fetch(responses):
    def fetch(sid):
        r = responses.get(sid)
        if r is None:
            raise hist_02_acquire.AcquisitionError("NETWORK_TIMEOUT source=%s" % sid)
        return r, {"bytes": len(r), "sha256": "0" * 64}
    return fetch


def test_unreachable_is_partial_exit_zero_and_defect_exit_one(monkeypatch, tmp_path):
    monkeypatch.setattr(m.hist_02_acquire, "fetch", _fake_fetch({"bis-spp-q-nl": LONG.encode()}))
    monkeypatch.setattr(m, "probe_status", lambda url: {"status": 403})
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out), "--only", "bis-spp-q-nl", "--only", "bis-spp-all-nl"]) == 0
    doc = json.loads(out.read_text())
    assert doc["status"] == "PARTIAL" and doc["missing_sources"] == ["bis-spp-all-nl"] and doc["publication_authorized"] is False
    labels = {r["source_id"]: r["label"] for r in doc["results"]}
    assert labels == {"bis-spp-q-nl": "OBTAINED", "bis-spp-all-nl": "UNREACHABLE"}
    assert doc["coverage_matrix"] and "knoll-schularick-steger-no-price-like-home" in doc["references_only"]
    monkeypatch.setattr(m.hist_02_acquire, "fetch", _fake_fetch({"bis-spp-q-nl": (LONG + LONG.splitlines()[1] + "\n").encode()}))
    assert m.main(["--summary-out", str(out), "--only", "bis-spp-q-nl"]) == 1
    assert json.loads(out.read_text())["defects"][0]["source_id"] == "bis-spp-q-nl"


def test_page_candidate_is_reference_only_with_rights_evidence(monkeypatch, tmp_path):
    page = b"<html><title>T</title><body><p>Reproduction of this material is permitted provided the source is cited.</p></body></html>"
    monkeypatch.setattr(m.hist_02_acquire, "fetch", _fake_fetch({"bis-terms": page}))
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out), "--only", "bis-terms"]) == 0
    r = json.loads(out.read_text())["results"][0]
    assert r["label"] == "REFERENCE_ONLY" and r["rights_evidence"] == "OFFICIAL_TEXT_READ" and r["licence_quotes"]


def test_cbs_baseline_overlap_end_to_end(monkeypatch, tmp_path):
    rows = ["date,series,value"]
    for y in range(2000, 2005):
        for mo in range(1, 13):
            rows.append(f"{y}-{mo:02d},nl_hpi,{50 + (y - 2000) * 5}")
    base = tmp_path / "b.csv"
    base.write_text("\n".join(rows) + "\n")
    ann = "FREQ,REF_AREA,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE\n" + "".join(f"A,NL,Index 2010=100,{y},{60 + (y - 2000) * 6}\n" for y in range(2000, 2005))
    monkeypatch.setattr(m.hist_02_acquire, "fetch", _fake_fetch({"bis-spp-q-nl": ann.encode()}))
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out), "--only", "bis-spp-q-nl", "--cbs-csv", str(base)]) == 0
    ov = json.loads(out.read_text())["results"][0]["overlap_vs_cbs"][0]
    assert ov["status"] == "COMPARED" and ov["vs_cbs_hpi_annual_mean"]["common_growth_years"] == 4
