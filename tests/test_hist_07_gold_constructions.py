"""Offline synthetic tests for tools.hist_07_gold_constructions (prove code behaviour only, no real data)."""
import json
from decimal import Decimal as D
from fractions import Fraction

import pytest

from tools import hist_07_gold_constructions as g

RATE = Fraction(220371, 100000)


def q(v, num, den, tag="OBSERVED"):
    return g.Quote(D(v), num, den, tag)


def test_constants_exact():
    assert g.NLG_PER_EUR == D("2.20371")
    assert g.GRAMS_PER_OZ == D("31.1034768")


def test_c1_c3_formula_matches_independent_fraction_implementation():
    usd = {"1990-01": D("410.5"), "1990-02": D("415"), "1990-03": D("368.25")}
    nlg = {"1990-01": D("1.9073"), "1990-02": D("1.8812"), "1990-03": D("1.8001")}
    months = list(usd)
    c1q, miss = g.c1(usd, nlg, months)
    c3q = g.c3(c1q)
    assert miss == []
    for m in months:
        ref1 = Fraction(usd[m]) * Fraction(nlg[m])
        ref3 = ref1 / RATE
        assert abs(Fraction(c1q[m].value) - ref1) / ref1 < Fraction(1, 10 ** 30)
        assert abs(Fraction(c3q[m].value) - ref3) / ref3 < Fraction(1, 10 ** 30)
        assert (c3q[m].num, c3q[m].den, c3q[m].tag) == ("EUR", "oz", "REDENOMINATED")


def test_c4_matches_independent_formula_and_c3_equals_c4_when_fx_is_fixed_cross():
    usd = {"1999-01": D("287"), "1999-02": D("287.3")}
    eur = {"1999-01": D("1.16078"), "1999-02": D("1.11")}
    months = list(usd)
    c4q, miss = g.c4(usd, eur, months)
    assert miss == []
    for m in months:
        assert abs(Fraction(c4q[m].value) - Fraction(usd[m]) / Fraction(eur[m])) < Fraction(1, 10 ** 28)
    nlg = {m: g.nlg_per_usd_from_usd_per_eur(g.Quote(eur[m], "USD", "EUR")).value for m in months}
    c3q = g.c3(g.c1(usd, nlg, months)[0])
    devs, _ = g.overlap_compare(c3q, c4q, months)
    assert all(abs(v) < D("1E-25") for v in devs.values())


def test_missing_months_stay_missing_no_fill():
    usd = {"1990-01": D("400"), "1990-02": D("401"), "1990-03": D("402")}
    nlg = {"1990-01": D("2"), "1990-03": D("2")}
    c1q, miss = g.c1(usd, nlg, ["1990-01", "1990-02", "1990-03"])
    assert miss == ["1990-02"] and "1990-02" not in c1q
    # gold missing too
    c1q, miss = g.c1({"1990-01": D("400")}, nlg, ["1990-01", "1990-02", "1990-03"])
    assert miss == ["1990-02", "1990-03"]
    # canonical rows show null, not an interpolated value
    rows = g.canonical_rows({"x": g.c1(usd, nlg, ["1990-01", "1990-02", "1990-03"])[0], "usd": usd})
    assert rows[1]["x"] is None and rows[1]["usd"] is not None


def test_annual_mean_requires_all_twelve_months():
    qs = {f"1995-{i:02d}": q("100", "EUR", "oz") for i in range(1, 12)}
    assert g.annual_mean(qs, 1995) is None
    qs["1995-12"] = q("112", "EUR", "oz")
    assert g.annual_mean(qs, 1995).value == (D("100") * 11 + D("112")) / 12
    qs["1995-12"] = q("112", "NLG", "oz")
    with pytest.raises(g.UnitError):
        g.annual_mean(qs, 1995)


def test_c4_refuses_pre_euro_months():
    with pytest.raises(g.ConstructionError):
        g.c4({"1998-12": D("290")}, {"1998-12": D("1.17")}, ["1998-12"])


def test_unit_mixing_rejected():
    usd_per_oz = q("400", "USD", "oz")
    usd_per_gram = q("12", "USD", "g")
    nlg_usd = q("2", "NLG", "USD")
    # per-gram gold chained legitimately gives NLG per gram (never silently NLG per oz)
    assert (g.mul(nlg_usd, usd_per_gram).num, g.mul(nlg_usd, usd_per_gram).den) == ("NLG", "g")
    # wrong direction: USD per NLG used as NLG per USD
    with pytest.raises(g.UnitError):
        g.mul(q("0.5", "USD", "NLG"), usd_per_oz)
    with pytest.raises(g.UnitError):
        g.mul(2, usd_per_oz)
    # grams per home: EUR house with NLG gold
    with pytest.raises(g.UnitError):
        g.grams_per_home_eur(q("100000", "EUR", "home"), q("250", "NLG", "oz"))
    with pytest.raises(g.UnitError):
        g.grams_per_home_nlg(q("220000", "NLG", "home"), q("250", "EUR", "oz"))
    with pytest.raises(g.UnitError):
        g.grams_per_home_eur(q("100000", "EUR", "home"), q("8", "EUR", "g"))


def test_rate_applied_exactly_once():
    nlg = q("440.742", "NLG", "oz")
    once = g.redenominate(nlg)
    assert once.value == D("440.742") / D("2.20371") == D("200")
    with pytest.raises(g.UnitError):
        g.redenominate(once)  # twice
    with pytest.raises(g.UnitError):
        g.redenominate(q("200", "EUR", "oz"))  # EUR is not NLG
    with pytest.raises(g.UnitError):
        g.redenominate(q("5", "USD", "oz"))


def test_nlg_vs_eur_confusion_in_grams_route_is_visible():
    house_eur, house_nlg = q("100000", "EUR", "home"), q("220371", "NLG", "home")
    gold_nlg = q("500", "NLG", "oz")
    gold_eur = g.redenominate(gold_nlg)
    a = g.grams_per_home_eur(house_eur, gold_eur)
    b = g.grams_per_home_nlg(house_nlg, gold_nlg)
    assert abs(a - b) / a < D("1E-28")
    # confusing the currencies would be off by the factor 2.20371
    wrong = house_nlg.value * g.GRAMS_PER_OZ / gold_eur.value
    assert abs(wrong / a - g.NLG_PER_EUR) < D("1E-25")


def test_grams_per_home_independent_formula():
    h, o = D("123456"), D("287.654")
    got = g.grams_per_home_eur(g.Quote(h, "EUR", "home"), g.Quote(o, "EUR", "oz"))
    ref = Fraction(h) * Fraction(D("31.1034768")) / Fraction(o)
    assert abs(Fraction(got) - ref) / ref < Fraction(1, 10 ** 30)


@pytest.mark.parametrize("bad", [0, "0", "-1", "abc", "1e3", "NaN", "Infinity", "", None, "1,5", "01 "])
def test_noncanonical_numbers_rejected(bad):
    with pytest.raises(g.ConstructionError):
        g.parse_decimal(bad)


def test_ordering_duplicates_and_periods():
    with pytest.raises(g.ConstructionError):
        g.load_series([("1990-02", "1"), ("1990-01", "1")])
    with pytest.raises(g.ConstructionError):
        g.load_series([("1990-01", "1"), ("1990-01", "2")])
    with pytest.raises(g.ConstructionError):
        g.load_series([("1990-13", "1")])
    with pytest.raises(g.ConstructionError):
        g.load_series([("1990-1", "1")])
    assert list(g.load_series([("1990-01", "1"), ("1990-02", "2")])) == ["1990-01", "1990-02"]


def test_month_range_and_reversed():
    assert g.month_range("1998-11", "1999-02") == ["1998-11", "1998-12", "1999-01", "1999-02"]
    with pytest.raises(g.ConstructionError):
        g.month_range("1999-01", "1998-12")


def test_overlap_compare_flags_missing_and_checks_tags():
    c3q = {"1999-01": q("100", "EUR", "oz", "REDENOMINATED"), "1999-02": q("101", "EUR", "oz", "REDENOMINATED")}
    c4q = {"1999-01": q("100.5", "EUR", "oz")}
    devs, miss = g.overlap_compare(c3q, c4q, ["1999-01", "1999-02", "1999-03"])
    assert miss == ["1999-02", "1999-03"] and list(devs) == ["1999-01"]
    assert abs(devs["1999-01"] - (D("100") - D("100.5")) / D("100.5")) < D("1E-30")
    with pytest.raises(g.UnitError):  # observed vs observed is not the C3/C4 test
        g.overlap_compare({"1999-01": q("100", "EUR", "oz")}, c4q, ["1999-01"])


def test_deviation_stats():
    devs = {"1999-01": D("0.001"), "1999-02": D("-0.003"), "1999-03": D("0.002")}
    s = g.deviation_stats(devs)
    assert s["months"] == 3 and s["max_abs_pct"] == "0.300000" and s["median_abs_pct"] == "0.200000"
    assert s["worst"][0] == ["1999-02", "-0.300000"]
    assert g.deviation_stats({}) == {"months": 0}


def test_euro_era_fixed_cross_and_bis_direction():
    v = g.nlg_per_usd_from_usd_per_eur(q("1.10", "USD", "EUR")).value
    assert abs(Fraction(v) - RATE / Fraction(110, 100)) < Fraction(1, 10 ** 30)
    assert g.nlg_per_usd_from_eur_per_usd(q("0.9", "EUR", "USD")).value == D("0.9") * D("2.20371")
    with pytest.raises(g.UnitError):
        g.nlg_per_usd_from_usd_per_eur(q("1.10", "EUR", "USD"))
    with pytest.raises(g.UnitError):
        g.nlg_per_usd_from_eur_per_usd(q("1.10", "USD", "EUR"))


def _inputs():
    return {"start": "1998-11", "end": "1999-02",
            "usd_oz": {"1998-11": "294.1", "1998-12": "292", "1999-01": "287", "1999-02": "287.3"},
            "nlg_per_usd": {"1998-11": "1.9", "1998-12": "1.8816"},
            "usd_per_eur": {"1999-01": "1.16078", "1999-02": "1.1214"}}


def test_cli_roundtrip_hash_and_mismatch(tmp_path):
    inp, out = tmp_path / "in.json", tmp_path / "out.json"
    inp.write_text(json.dumps(_inputs()))
    assert g.main(["--inputs", str(inp), "--out", str(out)]) == 0
    sha = json.loads(out.read_text())["sha256"]
    assert g.main(["--inputs", str(inp), "--out", str(out), "--expect-sha256", sha]) == 0
    assert g.main(["--inputs", str(inp), "--out", str(out), "--expect-sha256", "0" * 64]) == 2
    # deterministic
    assert json.loads(out.read_text())["sha256"] == sha
    data = json.loads(out.read_text())
    assert data["missing"] == {"c1": [], "c4": []}


def test_cli_fails_closed_on_defects(tmp_path):
    out = tmp_path / "o.json"
    bad = _inputs()
    bad["usd_oz"]["1998-12"] = "-3"
    p = tmp_path / "b.json"
    p.write_text(json.dumps(bad))
    assert g.main(["--inputs", str(p), "--out", str(out)]) == 1
    assert g.main(["--inputs", str(tmp_path / "missing.json"), "--out", str(out)]) == 1
    p.write_text("{not json")
    assert g.main(["--inputs", str(p), "--out", str(out)]) == 1


def test_cli_keeps_gap_null_not_filled(tmp_path):
    inp = _inputs()
    del inp["nlg_per_usd"]["1998-12"]
    p, out = tmp_path / "i.json", tmp_path / "o.json"
    p.write_text(json.dumps(inp))
    assert g.main(["--inputs", str(p), "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    assert res["missing"]["c1"] == ["1998-12"]
    row = next(r for r in res["rows"] if r["period"] == "1998-12")
    assert row["c1_gold_nlg_oz"] is None and row["c3_eur_equivalent_oz"] is None and row["usd_oz"] is not None


def test_c4_absent_before_1999_in_cli_rows():
    res = g.compute_from_inputs(_inputs())
    r = {x["period"]: x for x in res["rows"]}
    assert r["1998-11"].get("c4_gold_eur_oz") is None
    assert r["1999-01"]["c1_gold_nlg_oz"] is None and r["1999-01"]["c4_gold_eur_oz"] is not None


def test_hash_changes_when_any_value_changes():
    a = g.compute_from_inputs(_inputs())["sha256"]
    mod = _inputs()
    mod["usd_oz"]["1998-11"] = "294.2"
    assert g.compute_from_inputs(mod)["sha256"] != a
