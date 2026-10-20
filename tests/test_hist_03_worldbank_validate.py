"""Tests for tools.hist_03_worldbank_validate.

All workbooks here are SYNTHETIC. They prove parser/validator code only and
NEVER prove anything about historical World Bank data.
"""
import io
import zipfile
from xml.sax.saxutils import escape
import pytest
from tools.hist_03_worldbank_validate import ValidationError, expected_months, validate

UNIT = "($/troy oz)"


def make_xlsx(rows, sheet="Monthly Prices"):
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = ""
        for c, v in enumerate(row):
            if v is None:
                continue
            ref = f"{'ABCDEFGH'[c]}{r}"
            if isinstance(v, str):
                cells += f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
            else:
                cells += f'<c r="{ref}"><v>{v}</v></c>'
        xml_rows.append(f'<row r="{r}">{cells}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
    return buf.getvalue()


def book(skip=(), dup=None, unit=UNIT, gold="Gold", bad=None, badval=0, fmt="{y}M{m:02d}", sheet="Monthly Prices"):
    rows = [["Title"], ["", "Crude", gold], [None, "($/bbl)", unit]]
    for p in expected_months("1974-12", "2000-01"):
        if p in skip:
            continue
        y, m = int(p[:4]), int(p[5:])
        val = badval if p == bad else 100.5
        rows.append([fmt.format(y=y, m=m), 1.0, val])
        if p == dup:
            rows.append([fmt.format(y=y, m=m), 1.0, val])
    return make_xlsx(rows, sheet)


def test_good_path():
    s = validate(book())
    assert s["status"] == "VALIDATED"
    assert s["count_in_range"] == 300 and s["first_in_range"] == "1975-01" and s["last_in_range"] == "1999-12"
    assert s["unit_accepted"] == UNIT and s["sheet_first_period"] == "1974-12" and s["sheet_last_period"] == "2000-01"
    assert len(s["canonical_series_sha256"]) == 64 and len(s["anchors"]) <= 12


def test_missing_month():
    s = validate(book(skip={"1987-06"}))
    assert s["status"] == "FAILED" and s["missing_months"] == ["1987-06"]


def test_duplicate():
    assert "DUPLICATE_MONTHS" in validate(book(dup="1990-03"))["problems"]


def test_wrong_unit():
    assert "UNIT_NOT_TROY_OUNCE" in validate(book(unit="($/mt)"))["problems"]


def test_missing_gold_column():
    with pytest.raises(ValidationError, match="GOLD_COLUMN_NOT_FOUND"):
        validate(book(gold="Silver"))


def test_missing_sheet():
    with pytest.raises(ValidationError, match="SHEET_NOT_FOUND"):
        validate(book(sheet="Other"))


@pytest.mark.parametrize("v", [0, -5, ".."])
def test_nonpositive_or_nonnumeric(v):
    s = validate(book(bad="1980-01", badval=v))
    assert "INVALID_VALUES" in s["problems"] and s["invalid_rows"][0]["period"] == "1980-01"


def test_different_date_format():
    s = validate(book(fmt="{y}-{m:02d}"))
    assert s["status"] == "FAILED" and s["count_in_range"] == 0
