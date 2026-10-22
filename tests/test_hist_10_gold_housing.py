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
        # 16 days is above the 50% coverage threshold; the final month is complete (a partial final month is rejected)
        for day in range(1, (monthrange(int(m[:4]), int(m[5:]))[1] if m == last else 16) + 1):
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


# ---------------------------------------------------------------- Project Control decisions: audit tests
def fx_through(last_day, first=date(1998, 12, 1), unit="NLG_per_USD"):
    d, vals = first, {}
    from datetime import timedelta
    while d <= last_day:
        vals[d] = Decimal("2.0") + Decimal(d.day) / Decimal(100)
        d += timedelta(days=1)
    return h10.fx_daily_series("fed_nlg_per_usd_daily", vals, currency="NLG", unit=unit, source_id="s", raw_sha=RAW, definition="d")


@pytest.mark.parametrize("last,partial", [(date(1998, 12, 31), False), (date(1998, 12, 30), True), (date(1998, 12, 18), True),
                                          (date(1999, 1, 29), False), (date(1999, 1, 28), True)])
def test_partial_final_month_is_not_accepted_even_above_the_coverage_threshold(last, partial):
    first = last.replace(day=1)
    s = fx_through(last, first=first)
    strict = hm.monthly_mean(s, min_coverage=h10.MIN_DAY_COVERAGE, series_id="m_strict", complete_final_month=True)
    point = strict.points[-1]
    if partial:
        assert point.value is None and point.flags == ("PARTIAL_FINAL_MONTH",)
        assert last.day / 31 >= 0.5 or last.day >= 16  # it would have passed the 50% rule
    else:
        assert point.value is not None
    lax = hm.monthly_mean(s, min_coverage=h10.MIN_DAY_COVERAGE, series_id="m_lax")
    if last.day >= 16:
        assert lax.points[-1].value is not None  # without the rule the partial month would pass silently


def test_partial_final_month_propagates_to_a_null_gold_and_grams_period():
    first_days = {d: v for d, v in FED.items() if d < date(1998, 12, 1)}
    partial = {**first_days, **{date(1998, 12, d): Decimal("2.5") for d in range(1, 21)}}
    fed = h10.fx_daily_series("fed_nlg_per_usd_daily", partial, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW, definition="d")
    ecb = h10.fx_daily_series("ecb_usd_per_eur_daily", ECB, currency="USD", unit="USD_per_EUR", source_id="s", raw_sha=RAW, definition="d")
    gold = h10.build_gold(h10.gold_usd_series(WB, RAW), fed, ecb)
    assert pts(gold["fed_nlg_per_usd_monthly"])["1998-12"] is None
    assert pts(gold["gold_nlg_monthly"])["1998-12"] is None
    assert pts(gold["gold_nlg_half_mean"])["1998-H2"] is None  # no plausible-looking half-year value from a partial month
    nvm, _ = nvm_nlg_series()
    grams = pts(hm.grams_per_house(nvm, gold["gold_nlg_half_mean"], series_id="g"))
    assert grams.get("1998-H2") is None and max(grams) == "1998-H1"  # the result simply stops: no value is produced


def test_fx_coverage_report_flags_the_final_month():
    cov = h10.fx_coverage(dict(ECB), hm.monthly_mean(h10.fx_daily_series("ecb_usd_per_eur_daily", ECB, currency="USD", unit="USD_per_EUR",
                                                                         source_id="s", raw_sha=RAW, definition="d"),
                                                      min_coverage=h10.MIN_DAY_COVERAGE, series_id="m", complete_final_month=True))
    assert cov["final_month"] == "2000-12" and cov["final_month_complete"] is True and cov["null_months"] == []
    cut = {d: v for d, v in ECB.items() if d <= date(2000, 12, 20)}
    cov = h10.fx_coverage(cut, hm.monthly_mean(h10.fx_daily_series("ecb_usd_per_eur_daily", cut, currency="USD", unit="USD_per_EUR",
                                                                   source_id="s", raw_sha=RAW, definition="d"),
                                               min_coverage=h10.MIN_DAY_COVERAGE, series_id="m", complete_final_month=True))
    assert cov["final_month_complete"] is False and cov["null_months"] == [("2000-12", "PARTIAL_FINAL_MONTH")]


def test_fx_series_carry_direction_in_their_units(world):
    g = world["gold"]
    assert (g["fed_nlg_per_usd_daily"].unit, g["fed_nlg_per_usd_daily"].currency) == ("NLG_per_USD", "NLG")
    assert (g["ecb_usd_per_eur_daily"].unit, g["ecb_usd_per_eur_daily"].currency) == ("USD_per_EUR", "USD")
    assert g["gold_nlg_monthly"].unit == "NLG_per_troy_oz" and g["gold_eur_monthly"].unit == "EUR_per_troy_oz"


def test_era_boundary_and_retrospective_labels(world):
    g, h = world["gold"], world["houses"]
    assert [b.period for b in g["gold_nlg_monthly"].breaks] == ["1998-12"]
    assert [b.period for b in g["gold_eur_monthly"].breaks] == ["1999-01"]
    assert any(b.period == "1998-H2" and "NLG era ends" in b.reason for b in h["nvm_grams_nlg_era"].breaks)
    assert any(b.period == "1999-H1" and "observed-EUR era starts" in b.reason for b in h["nvm_grams_eur_era"].breaks)
    for name in ("gold_eur_retro_monthly", "nvm_grams_eur_retro", "cbs_grams_eur_retro_halfyear"):
        s = g.get(name) or h[name]
        assert all("RETROSPECTIVE_EUR" in p.flags for p in s.points), name
    for name in ("gold_nlg_monthly", "gold_eur_monthly", "nvm_grams_nlg_era"):
        s = g.get(name) or h[name]
        assert not any("RETROSPECTIVE_EUR" in p.flags for p in s.points), name
    # NVM_EUR is a redenomination of NLG source data, so the observed-EUR NVM grams carry the label through the house side only
    assert all("RETROSPECTIVE_EUR" in p.flags for p in h["nvm_median_eur_halfyear"].points)
    assert not any("RETROSPECTIVE_EUR" in p.flags for p in g["gold_eur_half_mean"].points)


def test_quality_levels_and_method_flag_reach_the_results(world):
    flags = {p.period: p.flags for p in world["houses"]["nvm_grams_nlg_era"].points}
    level = lambda f: [x for x in f if x.startswith("GOLD_LEVEL") or x.startswith("GOLD_ADR")]  # noqa: E731
    assert level(flags["1975-H1"]) == ["GOLD_LEVEL_B"] and level(flags["1978-H2"]) == ["GOLD_LEVEL_B"]
    assert level(flags["1979-H1"]) == ["GOLD_LEVEL_A"] and level(flags["1998-H2"]) == ["GOLD_LEVEL_A"]
    eur = {p.period: p.flags for p in world["houses"]["nvm_grams_eur_era"].points}
    assert level(eur["1999-H1"]) == ["GOLD_LEVEL_E"] and level(eur["2000-H1"]) == ["GOLD_ADR004_PERIOD"]
    for s in (world["houses"]["nvm_grams_nlg_era"], world["houses"]["nvm_grams_eur_era"], world["houses"]["cbs_grams_eur_halfyear"]):
        assert all(h10.METHOD_FLAG in p.flags and "HALF_RULE:MEAN" in p.flags for p in s.points)
    assert h10.METHOD_FLAG == "METHOD:HIST10_M1_V1"


def test_sensitivity_alternatives_are_not_primary_series(world):
    primary = {"nvm_grams_nlg_era", "nvm_grams_eur_era", "nvm_grams_eur_retro", "cbs_grams_eur_retro_halfyear", "cbs_grams_eur_halfyear"}
    assert primary <= set(world["houses"])
    assert all("half_mean" in s.series_id or s.series_id == "nvm_median_eur_halfyear" or "grams" in s.series_id or "price" in s.series_id
               for s in world["houses"].values())
    # grams use the M1 gold series only
    lineage_ids = {sid for s in (world["houses"]["nvm_grams_nlg_era"],) for sid, _ in s.inputs}
    assert lineage_ids == {"nvm_median_nlg_halfyear", "gold_nlg_half_mean"}


def test_m1_vs_m2_difference_is_small_and_ordered_on_synthetic_data(world):
    m1, m2 = pts(world["gold"]["gold_nlg_half_mean"]), pts(world["gold"]["gold_nlg_half_ratio_of_means"])
    assert set(m1) == set(m2) and any(m1[p] != m2[p] for p in m1)
    assert max(abs(Fraction(m1[p]) / Fraction(m2[p]) - 1) for p in m1) < Fraction(5, 100)


# ---- source vintage and pins
def points_for_hash():
    return {f"1975-{m:02d}": Decimal(100 + m) for m in range(1, 13)}


def test_window_hash_ignores_appended_data_but_detects_a_revision_inside_the_window():
    pts0 = points_for_hash()
    a = h10.window_hash(pts0, "1975-01", "1975-12")
    appended = {**pts0, "1976-01": Decimal(999)}
    assert h10.window_hash(appended, "1975-01", "1975-12") == a  # newer observations do not change the pinned window
    revised = {**pts0, "1975-06": Decimal(999)}
    assert h10.window_hash(revised, "1975-01", "1975-12")["sha256"] != a["sha256"]
    assert h10.window_hash({k: v for k, v in pts0.items() if k != "1975-06"}, "1975-01", "1975-12")["n"] == 11
    assert h10.window_hash({k: Decimal(str(v) + ".0") for k, v in pts0.items()}, "1975-01", "1975-12") == a  # canonical decimals
    with pytest.raises(h10.Hist10Error):
        h10.window_hash(pts0, "1990-01", "1990-12")


def test_pin_check_distinguishes_a_changed_source_from_the_pinned_result(world):
    wb = {m: v for m, v in WB.items()}
    cur = {"world_bank_gold_monthly": h10.window_hash(wb, "1975-01", "2000-12"),
           "fed_nlg_per_usd_daily": h10.window_hash({d.isoformat(): v for d, v in FED.items()}, "1975-01-01", "1998-12-31"),
           "ecb_usd_per_eur_daily": h10.window_hash({d.isoformat(): v for d, v in ECB.items()}, "1999-01-01", "2000-12-31")}
    derived = h10.derived_values_sha256(world["houses"])
    pins = {"method_id": h10.METHOD_ID, "sources": cur, "derived": {"halfyear_values_sha256": derived}}
    assert h10.check_pins(cur, derived, pins)["status"] == "MATCH"
    assert h10.check_pins(cur, derived, None)["status"] == "UNPINNED"
    revised = {**cur, "world_bank_gold_monthly": h10.window_hash({**wb, "1980-01": Decimal(1)}, "1975-01", "2000-12")}
    out = h10.check_pins(revised, "different", pins)
    assert out["status"] == "SOURCE_REVISED" and out["sources"]["world_bank_gold_monthly"] == "REVISED"
    assert h10.check_pins(cur, "different", pins)["status"] == "DEFECT_DERIVED_DRIFT"  # same sources, different values: code defect
    assert h10.check_pins(cur, derived, {**pins, "method_id": "OTHER"})["status"] == "METHOD_CHANGED"
    missing = {**pins, "sources": {k: v for k, v in cur.items() if k != "fed_nlg_per_usd_daily"}}
    assert h10.check_pins(cur, derived, missing)["status"] == "UNPINNED"


def test_derived_values_hash_is_stable_and_value_sensitive(world):
    a = h10.derived_values_sha256(world["houses"])
    assert a == h10.derived_values_sha256(world["houses"])
    s = world["houses"]["nvm_grams_nlg_era"]
    changed = dict(world["houses"], nvm_grams_nlg_era=replace(s, points=(replace(s.points[0], value=s.points[0].value + 1),) + s.points[1:]))
    assert h10.derived_values_sha256(changed) != a


def test_acquisition_timestamp_is_recorded_and_changes_bundles_not_derived_values():
    stamp1, stamp2 = "2026-10-22T10:00:00+00:00", "2026-10-23T10:00:00+00:00"

    def build(stamp):
        g = h10.build_gold(h10.gold_usd_series(WB, RAW, acquired_at=stamp),
                           h10.fx_daily_series("fed_nlg_per_usd_daily", FED, currency="NLG", unit="NLG_per_USD", source_id="s", raw_sha=RAW,
                                               definition="d", acquired_at=stamp),
                           h10.fx_daily_series("ecb_usd_per_eur_daily", ECB, currency="USD", unit="USD_per_EUR", source_id="s", raw_sha=RAW,
                                               definition="d", acquired_at=stamp))
        nvm, _ = nvm_nlg_series()
        price, count, fixture, csv_s = cbs_series()
        return g, h10.build_housing_grams(g, nvm, price, count, fixture, csv_s), nvm, price, count, fixture, csv_s
    a, b = build(stamp1), build(stamp2)
    assert all(o.retrieved_at == stamp1 for o in a[0]["gold_usd_monthly"].observations)
    assert h10.derived_values_sha256(a[1]) == h10.derived_values_sha256(b[1])
    ba = hb.bundle_bytes(hb.build_bundle(h10.bundles(h10.all_series(a[0], a[1], *a[2:]))["A_gold_original"]))
    bb = hb.bundle_bytes(hb.build_bundle(h10.bundles(h10.all_series(b[0], b[1], *b[2:]))["A_gold_original"]))
    assert ba != bb  # the bundle bytes identify the acquisition; the derived values hash identifies the result


def test_manifest_records_identifiers_hashes_method_and_quality(world):
    m = h10.build_manifest(acquired_at="2026-10-22T10:00:00+00:00", source_ids={"world_bank_gold": "id"}, source_hashes={"x": "y"},
                           windows={"w": {}}, derived_hash="d" * 64, bundle_digests={"b.json": {"sha256": "e" * 64}}, vintage={"status": "MATCH"})
    assert m["method_id"] == "HIST10_M1_V1" and m["acquired_at_utc"].startswith("2026-10-22") and m["derived_halfyear_values_sha256"] == "d" * 64
    assert m["bundle_sha256"] == {"b.json": "e" * 64} and set(m["quality_flags"]) >= {"GOLD_LEVEL_B", "GOLD_LEVEL_A", "RETROSPECTIVE_EUR"}
    assert "code determinism only" in m["note"] and "M5" in m["method"]["sensitivity_only"]


def test_committed_pin_file_holds_hashes_only_and_matches_the_method():
    pins = json.loads((ROOT / "data" / "fixtures" / "hist10" / "source_pins.json").read_text())
    assert pins["method_id"] == h10.METHOD_ID and set(pins["sources"]) == set(h10.PIN_WINDOWS)
    for name, w in pins["sources"].items():
        assert (w["first"], w["last"]) == h10.PIN_WINDOWS[name] or w["first"] >= h10.PIN_WINDOWS[name][0]
        assert len(w["sha256"]) == 64 and int(w["sha256"], 16) >= 0 and w["n"] > 0
        assert set(w) == {"first", "last", "n", "sha256"}  # no raw values
    assert len(pins["derived"]["halfyear_values_sha256"]) == 64 and pins["derived"]["series"] == list(h10.DERIVED_PIN_SERIES)
    assert "RESEARCH PIN" in pins["status"] and "no raw third-party data" in pins["status"]
