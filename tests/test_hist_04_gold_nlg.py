"""HIST-04 gold NLG/EUR research candidate: offline tests with SYNTHETIC data.

They prove code behaviour only (parsing, flags, formulas, exit semantics); they say nothing about real
World Bank, Fed or ECB values. Label of everything: research candidate - not approved.
"""
import csv
import io
import json
import re
import zipfile
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from tools import hist_02_acquire
from tools import hist_04_fx as fx
from tools import hist_04_gold_nlg as g
from tools.hist_02_coverage import month_range

D = Decimal
ROOT = Path(__file__).resolve().parents[1]
HEADER = "NETHERLANDS -- SPOT EXCHANGE RATE, GUILDERS/US$"


# --------------------------------------------------------------------------- synthetic inputs
def fed_value(m, day):
    i = month_range("1975-01", "1998-12").index(m)
    return D(2) + D(i % 7) / 10 + D(day) / 1000  # 4 decimals, inside 1..6


def fed_file(first, last, days=20, skip_months=(), few=None, nd=(), header=HEADER, dup=False):
    lines = [header, "Noon buying rates in New York"]
    for m in month_range(first, last):
        if m in skip_months:
            continue
        n = (few or {}).get(m, days)
        for day in range(1, n + 1):
            iso = f"{m}-{day:02d}"
            val = "ND" if iso in nd else f"{fed_value(m, day):.4f}"
            lines.append(f" {iso}   {val}")
            if dup and m == "1980-02" and day == 3:
                lines.append(f" {iso}   {val}")
    lines.append("Note: ND = no data")
    return "\n".join(lines).encode()


def xlsx(rows):
    cells_xml = []
    for r, row in enumerate(rows, 1):
        cells = ""
        for c, v in enumerate(row):
            if v is None:
                continue
            ref = f"{'ABCDEFGH'[c]}{r}"
            cells += (f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' if isinstance(v, str)
                      else f'<c r="{ref}"><v>{v}</v></c>')
        cells_xml.append(f'<row r="{r}">{cells}</row>')
    ns_ = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns_}" xmlns:r="{rel}"><sheets><sheet name="Monthly Prices" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns_}"><sheetData>{"".join(cells_xml)}</sheetData></worksheet>')
    return buf.getvalue()


def usd_value(m):
    return 300 + month_range("1974-12", "2000-01").index(m)


def wb_book(skip=()):
    body = [[f"{m[:4]}M{m[5:]}", 1.0, usd_value(m)] for m in month_range("1974-12", "2000-01") if m not in skip]
    return xlsx([["Title"], ["", "Crude", "Gold"], [None, "($/bbl)", "($/troy oz)"]] + body)


def ecb_monthly(skip=(), direction=("USD", "EUR")):
    lines = ["KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE,OBS_STATUS"]
    for i, m in enumerate(month_range("1999-01", "1999-12")):
        if m not in skip:
            lines.append(f"EXR.M.USD.EUR.SP00.A,M,{direction[0]},{direction[1]},{m},{D('1.10') + D(i) / 100},A")
    return ("\n".join(lines) + "\n").encode()


def ecb_daily():
    return (b"KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
            b"EXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-04,1.1789,A\nEXR.D.USD.EUR.SP00.A,D,USD,EUR,1999-01-05,1.1790,A\n")


def boe_monthly(extra=None):
    vals = {m: D(usd_value(m)) for m in month_range("1975-01", "1999-12")}
    vals.update(extra or {})
    return ("DATE,XUMAGPD\n" + "\n".join(f"{m}-28,{v}" for m, v in vals.items()) + "\n").encode()


def rec_for(sid, raw):
    import hashlib
    return {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0], "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def make_acquire(files, unavailable=()):
    def acquire(sid):
        if sid in unavailable or sid not in files:
            raise fx.SourceUnavailable(sid, "HTTP_404", "synthetic")
        return files[sid], rec_for(sid, files[sid])
    return acquire


def base_files(**kw):
    return {g.FED_IDS[0]: fed_file("1975-01", "1989-12", **kw), g.FED_IDS[1]: fed_file("1990-01", "1998-12"),
            g.ECB_M: ecb_monthly()}


@pytest.fixture
def workbook(tmp_path):
    p = tmp_path / "wb.xlsx"
    p.write_bytes(wb_book())
    return str(p)


def run(workbook, files, unavailable=()):
    return g.collect(workbook, acquire=make_acquire(files, unavailable))


# --------------------------------------------------------------------------- coverage and formulas
def test_full_synthetic_run_coverage_and_formulas(workbook):
    s, rows = run(workbook, base_files())
    assert s["status"] == "PARTIAL"  # optional sources (ECB daily, IMF, BoE) not supplied -> explicit
    assert {m["source_id"] for m in s["missing_sources"]} == {g.ECB_D, g.IMF_ID, g.BOE_M, g.BOE_D}
    c = s["coverage"]
    assert c["nlg_months_in_table"] == 288 and c["nlg_months_exactly_288"] is True
    assert c["nlg_months_with_gold_nlg"] == 288 and c["nlg_months_null_gold_nlg"] == 0
    assert c["eur_months_with_gold_eur"] == 12 and len(rows) == 300
    r = rows["1975-03"]
    pts = [fed_value("1975-03", d) for d in range(1, 21)]
    mean = sum(pts) / 20
    assert r["fx_obs_count"] == 20 and r["fx_nd_count"] == 0 and r["quality_label"] == "OK"
    assert Fraction(r["fx_nlg_per_usd"]) == Fraction(mean)  # exact: no float anywhere
    assert Fraction(r["gold_nlg_oz"]) == Fraction(usd_value("1975-03")) * Fraction(mean)
    exp_eur = Fraction(usd_value("1975-03")) * Fraction(mean) / Fraction(220371, 100000)
    assert abs(Fraction(r["hist_eur_equivalent_oz"]) - exp_eur) / exp_eur < Fraction(1, 10 ** 30)
    assert r["gold_eur_oz"] is None and r["fx_usd_per_eur"] is None  # NLG regime never carries a euro market price
    e = rows["1999-04"]
    assert e["regime"] == "EUR_ECB_MONTHLY" and e["gold_nlg_oz"] is None and e["hist_eur_equivalent_oz"] is None
    exp = Fraction(usd_value("1999-04")) / Fraction(e["fx_usd_per_eur"])
    assert abs(Fraction(e["gold_eur_oz"]) - exp) / exp < Fraction(1, 10 ** 30)
    assert s["checks"]["independent_recompute"]["pass"] and s["checks"]["independent_recompute"]["values_checked"] > 500
    assert all(isinstance(rows[m]["_gold_nlg"], D) for m in month_range("1975-01", "1998-12"))


def test_independent_recompute_detects_tampering(workbook):
    s, rows = run(workbook, base_files())
    pts = {date(int(m[:4]), int(m[5:]), d): fed_value(m, d) for m in month_range("1975-01", "1998-12") for d in range(1, 21)}
    wb = {m: D(usd_value(m)) for m in month_range("1975-01", "1999-12")}
    ecb = {m: D("1.10") + D(i) / 100 for i, m in enumerate(month_range("1999-01", "1999-12"))}
    assert g.independent_recompute(rows, wb, pts, ecb)["pass"]
    rows["1980-01"]["_gold_nlg"] = rows["1980-01"]["_gold_nlg"] * D("1.0000001")
    assert not g.independent_recompute(rows, wb, pts, ecb)["pass"]


def test_missing_days_stay_missing_and_are_counted(workbook):
    nd = {"1975-01-05", "1975-01-06"}
    s, rows = run(workbook, base_files(nd=nd))
    r = rows["1975-01"]
    assert r["fx_obs_count"] == 18 and r["fx_nd_count"] == 2
    present = [fed_value("1975-01", d) for d in range(1, 21) if f"1975-01-{d:02d}" not in nd]
    exp = Fraction(sum(present)) / 18  # no forward fill, no interpolation
    assert abs(Fraction(r["fx_nlg_per_usd"]) - exp) / exp < Fraction(1, 10 ** 30)
    assert s["coverage"]["nd_days_total"] == 2


def test_zero_observation_month_gives_null_fx_and_null_gold(workbook):
    files = base_files()
    files[g.FED_IDS[0]] = fed_file("1975-01", "1989-12", skip_months={"1980-05"})
    s, rows = run(workbook, files)
    r = rows["1980-05"]
    assert r["fx_nlg_per_usd"] is None and r["gold_nlg_oz"] is None and r["hist_eur_equivalent_oz"] is None
    assert r["fx_obs_count"] == 0 and r["quality_label"] == "NO_FX_OBSERVATIONS"
    assert rows["1980-04"]["gold_nlg_oz"] is not None and rows["1980-06"]["gold_nlg_oz"] is not None
    assert s["coverage"]["nlg_months_null_gold_nlg"] == 1 and s["coverage"]["months_zero_obs"] == 1


def test_incomplete_month_labelling(workbook):
    s, rows = run(workbook, base_files(few={"1976-02": 14, "1976-03": 15, "1976-04": 3}))
    assert rows["1976-02"]["quality_label"] == "INCOMPLETE_FEW_OBS" and rows["1976-02"]["fx_obs_count"] == 14
    assert rows["1976-03"]["quality_label"] == "OK"
    assert rows["1976-04"]["quality_label"] == "INCOMPLETE_FEW_OBS"
    assert rows["1976-02"]["gold_nlg_oz"] is not None  # labelled, never dropped or filled
    assert g.quality_label(None, D("2"), 20, "NLG_FED_H10_MEAN") == "NO_USD_OZ"
    assert g.quality_label(None, None, 0, "NLG_FED_H10_MEAN") == "NO_USD_OZ+NO_FX_OBSERVATIONS"


# --------------------------------------------------------------------------- hard errors
def test_invalid_quote_direction_is_hard_error():
    with pytest.raises(fx.DataIntegrityError):  # header says US$/GUILDER but values are NLG-per-USD sized
        g.parse_fed_file(fed_file("1975-01", "1975-02", header="NETHERLANDS -- SPOT EXCHANGE RATE, US$/GUILDER"), "t")
    with pytest.raises(fx.DataIntegrityError, match="NOT_ASSERTED_FROM_HEADER"):  # no direction text: value range alone is not enough
        g.parse_fed_file(fed_file("1975-01", "1975-02", header="NETHERLANDS -- SPOT EXCHANGE RATE"), "t")
    inverted = fed_file("1975-01", "1975-02").replace(b"2.", b"0.4")
    with pytest.raises(fx.DataIntegrityError):
        g.parse_fed_file(inverted, "t")
    parsed, d = g.parse_fed_file(fed_file("1975-01", "1975-02"), "t")
    assert d["direction"] == "NLG_PER_USD" and d["evidence"] == "TEXT_AND_VALUE_RANGE" and parsed["points"]


def test_ecb_direction_must_be_usd_per_eur():
    with pytest.raises(fx.DataIntegrityError):
        g.parse_ecb_monthly(ecb_monthly(direction=("EUR", "USD")))
    assert len(g.parse_ecb_monthly(ecb_monthly())) == 12


def test_duplicate_dates_are_hard_errors(workbook):
    with pytest.raises(fx.DataIntegrityError, match="DUPLICATE_DATE"):
        g.parse_fed_file(fed_file("1975-01", "1980-12", dup=True), "t")
    a, _ = g.parse_fed_file(fed_file("1975-01", "1975-03"), "a")
    b, _ = g.parse_fed_file(fed_file("1975-03", "1975-04"), "b")  # 1975-03 days appear in both files
    with pytest.raises(fx.DataIntegrityError, match="DUPLICATE_DATE_ACROSS_FILES"):
        g.merge_fed({"a": a, "b": b})
    files = base_files()
    files[g.FED_IDS[0]] = fed_file("1975-01", "1989-12", dup=True)
    with pytest.raises(fx.DataIntegrityError):
        run(workbook, files)


def test_world_bank_structure_failure_is_hard(tmp_path):
    p = tmp_path / "bad.xlsx"
    p.write_bytes(wb_book(skip={"1987-06"}))
    with pytest.raises(fx.DataIntegrityError, match="VALIDATION_FAILED"):
        g.collect(str(p), acquire=make_acquire(base_files()))


def test_source_revision_is_flagged_not_hidden(workbook):
    s, _ = run(workbook, base_files())
    wb = s["sources"][g.WB_ID]
    assert wb["matches_known_workbook_sha256"] is False and wb["matches_known_canonical_series_sha256"] is False
    assert any("WB_WORKBOOK_SHA256_DIFFERS_FROM_KNOWN" in f for f in s["flags"])
    assert any("WB_CANONICAL_SERIES_SHA256_DIFFERS_FROM_KNOWN" in f for f in s["flags"])
    assert s["sources"][g.WB_ID]["sha256"] and s["sources"][g.FED_IDS[0]]["sha256"]


# --------------------------------------------------------------------------- availability semantics
def test_unreachable_core_source_gives_incomplete_with_nulls(workbook):
    s, rows = run(workbook, base_files(), unavailable={g.FED_IDS[1]})
    assert s["status"] == "INCOMPLETE" and g.FED_IDS[1] in [m["source_id"] for m in s["missing_sources"]]
    assert rows["1995-06"]["gold_nlg_oz"] is None and rows["1995-06"]["quality_label"] == "NO_FX_OBSERVATIONS"
    assert rows["1985-06"]["gold_nlg_oz"] is not None


def _patch_fetch(monkeypatch, fn):
    monkeypatch.setattr(hist_02_acquire, "fetch", fn)


def test_main_exit_zero_when_all_sources_unreachable(monkeypatch, tmp_path):
    def boom(sid, **_):
        raise hist_02_acquire.AcquisitionError("NETWORK_TIMEOUT source=x phase=response_headers elapsed_seconds=30.00")
    _patch_fetch(monkeypatch, boom)
    out = tmp_path / "s.json"
    assert g.main(["--summary-out", str(out), "--table-json-out", str(tmp_path / "t.json"), "--table-csv-out", str(tmp_path / "t.csv")]) == 0
    s = json.loads(out.read_text())
    assert s["status"] == "INCOMPLETE" and len(s["missing_sources"]) == len(g.CORE_IDS) + len(g.OPTIONAL_IDS)
    t = json.loads((tmp_path / "t.json").read_text())
    assert len(t["rows"]) == 300 and all(r["gold_nlg_oz"] is None for r in t["rows"])  # nothing invented


def test_main_exit_one_on_real_defect(monkeypatch, tmp_path):
    def junk(sid, **_):
        raw = b"<html>not data</html>"
        return raw, {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0], "sha256": "0" * 64, "bytes": len(raw), "http_status": 200}
    _patch_fetch(monkeypatch, junk)
    out = tmp_path / "s.json"
    assert g.main(["--summary-out", str(out), "--workbook", str(tmp_path / "missing.xlsx")]) == 1
    assert json.loads(out.read_text())["status"] == "FAILED"


def test_main_writes_markers_and_tables(workbook, tmp_path):
    files = base_files()
    s, rows = run(workbook, files)
    g.write_table(rows, {"status": s["status"], "sources": s["sources"]}, tmp_path / "t.json", tmp_path / "t.csv")
    doc = json.loads((tmp_path / "t.json").read_text())
    assert doc["label"] == "research candidate - not approved" and doc["rights_status"] == "UNVERIFIED"
    assert "not approved for publication" in doc["publication_status"]
    assert all(not k.startswith("_") for r in doc["rows"] for k in r)
    assert all(r["rights_status"] == "UNVERIFIED" and "not approved" in r["publication_status"] for r in doc["rows"])
    rd = list(csv.DictReader((tmp_path / "t.csv").open()))
    assert list(rd[0]) == g.CSV_FIELDS and len(rd) == 300
    assert {"period", "usd_oz", "fx_nlg_per_usd", "fx_obs_count", "gold_nlg_oz", "hist_eur_equivalent_oz", "quality_label",
            "outlier_flag", "usd_oz_source_url", "usd_oz_source_sha256", "fx_source_url", "fx_source_sha256"} <= set(rd[0])
    assert "NOT a contemporaneous traded euro price" in doc["field_notes"]["hist_eur_equivalent_oz"]
    assert rd[0]["fx_source_sha256"] and rd[0]["usd_oz_source_sha256"]


# --------------------------------------------------------------------------- outliers
def test_outlier_months_flagged_with_numbers_and_never_corrected(workbook):
    files = base_files()
    files[g.BOE_M] = boe_monthly({"1980-12": D("558.9167"), "1983-07": D("410.75"), "1985-03": D("324.0")})
    s, rows = run(workbook, files)
    assert s["coverage"]["outlier_months_flagged"] == ["1980-12", "1983-07", "1985-03"]
    for m in ("1980-12", "1983-07", "1985-03"):
        r = rows[m]
        assert r["outlier_flag"] == "UNVERIFIED_OUTLIER"
        assert D(r["usd_oz"]) == D(usd_value(m))  # WB value unchanged, not replaced by BoE
        assert r["gold_nlg_oz"] is not None
        assert r["outlier_wb_minus_boe_usd"] is not None and r["outlier_boe_monthly_usd"] is not None
    assert rows["1980-12"]["outlier_wb_minus_boe_usd"] == f"{D(usd_value('1980-12')) - D('558.9167'):.4f}"
    assert rows["1980-11"]["outlier_flag"] is None and rows["1980-11"]["outlier_wb_minus_boe_usd"] is None


# --------------------------------------------------------------------------- transition
def test_transition_numbers_identity_and_boundary(workbook):
    files = base_files()
    files[g.ECB_D] = ecb_daily()
    s, rows = run(workbook, files)
    tm = s["transition"]["monthly_1998_12_to_1999_01"]
    assert tm["status"] == "COMPUTED"
    r98, r99 = rows["1998-12"], rows["1999-01"]
    eq98 = Fraction(r98["hist_eur_equivalent_oz"])
    chg = Fraction(r99["gold_eur_oz"]) / eq98 - 1
    assert abs(D(tm["eur_equivalent_change_pct"]) - D(float(chg * 100)).quantize(D("0.000001"))) <= D("0.000001")
    usd_chg = D(usd_value("1999-01")) / D(usd_value("1998-12")) - 1
    assert tm["wb_usd_change_pct"] == str((usd_chg * 100).quantize(D("0.000001")))
    implied = D("2.20371") / D(r98["fx_nlg_per_usd"])
    assert tm["implied_usd_per_eur_1998_12"] == format(implied.quantize(D("0.00000001")), "f")
    assert D(tm["identity"].split("residual ")[1]) < D("1E-25")
    assert len(s["transition"]["definitional_breaks"]) >= 4
    db = s["transition"]["daily_boundary"]
    assert db["status"] == "COMPUTED" and db["fed_last_day"] == "1998-12-20" and db["ecb_first_day"] == "1999-01-04"
    assert db["calendar_days_between"] == 15 and db["overlap_days"] == 0
    last = fed_value("1998-12", 20)
    jump = D("1.1789") / (D("2.20371") / last) - 1
    assert db["boundary_change_pct"] == str((jump * 100).quantize(D("0.000001")))


def test_transition_not_computable_without_inputs(workbook):
    s, rows = run(workbook, base_files(), unavailable={g.ECB_M})
    assert s["transition"]["monthly_1998_12_to_1999_01"]["status"] == "NOT_COMPUTABLE"
    assert s["status"] == "INCOMPLETE" and rows["1999-01"]["gold_eur_oz"] is None
    assert "transition_daily_boundary" in [a["analysis"] for a in s["analyses_not_performed"]]


# --------------------------------------------------------------------------- Fed vs IMF
def test_fed_vs_imf_stats_and_independence_note():
    months = ["1975-01", "1975-02", "1975-03", "1975-04"]
    fed = {m: {"mean": D("2.0000")} for m in months}
    imf = {"1975-01": D("2.0000"), "1975-02": D("2.0020"), "1975-03": D("1.9900"), "1975-05": D("9")}
    r = g.fed_vs_imf(fed, imf, months)
    assert r["months"] == 3 and r["max_abs_pct"] == "0.500000" and r["worst_months"][0]["month"] == "1975-03"
    assert r["worst_months"][0]["signed_pct"] == "-0.500000" and r["median_abs_pct"] == "0.100000"
    assert "NOT ASSUMED" in r["independence"] and r["unit_check"] == "NLG_PER_USD_BY_COMPARISON"
    assert g.fed_vs_imf(fed, {m: D("0.9") for m in months}, months)["unit_check"] == "MISMATCH_COMPARISON_NOT_RELIABLE"
    assert g.fed_vs_imf({}, imf, months) == {**g.fed_vs_imf({}, imf, months)} and g.fed_vs_imf({}, imf, months)["months"] == 0


def test_parse_imf_single_and_ambiguous_series():
    def xml(n):
        s = "".join(f'<Series COUNTRY="NLD" K="{k}"><Obs TIME_PERIOD="1975-M01" OBS_VALUE="2.4565"/><Obs TIME_PERIOD="1975-M02" OBS_VALUE="2.5"/></Series>' for k in range(n))
        return f"<Root>{s}</Root>".encode()
    monthly, reason = g.parse_imf(xml(1))
    assert reason is None and monthly["1975-01"] == D("2.4565")
    assert g.parse_imf(xml(2)) == (None, "IMF_SERIES_COUNT_2")
    with pytest.raises(fx.DataIntegrityError):
        g.parse_imf(b"<Root><Series><Obs TIME_PERIOD='1975-M01' OBS_VALUE='abc'/></Series></Root>")


# --------------------------------------------------------------------------- product of means vs mean of products
def test_product_sensitivity_numbers_and_common_days_only():
    boe = {date(1980, 1, 2): D(100), date(1980, 1, 3): D(200), date(1980, 1, 4): D(999), date(1980, 2, 1): D(50)}
    fed = {date(1980, 1, 2): D(2), date(1980, 1, 3): D(4), date(1980, 1, 7): D(7), date(1980, 2, 5): D(3)}
    per, st = g.product_sensitivity(boe, fed, {"1980-01": D(150)}, {"1980-01": {"mean": D(3)}}, ["1979-12", "1980-01", "1980-02"])
    assert list(per) == ["1980-01"]  # only months with both series on common days
    assert per["1980-01"]["n_common_days"] == 2 and per["1980-01"]["rel"] == D("-0.1")  # A=150*3=450, B=(200+800)/2=500
    assert st["months"] == 1 and st["product_of_means_vs_mean_of_products"]["max_abs_pct"] == "10.000000"
    assert st["wb_pipeline_vs_mean_of_products"]["months"] == 1  # (150*3-500)/500 = -0.1 as well
    flat_boe = {date(1980, 1, 2): D(10), date(1980, 1, 3): D(10)}
    per2, _ = g.product_sensitivity(flat_boe, fed, {}, {}, ["1980-01"])
    assert per2["1980-01"]["rel"] == 0  # constant gold: no covariance effect


def test_sensitivity_in_rows_does_not_change_values(workbook):
    boe_d = ("DATE,XUDLGPD\n" + "\n".join(f"1980-03-{d:02d},{600 + d}" for d in range(1, 21)) + "\n").encode()
    files = base_files()
    s, rows = run(workbook, files)
    s2, rows2 = run(workbook, {**files, g.BOE_D: boe_d})
    assert rows2["1980-03"]["sens_n_common_days"] == 20 and rows2["1980-03"]["sens_pom_vs_mop_rel"] is not None
    assert rows["1980-03"]["sens_pom_vs_mop_rel"] is None
    assert rows["1980-03"]["gold_nlg_oz"] == rows2["1980-03"]["gold_nlg_oz"]  # sensitivity is not a correction


# --------------------------------------------------------------------------- precision and hygiene
def test_wb_precision_note(workbook):
    s, _ = run(workbook, base_files())
    p = s["wb_precision"]
    assert p["non_integer_count_in_range"] == 0 and p["months"] == 300 and "whole USD" in p["note"]
    assert D(p["max_rel_rounding_bound_pct"]) == (D("0.5") / D(usd_value("1975-01")) * 100).quantize(D("0.000001"))


def test_no_float_arithmetic_in_module_source():
    src = (ROOT / "tools" / "hist_04_gold_nlg.py").read_text()
    assert "float(" not in src


def test_sources_are_registered_https_allowlist():
    for sid in g.CORE_IDS + g.OPTIONAL_IDS:
        url = hist_02_acquire.SOURCES[sid][0]
        assert url.startswith("https://")
        hist_02_acquire.validate_url(sid, url)


def test_workflow_semantics():
    text = (ROOT / ".github" / "workflows" / "hist-04-gold-nlg.yml").read_text()
    assert "continue-on-error" not in text
    assert re.search(r"permissions:\s*\n\s+contents: read", text)
    assert "research/hist-04-gold-fx-consolidated" in text and "workflow_dispatch" in text
    assert "retention-days: 14" in text and "pull_request" not in text
    assert "frontend/public" not in text and "contents: write" not in text
