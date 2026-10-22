import hashlib
import json
from calendar import monthrange
from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import hist_08_bundle as hb
from tools import hist_09_bundle as h9
from tools import hist_10_gold_housing as h10

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "cbs-housing.csv"
RAW = "b" * 64
RATE = Fraction(220371, 100000)
G = Fraction(311034768, 10 ** 7)


# ---------------------------------------------------------------- synthetic world (proves code, not data)
def months(first, last):
    out, (y, m) = [], (int(first[:4]), int(first[5:]))
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def wb_gold(first="1975-01", last="2000-12"):
    return {m: Decimal(100 + (i * 7) % 53) for i, m in enumerate(months(first, last))}  # whole USD, varies by month


def daily_fx(first, last, base, step):
    out = {}
    for i, m in enumerate(months(first, last)):
        for day in range(1, 17):  # 16 days: above the 50% calendar-day coverage threshold for every month
            out[date(int(m[:4]), int(m[5:]), day)] = Decimal(base) + Decimal(i % 9) * Decimal(step) + Decimal(day % 3) / Decimal(100)
    return out


FED = daily_fx("1975-01", "1998-12", "2.0", "0.05")
ECB = daily_fx("1999-01", "2000-12", "1.0", "0.02")
WB = wb_gold()


def nvm_nlg_series():
    values = {f"{y}-H{h}": Decimal(90000 + 1000 * (2 * (y - 1975) + h)) for y in range(1975, 2001) for h in (1, 2)}
    rows = tuple(hm.Observation("nvm_median_nlg_halfyear", p, v, "NLG", "NLG", h9.NVM_DEFINITION, "synthetic", RAW,
                                "2026-10-22T00:00:00+00:00", "v1", "CONFIRMED", ()) for p, v in values.items())
    s = hm.Series("nvm_median_nlg_halfyear", "source", "housing", "semiannual", "NLG", "NLG", h9.NVM_DEFINITION,
                  "median_price", "nominal", None, (), rows)
    hm.validate_series(s)
    return s, values


def cbs_series():
    def mk(series_id, kind, ccy, unit, fn, first, last):
        return hb.source_series(series_id, "housing", {m: fn(i) for i, m in enumerate(months(first, last))},
                                frequency="monthly", currency=ccy, unit=unit, kind=kind, definition_id=h9.CBS_DEFINITION,
                                source_id="synthetic", raw_sha256=RAW, retrieved_at="2026-10-22T00:00:00+00:00",
                                vintage="v1", quality_of=lambda p: "CONFIRMED")
    price = mk("cbs_avg_price", "average_price", "EUR", "EUR", lambda i: str(90000 + 300 * i), "1995-01", "2000-12")
    count = mk("cbs_sold", "transaction_count", "NONE", "homes", lambda i: str(1000 + 13 * (i % 7)), "1995-01", "2000-12")
    fixture = mk("cbs_fixture", "average_price", "EUR", "EUR", lambda i: str(90000 + 300 * i), "1995-01", "1999-12")
    csv_s = mk("cbs_csv", "average_price", "EUR", "EUR", lambda i: str(120000 + 300 * i), "2000-01", "2000-12")
    return price, count, fixture, csv_s


@pytest.fixture(scope="module")
def world():
    gold_usd = h10.gold_usd_series(WB, RAW)
    fed = h10.fx_daily_series("fed_nlg_per_usd_daily", FED, currency="NLG", unit="NLG_per_USD", source_id="syn", raw_sha=RAW,
                              definition="fed_h10_nlg_per_usd_daily")
    ecb = h10.fx_daily_series("ecb_usd_per_eur_daily", ECB, currency="USD", unit="USD_per_EUR", source_id="syn", raw_sha=RAW,
                              definition="ecb_ref_usd_per_eur_daily")
    gold = h10.build_gold(gold_usd, fed, ecb)
    nvm, nvm_values = nvm_nlg_series()
    price, count, fixture, csv_s = cbs_series()
    houses = h10.build_housing_grams(gold, nvm, price, count, fixture, csv_s)
    return {"gold": gold, "houses": houses, "nvm": nvm, "nvm_values": nvm_values, "price": price, "count": count,
            "fixture": fixture, "csv": csv_s}


def everything(world):
    return h10.all_series(world["gold"], world["houses"], world["nvm"], world["price"], world["count"], world["fixture"], world["csv"])


def pts(s):
    return {p.period: p.value for p in s.points}


# ---------------------------------------------------------------- FX direction, units, troy ounce
def usd_gold(values):
    return hb.source_series("g_usd", "gold", values, frequency="monthly", currency="USD", unit="USD_per_troy_oz",
                            kind="spot_price", definition_id="d", source_id="s", raw_sha256=RAW,
                            retrieved_at="2026-10-22T00:00:00+00:00", vintage="v", quality_of=lambda p: "CONFIRMED")


def quote(values, unit, ccy, kind="fx_rate", asset="fx"):
    return hb.source_series("q_fx", asset, values, frequency="monthly", currency=ccy, unit=unit, kind=kind, definition_id="d",
                            source_id="s", raw_sha256=RAW, retrieved_at="2026-10-22T00:00:00+00:00", vintage="v",
                            quality_of=lambda p: "CONFIRMED")


def test_quote_direction_is_enforced():
    gold = usd_gold({"1980-01": "400"})
    ok = hm.convert_currency_by_quote(gold, quote({"1980-01": "2.5"}, "NLG_per_USD", "NLG"), to_currency="NLG", series_id="g_nlg")
    assert pts(ok)["1980-01"] == Decimal("1000") and ok.unit == "NLG_per_troy_oz" and ok.currency == "NLG"
    with pytest.raises(hm.CurrencyMismatch):  # inverted quote USD per NLG must not be accepted
        hm.convert_currency_by_quote(gold, quote({"1980-01": "0.4"}, "USD_per_NLG", "USD"), to_currency="NLG", series_id="x")
    with pytest.raises(hm.CurrencyMismatch):  # the divide-style function rejects the multiply-style quote
        hm.convert_currency(gold, quote({"1980-01": "2.5"}, "NLG_per_USD", "NLG"), to_currency="NLG", series_id="x")
    with pytest.raises(hm.CurrencyMismatch):  # NLG/EUR is a redenomination, never a market quote
        hm.convert_currency_by_quote(replace(ok, series_id="n"), quote({"1980-01": "2"}, "EUR_per_NLG", "EUR"), to_currency="EUR", series_id="x")
    with pytest.raises(hm.CurrencyMismatch):
        hm.convert_currency_by_quote(gold, quote({"1980-01": "2"}, "NLG_per_USD", "NLG", kind="spot_price", asset="gold"),
                                     to_currency="NLG", series_id="x")


def test_usd_per_eur_quote_divides():
    gold = usd_gold({"2000-01": "280"})
    eur = hm.convert_currency(gold, quote({"2000-01": "1.0"}, "USD_per_EUR", "USD"), to_currency="EUR", series_id="g_eur")
    assert pts(eur)["2000-01"] == Decimal("280")
    eur = hm.convert_currency(gold, quote({"2000-01": "1.25"}, "USD_per_EUR", "USD"), to_currency="EUR", series_id="g_eur2")
    assert pts(eur)["2000-01"] == Decimal("224")
    with pytest.raises(hm.CurrencyMismatch):
        hm.convert_currency(gold, quote({"2000-01": "0.8"}, "EUR_per_USD", "EUR"), to_currency="EUR", series_id="bad")


def test_quote_frequency_must_match():
    gold = usd_gold({"1980-01": "400"})
    half = hm.half_year_aggregate(quote({f"1980-{m:02d}": "2" for m in range(1, 7)}, "NLG_per_USD", "NLG"), rule="mean", series_id="q_half")
    with pytest.raises(hm.FrequencyError):
        hm.convert_currency_by_quote(gold, half, to_currency="NLG", series_id="x")


def test_troy_ounce_constant_and_grams_formula():
    house = hb.source_series("h", "housing", {"1980-01": "311034.768"}, frequency="monthly", currency="NLG", unit="NLG",
                             kind="average_price", definition_id="d", source_id="s", raw_sha256=RAW,
                             retrieved_at="2026-10-22T00:00:00+00:00", vintage="v", quality_of=lambda p: "CONFIRMED")
    gold = hb.source_series("g", "gold", {"1980-01": "10000"}, frequency="monthly", currency="NLG", unit="NLG_per_troy_oz",
                            kind="spot_price", definition_id="d", source_id="s", raw_sha256=RAW,
                            retrieved_at="2026-10-22T00:00:00+00:00", vintage="v", quality_of=lambda p: "CONFIRMED")
    # price per gram = 10000 / 31.1034768; grams = house / price per gram
    assert pts(hm.grams_per_house(house, gold))["1980-01"] == Decimal("311034.768") * Decimal("31.1034768") / Decimal(10000)
    assert hm.TROY_OUNCE_GRAMS == Decimal("31.1034768")


# ---------------------------------------------------------------- half-year aggregation
def test_half_year_alignment_boundaries():
    assert [h10.half_of(m) for m in ("1998-06", "1998-07", "1998-12", "1999-01")] == ["1998-H1", "1998-H2", "1998-H2", "1999-H1"]
    assert h10.half_months("1998-H2") == [f"1998-{m:02d}" for m in range(7, 13)]
    g = usd_gold({f"1998-{m:02d}": str(100 + m) for m in range(1, 13)})
    for rule, h1, h2 in (("mean", Decimal("103.5"), Decimal("109.5")), ("last", Decimal(106), Decimal(112)), ("first", Decimal(101), Decimal(107))):
        out = pts(hm.half_year_aggregate(g, rule=rule, series_id=f"agg_{rule}"))
        assert out == {"1998-H1": h1, "1998-H2": h2}


def test_incomplete_half_year_is_null_not_partial():
    g = usd_gold({f"1998-{m:02d}": "100" for m in range(1, 13) if m != 9})
    assert pts(hm.half_year_aggregate(g, rule="mean", series_id="a"))["1998-H2"] is None
    assert pts(hm.half_year_aggregate(g, rule="last", series_id="b"))["1998-H2"] == Decimal(100)  # December is present
    missing_last = usd_gold({f"1998-{m:02d}": "100" for m in range(1, 13) if m != 12})
    assert pts(hm.half_year_aggregate(missing_last, rule="last", series_id="c"))["1998-H2"] is None


def test_half_year_aggregate_refuses_other_series():
    price, _, _, _ = cbs_series()
    with pytest.raises(hm.DefinitionMismatch):
        hm.half_year_aggregate(price, rule="mean", series_id="x")
    with pytest.raises(hm.FrequencyError):
        hm.half_year_aggregate(hm.half_year_aggregate(usd_gold({f"1998-{m:02d}": "1" for m in range(1, 7)}), rule="mean", series_id="h"),
                               rule="mean", series_id="x")
    with pytest.raises(hm.ModelError):
        hm.half_year_aggregate(usd_gold({"1998-01": "1"}), rule="median", series_id="x")


def test_model_aggregation_equals_independent_methods_on_synthetic(world):
    """The model's half-year series equal the independent Fraction implementation (M1, M3, M4, M2)."""
    g = world["gold"]
    for half in ("1975-H1", "1995-H1", "1998-H2", "1999-H1", "2000-H2"):
        nlg = half <= "1998-H2"
        methods = h10.half_gold_methods(WB, FED, ECB, half)
        key = "nlg" if nlg else "eur"
        for rule, name in (("mean", "M1_mean_of_monthly_local"), ("last", "M3_end_of_half"), ("first", "M4_start_of_half")):
            got = pts(g[f"gold_{key}_half_{rule}"])[half]
            assert abs(Fraction(got) - methods[name]) < Fraction(1, 10 ** 25), (half, rule)
        got = pts(g[f"gold_{key}_half_ratio_of_means"])[half]
        assert abs(Fraction(got) - methods["M2_ratio_of_half_means"]) < Fraction(1, 10 ** 25)
        assert methods["M2_ratio_of_half_means"] != methods["M1_mean_of_monthly_local"]  # the alternatives really differ


def test_alternatives_are_ordered_and_quantified(world):
    nvm, values = world["nvm"], world["nvm_values"]
    D = {"wb": WB, "fed_daily": FED, "ecb_d": ECB}
    cbs = {"price": world["price"], "count": world["count"]}
    out = h10.aggregation_impact(D, nvm, cbs)
    assert set(out["all_periods"]) == {"M2_ratio_of_half_means", "M2d_daily_weighted_fx", "M3_end_of_half", "M4_start_of_half",
                                       "M6_fx_last_of_month", "M7_fx_first_of_month"}
    assert out["all_periods"]["M3_end_of_half"]["n"] == 52 and float(out["all_periods"]["M3_end_of_half"]["max_abs_pct"]) > 0
    assert "1975-1978" in out["by_era"]["M3_end_of_half"] and "1999-2000" in out["by_era"]["M3_end_of_half"]
    assert out["M5_transaction_weighted_gold_vs_M1_cbs"]["n"] == 12


# ---------------------------------------------------------------- housing in grams
def test_nvm_grams_representative_periods_independent(world):
    nvm_values = world["nvm_values"]
    grams = {**pts(world["houses"]["nvm_grams_nlg_era"]), **pts(world["houses"]["nvm_grams_eur_era"])}
    for half in ("1975-H1", "1995-H1", "2000-H2"):
        methods = h10.half_gold_methods(WB, FED, ECB, half)
        house = Fraction(nvm_values[half]) if half <= "1998-H2" else Fraction(nvm_values[half]) / RATE
        exact = house * G / methods["M1_mean_of_monthly_local"]
        assert abs(Fraction(grams[half]) / exact - 1) < Fraction(1, 10 ** 25), half


def test_nlg_and_retro_eur_routes_are_identical(world):
    a, b = pts(world["houses"]["nvm_grams_nlg_era"]), pts(world["houses"]["nvm_grams_eur_retro"])
    assert set(a) == set(b) and len(a) == 48  # 1975-H1 .. 1998-H2
    assert max(abs(Fraction(a[p]) / Fraction(b[p]) - 1) for p in a) < Fraction(1, 10 ** 28)
    assert h10.retro_vs_nlg(world["houses"])["periods_compared"] == 48


def test_currency_transition_has_no_splice(world):
    nlg, eur = pts(world["houses"]["nvm_grams_nlg_era"]), pts(world["houses"]["nvm_grams_eur_era"])
    assert max(nlg) == "1998-H2" and min(eur) == "1999-H1" and not set(nlg) & set(eur)
    assert (min(nlg), max(eur)) == ("1975-H1", "2000-H2") and len(eur) == 4
    assert world["houses"]["nvm_grams_nlg_era"].currency == "NONE"
    assert all(s.series_id not in ("nvm_grams", "nvm_grams_all") for s in world["houses"].values())
    nlg_gold, eur_gold = world["gold"]["gold_nlg_monthly"], world["gold"]["gold_eur_monthly"]
    assert max(pts(nlg_gold)) == "1998-12" and min(pts(eur_gold)) == "1999-01"
    step = h10.transition(dict(wb=WB, fed_daily=FED, ecb_d=ECB), world["houses"], world["gold"])
    assert set(step) == {"gold_eur_1998-12_retro_to_1999-01_observed_pct", "nvm_grams_1998-H2_to_1999-H1_pct",
                         "cbs_grams_1998-12_retro_to_1999-01_pct"} and all(v is not None for v in step.values())


def test_nvm_median_and_cbs_mean_stay_separate(world):
    h = world["houses"]
    assert h["nvm_grams_nlg_era"].definition_id == "derived_grams_per_house_median"
    assert h["cbs_grams_eur_halfyear"].definition_id == "derived_grams_per_house"
    with pytest.raises(hm.DefinitionMismatch, match="cannot be mixed"):
        hm._combine(h["nvm_grams_eur_era"], h["cbs_grams_eur_halfyear"], lambda a, b: a / b, series_id="mix", step={"op": "x"})
    # the only allowed relation between the two housing statistics is the explicit ratio of prices
    ratio = hm.statistic_ratio(h["nvm_median_eur_halfyear"], h["cbs_avg_price_eur_halfyear"], series_id="r")
    assert ratio.kind == "statistic_ratio"
    # same gold denominator: the gap in grams equals the gap in price
    g = {p: pts(h["nvm_grams_eur_retro"])[p] / pts(h["cbs_grams_eur_retro_halfyear"])[p] for p in pts(h["cbs_grams_eur_retro_halfyear"])}
    for p, v in g.items():
        assert abs(v - pts(ratio)[p]) < Decimal("1e-25")


def test_cbs_monthly_eras_do_not_overlap(world):
    h = world["houses"]
    a, b, c = (pts(h[k]) for k in ("cbs_grams_1995_1998_retro_monthly", "cbs_grams_1999_monthly", "cbs_grams_2000_onward_monthly"))
    assert (min(a), max(a), len(a)) == ("1995-01", "1998-12", 48) and (min(b), max(b), len(b)) == ("1999-01", "1999-12", 12)
    assert min(c) == "2000-01" and not (set(a) & set(b) | set(a) & set(c) | set(b) & set(c))
    assert all(v is not None for v in a.values())


def test_missing_gold_month_gives_explicit_null_not_a_value():
    wb = dict(WB)
    del wb["1980-03"]
    gold_usd = h10.gold_usd_series(wb, RAW)
    fed = h10.fx_daily_series("fed_nlg_per_usd_daily", FED, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW, definition="d")
    ecb = h10.fx_daily_series("ecb_usd_per_eur_daily", ECB, currency="USD", unit="USD_per_EUR", source_id="s", raw_sha=RAW, definition="d")
    gold = h10.build_gold(gold_usd, fed, ecb)
    nvm, _ = nvm_nlg_series()
    g = hm.grams_per_house(nvm, gold["gold_nlg_half_mean"], series_id="g")
    by = {p.period: p for p in g.points}
    assert by["1980-H1"].value is None and "MISSING_INPUT" in by["1980-H1"].flags and by["1980-H2"].value is not None


# ---------------------------------------------------------------- source integrity, rejection of bad input
def test_source_adapters_reject_bad_input():
    with pytest.raises(h10.Hist10Error):
        h10.gold_usd_series({"1960-01": Decimal(35)}, RAW)  # nothing from the research start
    with pytest.raises(h10.Hist10Error):
        h10.fx_daily_series("x_fx", {}, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW, definition="d")
    with pytest.raises(h10.Hist10Error):
        h10.level_flag("1974-12")
    for bad in (Decimal(0), Decimal(-1)):
        with pytest.raises(hm.ModelError):
            h10.gold_usd_series({"1980-01": bad}, RAW)
        with pytest.raises(hm.ModelError):
            h10.fx_daily_series("x_fx", {date(1980, 1, 1): bad}, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW, definition="d")
    with pytest.raises(hm.ModelError):
        h10.gold_usd_series({"1980-01": Decimal(1)}, "not-a-hash")


def test_quality_levels_follow_the_documented_boundaries():
    assert [h10.level_flag(m) for m in ("1975-01", "1978-12", "1979-01", "1998-12", "1999-01", "1999-12", "2000-01")] == [
        "GOLD_LEVEL_B", "GOLD_LEVEL_B", "GOLD_LEVEL_A", "GOLD_LEVEL_A", "GOLD_LEVEL_E", "GOLD_LEVEL_E", "GOLD_ADR004_PERIOD"]
    s = h10.gold_usd_series(WB, RAW)
    assert s.observations[0].period == "1975-01" and "WB_WHOLE_USD" in s.observations[0].flags


def test_monthly_fx_mean_needs_enough_days():
    sparse = {date(1980, 1, d): Decimal("2") for d in range(1, 11)}  # 10 of 31 days: below the 50% threshold
    s = h10.fx_daily_series("fed_nlg_per_usd_daily", sparse, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW, definition="d")
    m = hm.monthly_mean(s, min_coverage=h10.MIN_DAY_COVERAGE, series_id="m")
    assert m.points[0].value is None and "INSUFFICIENT_DAILY_COVERAGE" in m.points[0].flags


def test_window_is_a_labelled_subset_not_new_data(world):
    full, w = world["gold"]["gold_usd_monthly"], world["gold"]["gold_usd_nlg_era"]
    v = {o.period: o.value for o in full.observations}
    assert {o.period: o.value for o in w.observations} == {p: v[p] for p in v if "1975-01" <= p <= "1998-12"}
    with pytest.raises(h10.Hist10Error):
        h10.window(world["gold"]["gold_nlg_monthly"], "1980-01", "1980-12", "x")
    with pytest.raises(h10.Hist10Error):
        h10.window(full, "1900-01", "1900-12", "x")


# ---------------------------------------------------------------- bundles, determinism, publication safety
def test_bundles_validate_and_rebuild_identically(world, tmp_path):
    allseries = everything(world)
    first = h10.write_bundles(h10.bundles(allseries), tmp_path / "a")
    second = h10.write_bundles(h10.bundles(allseries), tmp_path / "b")
    assert first == second and set(first) == {f"hist10_{n}.json" for n in ("A_gold_original", "B_gold_local", "C_nvm_grams", "D_cbs_grams")}
    for name in first:
        raw = (tmp_path / "a" / name).read_bytes()
        assert raw == (tmp_path / "b" / name).read_bytes() and hm.validate_bundle(json.loads(raw)) == []
    ids = {n: set(v["ids"]) for n, v in first.items()}
    assert "nvm_grams_nlg_era" in ids["hist10_C_nvm_grams.json"] and not any(i.startswith("cbs_") for i in ids["hist10_C_nvm_grams.json"])
    assert "nvm_grams_nlg_era" not in ids["hist10_D_cbs_grams.json"]  # NVM and CBS never share a bundle's derived members


def test_bundle_lineage_tamper_is_detected(world, tmp_path):
    h10.write_bundles(h10.bundles(everything(world)), tmp_path)
    bundle = json.loads((tmp_path / "hist10_C_nvm_grams.json").read_text())
    for s in bundle["series"]:
        if s["series_id"] == "gold_usd_nlg_era":
            s["observations"][0]["value"] = "1"
    assert any("lineage hash" in e for e in hm.validate_bundle(bundle))


def test_missing_ancestor_is_rejected(world):
    allseries = {k: v for k, v in {**world["gold"], **world["houses"]}.items() if k != "gold_nlg_monthly"}
    with pytest.raises(h10.Hist10Error, match="ancestor"):
        h10.lineage_closure(allseries, [allseries["nvm_grams_nlg_era"]])


def test_publication_allowlist_is_empty_and_gate_denies_everything(world):
    assert hm.ALLOWLIST == ()
    for s in list(world["houses"].values()) + [world["gold"]["gold_nlg_monthly"], world["gold"]["gold_usd_monthly"]]:
        with pytest.raises(hm.PublicationDenied):
            hm.publication_gate([s])


def test_production_files_unchanged_and_tool_names_no_public_path():
    assert hashlib.sha256((ROOT / "frontend/public/data/monthly.json").read_bytes()).hexdigest() == \
        "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"


def test_production_comparison_detects_difference(world, tmp_path):
    s = world["houses"]["cbs_grams_2000_onward_monthly"]
    good = {"data": [{"period": p.period, "gold_grams_per_house": float(p.value)} for p in s.points]}
    f = tmp_path / "p.json"
    f.write_text(json.dumps(good))
    assert float(h10.compare_production(s, f)["max_rel_diff"]) < 1e-12
    bad = {"data": [dict(r, gold_grams_per_house=r["gold_grams_per_house"] * 1.01) for r in good["data"]]}
    f.write_text(json.dumps(bad))
    assert float(h10.compare_production(s, f)["max_rel_diff"]) > 0.0099


def test_coverage_matrix_reports_nulls_and_counts(world):
    cov = h10.coverage_matrix(world["gold"], world["houses"], world["nvm"], {"price": world["price"], "count": world["count"]})
    assert cov["gold_usd_monthly"]["n"] == 312 and cov["nvm_grams_nlg_era"]["n"] == 48 and cov["nvm_grams_eur_era"]["n"] == 4
    assert cov["gold_nlg_monthly"]["first"] == "1975-01" and cov["gold_nlg_monthly"]["last"] == "1998-12"
