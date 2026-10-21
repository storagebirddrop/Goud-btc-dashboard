"""ARCH-02: tests for the research-only historical data model (etl/hist_model.py). Offline, stdlib only."""
import hashlib
import json
import random
import re
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

import etl.hist_model as hm
from etl.hist_model import (
    ALLOWLIST, Break, CurrencyMismatch, DefinitionMismatch, FrequencyError, ModelError, Observation, OverlapError,
    Point, PublicationDenied, ReleaseRecord, RevisionError, Series, canonical_json, convert_currency,
    coverage_report, deflate, detect_revisions, grams_per_house, monthly_mean, publication_gate, publication_rows,
    rebase_index, rebase_pair, redenominate_nlg_to_eur, relative_performance, relative_performance_from_levels,
    release_hash, require_no_revisions, sats_per_house, series_from_dict, series_sha256, validate_bundle,
    validate_series,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = "a" * 64
MONTHS = ["2000-01", "2000-02", "2000-03", "2000-04"]


def src(sid, values, *, freq="monthly", ccy="EUR", unit=None, kind="average_price", asset="housing",
        basis="nominal", index_base=None, vintage="v1", quality="CONFIRMED", flags=(), breaks=(), raw=RAW):
    unit = unit or ccy
    rows = tuple(Observation(sid, p, v, ccy, unit, f"def_{sid}", "fixture", raw, "2026-10-21T00:00:00+00:00",
                             vintage, quality, flags) for p, v in values.items())
    return Series(sid, "source", asset, freq, ccy, unit, f"def_{sid}", kind, basis, index_base, tuple(breaks), rows)


def house(values=None, **kw):
    return src("house_eur", values or dict(zip(MONTHS, ["300000", "303000", "306000", "309000"])), **kw)


def gold(values=None, ccy="EUR", **kw):
    return src("gold_eur_oz", values or dict(zip(MONTHS, ["300", "310", "330", "320"])), ccy=ccy,
               unit=f"{ccy}_per_troy_oz", kind="spot_price", asset="gold", **kw)


def btc(values=None, **kw):
    return src("btc_eur", values or dict(zip(MONTHS, ["1000", "2000", "4000", "3000"])), unit="EUR_per_BTC",
               kind="spot_price", asset="bitcoin", **kw)


def hpi(values=None, **kw):
    return src("hpi", values or dict(zip(MONTHS, ["50", "51", "52", "55"])), ccy="INDEX", unit="index_points",
               kind="constant_quality_index", index_base="2020=100", **kw)


def vals(s):
    return {p.period: p.value for p in s.points}


def close(a, b):
    return abs(Fraction(a) - b) <= abs(b) * Fraction(1, 10 ** 27)


def release_for(*series, restricted=()):
    return ReleaseRecord("rel1", release_hash(series), "owner", "2026-10-21", "DECIDED-X",
                         tuple(s.series_id for s in series), tuple(restricted))


# ---- layer 1 invariants --------------------------------------------------------------------------
def test_valid_source_series_passes():
    validate_series(house())
    validate_series(house({"2000": "1"}, freq="annual"))
    validate_series(src("d", {"2000-01-01": "1", "2000-01-02": "2"}, freq="daily"))


@pytest.mark.parametrize("make,message", [
    (lambda: src("h", {"2000-02": "1", "2000-01": "2"}), "ascending"),
    (lambda: src("h", {"2000": "1"}), "valid monthly"),
    (lambda: src("h", {"2000-13": "1"}), "real monthly"),
    (lambda: src("h", {"2000-02-30": "1"}, freq="daily"), "real daily"),
    (lambda: src("h", {"2000-01": "1"}, freq="weekly"), "frequency"),
    (lambda: src("h", {"2000-01": "0"}), "positive"),
    (lambda: src("h", {"2000-01": "-3"}), "positive"),
    (lambda: src("h", {"2000-01": "1"}, quality="GOOD"), "quality"),
    (lambda: src("h", {"2000-01": "1"}, flags=("bad flag",)), "flag"),
    (lambda: src("h", {"2000-01": "1"}, ccy="GBP"), "currency"),
    (lambda: src("H", {"2000-01": "1"}), "series_id"),
    (lambda: src("h", {"2000-01": "1"}, kind="mystery"), "kind"),
    (lambda: src("h", {"2000-01": "1"}, basis="adjusted"), "basis"),
    (lambda: src("h", {"2000-01": "1"}, raw="xyz"), "raw_sha256"),
    (lambda: src("h", {"2000-01": "1"}, ccy="INDEX", unit="index_points"), "index_base"),
    (lambda: src("h", {"2000-01": "1"}, index_base="2000=100"), "index_base"),
    (lambda: src("h", {"2000-01": "1"}, breaks=(Break("2000-01", ""),)), "break"),
    (lambda: src("h", {"2000-01": "1"}, breaks=(Break("2000-01-05", "x"),)), "monthly"),
])
def test_negative_series_fixtures(make, message):
    with pytest.raises(ModelError, match=message):
        validate_series(make())


def test_duplicate_period_is_rejected_explicitly():
    a = house().observations
    with pytest.raises(ModelError, match="duplicate period"):
        validate_series(replace(house(), observations=(a[0], a[0])))


@pytest.mark.parametrize("bad", [1.5, 100, True, None, "NaN", "Infinity", "", " 5", "1,5", "abc"])
def test_values_must_be_decimal_strings(bad):
    with pytest.raises(ModelError):
        Observation("h", "2000-01", bad, "EUR", "EUR", "d", "s", RAW, "2026-10-21T00:00:00Z", "v1", "CONFIRMED")


@pytest.mark.parametrize("field,value", [("source_id", ""), ("vintage", ""), ("retrieved_at", "yesterday"),
                                         ("retrieved_at", "2026-10-21T00:00:00"), ("raw_sha256", "A" * 64),
                                         ("currency", "USD"), ("unit", "USD"), ("definition_id", "other")])
def test_provenance_and_unit_integrity_required(field, value):
    s = house()
    bad = replace(s.observations[1], **{field: value})
    with pytest.raises(ModelError):
        validate_series(replace(s, observations=(s.observations[0], bad) + s.observations[2:]))


def test_one_vintage_per_series_object():
    s = house()
    mixed = replace(s.observations[0], vintage="v2")
    with pytest.raises(RevisionError, match="one vintage"):
        validate_series(replace(s, observations=(mixed,) + s.observations[1:]))


def test_source_series_cannot_carry_derived_fields_and_derived_needs_lineage():
    with pytest.raises(ModelError, match="source series holds observations only"):
        validate_series(replace(house(), transforms=({"op": "x"},)))
    with pytest.raises(ModelError, match="needs points, lineage"):
        validate_series(Series("d", "derived", "housing", "monthly", "EUR", "EUR", "d", "average_price",
                               points=(Point("2000-01", "1", "CONFIRMED"),)))


# ---- coverage, no filling, no frequency conversion -----------------------------------------------
def test_coverage_report_lists_explicit_gaps_and_never_fills():
    s = house({"2000-01": "1", "2000-04": "2"})
    r = coverage_report(s)
    assert r["missing"] == ["2000-02", "2000-03"] and not r["complete"]
    assert (r["expected"], r["present"], r["coverage"]) == (4, 2, "0.5")
    assert len(s.observations) == 2  # the series itself is untouched
    wide = coverage_report(s, "1999-12", "2000-05")
    assert wide["missing"][0] == "1999-12" and wide["missing"][-1] == "2000-05"
    assert coverage_report(s, "2000-02", "2000-03")["outside_range"] == ["2000-01", "2000-04"]
    assert coverage_report(house())["complete"]


def test_coverage_requires_range_for_empty_series():
    empty = replace(house(), points=(Point("2000-01", None, "UNRESOLVED"),), observations=())
    with pytest.raises(ModelError):
        coverage_report(empty)
    assert coverage_report(empty, "2000-01", "2000-02")["missing"] == ["2000-01", "2000-02"]


@pytest.mark.parametrize("freq,target", [("annual", "monthly"), ("annual", "daily"), ("monthly", "daily"),
                                         ("daily", "monthly"), ("monthly", "annual")])
def test_frequency_conversion_always_raises(freq, target):
    values = {"annual": {"2000": "1"}, "monthly": {"2000-01": "1"}, "daily": {"2000-01-01": "1"}}[freq]
    with pytest.raises(FrequencyError, match="not allowed"):
        hm.convert_frequency(src("h", values, freq=freq), target)


def test_no_fill_interpolation_or_annual_to_monthly_function_exists():
    names = [n.lower() for n in dir(hm)]
    for banned in ("interpol", "ffill", "forward", "backfill", "fillna", "annual_to_monthly", "upsample", "resample"):
        assert not [n for n in names if banned in n], banned
    code = (ROOT / "etl" / "hist_model.py").read_text(encoding="utf-8")
    assert not re.search(r"def\s+\w*(fill|interpol|annual_to_monthly)", code, re.I)


def test_mixing_annual_and_monthly_in_a_derivation_raises():
    with pytest.raises(FrequencyError, match="never converted"):
        grams_per_house(house(), gold({"2000": "300"}, freq="annual"))


# ---- layer 2 transformations ---------------------------------------------------------------------
def test_redenomination_applies_constant_once_and_records_it():
    nlg = src("house_nlg", {"1995-01": "220371", "1995-02": "440742"}, ccy="NLG")
    eur = redenominate_nlg_to_eur(nlg, series_id="house_eur_hist")
    assert vals(eur) == {"1995-01": Decimal("100000"), "1995-02": Decimal("200000")}
    step = eur.transforms[-1]
    assert (step["op"], step["constant"], step["applied"]) == ("redenominate", "2.20371", 1)
    assert eur.currency == "EUR" and eur.layer == "normalized" and "REDENOMINATED" in eur.points[0].flags
    assert eur.inputs == (("house_nlg", series_sha256(nlg)),)
    with pytest.raises(CurrencyMismatch, match="already applied"):
        redenominate_nlg_to_eur(eur, series_id="again")
    with pytest.raises(CurrencyMismatch, match="needs currency NLG"):
        redenominate_nlg_to_eur(house(), series_id="eur_never")
    forged = replace(nlg, layer="normalized", observations=(), inputs=(("x_y", RAW),),
                     points=(Point("1995-01", "1", "CONFIRMED"),), transforms=({"op": "redenominate"},))
    with pytest.raises(CurrencyMismatch, match="already applied"):
        redenominate_nlg_to_eur(forged, series_id="twice")


def fx(values, **kw):
    return src("usd_per_eur", values, ccy="USD", unit="USD_per_EUR", kind="fx_rate", asset="fx", **kw)


def test_currency_conversion_needs_explicit_directional_rate():
    usd = gold(ccy="USD")
    rate = fx(dict(zip(MONTHS, ["1", "1.25", "2", "2"])))
    eur = convert_currency(usd, rate, to_currency="EUR", series_id="gold_eur_conv")
    assert eur.currency == "EUR" and eur.unit == "EUR_per_troy_oz"
    assert vals(eur)["2000-02"] == Decimal("310") / Decimal("1.25")
    assert eur.transforms[-1]["rate_series"] == "usd_per_eur"
    assert [i[0] for i in eur.inputs] == ["gold_eur_oz", "usd_per_eur"]
    inverse = replace(rate, unit="EUR_per_USD",
                      observations=tuple(replace(o, unit="EUR_per_USD") for o in rate.observations))
    with pytest.raises(CurrencyMismatch, match="expected USD_per_EUR"):
        convert_currency(usd, inverse, to_currency="EUR", series_id="x")
    with pytest.raises(CurrencyMismatch, match="redenomination"):
        convert_currency(src("n", {"2000-01": "1"}, ccy="NLG"), rate, to_currency="EUR", series_id="x")
    with pytest.raises(CurrencyMismatch):
        convert_currency(house(), hpi(), to_currency="EUR", series_id="x")


def test_currency_conversion_frequency_overlap_and_null_propagation():
    usd = gold(ccy="USD")
    with pytest.raises(FrequencyError, match="aggregate the rate first"):
        convert_currency(usd, fx({"2000": "1"}, freq="annual"), to_currency="EUR", series_id="x")
    with pytest.raises(OverlapError):
        convert_currency(usd, fx({"1999-01": "1"}), to_currency="EUR", series_id="x")
    out = convert_currency(usd, fx({"2000-01": "2", "2000-03": "2"}, quality="INFERRED"), to_currency="EUR",
                           series_id="x")
    assert vals(out)["2000-02"] is None and vals(out)["2000-04"] is None  # gaps stay null
    assert out.points[1].flags == ("MISSING_INPUT",) and out.points[0].quality == "INFERRED"


def daily(values, **kw):
    return src("fx", values, freq="daily", ccy="USD", unit="USD_per_EUR", kind="fx_rate", asset="fx", **kw)


def test_monthly_mean_full_partial_and_explicit_threshold():
    days = {f"2000-01-{d:02d}": str(d) for d in range(1, 32)}
    days.update({"2000-02-01": "10", "2000-02-02": "20"})
    s = daily(days)
    out = monthly_mean(s, min_coverage=Decimal("1"), series_id="fx_m")
    assert out.frequency == "monthly" and vals(out)["2000-01"] == Decimal("16")
    assert vals(out)["2000-02"] is None and out.points[1].flags == ("INSUFFICIENT_DAILY_COVERAGE",)
    assert "DAYS:31/31" in out.points[0].flags
    loose = monthly_mean(s, min_coverage=Decimal("0.05"), series_id="fx_m")
    assert vals(loose)["2000-02"] == Decimal("15")
    assert loose.transforms[-1]["min_coverage"] == "0.05"
    with pytest.raises(TypeError):
        monthly_mean(s, series_id="x")  # the threshold is never implicit
    for bad in ("0", "1.5"):
        with pytest.raises(ModelError):
            monthly_mean(s, min_coverage=Decimal(bad), series_id="x")


def test_monthly_mean_requires_daily_input_and_maps_breaks_to_months():
    with pytest.raises(FrequencyError):
        monthly_mean(house(), min_coverage=Decimal("1"), series_id="x")
    s = daily({"2000-01-01": "1", "2000-01-02": "3"}, breaks=(Break("2000-01-02", "source change"),))
    out = monthly_mean(s, min_coverage=Decimal("0.01"), series_id="fx_m")
    assert out.breaks == (Break("2000-01", "fx: source change"),) and vals(out)["2000-01"] == Decimal("2")


def test_monthly_mean_missing_whole_month_is_explicit_gap():
    out = monthly_mean(daily({"2000-01-01": "1", "2000-03-01": "3"}), min_coverage=Decimal("0.01"), series_id="m")
    assert [p.period for p in out.points] == ["2000-01", "2000-02", "2000-03"] and out.points[1].value is None


def test_deflate_keeps_nominal_and_real_apart():
    cpi = src("cpi", dict(zip(MONTHS, ["100", "110", "120", "125"])), ccy="INDEX", unit="index_points", kind="cpi",
              asset="cpi", index_base="2000-01=100")
    real = deflate(house(), cpi, base_period="2000-01", series_id="house_real")
    assert real.basis == "real" and vals(real)["2000-03"] == Decimal("306000") * 100 / Decimal("120")
    assert real.unit == "EUR@2000-01"
    with pytest.raises(DefinitionMismatch, match="nominal"):
        deflate(real, cpi, base_period="2000-01", series_id="again")
    with pytest.raises(DefinitionMismatch, match="nominal and real"):
        grams_per_house(real, gold(), series_id="mix")  # real house vs nominal gold
    with pytest.raises(OverlapError):
        deflate(house(), cpi, base_period="1999-12", series_id="x")


# ---- layer 3 derived comparisons: formulas cross-checked independently ----------------------------
def test_grams_per_house_matches_independent_fraction_formula():
    h, g = house(), gold()
    out = grams_per_house(h, g)
    assert out.layer == "derived" and out.unit == "gram" and out.currency == "NONE"
    for hv, gv, point in zip(h.observations, g.observations, out.points):
        assert close(point.value, Fraction(hv.value) * Fraction("31.1034768") / Fraction(gv.value))
    assert out.inputs == (("house_eur", series_sha256(h)), ("gold_eur_oz", series_sha256(g)))
    assert out.transforms[-1]["formula"] == "house * 31.1034768 / gold_per_oz"


def test_grams_per_house_unit_and_definition_integrity():
    with pytest.raises(CurrencyMismatch, match="expected 'EUR_per_troy_oz'"):
        grams_per_house(house(), gold(ccy="USD"))
    with pytest.raises(DefinitionMismatch, match="average_price"):
        grams_per_house(hpi(), gold())  # an index is not a price level
    with pytest.raises(DefinitionMismatch, match="spot_price"):
        grams_per_house(house(), house())
    nlg_house = src("house_nlg", {m: "600" for m in MONTHS}, ccy="NLG")
    nlg_gold = gold({m: "2" for m in MONTHS}, ccy="NLG")
    assert vals(grams_per_house(nlg_house, nlg_gold))["2000-01"] == Decimal("300") * Decimal("31.1034768")


def test_sats_per_house_matches_independent_formula():
    h, b = house(), btc()
    out = sats_per_house(h, b)
    for hv, bv, point in zip(h.observations, b.observations, out.points):
        assert close(point.value, Fraction(hv.value) / Fraction(bv.value) * 100000000)
    assert out.asset_class == "bitcoin" and out.unit == "satoshi"
    with pytest.raises(CurrencyMismatch):
        sats_per_house(house(), gold())


def test_common_baseline_is_detected_from_overlap_and_refuses_disjoint_ranges():
    a = gold({"2000-02": "310", "2000-03": "330", "2000-04": "320"})
    h = house({"2000-01": "300000", "2000-02": "303000", "2000-03": "306000"})
    assert hm.common_base_period(a, h) == "2000-02"
    assert hm.common_base_period(a, h, "2000-03") == "2000-03"
    with pytest.raises(OverlapError, match="outside the overlap"):
        hm.common_base_period(a, h, "2000-01")
    with pytest.raises(OverlapError, match="do not overlap"):
        hm.common_base_period(gold({"2000-04": "1"}), house({"2000-01": "1"}))
    with pytest.raises(OverlapError):
        relative_performance_from_levels(gold({"2000-04": "1"}), house({"2000-01": "1"}))


def test_gap_inside_overlap_is_not_a_base_period():
    ga, gh = rebase_pair(gold({"2000-01": "300", "2000-02": "310"}), house({"2000-02": "1", "2000-03": "2"}))
    assert ga.index_base == gh.index_base == "2000-02=100"


def test_relative_performance_matches_independent_formula():
    a, h = gold(), house()
    out = relative_performance_from_levels(a, h)
    assert out.currency == "INDEX" and out.index_base == "2000-01=100" and vals(out)["2000-01"] == Decimal("100")
    av = [Fraction(o.value) for o in a.observations]
    hv = [Fraction(o.value) for o in h.observations]
    for i, point in enumerate(out.points):
        assert close(point.value, 100 * (av[i] / av[0]) / (hv[i] / hv[0]))


def test_relative_performance_on_hpi_uses_one_base_for_both_sides():
    out = relative_performance_from_levels(gold(), hpi(), base_period="2000-02")
    assert out.index_base == "2000-02=100" and vals(out)["2000-02"] == Decimal("100")
    assert out.transforms[-1]["base_period"] == "2000-02"


def test_relative_performance_refuses_different_bases_and_unconverted_levels():
    a1, h1 = rebase_pair(gold(), house(), "2000-01")
    a2 = rebase_index(gold(), "2000-02", series_id="gold_b")
    with pytest.raises(CurrencyMismatch, match="index bases differ"):
        relative_performance(a2, h1)
    with pytest.raises(CurrencyMismatch, match="explicit step"):
        relative_performance(gold(), h1)
    with pytest.raises(CurrencyMismatch, match="explicit step"):
        relative_performance(a1, house())
    assert relative_performance(a1, h1).layer == "derived"


def test_relative_performance_refuses_unnormalised_source_index_base():
    with pytest.raises(CurrencyMismatch, match="index bases differ"):
        relative_performance(rebase_index(gold(), "2000-01", series_id="g"), hpi())  # hpi is 2020=100


@pytest.mark.parametrize("a_kind,b_kind", [("price_return", "total_return"), ("total_return", "price_return"),
                                           ("average_price", "constant_quality_index"),
                                           ("constant_quality_index", "average_price")])
def test_definition_kinds_cannot_be_mixed(a_kind, b_kind):
    a = replace(rebase_index(gold(), "2000-01", series_id="a_i"), kind=a_kind)
    b = replace(rebase_index(gold(), "2000-01", series_id="b_i"), kind=b_kind)
    with pytest.raises(DefinitionMismatch, match="cannot be mixed"):
        relative_performance(a, b)


def test_rebase_index_requires_value_at_base_and_is_not_a_price():
    with pytest.raises(OverlapError):
        rebase_index(gold({"2000-02": "1"}), "2000-01", series_id="x")
    idx = rebase_index(gold(), "2000-01", series_id="g_idx")
    assert idx.currency == "INDEX" and idx.index_base == "2000-01=100" and idx.unit == "index_points"
    with pytest.raises(CurrencyMismatch):
        grams_per_house(house(), idx)  # unit EUR_per_troy_oz required


def test_quality_flags_and_breaks_are_carried_through_derivations():
    h = house(breaks=(Break("2000-02", "CBS revision"),), flags=("PRELIMINARY",))
    g = gold(quality="INFERRED", breaks=(Break("2000-02", "World Bank source change"),))
    out = grams_per_house(h, g)
    assert all(p.quality == "INFERRED" and "PRELIMINARY" in p.flags for p in out.points)
    assert [b.period for b in out.breaks] == ["2000-02"]
    assert "CBS revision" in out.breaks[0].reason and "World Bank source change" in out.breaks[0].reason
    idx = rebase_index(g, "2000-01", series_id="g_i")
    assert idx.breaks == g.breaks and idx.points[0].quality == "INFERRED"
    chained = relative_performance(idx, rebase_index(h, "2000-01", series_id="h_i"))
    assert chained.breaks and chained.points[0].quality == "INFERRED" and "PRELIMINARY" in chained.points[0].flags


def test_unresolved_quality_wins_over_better_labels():
    assert hm.worst_quality("CONFIRMED", "UNRESOLVED", "PROPOSED") == "UNRESOLVED"
    assert hm.worst_quality("CONFIRMED", "PROPOSED") == "PROPOSED"


# ---- revisions ------------------------------------------------------------------------------------
def test_revisions_value_hash_and_dropped_are_flagged_not_overwritten():
    old = house()
    changed = list(house(vintage="v2").observations)
    changed[0] = replace(changed[0], value="301000")
    changed[1] = replace(changed[1], raw_sha256="b" * 64)
    new = replace(house(vintage="v2"), observations=tuple(changed[:3]))
    found = detect_revisions(old, new)
    assert [(r.period, r.kind) for r in found] == [("2000-01", "value_changed"), ("2000-02", "hash_changed"),
                                                   ("2000-04", "dropped")]
    assert found[0].old_value == "300000" and found[0].new_value == "301000" and found[2].new_value is None
    assert old.observations[0].value == Decimal("300000")  # the earlier vintage is untouched
    with pytest.raises(RevisionError, match="human review"):
        require_no_revisions(found)


def test_new_periods_and_identical_vintages_are_not_revisions():
    old = house({"2000-01": "1", "2000-02": "2"})
    assert detect_revisions(old, house({"2000-01": "1", "2000-02": "2", "2000-03": "3"}, vintage="v2")) == ()
    require_no_revisions(())
    with pytest.raises(RevisionError, match="re-issued"):
        detect_revisions(old, house({"2000-01": "9", "2000-02": "2"}))  # same vintage label, different content


def test_revision_detection_needs_same_source_series():
    with pytest.raises(RevisionError):
        detect_revisions(house(), gold(vintage="v2"))
    with pytest.raises(RevisionError):
        detect_revisions(house(), grams_per_house(house(), gold()))


# ---- canonical serialization and hashing ---------------------------------------------------------
def test_canonical_json_is_sorted_compact_ascii_decimal_strings():
    raw = canonical_json({"b": Decimal("1.50"), "a": [Decimal("100"), Decimal("0.000")], "\u00e9": None})
    assert raw == b'{"a":["100","0"],"b":"1.5","\\u00e9":null}\n'
    with pytest.raises(ModelError):
        canonical_json({"x": 1.5})


def test_hashes_are_deterministic_and_value_sensitive():
    assert series_sha256(house()) == series_sha256(house())
    assert series_sha256(house({"2000-01": "1.50"})) == series_sha256(house({"2000-01": "1.5"}))
    assert series_sha256(house({"2000-01": "1.5"})) != series_sha256(house({"2000-01": "1.6"}))
    assert series_sha256(house(raw="b" * 64)) != series_sha256(house())
    assert series_sha256(house()) == hashlib.sha256(canonical_json(house())).hexdigest()
    a, b = grams_per_house(house(), gold()), grams_per_house(house(), gold())
    assert canonical_json(a) == canonical_json(b) and series_sha256(a) == series_sha256(b)
    other = grams_per_house(house(), gold({"2000-01": "301", "2000-02": "310"}))
    assert series_sha256(other) != series_sha256(a)


def test_serialization_round_trip_is_key_order_independent():
    s = grams_per_house(house(), gold())
    items = list(json.loads(canonical_json(s)).items())
    random.Random(7).shuffle(items)
    assert series_sha256(series_from_dict(dict(items))) == series_sha256(s)
    src_doc = json.loads(canonical_json(house()))
    assert series_sha256(series_from_dict(src_doc)) == series_sha256(house())
    with pytest.raises(ModelError, match="unexpected series keys"):
        series_from_dict({**src_doc, "extra": 1})


def test_lineage_hash_changes_when_an_input_changes():
    a = grams_per_house(house(), gold())
    b = grams_per_house(house(raw="c" * 64), gold())
    assert a.inputs != b.inputs and series_sha256(a) != series_sha256(b)


def test_decimal_precision_is_not_rounded_for_display():
    out = grams_per_house(house({"2000-01": "300000"}), gold({"2000-01": "7"}))
    text = hm.dec_str(out.points[0].value)
    assert len(text.replace(".", "")) >= 30 and "e" not in text.lower()


# ---- publication gate ------------------------------------------------------------------------------
def make_derived():
    return grams_per_house(house(), gold())


def test_default_allowlist_is_empty_and_denies_everything():
    assert ALLOWLIST == ()
    with pytest.raises(PublicationDenied, match="allowlist"):
        publication_gate([make_derived()])
    assert publication_gate([]) == ()


def test_authorized_release_publishes_only_matching_hash():
    s = make_derived()
    assert publication_gate([s], [release_for(s)]) == (s,)
    tampered = replace(s, points=(replace(s.points[0], value=s.points[0].value + 1),) + s.points[1:])
    with pytest.raises(PublicationDenied, match="hash differs"):
        publication_gate([tampered], [release_for(s)])


def test_gate_denies_unlisted_second_series_and_missing_members():
    s, t = make_derived(), grams_per_house(house(), gold(), series_id="other_grams")
    with pytest.raises(PublicationDenied, match="other_grams"):
        publication_gate([s, t], [release_for(s)])
    with pytest.raises(PublicationDenied, match="not supplied"):
        publication_gate([s], [release_for(s, t)])


def test_gate_denies_raw_source_observations():
    h = house()
    with pytest.raises(PublicationDenied, match="never published"):
        publication_gate([h], [release_for(h)])


def test_bitcoin_and_equity_ids_are_denied_unless_explicitly_authorized():
    sats = sats_per_house(house(), btc())
    with pytest.raises(PublicationDenied, match="bitcoin/equity"):
        publication_gate([sats], [release_for(sats)])
    assert publication_gate([sats], [release_for(sats, restricted=["sats_per_house"])]) == (sats,)
    other = replace(sats, series_id="sat_per_house")
    with pytest.raises(PublicationDenied, match="bitcoin/equity"):
        publication_gate([other], [release_for(other)])
    with pytest.raises(PublicationDenied, match="incomplete"):  # authorization must name a member of the record
        publication_gate([sats], [release_for(sats, restricted=["not_a_member"])])


@pytest.mark.parametrize("sid", ["btc_eur_rel", "bitcoin_index", "sp500_vs_house", "aex_rel", "equity_ratio",
                                 "house_in_sats", "spx_total"])
def test_restricted_tokens_in_ids_are_denied_even_when_class_is_mislabelled(sid):
    s = replace(make_derived(), series_id=sid)
    assert s.asset_class == "housing"
    with pytest.raises(PublicationDenied, match="bitcoin/equity"):
        publication_gate([s], [release_for(s)])


def test_restricted_input_lineage_taints_derived_series():
    bad = replace(make_derived(), series_id="neutral_name", inputs=(("btc_eur", RAW), ("house_eur", RAW)))
    assert hm.is_restricted(bad)
    equity = src("idx_total", {m: "1" for m in MONTHS}, ccy="INDEX", unit="index_points", kind="total_return",
                 asset="equity", index_base="2000-01=100")
    derived = relative_performance(rebase_index(equity, "2000-01", series_id="eq_i"),
                                   rebase_index(hpi(), "2000-01", series_id="h_i"))
    assert derived.asset_class == "equity" and hm.is_restricted(derived)


def test_gate_denies_unresolved_values_and_incomplete_records():
    s = make_derived()
    flawed = replace(s, points=(replace(s.points[0], quality="UNRESOLVED"),) + s.points[1:])
    with pytest.raises(PublicationDenied, match="UNRESOLVED"):
        publication_gate([flawed], [release_for(flawed)])
    good = release_for(s)
    for change in ({"authorizer": " "}, {"decision_ref": ""}, {"release_sha256": "zz"}, {"series_ids": ()},
                   {"authorized_on": "21-10-2026"}, {"release_id": ""}):
        with pytest.raises(PublicationDenied, match="incomplete|ISO date"):
            publication_gate([s], [replace(good, **change)])
    with pytest.raises(PublicationDenied, match="two release records"):
        publication_gate([s], [good, replace(good, release_id="rel2")])
    with pytest.raises(PublicationDenied, match="duplicate candidate"):
        publication_gate([s, s], [good])


def test_publication_rows_are_monthly_decimal_strings_with_null_gaps():
    out = grams_per_house(house({"2000-01": "300000", "2000-03": "306000"}),
                          gold({"2000-01": "300", "2000-02": "310", "2000-03": "330"}))
    rows = publication_rows([out])["data"]
    assert [r["period"] for r in rows] == ["2000-01", "2000-02", "2000-03"]
    assert rows[1]["grams_per_house"] is None and isinstance(rows[0]["grams_per_house"], str)
    annual = grams_per_house(house({"2000": "1"}, freq="annual"), gold({"2000": "1"}, freq="annual"))
    with pytest.raises(FrequencyError):
        publication_rows([annual])


# ---- bundle validation and CLI ----------------------------------------------------------------------
def bundle(*, releases=()):
    h, g = house(), gold()
    docs = [json.loads(canonical_json(s)) for s in (h, g, grams_per_house(h, g))]
    return {"schema": hm.SCHEMA, "series": docs, "releases": list(releases)}


def test_bundle_clean_and_tampered_lineage_detected():
    assert validate_bundle(bundle()) == []
    bad = bundle()
    bad["series"][0]["observations"][0]["value"] = "1"
    assert any("lineage hash of house_eur does not match" in e for e in validate_bundle(bad))
    missing = bundle()
    del missing["series"][1]
    assert any("not in the bundle" in e for e in validate_bundle(missing))
    assert validate_bundle({"schema": "x"}) == ["bundle schema must be 'hist-model/1'"]


def test_bundle_releases_follow_the_gate():
    rec = json.loads(canonical_json(release_for(make_derived())))
    assert validate_bundle(bundle(releases=[rec])) == []
    rec["release_sha256"] = "0" * 64
    assert any("hash differs" in e for e in validate_bundle(bundle(releases=[rec])))


def test_bundle_series_violation_is_reported_not_raised():
    bad = bundle()
    bad["series"][0]["observations"][1]["period"] = "2000-01"
    assert any("duplicate period" in e for e in validate_bundle(bad))


def run_cli(path):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "hist_model_check.py"), str(path)], cwd=ROOT,
                          capture_output=True, text=True)


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_bytes(canonical_json(bundle()))
    result = run_cli(good)
    assert result.returncode == 0 and "OK" in result.stdout
    broken = bundle()
    broken["series"][2]["points"][0]["quality"] = "GOOD"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(broken))
    result = run_cli(bad)
    assert result.returncode == 1 and "quality" in result.stdout
    garbage = tmp_path / "garbage.json"
    garbage.write_text("{")
    assert run_cli(garbage).returncode == 2
    assert run_cli(tmp_path / "missing.json").returncode == 2


# ---- isolation: nothing production-facing is touched ------------------------------------------------
def test_model_does_not_import_or_alter_production_modules():
    code = (ROOT / "etl" / "hist_model.py").read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import)\s+([\w.]+)", code, re.M))
    stdlib = {"__future__", "hashlib", "json", "re", "calendar", "dataclasses", "datetime", "decimal"}
    assert imports - stdlib == {"etl.asset_quality"}
    assert "import static_export" not in code and "etl.static_export" not in code
    probe = subprocess.run([sys.executable, "-c",
                            "import sys, etl.hist_model; print(any(m.startswith('etl.static_export') for m in sys.modules))"],
                           cwd=ROOT, capture_output=True, text=True)
    assert probe.stdout.strip() == "False"


def test_no_production_file_references_the_model():
    users = []
    for base in ("etl", "scripts", "frontend/src", ".github/workflows", "data"):
        for path in (ROOT / base).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".yml", ".yaml", ".json", ".csv"}:
                if path.name != "hist_model.py" and "hist_model" in path.read_text(encoding="utf-8", errors="ignore"):
                    users.append(str(path.relative_to(ROOT)))
    assert users == []


def test_published_json_is_untouched_by_the_model():
    path = ROOT / "frontend" / "public" / "data" / "monthly.json"
    before = path.read_bytes()
    make_derived()
    assert path.read_bytes() == before
