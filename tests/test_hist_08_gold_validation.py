"""Offline synthetic tests for tools.hist_08_gold_validate (prove code behaviour only; no network, no real data).

The expected values below are computed by hand or with plain Fraction arithmetic in the test itself, never by calling
the function under test twice."""
import socket
from datetime import date
from decimal import Decimal as D
from fractions import Fraction as F

import pytest

from tools import hist_02_acquire as acq
from tools import hist_07_gold_constructions as hc
from tools import hist_08_gold_validate as v

R = F(220371, 100000)


# ------------------------------------------------------------------ direction and unit conversions
def test_constants_are_exact_and_equal_hist07():
    assert v.RATE == R == F(hc.NLG_PER_EUR)
    assert v.G_PER_OZ == F(hc.GRAMS_PER_OZ) == F("31.1034768")


def test_direction_accepts_nlg_per_usd_header_and_values():
    r = v.assert_direction("FED H.10  GUILDERS/US$  noon buying rates", [D("1.9"), D("2.1"), D("1.8")])
    assert r["direction"] == "NLG_PER_USD" and r["by_text"] == "NLG_PER_USD" and r["by_value"] == "NLG_PER_USD"


def test_direction_rejects_inverted_values_under_nlg_header():
    with pytest.raises(v.ValidationDefect, match="CONFLICT"):
        v.assert_direction("GUILDERS/US$", [D("0.52"), D("0.50"), D("0.55")])


def test_direction_rejects_usd_per_nlg_header_and_unknown():
    with pytest.raises(v.ValidationDefect):
        v.assert_direction("US$/GUILDER", [D("0.5")])  # values and text agree on USD_PER_NLG, but we expect NLG_PER_USD
    with pytest.raises(v.ValidationDefect, match="UNDETERMINED"):
        v.assert_direction("no hint", [D("50"), D("60")])
    with pytest.raises(v.ValidationDefect, match="NO_VALUES"):
        v.assert_direction("GUILDERS/US$", [])


def test_direction_continuity_confirms_and_detects_inverted_series():
    fed = {f"1998-{m:02d}": F("1.87") for m in range(7, 13)}
    ecb = {f"1999-{m:02d}": F("1.17") for m in range(1, 7)}
    ok = v.continuity_direction_test(fed, ecb, v.months_between("1998-07", "1998-12"), v.months_between("1999-01", "1999-06"))
    assert ok["direction_confirmed"] is True
    assert F(ok["implied_usd_per_eur_if_nlg_per_usd"]) == (R / F("1.87")).limit_denominator(10 ** 5) or abs(F(ok["implied_usd_per_eur_if_nlg_per_usd"]) - R / F("1.87")) < F(1, 10 ** 5)
    # the same data read as USD per NLG (value 0.535) would be inverted: feed the reciprocal and expect rejection
    inv = {m: 1 / F("1.87") for m in fed}
    bad = v.continuity_direction_test(inv, ecb, v.months_between("1998-07", "1998-12"), v.months_between("1999-01", "1999-06"))
    assert bad["direction_confirmed"] is False
    assert v.continuity_direction_test({}, ecb, ["1998-07"], ["1999-01"]) is None


def test_c1_c3_c4_conversions_by_hand():
    usd, nlg = F(400), F("1.9")
    assert v.c1_f(usd, nlg) == F(760)  # USD/oz x NLG/USD = NLG/oz
    assert v.c3_f(F(760)) == F(760) / R  # NLG/oz / (NLG/EUR) = EUR/oz
    assert v.c4_f(F(287), F("1.16078")) == F(287) / F("1.16078")  # USD/oz / (USD/EUR) = EUR/oz
    assert v.nlg_per_usd_from_usd_per_eur(F("1.16078")) == R / F("1.16078")
    # grams: same-currency ratio times grams per troy ounce
    assert v.grams_per_home(F(31103), F(1000)) == F(31103) * F("31.1034768") / 1000


def test_redenomination_is_value_neutral_for_grams_per_home_exactly():
    usd, nlg, house_nlg = F(350), F("1.75"), F(300000)
    g_nlg = v.grams_per_home(house_nlg, v.c1_f(usd, nlg))
    g_eur = v.grams_per_home(house_nlg / R, v.c3_f(v.c1_f(usd, nlg)))
    assert g_nlg == g_eur


def test_fixed_rate_sensitivity_numbers():
    out = v.fixed_rate_sensitivity(F(500), F(250000), F(1, 100))
    assert out["c3_level_change_pct"] == "-0.990099"  # 1/1.01 - 1
    assert out["grams_change_pct_same_rate_for_both"] == "0.000000"
    assert out["grams_change_pct_house_fixed_gold_at_wrong_rate"] == "1.000000"


def test_fr_rejects_floats_nonpositive_and_nonfinite():
    for bad in (1.5, True, 0, -1, D("NaN"), D("Infinity"), "abc"):
        with pytest.raises(v.ValidationDefect):
            v.fr(bad)
    assert v.fr(D("1.25")) == F(5, 4)


# ------------------------------------------------------------------ aggregation
def daily(vals, y=1990, m=1):
    return {date(y, m, i + 1): D(x) for i, x in enumerate(vals)}


def test_aggregation_rules_by_hand():
    pts = {**daily(["2.0", "2.2", "2.4", "2.6"]), **daily(["3.0", "3.4"], m=2)}
    mean, n = v.aggregate(pts, "mean")
    assert mean == {"1990-01": F("2.3"), "1990-02": F("3.2")} and n == {"1990-01": 4, "1990-02": 2}
    assert v.aggregate(pts, "last")[0] == {"1990-01": F("2.6"), "1990-02": F("3.4")}
    assert v.aggregate(pts, "first")[0] == {"1990-01": F("2.0"), "1990-02": F("3.0")}
    assert v.aggregate(pts, "median")[0] == {"1990-01": F("2.3"), "1990-02": F("3.2")}
    assert v.aggregate(pts, "mean", min_obs=3)[0] == {"1990-01": F("2.3")}  # short month dropped, not filled
    with pytest.raises(v.ValidationDefect):
        v.aggregate(pts, "weighted")


def test_aggregation_uses_date_order_not_insertion_order():
    pts = {date(1990, 1, 3): D("3"), date(1990, 1, 1): D("1"), date(1990, 1, 2): D("2")}
    assert v.aggregate(pts, "last")[0]["1990-01"] == 3 and v.aggregate(pts, "first")[0]["1990-01"] == 1


def test_aggregation_sensitivity_is_zero_for_constant_and_exact_for_known_drift():
    const = {**daily(["2"] * 5), **daily(["2"] * 5, m=2)}
    s = v.aggregation_sensitivity(const, {"all": ["1990-01", "1990-02"]})
    assert all(s[r]["all"]["max_abs_pct"] == "0.000000" for r in ("last", "first", "median"))
    drift = daily(["2.0", "2.0", "2.0", "2.4"])  # mean 2.1, last 2.4
    s = v.aggregation_sensitivity(drift, {"all": ["1990-01"]})
    assert s["last"]["all"]["mean_signed_pct"] == v.pct_str(F("2.4") / F("2.1") - 1)
    assert s["first"]["all"]["mean_signed_pct"] == v.pct_str(F("2.0") / F("2.1") - 1)


def test_product_of_means_vs_mean_of_products_by_hand():
    gold = daily(["100", "200"])
    fxs = daily(["2", "4"])
    # A = 150 * 3 = 450 ; B = (200 + 800) / 2 = 500 ; A/B - 1 = -10%
    out = v.product_of_means_effect(gold, fxs, ["1990-01"])
    assert out["mean_signed_pct"] == "-10.000000"
    # days present in only one series are not used
    out = v.product_of_means_effect({**gold, date(1990, 1, 9): D("999")}, fxs, ["1990-01"])
    assert out["mean_signed_pct"] == "-10.000000"


# ------------------------------------------------------------------ statistics (percentile definitions)
def test_nearest_rank_and_linear_percentiles_on_known_vector():
    xs = [F(i) for i in range(1, 11)]
    assert v.nearest_rank(xs, 50) == 5 and v.nearest_rank(xs, 95) == 10 and v.nearest_rank(xs, 10) == 1
    assert v.linear_pct(xs, 50) == F(11, 2) and v.linear_pct(xs, 100) == 10
    assert v.median_exact(xs) == F(11, 2) and v.median_exact(xs[:9]) == 5


def test_dev_stats_known_values_and_worst_ordering():
    devs = {"2000-01": F(1, 1000), "2000-02": F(-3, 1000), "2000-03": F(2, 1000), "2000-04": F(-1, 1000)}
    st = v.dev_stats(devs)
    assert st["months"] == 4 and st["mean_signed_pct"] == "-0.025000"
    assert st["max_abs_pct"] == "0.300000" and st["median_abs_pct"] == "0.100000"
    assert st["median_abs_pct_linear"] == "0.150000"
    assert st["worst"][0] == ["2000-02", "-0.300000"]
    assert v.dev_stats({}) == {"months": 0}


# ------------------------------------------------------------------ overlap recompute
def synthetic_overlap(n=36):
    ms = v.months_between("1999-01", "2001-12")[:n]
    usd = {m: D(280 + 3 * i) for i, m in enumerate(ms)}
    ecb = {m: D("1.05") + D(i % 7) / 100 for i, m in enumerate(ms)}
    alt = {m: ecb[m] * (1 + (D((-1) ** i) * D(i % 5)) / 1000) for i, m in enumerate(ms)}  # +-0..0.4% around ECB
    return ms, usd, ecb, alt


def test_overlap_devs_equal_closed_form_and_hand_check():
    ms, usd, ecb, alt = synthetic_overlap()
    devs, missing = v.overlap_devs({m: F(x) for m, x in usd.items()}, {m: F(x) for m, x in alt.items()}, {m: F(x) for m, x in ecb.items()}, ms)
    assert missing == [] and len(devs) == 36
    m = ms[1]
    nlg = R / F(alt[m])
    c3 = F(usd[m]) * nlg / R
    c4 = F(usd[m]) / F(ecb[m])
    assert devs[m] == c3 / c4 - 1 == F(ecb[m]) / F(alt[m]) - 1  # independent hand computation


def test_overlap_agrees_with_hist07_code_on_synthetic_data():
    ms, usd, ecb, alt = synthetic_overlap()
    fu, fa, fe = ({m: F(x) for m, x in s.items()} for s in (usd, alt, ecb))
    devs, _ = v.overlap_devs(fu, fa, fe, ms)
    nlg_dec = {m: hc.nlg_per_usd_from_usd_per_eur(hc.Quote(alt[m], "USD", "EUR")).value for m in ms}
    res = v.compare_with_hist07(usd, nlg_dec, ecb, ms, devs)
    assert res["agree"] is True and res["same_month_set"] and res["stat_differences"] == {}


def test_overlap_comparison_detects_a_corrupted_fixture():
    ms, usd, ecb, alt = synthetic_overlap()
    fu, fa, fe = ({m: F(x) for m, x in s.items()} for s in (usd, alt, ecb))
    devs, _ = v.overlap_devs(fu, fa, fe, ms)
    corrupted = dict(alt)
    corrupted[ms[10]] = alt[ms[10]] * D("1.02")  # one month differs by 2% in the HIST-07 input only
    nlg_dec = {m: hc.nlg_per_usd_from_usd_per_eur(hc.Quote(corrupted[m], "USD", "EUR")).value for m in ms}
    res = v.compare_with_hist07(usd, nlg_dec, ecb, ms, devs)
    assert res["agree"] is False


def test_overlap_missing_month_is_reported_not_filled():
    ms, usd, ecb, alt = synthetic_overlap()
    del alt[ms[5]]
    devs, missing = v.overlap_devs({m: F(x) for m, x in usd.items()}, {m: F(x) for m, x in alt.items()}, {m: F(x) for m, x in ecb.items()}, ms)
    assert missing == [ms[5]] and ms[5] not in devs and len(devs) == 35


def test_overlap_wrong_direction_ecb_is_visible_as_huge_deviation():
    ms, usd, ecb, alt = synthetic_overlap()
    inverted = {m: 1 / F(x) for m, x in ecb.items()}  # EUR per USD instead of USD per EUR
    devs, _ = v.overlap_devs({m: F(x) for m, x in usd.items()}, {m: F(x) for m, x in alt.items()}, inverted, ms)
    assert float(v.dev_stats(devs)["max_abs_pct"]) > 10


def test_reproduces_reported_tolerance():
    st = {"months": 36, "median_abs_pct": "0.058200", "mean_signed_pct": "0.032400", "p95_abs_pct": "0.303500", "max_abs_pct": "0.307400"}
    rep = {"median_abs_pct": "0.0582", "mean_signed_pct": "0.0324", "p95_abs_pct": "0.3035", "max_abs_pct": "0.3074"}
    assert all(v.reproduces_reported(st, rep).values())
    st["max_abs_pct"] = "0.310000"
    assert v.reproduces_reported(st, rep)["max_abs_pct"] is False


# ------------------------------------------------------------------ World Bank precision, rounding and regime
def test_wb_precision_counts_non_integers_and_bounds():
    wb = {"1990-01": D("400"), "1990-02": D("401.5"), "1990-03": D("250")}
    p = v.wb_precision(wb)["1990-98"]
    assert p["n"] == 3 and p["non_integer"] == 1 and p["min"] == "250.0000"
    assert p["bound_pct_at_min"] == "0.2000"  # 0.5 / 250


def test_rounding_vs_reference_counts():
    ref = {"1990-01": D("400.4"), "1990-02": D("401.6"), "1990-03": D("410.0"), "1990-04": D("390.0")}
    wb = {"1990-01": D("400"), "1990-02": D("402"), "1990-03": D("412"), "1990-04": D("390")}
    r = v.rounding_vs_reference(wb, ref, list(ref))
    assert r["months"] == 4 and r["within_half_usd"] == 3 and r["gt_one_usd"] == 1 and r["wb_equals_round_half_up_of_ref"] == 3
    assert r["max_abs_usd"] == "2.0000" and r["max_month"] == "1990-03"
    assert v.rounding_vs_reference(wb, {}, list(ref)) == {"months": 0}


def test_regime_scan_flat_official_price_then_moves():
    wb = {f"1960-{m:02d}": D(35) for m in range(1, 13)}
    wb.update({"1961-01": D(35), "1961-02": D(36), "1961-03": D(36)})
    r = v.regime_scan(wb, "1960-01", "1961-03")
    assert r["longest_equal_run"] == 13 and r["longest_run_ends"] == "1961-01" and r["first_change_month"] == "1961-02"
    assert r["distinct_values"] == 2 and r["months_equal_first_value"] == 13
    assert v.regime_scan(wb, "1980-01", "1980-12") == {"months": 0}


def test_top_steps_ranks_by_absolute_change():
    s = {"1961-01": D("3.77"), "1961-02": D("3.78"), "1961-03": D("3.62"), "1961-04": D("3.62")}
    assert v.top_steps(s, "1961-01", "1961-04", 1)[0][0] == "1961-03"


def test_closeness_and_decimals_distribution():
    a = {"1990-01": D("1.9000"), "1990-02": D("1.9100"), "1990-03": D("2.0")}
    b = {"1990-01": D("1.90004"), "1990-02": D("1.9109"), "1990-03": D("2.5")}
    c = v.closeness(a, b, ["1990-01", "1990-02", "1990-03", "1990-04"])
    assert c == {"months": 3, "le_0_00005": 1, "le_0_0001": 1, "le_0_001": 2}
    assert v.decimals_distribution([D("1.90"), D("1.9"), D("2"), D("1.234")]) == {2: 1, 1: 1, 0: 1, 3: 1}


# ------------------------------------------------------------------ BIS parser and production ADR-004 wiring
def test_parse_bis_collections_splits_average_and_end_of_period():
    t = ("KEY,FREQ:Frequency,COLLECTION:Collection,TIME_PERIOD:Time period,OBS_VALUE:Value\n"
         "k,M:Monthly,A:Average,1975-01,1.1146\nk,M:Monthly,E:End,1975-01,1.12\nk,D:Daily,A:Average,1975-01,9\n")
    out, combos = v.parse_bis_collections(t.encode())
    assert out == {"A": {"1975-01": D("1.1146")}, "E": {"1975-01": D("1.12")}} and combos["D|A|"] == 1
    dup = t + "k,M:Monthly,A:Average,1975-01,1.2\n"
    with pytest.raises(v.ValidationDefect, match="DUPLICATE"):
        v.parse_bis_collections(dup.encode())
    with pytest.raises(v.ValidationDefect, match="COLUMNS"):
        v.parse_bis_collections(b"A,B\n1,2\n")


ECB_CSV = ("KEY,FREQ,CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE\n"
           + "".join(f"EXR,D,USD,EUR,2000-01-{d:02d},{x}\n" for d, x in ((3, "1.0"), (4, "1.1"), (5, "1.2")))
           + "".join(f"EXR,D,USD,EUR,2000-02-{d:02d},{x}\n" for d, x in ((1, "1.0"), (2, "1.2"))))


def test_production_adr004_matches_independent_c4_on_synthetic_ecb():
    wb = {"2000-01": D("284"), "2000-02": D("300")}
    prod = v.production_adr004(ECB_CSV.encode(), wb)
    mean, _ = v.aggregate({date(2000, 1, 3): D("1.0"), date(2000, 1, 4): D("1.1"), date(2000, 1, 5): D("1.2"),
                           date(2000, 2, 1): D("1.0"), date(2000, 2, 2): D("1.2")}, "mean")
    assert mean == {"2000-01": F("1.1"), "2000-02": F("1.1")}
    for m in wb:
        assert abs(F(prod["gold_eur"][m]) / (F(wb[m]) / mean[m]) - 1) < F(1, 10 ** 20)


# ------------------------------------------------------------------ analysis end to end on synthetic data
def full_synthetic():
    ms_pre = v.months_between("1960-01", "1999-12")
    wb = {m: D(35) if m <= "1967-12" else D(100 + (i % 40) * 5) for i, m in enumerate(ms_pre)}
    wb.update({m: D(280 + i) for i, m in enumerate(v.months_between("2000-01", "2002-12"))})
    fed_daily = {}
    for m in v.months_between("1971-01", "1998-12"):
        y, mo = int(m[:4]), int(m[5:])
        for d in range(1, 21):
            fed_daily[date(y, mo, d)] = D("1.9") + D((y + mo + d) % 9) / 100
    ecb_m = {m: D("1.10") + D(i % 5) / 100 for i, m in enumerate(v.months_between("1999-01", "2002-12"))}
    fed_eu = {}
    for m in v.months_between("1999-01", "2002-12"):
        y, mo = int(m[:4]), int(m[5:])
        for d in range(1, 21):
            fed_eu[date(y, mo, d)] = ecb_m[m] * (1 + D((d % 3) - 1) / 1000)
    bis_a = {m: (fed_m := D("1.95")) / hc.NLG_PER_EUR for m in v.months_between("1960-01", "1998-12")}
    bis_e = {m: x * D("1.001") for m, x in bis_a.items()}
    house = {m: D(100000 + 1000 * i) for i, m in enumerate(v.months_between("1995-01", "1999-12"))}
    ecb_d = {date(1999 + (i // 12), i % 12 + 1, 3): ecb_m[m] for i, m in enumerate(v.months_between("1999-01", "2002-12"))}
    return {"wb": wb, "wb_meta": {"unit_rows": ["($/troy oz)"]}, "fed_daily": fed_daily, "fed_header": "GUILDERS/US$ noon buying", "fed_nd": 3,
            "fed_eu_daily": fed_eu, "bis": {"A": bis_a, "E": bis_e}, "ecb_m": ecb_m, "ecb_d": ecb_d, "house": house,
            "boe_m": {m: wb[m] + D("0.3") for m in v.months_between("1979-01", "1999-12")}}


def test_analyze_full_synthetic_has_no_defects_and_all_checks_pass():
    D_ = full_synthetic()
    S = {"defects": [], "missing_sources": [], "bis_combos": {}}
    R_ = v.analyze(D_, S)
    assert S["defects"] == [], S["defects"]
    assert all(c["pass"] for c in R_["checks"]) and R_["checks"]
    assert R_["unit_consistency"]["euro_era_identity_c3_of_fixed_cross_equals_c4_exactly"] is True
    assert R_["fx_direction"]["continuity_1998H2_vs_1999H1"]["direction_confirmed"] is True
    assert R_["overlap_1999_2001"]["fed_euro_noon"]["agreement_with_hist07_code"]["agree"] is True
    assert R_["overlap_1999_2001"]["fed_euro_noon"]["stats"]["months"] == 36
    assert R_["worldbank"]["precision_by_period"]["1960-67"]["non_integer"] == 0
    assert R_["worldbank"]["regime_1960_1967"]["longest_equal_run"] == 96
    assert "grams_per_home_1995_1999" in R_ and R_["grams_per_home_1995_1999"]["base_fed_mean"]["monthly_vs_base"] == "base"
    # C1 rounding worst case equals 0.5 / value for the smallest value in range
    assert R_["fixed_rate_sensitivity_example_1998_06"]["grams_change_pct_same_rate_for_both"] == "0.000000"


def test_analyze_gap_in_world_bank_series_is_flagged_not_filled():
    D_ = full_synthetic()
    del D_["wb"]["1985-06"]
    S = {"defects": [], "missing_sources": []}
    R_ = v.analyze(D_, S)
    assert any(c["name"] == "wb_complete_range" and not c["pass"] for c in R_["checks"])
    assert "1985-06" not in D_["wb"]


def test_analyze_inverted_fed_series_is_rejected():
    D_ = full_synthetic()
    D_["fed_daily"] = {d: 1 / x for d, x in D_["fed_daily"].items()}
    S = {"defects": [], "missing_sources": []}
    v.analyze(D_, S)
    assert any("DIRECTION" in d["error"] or "CHECK_FAILED" in d["error"] for d in S["defects"])


def test_analyze_missing_sources_skips_sections_without_inventing_values():
    S = {"defects": [], "missing_sources": []}
    R_ = v.analyze({}, S)
    assert S["defects"] == []
    assert "overlap_1999_2001" not in R_ and "worldbank" not in R_
    assert any(x.startswith("overlap") for x in R_["not_performed"])


def test_no_network_and_all_sources_unreachable_is_incomplete(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network access attempted")

    def unreachable(source, **k):
        raise acq.AcquisitionError("NETWORK_ERROR source=" + source)

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(acq, "fetch", unreachable)
    monkeypatch.setattr(v.time, "sleep", lambda s: None)
    R_, rows = v.run(fetch_fn=unreachable)
    assert R_["status"] == "INCOMPLETE" and rows == []
    assert R_["sources"] == {} or set(R_["sources"]) <= {"fixture"}
    assert "overlap_1999_2001" not in R_


def test_tool_never_writes_to_repository_data_dirs():
    import inspect
    src = inspect.getsource(v)
    for forbidden in ("data/cbs-housing.csv", "frontend/public", "write_text(json.dumps(data", "etl/static_export"):
        assert forbidden not in src


def test_ecb_monthly_unavailable_falls_back_to_flagged_exact_daily_mean(monkeypatch):
    import hashlib
    from tools import hist_03_worldbank_validate as wbv
    from tools import hist_04_fx as fx

    def fetch(sid, **k):
        if sid == fx.ECB_DAILY:
            raw = ECB_CSV.encode()
            return raw, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        raise acq.AcquisitionError("HTTP_STATUS_ERROR source=" + sid)

    def wb_down(p=None):
        raise acq.AcquisitionError("WB_DOWN")

    monkeypatch.setattr(v.time, "sleep", lambda s: None)
    monkeypatch.setattr(wbv, "load_workbook", wb_down)
    Dd, S = v.load(fetch)
    assert "ECB_MONTHLY_UNAVAILABLE_USED_EXACT_MEAN_OF_ECB_DAILY" in S["flags"]
    assert Dd["ecb_m"]["2000-01"] == D("1.1") and Dd["ecb_m"]["2000-02"] == D("1.1")
    assert any(m["source_id"] == fx.ECB_MONTHLY for m in S["missing_sources"])
