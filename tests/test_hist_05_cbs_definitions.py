"""HIST-05 CBS definitions probe: offline tests with SYNTHETIC fixtures (prove parser code only, no CBS facts)."""
import json
from decimal import Decimal

import pytest

from tools import hist_02_acquire
from tools import hist_05_cbs_definitions as m

D = Decimal


def test_candidates_registered_exact_https():
    assert len(m.CANDIDATES) >= 60
    for sid, (url, _, _) in m.CANDIDATES.items():
        assert url.startswith("https://") and hist_02_acquire.SOURCES[sid][0] == url
        hist_02_acquire.validate_url(sid, url)
    with pytest.raises(hist_02_acquire.AcquisitionError):
        hist_02_acquire.validate_url("def3-85773NED-info", "https://example.org/x")


# ---- table info
def test_table_info_v3_fields_and_missing_are_not_retrieved():
    info = m.parse_table_info({"value": [{"Title": "T", "Period": "1995 - 2026", "Summary": " ", "Modified": "2026-09-01T00:00:00", "Description": "x" * 12000}]})
    f = info["fields"]
    assert f["Title"] == {"status": "OFFICIAL_CONFIRMED", "value": "T"}
    assert f["Summary"]["status"] == "NOT_RETRIEVED" and f["Summary"]["value"] is None
    assert f["ReleaseDate"]["status"] == "NOT_RETRIEVED" and f["Source"]["status"] == "NOT_RETRIEVED"
    assert len(f["Description"]["value"]) == 9000
    assert info["retrieved"] == 4


def test_table_info_v4_single_object():
    info = m.parse_table_info({"Identifier": "85773NED", "Title": "T", "Modified": "2026-09-01"})
    assert info["fields"]["Modified"]["value"] == "2026-09-01" and info["retrieved"] == 2


@pytest.mark.parametrize("doc,msg", [
    ([], "NOT_AN_OBJECT"), ({"value": []}, "EMPTY_TABLEINFOS"), ({"value": ["x"]}, "EMPTY_TABLEINFOS"),
    ({"foo": 1}, "MISSING_VALUE_ARRAY"), ({"value": [{"Title": {"a": 1}}]}, "INVALID_FIELD_TYPE Title"),
    ({"value": [{"Description": [1]}]}, "INVALID_FIELD_TYPE Description"), ({"value": [{"Title": True}]}, "INVALID_FIELD_TYPE Title")])
def test_table_info_malformed_fails_closed(doc, msg):
    with pytest.raises(m.Hist05DefError, match=msg):
        m.parse_table_info(doc)


# ---- units
@pytest.mark.parametrize("unit,cur,kind,scale", [
    ("euro", "EUR", "MONEY", "unit"), ("mln euro", "EUR", "MONEY", "million"), ("gulden", "NLG", "MONEY", "unit"),
    ("2020 = 100", None, "INDEX", "unit"), ("%", None, "PERCENT", "unit"), ("aantal", None, "COUNT", "unit")])
def test_parse_unit(unit, cur, kind, scale):
    u = m.parse_unit(unit)
    assert (u["status"], u["currency"], u["kind"], u["scale"]) == ("OFFICIAL_CONFIRMED", cur, kind, scale)


def test_parse_unit_missing_and_unknown_never_guessed():
    assert m.parse_unit(None)["status"] == "NOT_RETRIEVED" and m.parse_unit("  ")["status"] == "NOT_RETRIEVED"
    u = m.parse_unit("kilo gram")
    assert u["status"] == "UNRECOGNISED" and u["currency"] is None


PROPS = {"value": [
    {"Type": "TimeDimension", "Key": "Perioden", "Title": "Perioden"},
    {"Type": "Topic", "Key": "P1", "Title": "Gemiddelde verkoopprijs", "Unit": "euro", "Description": "Som / aantal", "Decimals": 0},
    {"Type": "Topic", "Key": "I2", "Title": "Prijsindex bestaande koopwoningen", "Unit": "2020 = 100"},
    {"Type": "TopicGroup", "Key": "G", "Title": "Groep"}]}


def test_property_details():
    det = m.parse_property_details(PROPS)
    assert set(det) == {"P1", "I2"}
    assert det["P1"]["unit_parsed"]["currency"] == "EUR" and det["P1"]["decimals"] == "0"
    assert det["P1"]["description"]["status"] == "OFFICIAL_CONFIRMED"
    assert det["I2"]["description"] == {"status": "NOT_RETRIEVED", "value": None} and det["I2"]["decimals"] is None


@pytest.mark.parametrize("doc,msg", [
    ({}, "MISSING_VALUE_ARRAY"), ({"value": ["x"]}, "PROPERTY_NOT_OBJECT"), ({"value": []}, "NO_TOPICS"),
    ({"value": [{"Type": "Topic", "Key": "A", "Decimals": [1]}]}, "INVALID_FIELD_TYPE Decimals")])
def test_property_details_malformed(doc, msg):
    with pytest.raises(m.Hist05DefError, match=msg):
        m.parse_property_details(doc)


# ---- perioden status
def test_perioden_status_counts():
    r = m.parse_perioden_status({"value": [{"Key": "1995MM01", "Status": "Definitief"}, {"Key": "2026MM08", "Status": "Voorlopig"},
                                           {"Key": "2026MM09", "Status": ""}]})
    assert r["status_counts"] == {"Definitief": 1, "Voorlopig": 1, "NOT_RETRIEVED": 1}
    assert r["non_final_periods_head"] == ["2026MM08"] and r["status_field"] == "OFFICIAL_CONFIRMED"


def test_perioden_without_status_field_is_not_retrieved():
    r = m.parse_perioden_status({"value": [{"Key": "1995MM01"}, {"Key": "1995MM02"}]})
    assert r["status_field"] == "NOT_RETRIEVED" and r["non_final_count"] == 0


@pytest.mark.parametrize("doc,msg", [({"value": "x"}, "MISSING_VALUE_ARRAY"), ({"value": [1]}, "PERIOD_ROW_NOT_OBJECT"),
                                     ({"value": [{"Status": {"a": 1}}]}, "INVALID_FIELD_TYPE Status")])
def test_perioden_malformed(doc, msg):
    with pytest.raises(m.Hist05DefError, match=msg):
        m.parse_perioden_status(doc)


# ---- fact extraction
CORPUS = {
    "a": "De prijsindex is gebaseerd op de verkoopprijzen van bestaande koopwoningen van het Kadaster. Dit is een zin zonder bijzonderheden erin.",
    "b": "De ontwikkeling van de gemiddelde verkoopprijs is geen indicator voor de prijsontwikkeling van bestaande koopwoningen. SPAR staat voor Sale Price Appraisal Ratio en wordt gebruikt.",
}


def test_extract_facts_confirmed_and_not_retrieved():
    f = m.extract_facts(CORPUS)
    assert f["existing_dwellings_scope"]["status"] == "OFFICIAL_CONFIRMED" and len(f["existing_dwellings_scope"]["quotes"]) == 2
    assert f["source_kadaster"]["quotes"][0]["source"] == "a"
    assert f["spar_method"]["status"] == "OFFICIAL_CONFIRMED"
    assert f["average_not_price_development"]["status"] == "OFFICIAL_CONFIRMED"
    assert f["guilder_or_conversion"] == {"status": "NOT_RETRIEVED", "quotes": [], "sources_with_text": 2}
    assert f["asking_price_mention"]["status"] == "NOT_RETRIEVED"


def test_extract_facts_empty_corpus_is_all_not_retrieved():
    f = m.extract_facts({})
    assert all(v["status"] == "NOT_RETRIEVED" and v["quotes"] == [] for v in f.values())


def test_guilder_sentence_detected_only_when_present():
    f = m.extract_facts({"x": "Bedragen vóór 2002 zijn omgerekend van guldens naar euro tegen de vaste koers van 2,20371 gulden."})
    assert f["guilder_or_conversion"]["status"] == "OFFICIAL_CONFIRMED"


def test_rights_quotes_and_level():
    text = "Welkom op onze site en veel plezier. Hergebruik is toegestaan, mits CBS als bron wordt vermeld. Meer weten? Bel ons."
    assert m.rights_level(text) == "OFFICIAL_TEXT_READ" and m.rights_quotes(text)[0].startswith("Hergebruik is toegestaan")
    assert m.rights_level("") == "NOT_RETRIEVED" and m.rights_level("Geen relevante inhoud op deze pagina hier.") == "NOT_RETRIEVED"


# ---- numeric analyses
def months(first, n):
    y, mo = int(first[:4]), int(first[5:])
    return [f"{y + (mo - 1 + i) // 12}-{(mo - 1 + i) % 12 + 1:02d}" for i in range(n)]


def test_mom_changes_do_not_bridge_gaps():
    s = {"1995-01": D(100), "1995-02": D(110), "1995-04": D(121)}
    assert list(m.mom_changes(s)) == ["1995-02"] and m.mom_changes(s)["1995-02"] == D(10)


def test_compare_mom_ignores_index_base():
    ms = months("1995-01", 12)
    a = {k: D(100) + i for i, k in enumerate(ms)}
    b = {k: v * 2 for k, v in a.items()}  # other base: identical mom
    r = m.compare_mom(a, b, "1995-02", "1995-12")
    assert r["common_months"] == 11 and D(r["max_abs_diff_pp"]) == 0 and r["label"] == "DERIVED"
    assert m.compare_mom(a, {}, "1995-02", "1995-12") == {"common_months": 0}


def test_guilder_numbers_reports_counts_only():
    # 100 * 2.20371 = 220.371 is not near a multiple of 100 NLG; 45378 EUR ~ 100000.0 NLG (45378 * 2.20371 = 100,000.1)
    r = m.guilder_numbers({"1995-01": D(45378), "1995-02": D(50000)})
    assert r["label"] == "DERIVED_NOT_CONCLUSIVE" and r["by_step"]["1000"]["within_tolerance"] == 1
    assert r["by_step"]["1"]["within_tolerance"] == 2 and r["observations"] == 2
    assert m.guilder_numbers({}) == {"observations": 0}


def test_core_analysis_and_revision_comparison():
    ms = months("1995-01", 60)
    data = {"value": [{"Perioden": f"{k[:4]}MM{k[5:]}", "P1": 90000 + 100 * i, "I2": 40.5 + i * 0.5} for i, k in enumerate(ms)]}
    props = {"value": PROPS["value"][:3]}
    c = m.analyse_core("T", props, data)
    assert c["price_key"] == "P1" and c["index_keys"] == ["I2"] and len(c["price"]) == 60
    fixture = {k: D(90000 + 100 * i) for i, k in enumerate(ms)}
    rev = m.revision_comparison({"T1": c, "T2": c}, fixture)
    assert rev["fixture_vs_T1_price"]["exact_equal"] == 60 and rev["T1_vs_T2_price"]["common_periods"] == 60
    assert rev["T1_vs_T2_index_mom"]["common_months"] == 59
    changed = dict(fixture, **{"1997-05": D(1)})
    assert m.revision_comparison({"T1": c}, changed)["fixture_vs_T1_price"]["exact_equal"] == 59


def test_core_analysis_duplicate_period_is_a_defect():
    data = {"value": [{"Perioden": "1995MM01", "P1": 1, "I2": 1}, {"Perioden": "1995MM01", "P1": 2, "I2": 2}]}
    with pytest.raises(m.Hist05Error, match="DUPLICATE_PERIOD"):
        m.analyse_core("T", {"value": PROPS["value"][:3]}, data)


def test_core_analysis_invalid_numeric_is_a_defect():
    data = {"value": [{"Perioden": "1995MM01", "P1": "abc", "I2": 1}]}
    with pytest.raises(m.Hist05Error, match="INVALID_NUMERIC"):
        m.analyse_core("T", {"value": PROPS["value"][:3]}, data)


def test_core_analysis_missing_values_stay_none():
    data = {"value": [{"Perioden": "1995MM01", "P1": None, "I2": 1}, {"Perioden": "1995MM02", "P1": 5, "I2": 2}]}
    c = m.analyse_core("T", {"value": PROPS["value"][:3]}, data)
    assert c["price"]["1995-01"] is None and c["price"]["1995-02"] == D(5)


def test_break_statistics_boundary():
    ms = months("1999-01", 24)
    s = {k: D(100) * (D("1.01") ** i) for i, k in enumerate(ms)}
    b = m.break_statistics({"T": {"price": s, "index": {}}})
    assert b["T_price_boundary_1999-12_2000-01"]["status"] == "COMPUTED"
    assert D(b["T_price_boundary_1999-12_2000-01"]["boundary_change_pct"]) == D("1.000")


def test_catalog_info_rows_defaults_not_retrieved():
    rows = m.catalog_info_rows({"value": [{"Identifier": "85773NED", "Title": "T", "Modified": "2026-09-01"}, {"Title": "no id"}]})
    assert len(rows) == 1 and rows[0]["release_date"] == "NOT_RETRIEVED" and rows[0]["status"] == "NOT_RETRIEVED"
    with pytest.raises(m.Hist05DefError):
        m.catalog_info_rows({"nope": 1})


def test_report_lines_render_minimal_summary():
    s = {"facts": m.extract_facts(CORPUS), "table_metadata": {"T": m.parse_table_info({"value": [{"Title": "T"}]})},
         "measure_details": {"T": m.parse_property_details(PROPS)}, "perioden_status": {}, "catalog_entries_of_known_tables": {},
         "catalog_title_hits": [], "revision_comparison": {}, "weighted_annual_check": {}, "pdf_tables": {}, "break_statistics": {}, "guilder_numbers_derived": {}, "price_keys": {},
         "index_keys": {}, "rights": {}, "results": [], "findings": [], "missing_sources": [], "defects": [],
         "description_excerpts": {"T": ["x"]}, "method_history": {}, "kadaster_excerpts": {}, "kadaster_page_rights_quotes": {}, "rights_windows": {}}
    lines = m.report_lines(s)
    assert any(l.startswith("FACT guilder_or_conversion NOT_RETRIEVED") for l in lines)
    json.dumps(lines)


def test_focus_sentences_and_window():
    text = "Eerste zin zonder inhoud hier voor de test. De gemiddelde verkoopprijs is een gemiddelde. Nog een lange neutrale zin hier."
    assert m.focus_sentences(text, r"verkoopprijs") == ["De gemiddelde verkoopprijs is een gemiddelde."]
    assert m.focus_sentences("", r"x") == []
    assert m.window_after("a TERMS b TERMS c", "TERMS", 7, occurrence=-1) == "TERMS c"
    assert m.window_after("a TERMS b TERMS c", "TERMS", 7) == "TERMS b"
    assert m.window_after("a TERMS b", "ABSENT") == ""


class _Hdr(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def test_probe_redirect_reports_location_only_and_respects_allowlist():
    from urllib.error import HTTPError
    sid = "bis-terms-statistics"

    def opener(req, timeout=None):
        raise HTTPError(req.full_url, 301, "moved", _Hdr(Location="https://www.bis.org/other"), None)
    assert m.probe_redirect(sid, opener) == {"http": 301, "location": "https://www.bis.org/other"}

    def refuse(req, timeout=None):
        raise OSError("boom")
    assert m.probe_redirect(sid, refuse) == {"http": None, "error": "OSError"}
    with pytest.raises(KeyError):
        m.probe_redirect("not-registered", opener)


def test_weighted_annual_check_and_skips_incomplete_years():
    ms = months("1995-01", 12) + months("1996-01", 11)  # 1996 incomplete: December missing
    price = {k: D(100000 + 1000 * i) for i, k in enumerate(ms)}
    count = {k: D(10 + i) for i, k in enumerate(ms)}
    n = sum(count[k] for k in ms[:12])
    w = sum(price[k] * count[k] for k in ms[:12]) / n
    core = {"T": {"price": price, "count": count, "price_annual": {"1995": w.quantize(D("1")), "1996": D(1)}}}
    r = m.weighted_annual_check(core, range(1995, 1997))["T"]
    assert set(r) == {"1995"} and abs(D(r["1995"]["diff"])) <= D("0.5") and r["1995"]["label"] == "DERIVED"
    assert m.weighted_annual_check({"T": {"price": price}}) == {}


def test_core_analysis_picks_count_and_annual():
    props = {"value": PROPS["value"][:3] + [{"Type": "Topic", "Key": "N", "Title": "Aantal verkochte woningen", "Unit": "aantal"}]}
    data = {"value": [{"Perioden": "1995MM01", "P1": 5, "I2": 1, "N": 7}, {"Perioden": "1995JJ00", "P1": 6, "I2": 1, "N": 70}]}
    c = m.analyse_core("T", props, data)
    assert c["count"]["1995-01"] == D(7) and c["price_annual"]["1995"] == D(6)


def test_pdf_year_rows_only_exact_three_column_rows():
    text = "Jaar  aantal  prijs\n 1995      154.568      93.750\n1996  1.2 3\n 1999   199.000   123.456  \ntekst 2000 1 2 3\n"
    assert m.pdf_year_rows(text) == [{"year": "1995", "col_a": "154.568", "col_b": "93.750"}, {"year": "1999", "col_a": "199.000", "col_b": "123.456"}]
