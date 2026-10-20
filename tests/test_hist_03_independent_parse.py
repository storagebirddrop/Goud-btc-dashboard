"""Tests for the HIST-03 second-parser reproducibility check.

All workbooks are SYNTHETIC. They prove comparison/parsing code only, never
anything about real World Bank data, and a parser match is not a second source.
"""
import io
import pytest
from test_hist_03_worldbank_validate import UNIT, book, make_xlsx
from tools.hist_03_independent_parse import FIELDS, compare, crosscheck, fingerprint
from tools.hist_03_worldbank_validate import ValidationError, expected_months, validate

openpyxl = pytest.importorskip("openpyxl")


def openpyxl_book(value=lambda p: 100.5, gold_cols=("Gold",)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Monthly Prices"
    ws.append(["Synthetic title"])
    ws.append(["", "Crude"] + list(gold_cols))
    ws.append([None, "($/bbl)"] + [UNIT] * len(gold_cols))
    for p in expected_months("1974-12", "2000-01"):
        ws.append([f"{p[:4]}M{p[5:]}", 1.0] + [value(p)] * len(gold_cols))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_two_parsers_match_on_synthetic_openpyxl_workbook():
    r = crosscheck(openpyxl_book())
    assert r["status"] == "MATCH" and r["differing_fields"] == []
    assert r["independent_fingerprint"]["count_in_range"] == 300


def test_two_parsers_match_on_minimal_inline_string_workbook():
    # make_xlsx has no [Content_Types].xml; openpyxl may reject it -> must be reported, never a silent pass.
    r = crosscheck(book())
    assert r["status"] in ("MATCH", "UNAVAILABLE_OR_FAILED")


def test_integer_and_decimal_values_both_reproduce():
    r = crosscheck(openpyxl_book(value=lambda p: 300 if p < "1990-01" else 300.25))
    assert r["status"] == "MATCH"
    assert r["independent_fingerprint"]["non_integer_count_in_range"] == 120


@pytest.mark.parametrize("field", FIELDS)
def test_compare_flags_every_field_difference(field):
    a = {f: "x" for f in FIELDS}
    b = dict(a)
    b[field] = "y"
    assert compare(a, a) == [] and compare(a, b) == [field]


def test_compare_flags_differing_series_hash():
    a = fingerprint(_parsed(100.5))
    b = fingerprint(_parsed(100.75))
    assert "canonical_series_sha256" in compare(a, b)


def _parsed(v):
    from tools.hist_03_worldbank_validate import parse
    return parse(book_const(v))


def book_const(v):
    rows = [["T"], ["", "Crude", "Gold"], [None, "($/bbl)", UNIT]]
    rows += [[f"{p[:4]}M{p[5:]}", 1.0, v] for p in expected_months("1975-01", "1999-12")]
    return make_xlsx(rows)


def test_precision_stats_and_non_integer_count_are_aggregate_only():
    s = validate(book_const(100.5))
    assert s["non_integer_count_in_range"] == 300
    assert s["decimal_places_histogram"]["in_range"] == {"1": 300}
    s2 = validate(book_const(100))
    assert s2["non_integer_count_in_range"] == 0 and s2["decimal_places_histogram"]["in_range"] == {"0": 300}


def test_two_gold_columns_fail_closed():
    with pytest.raises(ValidationError, match="AMBIGUOUS_GOLD_COLUMN"):
        validate(openpyxl_book(gold_cols=("Gold", "GOLD")))
    r = crosscheck(openpyxl_book(gold_cols=("Gold", "GOLD")))
    assert r["status"] == "UNAVAILABLE_OR_FAILED" and r["error_class"] == "ValueError"


def _run_main(monkeypatch, tmp_path, raw):
    import json
    import tools.hist_02_acquire as acq
    from tools import hist_03_worldbank_validate as v
    rec = {"url": "synthetic", "sha256": "0" * 64, "bytes": len(raw), "http_status": 200}
    monkeypatch.setattr(acq, "fetch", lambda source: (raw, rec))
    out = tmp_path / "s.json"
    code = v.main(["--summary-out", str(out), "--independent-parser", "openpyxl"])
    return code, json.loads(out.read_text())


def test_main_passes_when_parsers_match(monkeypatch, tmp_path):
    code, s = _run_main(monkeypatch, tmp_path, openpyxl_book())
    assert code == 0 and s["status"] == "VALIDATED" and s["independent_parser"]["status"] == "MATCH"


def test_main_fails_when_parsers_differ(monkeypatch, tmp_path):
    import tools.hist_03_independent_parse as ip
    orig = ip.fingerprint
    calls = []

    def skewed(p, *a, **k):
        f = orig(p, *a, **k)
        calls.append(1)
        if len(calls) == 1:  # first call is the independent parse inside crosscheck()
            f["canonical_series_sha256"] = "f" * 64
        return f

    monkeypatch.setattr(ip, "fingerprint", skewed)
    code, s = _run_main(monkeypatch, tmp_path, openpyxl_book())
    assert code == 2 and s["status"] == "CROSSCHECK_FAILED"
    assert s["independent_parser"]["differing_fields"] == ["canonical_series_sha256"]
