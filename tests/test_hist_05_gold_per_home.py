"""HIST-05 gold per Dutch home (1995-01..1999-12): offline tests with SYNTHETIC data.

They prove code behaviour only (formula, units, window enforcement, missing-input semantics, exit codes); they say nothing
about real CBS, World Bank, Fed or ECB values. Label of everything: research candidate - not approved.
"""
import csv
import hashlib
import io
import json
import zipfile
from decimal import Decimal
from fractions import Fraction
from xml.sax.saxutils import escape

import pytest

from tools import hist_02_acquire
from tools import hist_04_fx as fx
from tools import hist_04_gold_nlg as g
from tools import hist_05_cbs_kadaster as ck
from tools import hist_05_gold_per_home as h
from tools.hist_02_coverage import month_range

D = Decimal
WINDOW = month_range("1995-01", "1999-12")
HEADER = "NETHERLANDS -- SPOT EXCHANGE RATE, GUILDERS/US$"


# --------------------------------------------------------------------------- synthetic inputs (as in the HIST-04 tests)
def fed_value(m, day):
    i = month_range("1975-01", "1998-12").index(m)
    return D(2) + D(i % 7) / 10 + D(day) / 1000


def fed_file(first, last, days=20, skip_months=()):
    lines = [HEADER, "Noon buying rates in New York"]
    for m in month_range(first, last):
        if m in skip_months:
            continue
        for day in range(1, days + 1):
            lines.append(f" {m}-{day:02d}   {fed_value(m, day):.4f}")
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


def wb_book():
    body = [[f"{m[:4]}M{m[5:]}", 1.0, usd_value(m)] for m in month_range("1974-12", "2000-01")]
    return xlsx([["Title"], ["", "Crude", "Gold"], [None, "($/bbl)", "($/troy oz)"]] + body)


def ecb_monthly():
    lines = ["KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE,OBS_STATUS"]
    for i, m in enumerate(month_range("1999-01", "1999-12")):
        lines.append(f"EXR.M.USD.EUR.SP00.A,M,USD,EUR,{m},{D('1.10') + D(i) / 100},A")
    return ("\n".join(lines) + "\n").encode()


def rec_for(sid, raw):
    return {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0], "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def make_acquire(files, unavailable=()):
    def acquire(sid):
        if sid in unavailable or sid not in files:
            raise fx.SourceUnavailable(sid, "HTTP_404", "synthetic")
        return files[sid], rec_for(sid, files[sid])
    return acquire


def base_files(skip_fed=()):
    return {g.FED_IDS[0]: fed_file("1975-01", "1989-12"), g.FED_IDS[1]: fed_file("1990-01", "1998-12", skip_months=skip_fed),
            g.ECB_M: ecb_monthly()}


@pytest.fixture
def workbook(tmp_path):
    p = tmp_path / "wb.xlsx"
    p.write_bytes(wb_book())
    return str(p)


@pytest.fixture
def synthetic_gold(monkeypatch):
    """Route the HIST-04 collector (used by h.run/h.main) to synthetic files instead of the network."""
    orig = g.collect

    def patched(wb, acquire=None):
        return orig(wb, acquire=make_acquire(base_files()))
    monkeypatch.setattr(g, "collect", patched)


def house_value(m):
    return 90000 + 137 * WINDOW.index(m)


PROPS = {"value": [
    {"Type": "TimeDimension", "Key": "Perioden", "Title": "Perioden"},
    {"Type": "Topic", "Key": "GemiddeldeVerkoopprijs_7", "Title": "Gemiddelde verkoopprijs", "Unit": "euro"},
    {"Type": "Topic", "Key": "PrijsindexVerkoopprijzen_1", "Title": "Prijsindex verkoopprijzen", "Unit": "2020 = 100"},
]}


def props_with(**topic0):
    p = json.loads(json.dumps(PROPS))
    p["value"][1].update(topic0)
    return p


def cbs_data(skip=(), dup=None, bad_value=None):
    rows = []
    for m in WINDOW:
        if m in skip:
            continue
        rows.append({"ID": len(rows), "Perioden": f"{m[:4]}MM{m[5:]}", "GemiddeldeVerkoopprijs_7": house_value(m), "PrijsindexVerkoopprijzen_1": 41.5})
        if m == dup:
            rows.append(dict(rows[-1]))
    if bad_value is not None:
        rows[3]["GemiddeldeVerkoopprijs_7"] = bad_value
    rows.append({"ID": 999, "Perioden": "1995KW01", "GemiddeldeVerkoopprijs_7": 1, "PrijsindexVerkoopprijzen_1": 1})
    rows.append({"ID": 998, "Perioden": "1995JJ00", "GemiddeldeVerkoopprijs_7": 2, "PrijsindexVerkoopprijzen_1": 2})
    return {"value": rows}


def cbs_fetch_for(props=PROPS, data=None, unreachable=()):
    data = cbs_data() if data is None else data
    bodies = {h.CBS_PROPS_ID: json.dumps(props).encode(), h.CBS_DATA_ID: json.dumps(data).encode()}

    def fetch(sid):
        entry = {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0]}
        if sid in unreachable:
            entry.update(status="UNREACHABLE", error="HTTP_STATUS_ERROR synthetic", http_status=500)
            return None, entry
        raw = bodies[sid]
        entry.update(status="FETCHED", http_status=200, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        return raw, entry
    return fetch


def run(workbook, files=None, cbs=None, unavailable=()):
    return h.run(workbook, cbs or cbs_fetch_for(), acquire=make_acquire(files or base_files(), unavailable))


# --------------------------------------------------------------------------- constants and formula
def test_constants_are_exact_decimal_strings():
    assert h.TROY_OZ_G == D("31.1034768") and str(h.TROY_OZ_G) == "31.1034768"
    assert h.NLG_PER_EUR == D("2.20371") and h.NLG_PER_EUR == fx.NLG_PER_EUR == g.NLG_PER_EUR
    assert h.EXPECTED_MONTHS == 60 == len(WINDOW) and (h.WINDOW_START, h.WINDOW_END) == ("1995-01", "1999-12")


def test_formula_exactness_with_decimal():
    house, gold = h.Price(D("100000"), h.EUR, h.HOME), h.Price(D("311.034768"), h.EUR, h.TROY_OZ)
    assert h.grams_per_home(house, gold) == D("10000")  # 100000 x 31.1034768 / 311.034768 exactly
    gold2 = h.Price(D("333.3333"), h.EUR, h.TROY_OZ)
    exp = Fraction(100000) * Fraction("31.1034768") / Fraction("333.3333")
    got = Fraction(h.grams_per_home(house, gold2))
    assert abs(got - exp) / exp < Fraction(1, 10 ** 30)
    assert h.grams_per_home(h.Price(D("1"), h.NLG, h.HOME), h.Price(D("1"), h.NLG, h.TROY_OZ)) == D("31.1034768")


def test_unit_mismatch_is_a_hard_error():
    eur_home = h.Price(D("100000"), h.EUR, h.HOME)
    with pytest.raises(h.UnitMismatchError, match="CURRENCY_MISMATCH"):
        h.grams_per_home(eur_home, h.Price(D("600"), h.NLG, h.TROY_OZ))
    with pytest.raises(h.UnitMismatchError, match="PER_UNIT_MISMATCH"):
        h.grams_per_home(eur_home, h.Price(D("600"), h.EUR, h.HOME))
    with pytest.raises(h.UnitMismatchError, match="PER_UNIT_MISMATCH"):
        h.grams_per_home(h.Price(D("100000"), h.EUR, h.TROY_OZ), h.Price(D("600"), h.EUR, h.TROY_OZ))
    with pytest.raises(h.UnitMismatchError):
        h.grams_per_home(eur_home, D("600"))  # untyped number: no implicit currency
    with pytest.raises(h.UnitMismatchError):
        h.grams_per_home(eur_home, h.Price(D("600"), "USD", h.TROY_OZ))
    with pytest.raises(h.UnitMismatchError, match="NLG_EXPECTED"):
        h.nlg_to_eur(eur_home)
    with pytest.raises(h.UnitMismatchError, match="EUR_EXPECTED"):
        h.eur_to_nlg(h.Price(D("1"), h.NLG, h.HOME))
    assert issubclass(h.UnitMismatchError, fx.DataIntegrityError)  # exit-1 class


def test_mixed_regime_gold_row_is_rejected():
    row = {"regime": "EUR_ECB_MONTHLY", "_gold_eur": D("300"), "_gold_nlg": None}
    with pytest.raises(h.UnitMismatchError, match="REGIME_MISMATCH"):
        h.compute_month("1998-06", D("100000"), row)  # euro-regime row used for an NLG-period month


@pytest.mark.parametrize("bad", [0, -5, D("0"), D("-1"), D("NaN"), D("Infinity"), 1.5, "88991", True])
def test_invalid_house_values_are_hard_errors(bad):
    with pytest.raises(h.InputError, match="INVALID_HOUSE_PRICE"):
        h.normalize_house({"1995-01": bad})


def test_duplicate_and_invalid_periods_are_hard_errors():
    with pytest.raises(h.InputError, match="DUPLICATE_PERIOD 1995-02"):
        h.normalize_house([("1995-01", D("1")), ("1995-02", D("2")), ("1995-02", D("2"))])
    for p in ("1995-1", "95-01", "1995/01", "1995-0a", None, 199501):
        with pytest.raises(h.InputError, match="INVALID_PERIOD"):
            h.normalize_house([(p, D("1"))])


def test_normalize_keeps_missing_missing_and_ignores_outside_window():
    out = h.normalize_house({"1995-01": D("5"), "1994-12": D("7"), "2000-01": D("8"), "1995-02": None})
    assert list(out) == WINDOW and out["1995-01"] == D("5") and out["1995-02"] is None and out["1995-03"] is None


# --------------------------------------------------------------------------- end to end (synthetic)
def test_full_run_exact_60_rows_and_both_routes(workbook):
    s, rows = run(workbook)
    assert s["status"] == "PARTIAL"  # optional HIST-04 sources (ECB daily, IMF, BoE) not supplied -> explicit
    assert {m["source_id"] for m in s["missing_sources"]} == {g.ECB_D, g.IMF_ID, g.BOE_M, g.BOE_D}
    assert [r["period"] for r in rows] == WINDOW and len(rows) == 60
    c = s["coverage"]
    assert c["rows_exactly_60"] and c["months_with_house_price"] == 60 and c["months_with_grams_both_routes"] == 60
    assert c["months_null_output"] == 0 and c["quality_labels"] == {"OK": 60}
    # month 1995-03 recomputed with exact fractions from the synthetic inputs
    r = next(x for x in rows if x["period"] == "1995-03")
    fed = sum(Fraction(fed_value("1995-03", d)) for d in range(1, 21)) / 20
    gold_nlg = Fraction(usd_value("1995-03")) * fed
    exp_eur = Fraction(house_value("1995-03")) * Fraction("31.1034768") / (gold_nlg / Fraction("2.20371"))
    assert abs(Fraction(D(r["grams_per_home_eur_route"])) - exp_eur) <= Fraction(1, 20000)
    assert r["gold_price_local_currency_code"] == "NLG" and r["fx_applied_unit"].startswith("NLG per USD")
    assert r["house_price_nlg_equiv"] == format(D(house_value("1995-03")) * D("2.20371"), "f")
    assert r["fx_nlg_per_eur_fixed"] == "2.20371" and r["fx_obs_count"] == 20 and r["cbs_status"] == "CBS_OBSERVED"
    assert s["checks"]["independent_recompute"]["pass"] and s["checks"]["independent_recompute"]["values_checked"] == 120


def test_nlg_and_eur_routes_agree_within_stated_tolerance(workbook):
    s, rows = run(workbook)
    rd = s["route_discrepancy"]
    assert rd["months_compared"] == 60 and rd["within_tolerance"] is True
    assert D(rd["max_abs_rel_full_precision"]) <= h.ROUTE_TOLERANCE
    for r in rows:
        assert abs(D(r["route_discrepancy_rel"])) <= h.ROUTE_TOLERANCE
        # 4-decimal display values never differ by more than one unit of the 4th decimal
        assert abs(D(r["grams_per_home_nlg_route"]) - D(r["grams_per_home_eur_route"])) <= D("0.0001")
    assert D(rd["max_abs_diff_4dp_grams"]) <= D("0.0001") and rd["months_4dp_differ_count"] == len(rd["months_where_4dp_values_differ"])


def test_1999_uses_ecb_and_derived_nlg_gold_and_1998_uses_eur_equivalent(workbook):
    s, rows = run(workbook)
    by = {r["period"]: r for r in rows}
    r99, r98 = by["1999-03"], by["1998-12"]
    ecb = D("1.10") + D(2) / 100
    gold_eur = D(usd_value("1999-03")) / ecb
    assert r99["gold_price_local_currency_code"] == "EUR" and r99["fx_applied"] == str(ecb) and r99["fx_applied_unit"].startswith("USD per EUR")
    assert D(r99["gold_eur_equiv_per_oz"]) == gold_eur.quantize(D("0.0001"))
    assert D(r99["gold_nlg_per_oz"]) == (gold_eur * D("2.20371")).quantize(D("0.0001"))
    assert r99["fx_obs_count"] is None
    assert r98["gold_price_local_currency_code"] == "NLG"
    assert abs(D(r98["gold_eur_equiv_per_oz"]) * D("2.20371") - D(r98["gold_nlg_per_oz"])) < D("0.001")


def test_transition_step_decomposition(workbook):
    s, _ = run(workbook)
    t = s["transition_1998_12_to_1999_01"]
    assert t["status"] == "COMPUTED"
    step = (1 + D(t["house_price_step_pct"]) / 100) / (1 + D(t["gold_eur_step_pct"]) / 100) - 1
    assert abs(step * 100 - D(t["grams_step_pct"])) < D("0.0001")
    assert t["larger_component"] in ("house price", "gold (EUR terms)")
    assert "wb_usd_step_pct" in t["gold_components"] and "residual" in t["identity"]


def test_summary_results_and_development(workbook):
    s, rows = run(workbook)
    ex, y = s["results"]["extremes"], s["results"]["yearly"]
    assert ex["first"]["period"] == "1995-01" and ex["last"]["period"] == "1999-12"
    assert set(y) == {"1995", "1996", "1997", "1998", "1999"} and all(v["months_with_value"] == 12 and v["complete_year"] for v in y.values())
    dev = s["results"]["development_1995_to_1999"]["mean_1995_to_mean_1999"]
    a, b = D(y["1995"]["mean_grams_per_home_eur_route"]), D(y["1999"]["mean_grams_per_home_eur_route"])
    assert abs((b / a - 1) * 100 - D(dev["change_pct"])) < D("0.00001") and dev["complete_years"] is True
    grams = [D(r["grams_per_home_eur_route"]) for r in rows]
    assert D(ex["min"]["grams_per_home_eur_route"]) == min(grams) and D(ex["max"]["grams_per_home_eur_route"]) == max(grams)


def test_status_fields_and_source_refs_on_every_row(workbook):
    s, rows = run(workbook)
    for r in rows:
        assert r["methodology"] == "research candidate - not approved" and r["rights_status"] == "UNVERIFIED"
        assert r["publication_status"].startswith("NOT APPROVED")
        assert len(r["house_source_sha256"]) == 64 and r["house_source_url"].startswith("https://opendata.cbs.nl/")
        assert len(r["usd_oz_source_sha256"]) == 64 and r["fx_source_sha256"] and r["fx_source_url"]
    assert s["publication_authorized"] is False and s["source_approved"] is False
    assert s["cbs"]["measure_key"] == "GemiddeldeVerkoopprijs_7" and s["cbs"]["measure_key_matches_documented"] is True
    assert s["cbs"]["measure_unit"] == "euro" and s["cbs"]["sources"][h.CBS_DATA_ID]["sha256"]


def test_outlier_flag_list_is_carried_and_none_in_window(workbook):
    s, rows = run(workbook)
    o = s["outliers"]
    assert o["carried_flag_list_unverified_outlier"] == ["1980-12", "1983-07", "1985-03"] and o["flagged_months_inside_window"] == []
    assert all(r["outlier_flag"] is None for r in rows)


def test_definition_breaks_are_documented(workbook):
    s, _ = run(workbook)
    text = " ".join(s["breaks"])
    for needle in ("Fed H.10", "ECB", "retrospective euro", "whole USD", "2.20371"):
        assert needle in text


# --------------------------------------------------------------------------- missing inputs: null, never filled
def test_missing_cbs_month_gives_null_and_incomplete_label_not_filled(workbook):
    s, rows = run(workbook, cbs=cbs_fetch_for(data=cbs_data(skip={"1996-07"})))
    by = {r["period"]: r for r in rows}
    r = by["1996-07"]
    assert len(rows) == 60 and r["house_price_eur"] is None and r["grams_per_home_eur_route"] is None and r["grams_per_home_nlg_route"] is None
    assert r["quality_label"] == "INCOMPLETE:NO_HOUSE_PRICE" and r["cbs_status"] == "CBS_MISSING" and r["route_discrepancy_rel"] is None
    assert by["1996-06"]["grams_per_home_eur_route"] is not None and by["1996-08"]["grams_per_home_eur_route"] is not None
    assert s["status"] == "INCOMPLETE" and s["coverage"]["months_null_output"] == 1 and s["coverage"]["months_with_house_price"] == 59
    assert s["cbs_fixture_crosscheck"]["status"] in ("DIFFERENCES_OR_GAPS", "NOT_PERFORMED_NO_CBS_VALUES")


def test_missing_fed_month_gives_null_gold_and_incomplete(workbook):
    s, rows = run(workbook, files=base_files(skip_fed={"1997-05"}))
    r = next(x for x in rows if x["period"] == "1997-05")
    assert r["grams_per_home_eur_route"] is None and r["gold_nlg_per_oz"] is None and r["fx_applied"] is None
    assert r["quality_label"] == "INCOMPLETE:NO_FX_OBSERVATIONS" and s["status"] == "INCOMPLETE"
    assert r["house_price_eur"] is not None  # the available input stays visible, nothing is derived from it


def test_missing_ecb_1999_gives_null_for_1999_only(workbook):
    s, rows = run(workbook, unavailable={g.ECB_M})
    assert s["status"] == "INCOMPLETE" and g.ECB_M in {m["source_id"] for m in s["missing_sources"]}
    assert all(r["grams_per_home_eur_route"] is None for r in rows if r["period"] >= "1999-01")
    assert all(r["grams_per_home_eur_route"] is not None for r in rows if r["period"] <= "1998-12")


def test_duplicate_cbs_period_is_a_hard_error(workbook):
    with pytest.raises(h.InputError, match="DUPLICATE_PERIOD"):
        run(workbook, cbs=cbs_fetch_for(data=cbs_data(dup="1996-02")))


def test_cbs_unit_not_euro_is_a_hard_unit_error(workbook):
    with pytest.raises(h.UnitMismatchError, match="UNIT_NOT_EURO"):
        run(workbook, cbs=cbs_fetch_for(props=props_with(Unit="gulden")))


def test_cbs_index_is_never_taken_as_level(workbook):
    props = props_with(Title="Prijsindex verkoopprijzen", Unit="2020 = 100")  # no average price level measure left
    with pytest.raises(h.InputError, match="AMBIGUOUS_OR_MISSING_AVERAGE_PRICE_MEASURE"):
        run(workbook, cbs=cbs_fetch_for(props=props))


def test_cbs_invalid_value_is_a_hard_error(workbook):
    with pytest.raises(h.InputError):
        run(workbook, cbs=cbs_fetch_for(data=cbs_data(bad_value="88991")))
    with pytest.raises(h.InputError, match="INVALID_HOUSE_PRICE"):
        run(workbook, cbs=cbs_fetch_for(data=cbs_data(bad_value=-1)))


# --------------------------------------------------------------------------- window acceptance
def test_validate_table_enforces_exactly_60_consecutive_unique_rows(workbook):
    rows = run(workbook)[1]
    assert h.validate_table(rows) is True
    with pytest.raises(h.InputError, match="ROW_COUNT_59"):
        h.validate_table(rows[:-1])
    with pytest.raises(h.InputError, match="ROW_COUNT_61"):
        h.validate_table(rows + [dict(rows[-1])])
    dup = rows[:59] + [dict(rows[58])]
    with pytest.raises(h.InputError, match="DUPLICATE_PERIODS"):
        h.validate_table(dup)
    swapped = [rows[1], rows[0]] + rows[2:]
    with pytest.raises(h.InputError, match="NOT_CONSECUTIVE"):
        h.validate_table(swapped)
    bad = [dict(r) for r in rows]
    bad[5]["grams_per_home_eur_route"], bad[5]["quality_label"] = None, "OK"
    with pytest.raises(h.InputError, match="NULL_WITHOUT_INCOMPLETE_LABEL"):
        h.validate_table(bad)
    bad = [dict(r) for r in rows]
    bad[0]["rights_status"] = "CLEARED"
    with pytest.raises(h.InputError, match="STATUS_FIELDS_MISSING"):
        h.validate_table(bad)


def test_build_table_always_yields_60_rows_even_without_inputs():
    rows, calc = h.build_table({}, {})
    assert len(rows) == 60 and all(r["quality_label"].startswith("INCOMPLETE:") for r in rows)
    assert all(r["grams_per_home_eur_route"] is None and r["house_price_eur"] is None for r in rows)
    assert h.coverage(rows, calc)["months_null_output"] == 60


# --------------------------------------------------------------------------- fixture cross-check (offline, real pinned fixture)
def test_pinned_fixture_has_exactly_the_60_window_months():
    fixture = ck.load_fixture(h.FIXTURE_PATH)
    assert sorted(m for m in fixture if m in WINDOW) == WINDOW and len(fixture) == 60
    assert all(v > 0 for v in fixture.values())


def test_fixture_crosscheck_equal_and_difference_detection():
    fixture = ck.load_fixture(h.FIXTURE_PATH)
    house = h.normalize_house(dict(fixture))
    assert h.fixture_crosscheck(house)["status"] == "EQUAL_60_OF_60"
    changed = dict(house)
    changed["1997-06"] += 1
    res = h.fixture_crosscheck(changed)
    assert res["status"] == "DIFFERENCES_OR_GAPS" and res["different"][0]["period"] == "1997-06"
    gap = dict(house)
    gap["1997-07"] = None
    assert h.fixture_crosscheck(gap)["not_comparable_months"] == ["1997-07"]
    assert h.fixture_crosscheck(h.normalize_house({}))["status"] == "NOT_PERFORMED_NO_CBS_VALUES"


# --------------------------------------------------------------------------- main / exit semantics
def test_main_writes_tables_and_summary(workbook, tmp_path, synthetic_gold):
    rc = h.main(["--summary-out", str(tmp_path / "s.json"), "--table-json-out", str(tmp_path / "t.json"),
                 "--table-csv-out", str(tmp_path / "t.csv"), "--workbook", workbook], cbs_fetch=cbs_fetch_for())
    assert rc == 0
    t = json.loads((tmp_path / "t.json").read_text())
    assert t["methodology"] == "research candidate - not approved" and t["rights_status"] == "UNVERIFIED"
    assert t["publication_status"].startswith("NOT APPROVED") and len(t["rows"]) == 60
    rd = list(csv.DictReader((tmp_path / "t.csv").open()))
    assert list(rd[0]) == h.CSV_FIELDS and len(rd) == 60
    assert all(not k.startswith("_") for r in t["rows"] for k in r)
    assert json.loads((tmp_path / "s.json").read_text())["status"] == "PARTIAL"


def test_main_exit_zero_when_all_sources_unreachable(monkeypatch, tmp_path):
    def boom(sid, **_):
        raise hist_02_acquire.AcquisitionError("NETWORK_TIMEOUT source=x phase=response_headers elapsed_seconds=30.00")
    monkeypatch.setattr(hist_02_acquire, "fetch", boom)
    out = tmp_path / "s.json"
    assert h.main(["--summary-out", str(out), "--table-json-out", str(tmp_path / "t.json"), "--table-csv-out", str(tmp_path / "t.csv")]) == 0
    s = json.loads(out.read_text())
    ids = {m["source_id"] for m in s["missing_sources"]}
    assert s["status"] == "INCOMPLETE" and set(h.CBS_ONLY_IDS) <= ids and set(g.CORE_IDS) <= ids
    t = json.loads((tmp_path / "t.json").read_text())
    assert len(t["rows"]) == 60 and all(r["grams_per_home_eur_route"] is None and r["house_price_eur"] is None for r in t["rows"])
    assert all(r["quality_label"].startswith("INCOMPLETE:") for r in t["rows"])


def test_main_exit_zero_when_only_cbs_unreachable(workbook, tmp_path, synthetic_gold):
    out = tmp_path / "s.json"
    rc = h.main(["--summary-out", str(out), "--table-json-out", str(tmp_path / "t.json"), "--workbook", workbook],
                cbs_fetch=cbs_fetch_for(unreachable={h.CBS_DATA_ID}))
    s = json.loads(out.read_text())
    assert rc == 0 and s["status"] == "INCOMPLETE" and h.CBS_DATA_ID in {m["source_id"] for m in s["missing_sources"]}
    t = json.loads((tmp_path / "t.json").read_text())
    assert all(r["house_price_eur"] is None and r["grams_per_home_eur_route"] is None for r in t["rows"])
    assert all(r["gold_nlg_per_oz"] is not None for r in t["rows"])  # gold part still computed, house part not invented


def test_main_exit_one_on_real_defect(monkeypatch, tmp_path):
    def junk(sid, **_):
        raw = b"<html>not data</html>"
        return raw, {"source_id": sid, "url": hist_02_acquire.SOURCES[sid][0], "sha256": "0" * 64, "bytes": len(raw), "http_status": 200}
    monkeypatch.setattr(hist_02_acquire, "fetch", junk)
    out = tmp_path / "s.json"
    assert h.main(["--summary-out", str(out), "--workbook", str(tmp_path / "missing.xlsx")]) == 1
    assert json.loads(out.read_text())["status"] == "FAILED"


def test_main_exit_one_on_unit_mismatch_in_cbs(workbook, tmp_path, synthetic_gold):
    rc = h.main(["--summary-out", str(tmp_path / "s.json"), "--workbook", workbook], cbs_fetch=cbs_fetch_for(props=props_with(Unit="gulden")))
    assert rc == 1 and "UNIT_NOT_EURO" in json.loads((tmp_path / "s.json").read_text())["error"]


def test_tool_does_not_name_repository_data_paths():
    src = open(h.__file__, encoding="utf-8").read()
    assert "frontend/public" not in src and "monthly.json" not in src and "cbs-housing.csv" not in src
