"""Synthetic tests (labelled SYNTHETIC: prove code only, not source behaviour)."""
import io
import zipfile
from decimal import Decimal as D
import pytest
from tools.hist_03_precision import (deviation_stats, PrecisionError, rounding_sensitivity, gram_error_for,
                                     analyse_monthly_sheet, analyse_other_sheets, workbook_metadata,
                                     format_shows_decimals)


def test_synthetic_zero_deviation():
    s = {"1975-01": D("100"), "1980-06": D("200")}
    r = deviation_stats(s, dict(s))
    assert r["n"] == 2 and r["mean_signed_diff"] == 0 and r["max_abs"] == 0
    assert r["share_within_0_5_usd"] == 1.0 and r["only_wb"] == 0 and r["only_other"] == 0


def test_synthetic_sign_and_stats():
    wb = {"1975-01": D("101"), "1975-02": D("98"), "1985-03": D("100.5")}
    ot = {"1975-01": D("100"), "1975-02": D("100"), "1985-03": D("100")}
    r = deviation_stats(wb, ot)
    assert r["mean_signed_diff"] == pytest.approx((1 - 2 + 0.5) / 3, abs=1e-6)
    assert r["max_abs"] == 2 and r["median_abs"] == 1
    assert r["share_within_0_5_usd"] == pytest.approx(1 / 3, abs=1e-6)  # only 0.5 qualifies
    assert r["max_rel_pct"] == 2.0
    assert r["subperiods"]["1975-79"]["n"] == 2 and r["subperiods"]["1985-89"]["n"] == 1
    assert r["subperiods"]["1990-94"]["n"] == 0 and r["subperiods"]["1990-94"]["mean_abs"] is None
    assert [t["month"] for t in r["top3_abs_diff"]] == ["1975-02", "1975-01", "1985-03"]
    assert r["top3_abs_diff"][0]["diff"] == -2.0


def test_synthetic_unequal_sets():
    r = deviation_stats({"1975-01": D("1"), "1975-02": D("1")}, {"1975-01": D("1"), "1975-03": D("1"), "1975-04": D("1")})
    assert r["n"] == 1 and r["only_wb"] == 1 and r["only_other"] == 2


@pytest.mark.parametrize("wb,ot", [
    ({}, {}), ({"1975-01": D("1")}, {"1975-02": D("1")}),
    ({"1975-01": D("1")}, {"1975-01": D("0")}),
    ({"1975-01": 1.0}, {"1975-01": D("1")}),
    ({"1975-13": D("1")}, {"1975-13": D("1")}),
    ({"1975-01": D("NaN")}, {"1975-01": D("1")}),
    (None, {}),
])
def test_synthetic_fail_closed(wb, ot):
    with pytest.raises(PrecisionError):
        deviation_stats(wb, ot)


# ---- rounding_sensitivity (SYNTHETIC prices) ----
def test_synthetic_gram_error_for_exact():
    # price 100 too high by 1 -> gram -1/101
    assert float(gram_error_for(D("100"), D("1"))) == pytest.approx(-1 / 101, rel=1e-12)
    assert float(gram_error_for(D("100"), D("-1"))) == pytest.approx(1 / 99, rel=1e-12)
    assert gram_error_for(D("100"), D("0")) == 0
    for bad in [(D("0"), D("1")), (D("10"), D("-10")), (D("NaN"), D("1")), (100, D("1"))]:
        with pytest.raises(PrecisionError):
            gram_error_for(*bad)


def test_synthetic_rounding_sensitivity():
    r = rounding_sensitivity({"1975-01": D("100"), "1975-02": D("200"), "1995-06": D("400")})
    assert r["rel_price_bound_pct"]["max"] == 0.5          # 0.5/100
    assert r["gram_error_pct"]["max"] == pytest.approx(0.5 / 99.5 * 100, abs=1e-5)
    assert r["worst_month"]["month"] == "1975-01"
    assert r["subperiods"]["1975-79"]["gram_error_pct"]["n"] == 2
    assert r["subperiods"]["1990-94"]["gram_error_pct"]["n"] == 0
    assert "THEORETICAL" in r["basis"]


@pytest.mark.parametrize("prices", [{}, {"1975-01": D("0.5")}, {"1975-01": D("-3")}, {"bad": D("5")}, {"1975-01": 5}])
def test_synthetic_rounding_sensitivity_fail_closed(prices):
    with pytest.raises(PrecisionError):
        rounding_sensitivity(prices)


# ---- XML cell analysis on a minimal SYNTHETIC xlsx built in the test ----
MAIN = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def make_xlsx(gold_values, numfmt="1", extra_col=("1.5", "2.5"), fmt_code=None, header="Gold"):
    rows = [f'<row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c><c r="B1" t="inlineStr"><is><t>{header}</t></is></c>'
            '<c r="C1" t="inlineStr"><is><t>Silver</t></is></c></row>']
    for i, v in enumerate(gold_values, start=2):
        rows.append(f'<row r="{i}"><c r="A{i}" t="inlineStr"><is><t>1975M{i - 1:02d}</t></is></c>'
                    f'<c r="B{i}" s="1"><v>{v}</v></c><c r="C{i}"><v>{extra_col[(i - 2) % 2]}</v></c></row>')
    sheet = f'<worksheet {MAIN}><sheetData>{"".join(rows)}</sheetData></worksheet>'
    nf = f'<numFmts count="1"><numFmt numFmtId="164" formatCode="{fmt_code}"/></numFmts>' if fmt_code else ""
    styles = f'<styleSheet {MAIN}>{nf}<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="{numfmt}"/></cellXfs></styleSheet>'
    wb = (f'<workbook {MAIN} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets><sheet name="Monthly Prices" sheetId="1" r:id="rId1"/><sheet name="Annual Prices (Nominal)" sheetId="2" r:id="rId2"/></sheets></workbook>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
    annual = (f'<worksheet {MAIN}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Year</t></is></c>'
              '<c r="B1" t="inlineStr"><is><t>Gold</t></is></c></row>'
              '<row r="2"><c r="A2"><v>1975</v></c><c r="B2"><v>150.25</v></c></row></sheetData></worksheet>')
    core = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
            '<dc:creator>SYNTH</dc:creator><dcterms:modified>2026-01-01T00:00:00Z</dcterms:modified></cp:coreProperties>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/worksheets/sheet2.xml", annual)
        z.writestr("docProps/core.xml", core)
    return buf.getvalue()


def test_synthetic_xml_whole_numbers():
    r = analyse_monthly_sheet(make_xlsx(["100", "200", "300"]))
    assert r["gold_column"] == "B" and r["data_rows"] == 3
    assert r["gold"]["raw_v_decimal_places_histogram"] == {"0": 3}
    assert r["gold"]["numeric_cells_non_integer_raw"] == 0
    assert r["regex_check"] == {"cells_matched_in_data_rows": 3, "cells_with_dot_or_E": 0, "mismatch_vs_xml_parse": 0}
    assert r["all_columns"]["C:Silver"]["non_integer_cells"] == 3
    assert r["all_columns"]["B:Gold"]["non_integer_cells"] == 0
    assert "integer" in next(iter(r["gold"]["style_numfmt"]))


def test_synthetic_xml_decimals_and_format():
    r = analyse_monthly_sheet(make_xlsx(["100.25", "200", "3E2"], numfmt="164", fmt_code="0.00"))
    assert r["gold"]["raw_v_decimal_places_histogram"] == {"2": 1, "0": 2}
    assert r["gold"]["numeric_cells_non_integer_raw"] == 2
    assert r["regex_check"]["cells_with_dot_or_E"] == 2 and r["regex_check"]["mismatch_vs_xml_parse"] == 0
    assert "decimals" in next(iter(r["gold"]["style_numfmt"]))


def test_synthetic_hidden_decimals_format():
    # stored decimals but display format '0' (hides decimals): raw analysis still sees them
    r = analyse_monthly_sheet(make_xlsx(["100.4", "200.6"], numfmt="1"))
    assert r["gold"]["numeric_cells_non_integer_raw"] == 2
    assert "integer" in next(iter(r["gold"]["style_numfmt"]))


@pytest.mark.parametrize("code,kind", [("General", "general"), ("0", "integer"), ("#,##0", "integer"), ("0.00", "decimals"),
                                       ('0"x.y"', "integer"), ("@", "text"), (None, "unknown"), ("[Red]#,##0.0;0", "decimals")])
def test_synthetic_format_classifier(code, kind):
    assert format_shows_decimals(code) == kind


def test_synthetic_other_sheets_and_metadata():
    raw = make_xlsx(["100"])
    o = analyse_other_sheets(raw, {"1975-%02d" % m: D("150") for m in range(1, 13)})
    assert o["sheet_names"] == ["Monthly Prices", "Annual Prices (Nominal)"]
    a = o["annual"]
    assert a["non_integer_annual_values"] == 1 and a["raw_v_decimal_places_histogram"] == {"2": 1}
    assert a["annual_vs_monthly_mean_1975_1999"]["n_years"] == 1 and a["annual_vs_monthly_mean_1975_1999"]["max_abs"] == 0.25
    assert a["annual_vs_monthly_mean_1975_1999"]["years_within_0_5"] == 1
    md = workbook_metadata(raw)
    assert md["docProps/core.xml"]["creator"] == "SYNTH" and md["docProps/app.xml"] == "ABSENT"


def test_synthetic_xml_fail_closed():
    with pytest.raises(PrecisionError):
        analyse_monthly_sheet(make_xlsx(["1"], header="Zinc"))  # no GOLD header
    with pytest.raises(Exception):
        analyse_monthly_sheet(b"not a zip")
