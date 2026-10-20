"""HIST-04 USD/NLG source probe: offline tests with SYNTHETIC fixtures (prove parser code only)."""
import io
import json
import zipfile
from decimal import Decimal

import pytest

from tools import hist_02_acquire
from tools import hist_04_nlg_sources as m

FED = b"""NETHERLANDS -- SPOT EXCHANGE RATE, GUILDERS/US$
Noon buying rates in New York
 1975-01-02   2.5000
 1975-01-03   ND
 1975-01-06   2.6000
 1975-02-03   2.4000
Note: ND = no data
"""


def test_all_candidates_registered_https_and_exact():
    for sid, (url, _, _) in m.CANDIDATES.items():
        assert url.startswith("https://") and hist_02_acquire.SOURCES[sid][0] == url
        hist_02_acquire.validate_url(sid, url)
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("fed-h10-dat89-ne-txt", "https://www.federalreserve.gov/releases/h10/hist/other.txt")


def test_fed_text_parses_missing_and_monthly_mean():
    p = m.parse_dated_text(FED)
    assert p["missing_markers"] == 1 and len(p["points"]) == 3 and p["trailer_count"] == 1
    s, monthly, direction = m.summarize_series(p, "daily")
    assert direction == "NLG_PER_USD" and s["direction"]["evidence"] == "TEXT_AND_VALUE_RANGE"
    assert monthly["1975-01"] == Decimal("2.55") and monthly["1975-02"] == Decimal("2.4")
    assert "1975-03" not in monthly and s["coverage_1975_1998"]["missing_count"] == 24 * 12 - 2  # no filling


def test_two_digit_year_needs_explicit_century():
    raw = b"X GUILDERS/US$\n01/13/75 2.5\n01/14/75 2.6\n"
    with pytest.raises(m.NlgSourceError, match="CENTURY"):
        m.parse_dated_text(raw)
    p = m.parse_dated_text(raw, century=1900)
    assert min(p["points"]).year == 1975 and p["slash_order"] == "MDY"


def test_duplicate_date_invalid_value_and_garbled_line_fail():
    with pytest.raises(m.NlgSourceError, match="DUPLICATE_DATE"):
        m.parse_dated_text(b"h\n1975-01-02 2.5\n1975-01-02 2.5\n")
    with pytest.raises(m.NlgSourceError, match="INVALID_VALUE"):
        m.parse_dated_text(b"h\n1975-01-02 2.5\n1975-01-03 2,5\n")
    with pytest.raises(m.NlgSourceError, match="UNPARSED_DATA_LINE"):
        m.parse_dated_text(b"h\n1975-01-02 2.5\n19750103 2.5 2.6 junk\n")
    with pytest.raises(m.NlgSourceError, match="INVALID_VALUE"):
        m.parse_dated_text(b"h\n1975-01-02 abc\n")
    with pytest.raises(m.NlgSourceError, match="NON_POSITIVE"):
        m.parse_dated_text(b"h\n1975-01-02 0\n")
    with pytest.raises(m.NlgSourceError, match="NO_DATA_LINES"):
        m.parse_dated_text(b"<html>not data</html>")


def test_direction_text_value_and_conflicts():
    assert m.detect_direction("GUILDERS/US$", [Decimal("2.5")])["direction"] == "NLG_PER_USD"
    assert m.detect_direction("US$/GUILDER", [Decimal("0.4")])["direction"] == "USD_PER_NLG"
    assert m.detect_direction("", [Decimal("2.5")])["evidence"] == "VALUE_RANGE_ONLY"
    with pytest.raises(m.NlgSourceError, match="TEXT_VS_VALUE"):
        m.detect_direction("GUILDERS/US$", [Decimal("0.4")])  # direction never assumed
    with pytest.raises(m.NlgSourceError, match="UNDETERMINED"):
        m.detect_direction("", [Decimal("50")])
    with pytest.raises(m.NlgSourceError, match="OUT_OF_RANGE"):
        m.detect_direction("GUILDERS/US$", [Decimal("2.5"), Decimal("9")])


def test_no_forward_fill_in_provider_monthly():
    raw = b"h GUILDERS/US$\n1975-01-01 2.5\n1975-03-01 2.6\n"
    s, monthly, _ = m.summarize_series(m.parse_dated_text(raw), "monthly")
    assert sorted(monthly) == ["1975-01", "1975-03"] and "1975-02" in s["coverage_1975_1998"]["missing_months"]
    with pytest.raises(m.NlgSourceError, match="DUPLICATE_MONTH"):
        m.summarize_series(m.parse_dated_text(b"h GUILDERS/US$\n1975-01-01 2.5\n1975-01-15 2.6\n"), "monthly")


def _cbs(values, title="Amerikaanse dollar, per 1, in guldens", extra=None):
    props = {"value": [{"Key": "D1", "Title": title, "Unit": "gld", "Type": "Topic", "Description": ""}] + (extra or [])}
    rows = [{"ID": i, "Perioden": per, "D1": v} for i, (per, v) in enumerate(values)]
    return json.dumps(props).encode(), json.dumps({"value": rows}).encode()


def test_cbs_parse_exact_decimals_and_annual_ignored():
    props, data = _cbs([("1975JJ00", 2.5), ("1975MM01", 2.4963), ("1975MM02", None), ("1975MM03", 2.5)])
    s, monthly, d = m.parse_cbs(props, data)
    assert d == "NLG_PER_USD" and monthly == {"1975-01": Decimal("2.4963"), "1975-03": Decimal("2.5")}
    assert s["missing_values"] == 1 and s["annual_points"] == 1 and "1975-02" in s["coverage_1975_1998"]["missing_months"]


def test_cbs_fail_closed():
    with pytest.raises(m.NlgSourceError, match="UNEXPECTED_PERIOD_CODE"):
        m.parse_cbs(*_cbs([("1975Q1", 2.5)]))
    with pytest.raises(m.NlgSourceError, match="DUPLICATE_MONTH"):
        m.parse_cbs(*_cbs([("1975MM01", 2.5), ("1975MM01", 2.5)]))
    with pytest.raises(m.NlgSourceError, match="AMBIGUOUS_OR_MISSING"):
        m.parse_cbs(*_cbs([("1975MM01", 2.5)], extra=[{"Key": "D2", "Title": "US dollar", "Type": "Topic"}]))
    with pytest.raises(m.NlgSourceError, match="TEXT_VS_VALUE"):
        m.parse_cbs(*_cbs([("1975MM01", 0.4)]))
    with pytest.raises(m.NlgSourceError, match="NOT_JSON"):
        m.parse_cbs(b"<html>", b"{}")


LONG = b"FREQ,REF_AREA,CURRENCY,TIME_PERIOD,OBS_VALUE\nM,NL,NLG,1975-01,2.5\nM,NL,NLG,1975-02,\nM,NL,NLG,1975-03,2.6\nM,DE,DEM,1975-01,2.4\n"


def test_sdmx_long_csv_selects_nl_without_filling():
    r = m.scan_csv_bytes(LONG)
    assert r["layout"] == "long" and r["nl_series_count"] == 1 and r["distinct_areas"] == 2
    s = r["nl_series"][0]
    assert s["observations"] == 2 and s["missing_markers"] == 1 and s["direction"]["direction"] == "NLG_PER_USD"
    assert "1975-02" in s["coverage_1975_1998"]["missing_months"]


def test_sdmx_wide_csv_and_zip():
    cols = [f"1975-{i:02d}" for i in range(1, 13)] + [f"1976-{i:02d}" for i in range(1, 13)]
    raw = ("FREQ,REF_AREA,Title," + ",".join(cols) + "\nM,NL,Dutch guilder per US dollar," + ",".join(["2.5"] * 23 + [""]) + "\n").encode()
    r = m.scan_csv_bytes(raw)
    assert r["layout"] == "wide" and r["nl_series"][0]["observations"] == 23
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", LONG)
    assert m.scan_zip_bytes(buf.getvalue())["nl_series_count"] == 1
    b2 = io.BytesIO()
    with zipfile.ZipFile(b2, "w") as z:
        z.writestr("x.txt", "a")
    with pytest.raises(m.NlgSourceError, match="NO_CSV_IN_ZIP"):
        m.scan_zip_bytes(b2.getvalue())


def test_sdmx_unrecognised_and_duplicate_fail():
    with pytest.raises(m.NlgSourceError, match="LAYOUT_UNRECOGNISED"):
        m.scan_csv_bytes(b"<html>\n")
    with pytest.raises(m.NlgSourceError, match="DUPLICATE_PERIOD"):
        m.scan_csv_bytes(LONG + b"M,NL,NLG,1975-01,2.5\n")


def test_fixed_rate_extraction():
    r = m.extract_fixed_rate(b"<td>Netherlands</td><td>Dutch guilder</td><td>2.20371</td>")
    assert r["status"] == "FOUND" and r["equals_expected"] and "2.20371" in r["quote"]
    assert m.extract_fixed_rate(b"2,20371 Dutch guilders")["equals_expected"]
    assert m.extract_fixed_rate(b"<p>nothing 2.20371 unrelated</p>")["status"] == "NOT_FOUND_IN_PAGE"
    assert m.extract_fixed_rate(b"Dutch guilder 2.2037")["status"] == "NOT_FOUND_IN_PAGE"


def test_compare_monthly_and_page_facts():
    c = m.compare_monthly({"1975-01": Decimal("2.5")}, {"1975-01": Decimal("2.5"), "1975-02": Decimal("2")})
    assert c["common_months"] == 1 and Decimal(c["max_rel_diff"]) == 0
    f = m.page_facts(b"<title>T</title><p>These data are in the public domain and may be copied. Other.</p><a href='x_ne.txt'>a</a>", m.PAGE_KEYWORDS, r"_ne\.")
    assert f["title"] == "T" and f["links"] == ["x_ne.txt"] and "public domain" in f["sentences"][0]


def test_main_exits_zero_when_unreachable_and_one_on_defect(tmp_path, monkeypatch):
    def unreachable(sid, **k):
        raise hist_02_acquire.AcquisitionError("NETWORK_TIMEOUT")
    monkeypatch.setattr(hist_02_acquire, "fetch", unreachable)
    monkeypatch.setattr(m, "probe_status", lambda url: {"status": 404})
    out = tmp_path / "s.json"
    assert m.main(["--summary-out", str(out), "--only", "fed-h10-dat89-ne-txt", "--only", "fixed-ecb-pr981231"]) == 0
    doc = json.loads(out.read_text())
    assert doc["publication_authorized"] is False and doc["source_approved"] is False
    assert all(r["fetch"] == "FAILED" and r["probe"] == {"status": 404} for r in doc["results"])
    monkeypatch.setattr(hist_02_acquire, "fetch", lambda sid, **k: (b"h GUILDERS/US$\n1975-01-02 2.5\n1975-01-02 2.5\n", {"bytes": 1, "sha256": "x"}))
    assert m.main(["--summary-out", str(out), "--only", "fed-h10-dat89-ne-txt"]) == 1
    assert json.loads(out.read_text())["defects"] == ["fed-h10-dat89-ne-txt"]
