import hashlib
import json
from calendar import monthrange
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import btc_02_history as H
from tools import btc_03_housing as b3
from tools import hist_08_bundle as hb
from tools import hist_09_bundle as h9
from tools import hist_10_gold_housing as h10

ROOT = Path(__file__).resolve().parents[1]
RAW = "c" * 64
STAMP = "2026-10-22T10:00:00+00:00"


# ---------------------------------------------------------------- synthetic world (proves code, not data)
def days(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def price(day, base):
    d = date.fromisoformat(day)
    return Decimal(base) + Decimal((d.year - 2010) * 40 + d.month * 7) + Decimal(d.day) / Decimal(4)


def usd_closes(first, last, base="100"):
    return {d: price(d, base) for d in days(first, last)}


def ecb_valid(first, last):
    """ECB publishes weekdays only: weekends are simply absent."""
    return {d: Decimal("1.25") + Decimal(date.fromisoformat(d).day % 5) / Decimal(100) for d in days(first, last)
            if date.fromisoformat(d).weekday() < 5}


BSU = usd_closes("2013-01-01", "2013-08-20")  # August is partial and must stay null
BSE = usd_closes("2013-03-01", "2013-08-20", "80")
MG = usd_closes("2010-08-01", "2010-12-31", "0.5")
ECB = ecb_valid("2010-01-01", "2013-08-20")


def sources(with_mtgox=True):
    q = {m: "Q3" for m in ("2013-01", "2013-02")} | {m: "Q2" for m in ("2013-03", "2013-04", "2013-05", "2013-06", "2013-07")}
    s = {"ecb": b3.ecb_daily_series(ECB, RAW, STAMP),
         "bitstamp_usd": b3.daily_btc_series("bitstamp_usd_daily", BSU, "USD", source_id="bitstamp_btcusd", raw_sha=RAW,
                                             month_quality=q, acquired_at=STAMP),
         "bitstamp_eur": b3.daily_btc_series("bitstamp_eur_daily", BSE, "EUR", source_id="bitstamp_btceur", raw_sha=RAW,
                                             fixed_quality="Q1", acquired_at=STAMP)}
    if with_mtgox:
        s["mtgox_usd"] = b3.daily_btc_series("mtgox_usd_daily", MG, "USD", source_id="mtgox_btcusd_archive", raw_sha=RAW,
                                             fixed_quality="Q3", acquired_at=STAMP)
    return s


def house_series():
    months = [f"{y}-{m:02d}" for y in (2010, 2011, 2012, 2013) for m in range(1, 13) if f"{y}-{m:02d}" <= "2013-08"]
    return hb.source_series("cbs_house", "housing", {m: str(200000 + 1000 * i) for i, m in enumerate(months)}, frequency="monthly",
                            currency="EUR", unit="EUR", kind="average_price", definition_id=h9.CBS_DEFINITION, source_id="syn",
                            raw_sha256=RAW, retrieved_at=STAMP, vintage="v", quality_of=lambda p: "CONFIRMED")


@pytest.fixture(scope="module")
def world():
    btc = b3.build_btc(sources())
    house = house_series()
    housing = b3.build_housing(btc, house)
    return {"btc": btc, "house": house, "housing": housing}


def pts(s):
    return {p.period: p.value for p in s.points}


def mean(vals):
    return sum(vals) / len(vals)


# ---------------------------------------------------------------- A1: complete months only
def test_a1_is_the_exact_mean_of_all_daily_closes_of_a_complete_month(world):
    m = pts(world["btc"]["bitstamp_usd_monthly_a1"])
    expected = Fraction(sum(Fraction(v) for d, v in BSU.items() if d[:7] == "2013-04"), 30)
    assert Fraction(m["2013-04"]) == expected
    assert all(m[x] is not None for x in ("2013-01", "2013-02", "2013-03", "2013-04", "2013-05", "2013-06", "2013-07"))


def test_incomplete_and_final_partial_months_are_explicit_nulls(world):
    m = {p.period: p for p in world["btc"]["bitstamp_usd_monthly_a1"].points}
    assert m["2013-08"].value is None and m["2013-08"].flags == ("INSUFFICIENT_DAILY_COVERAGE",)
    gap = dict(BSU)
    del gap["2013-04-15"]  # one missing day inside an otherwise complete month
    s = b3.daily_btc_series("bitstamp_usd_daily", gap, "USD", source_id="bitstamp_btcusd", raw_sha=RAW, acquired_at=STAMP)
    got = {p.period: p for p in hm.monthly_mean(s, min_coverage=Decimal(1), series_id="m").points}
    assert got["2013-04"].value is None  # not carried forward, not averaged over 29 days
    assert got["2013-03"].value is not None and got["2013-05"].value is not None


def test_no_value_is_invented_for_months_without_data(world):
    m = pts(world["btc"]["mtgox_usd_monthly_a1"])
    assert min(m) == "2010-08" and max(m) == "2010-12" and len(m) == 5  # nothing before or after the archive
    assert "2010-07" not in m and "2011-01" not in m


# ---------------------------------------------------------------- C1 and quotation direction
def test_c1_is_the_ratio_of_monthly_means_over_valid_ecb_days(world):
    got = pts(world["btc"]["bitstamp_usd_derived_eur_c1"])["2013-04"]
    usd = mean([Fraction(v) for d, v in BSU.items() if d[:7] == "2013-04"])
    fx = mean([Fraction(v) for d, v in ECB.items() if d[:7] == "2013-04"])  # weekends are absent, not filled
    assert abs(Fraction(got) - usd / fx) < Fraction(1, 10 ** 25)
    assert b3.c1_months(BSU, ECB)["2013-04"] == usd / fx


def test_matched_day_alternatives_differ_and_no_fx_is_carried_forward():
    from tools import hist_08_btc_definition as B8
    usd = H.DailySeries("u", "USD", tuple(sorted(BSU.items())))
    ecb = H.DailySeries("e", "USD", tuple(sorted(ECB.items())))
    c1 = B8.convert_usd_to_eur(usd, ecb, "C1")["2013-04"]
    c2 = B8.convert_usd_to_eur(usd, ecb, "C2")["2013-04"]
    assert c1["value"] != c2["value"] and c2["matched_days"] == c1["fx_days"] < c1["usd_days"]  # weekend USD days are not matched


def test_quote_direction_and_currency_confusion_are_rejected():
    s = sources()
    bad_fx = hb.source_series("ecb_inv", "fx", {d: "0.8" for d in ("2013-04-01", "2013-04-02")}, frequency="daily", currency="EUR",
                              unit="EUR_per_USD", kind="fx_rate", definition_id="d", source_id="s", raw_sha256=RAW, retrieved_at=STAMP,
                              vintage="v", quality_of=lambda p: "CONFIRMED")
    usd_m = hm.monthly_mean(s["bitstamp_usd"], min_coverage=Decimal(1), series_id="u_m")
    with pytest.raises(hm.CurrencyMismatch):
        hm.convert_currency(usd_m, hm.monthly_mean(bad_fx, min_coverage=Decimal("0.5"), series_id="x_m"), to_currency="EUR", series_id="x")
    eur_m = hm.monthly_mean(s["bitstamp_eur"], min_coverage=Decimal(1), series_id="e_m")
    ecb_m = hm.monthly_mean(s["ecb"], min_coverage=Decimal("0.5"), series_id="ecb_m")
    with pytest.raises(hm.CurrencyMismatch):  # an EUR price cannot be "converted" to EUR again
        hm.convert_currency(eur_m, ecb_m, to_currency="EUR", series_id="x")
    with pytest.raises(b3.Btc03Error):
        b3.daily_btc_series("x_btc", {"2013-04-01": Decimal(1)}, "GBP", source_id="s", raw_sha=RAW)
    assert s["ecb"].unit == "USD_per_EUR" and s["bitstamp_usd"].unit == "USD_per_BTC" and s["bitstamp_eur"].unit == "EUR_per_BTC"


def test_a_usd_price_cannot_enter_the_eur_housing_formula(world):
    with pytest.raises(hm.CurrencyMismatch):
        hm.sats_per_house(world["house"], world["btc"]["bitstamp_usd_monthly_a1"], series_id="x_sats")
    with pytest.raises(hm.CurrencyMismatch):
        hm.btc_per_house(world["house"], world["btc"]["bitstamp_usd_monthly_a1"], series_id="x_btc")


# ---------------------------------------------------------------- BTC and satoshi per house
def test_btc_and_satoshi_per_house_are_exact(world):
    h = world["housing"]
    house = {o.period: Fraction(o.value) for o in world["house"].observations}
    btc = pts(world["btc"]["bitstamp_eur_monthly_a1"])
    for month in ("2013-03", "2013-05", "2013-07"):
        b = pts(h["cbs_btc_per_house_bitstamp_eur_native"])[month]
        s = pts(h["cbs_sats_per_house_bitstamp_eur_native"])[month]
        assert abs(Fraction(b) - house[month] / Fraction(btc[month])) < Fraction(1, 10 ** 25)
        with localcontext() as ctx:
            ctx.prec = 60  # the module-level precision of other tools must not influence the check
            assert s == b * Decimal(100000000)  # exact Decimal conversion, no rounding
    assert h["cbs_sats_per_house_bitstamp_eur_native"].unit == "satoshi" and h["cbs_btc_per_house_bitstamp_eur_native"].unit == "btc"


def test_segments_are_separate_and_never_spliced(world):
    h = world["housing"]
    seg = {k: set(pts(v)) for k, v in h.items() if k.startswith("cbs_btc_per_house_")}
    assert set(seg) == {"cbs_btc_per_house_mtgox_usd_derived", "cbs_btc_per_house_bitstamp_usd_derived", "cbs_btc_per_house_bitstamp_eur_native"}
    assert max(seg["cbs_btc_per_house_mtgox_usd_derived"]) == "2010-12" and min(seg["cbs_btc_per_house_bitstamp_eur_native"]) == "2013-03"
    assert not (seg["cbs_btc_per_house_mtgox_usd_derived"] & seg["cbs_btc_per_house_bitstamp_usd_derived"])
    # the early segment stops where Mt. Gox data stop; the next segment is a separate series, not a continuation
    assert "2011-06" not in pts(h["cbs_btc_per_house_mtgox_usd_derived"])


def test_interior_btc_null_gives_a_null_housing_point_not_a_value():
    gap = dict(BSU)
    del gap["2013-04-15"]
    s = sources()
    s["bitstamp_usd"] = b3.daily_btc_series("bitstamp_usd_daily", gap, "USD", source_id="bitstamp_btcusd", raw_sha=RAW, acquired_at=STAMP)
    btc = b3.build_btc(s)
    by = {p.period: p for p in b3.build_housing(btc, house_series())["cbs_sats_per_house_bitstamp_usd_derived"].points}
    assert by["2013-04"].value is None and "MISSING_INPUT" in by["2013-04"].flags and by["2013-05"].value is not None


def test_nvm_median_and_cbs_mean_cannot_be_mixed_and_have_no_btc_overlap(world):
    nvm = h9.nvm_nlg_series(h9.read_nvm_csv(ROOT / "data" / "fixtures" / "hist09"), h9.NVM_CSV_SHA256)
    nvm_eur = hm.redenominate_nlg_to_eur(nvm, series_id="nvm_eur")
    rep = b3.nvm_overlap_report(nvm, {k: world["btc"][v] for k, v in b3.SEGMENT_SERIES.items() if v in world["btc"]})
    assert rep["nvm_first"] == "1975-H1" and rep["nvm_last"] == "2000-H2" and rep["n_nvm"] == 52
    assert all(n == 0 for n in rep["n_overlap"].values()) and "no complete BTC month" in rep["reason"]
    with pytest.raises(hm.FrequencyError):  # a half-year house cannot meet a monthly price: nothing is spread
        hm.sats_per_house(nvm_eur, world["btc"]["bitstamp_eur_monthly_a1"], series_id="nvm_sats")
    with pytest.raises(hm.DefinitionMismatch):  # the gold half-year rule is not reused for BTC
        hm.half_year_aggregate(world["btc"]["bitstamp_eur_monthly_a1"], rule="mean", series_id="btc_half")
    cbs = hm.btc_per_house(world["house"], world["btc"]["bitstamp_eur_monthly_a1"], series_id="a")
    house = world["house"]
    med = replace(house, kind="median_price", definition_id="nvm_like",
                  observations=tuple(replace(o, definition_id="nvm_like") for o in house.observations))
    med_btc = hm.btc_per_house(med, world["btc"]["bitstamp_eur_monthly_a1"], series_id="b")
    assert cbs.definition_id == "derived_btc_per_house" and med_btc.definition_id == "derived_btc_per_house_median"
    with pytest.raises(hm.DefinitionMismatch, match="cannot be mixed"):
        hm._combine(cbs, med_btc, lambda a, b: a / b, series_id="mix", step={"op": "x"})
    with pytest.raises(b3.Btc03Error):
        b3.build_housing(world["btc"], hb.source_series("hpi", "housing", {"2013-03": "1"}, frequency="monthly", currency="EUR", unit="EUR",
                                                        kind="transaction_value", definition_id="d", source_id="s", raw_sha256=RAW,
                                                        retrieved_at=STAMP, vintage="v", quality_of=lambda p: "CONFIRMED"))


# ---------------------------------------------------------------- quality labels
def test_quality_levels_follow_sustained_liquidity_and_the_segment():
    usd = usd_closes("2013-01-01", "2013-06-30")
    vol = {d: (Decimal(5) if d[:7] in ("2013-01", "2013-02") else Decimal(20000)) for d in usd}  # notional ~ 500-5000 vs 1e6
    vol = {d: (v if d[:7] not in ("2013-03", "2013-04") else Decimal(0) + Decimal(1)) for d, v in vol.items()}
    q = b3.quality_months(usd, {d: Decimal(1_000_000) / price(d, "100") * 2 if d[:7] >= "2013-05" else v for d, v in vol.items()},
                          usd_closes("2013-03-01", "2013-06-30", "80"))
    assert q["liquid_start"] == "2013-05"
    assert q["bitstamp_usd"] == {"2013-01": "Q3", "2013-02": "Q3", "2013-03": "Q3", "2013-04": "Q3", "2013-05": "Q2", "2013-06": "Q2"}
    assert q["bitstamp_eur"]["2013-04"] == "Q3" and q["bitstamp_eur"]["2013-06"] == "Q1"
    flags = {p.period: p.flags for p in hm.monthly_mean(sources()["bitstamp_usd"], min_coverage=Decimal(1), series_id="m").points}
    assert "BTC_Q3" in flags["2013-01"] and "BTC_Q2" in flags["2013-04"]
    mg = hm.monthly_mean(sources()["mtgox_usd"], min_coverage=Decimal(1), series_id="mg")
    assert all("BTC_Q3" in p.flags for p in mg.points if p.value is not None)  # Mt. Gox is never better than Q3


def test_liquidity_that_drops_again_resets_the_start():
    usd = usd_closes("2013-01-01", "2013-04-30")
    vol = {d: Decimal(1_000_000) / price(d, "100") * 2 for d in usd}
    vol.update({d: Decimal(1) for d in usd if d[:7] == "2013-03"})  # thin March resets the sustained start
    assert b3.quality_months(usd, vol)["liquid_start"] == "2013-04"


# ---------------------------------------------------------------- invalid input
@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-5), 1.5, True, Decimal("nan"), Decimal("inf")])
def test_invalid_prices_are_rejected(bad):
    with pytest.raises((b3.Btc03Error, hm.ModelError)):
        b3.daily_btc_series("x_btc", {"2013-04-01": bad}, "USD", source_id="s", raw_sha=RAW)


def test_bad_days_empty_input_and_duplicates_are_rejected():
    with pytest.raises(b3.Btc03Error):
        b3.daily_btc_series("x_btc", {}, "USD", source_id="s", raw_sha=RAW)
    for day in ("2013-4-1", "20130401", "2013-02-30", "2013-04-01T00:00:00"):
        with pytest.raises((b3.Btc03Error, ValueError)):
            b3.daily_btc_series("x_btc", {day: Decimal(1)}, "USD", source_id="s", raw_sha=RAW)
    with pytest.raises(H.HistoryError):  # the BTC-02 parser refuses duplicated or unordered days before they reach the model
        H.parse_daily([("2013-04-01", "1"), ("2013-04-01", "2")], source="s", currency="USD")
    with pytest.raises(H.HistoryError):
        H.parse_daily([("2013-04-02", "1"), ("2013-04-01", "2")], source="s", currency="USD")
    with pytest.raises(b3.Btc03Error):
        b3.ecb_daily_series({}, RAW)


def test_utc_day_boundaries():
    from tools import btc_02_probe as P
    assert P.utc_day(0) == "1970-01-01" and P.utc_day(86399) == "1970-01-01" and P.utc_day(86400) == "1970-01-02"
    ts = 1367279999  # 2013-04-29 23:59:59 UTC
    assert P.utc_day(ts) == "2013-04-29" and P.utc_day(ts + 1) == "2013-04-30"


# ---------------------------------------------------------------- independent recalculation, half-years, sensitivity
def test_independent_recalculation_matches_the_model(world):
    data = {"bitstamp_usd": BSU, "bitstamp_eur": BSE, "mtgox_usd": MG, "ecb": ECB}
    out = b3.independent_check(data, world["btc"], world["housing"], world["house"])
    checked = {k: v for k, v in out.items() if "btc_rel_diff" in v}
    assert any(k.startswith("2013-04") or k.startswith("2010-08") for k in checked)
    for k, v in checked.items():
        assert float(v["btc_rel_diff"]) < 1e-25 and float(v["sats_rel_diff"]) < 1e-25, k
    assert out["2026-08 bitstamp_eur_native"]["status"] == "NOT_AVAILABLE"  # nothing is extrapolated to months without data


def test_half_year_methods_need_six_complete_months_and_differ():
    daily = usd_closes("2013-01-01", "2013-12-31")
    r = b3.half_year_methods(daily, "2013-H1")
    assert set(r) == {"M1_mean_of_monthly_a1", "D_day_weighted", "M3_last_month", "M4_first_month", "M5_median_of_months", "M6_last_day_close"}
    assert r["M1_mean_of_monthly_a1"] != r["D_day_weighted"]  # month lengths differ, so the rules are not equivalent
    assert b3.half_year_methods(daily, "2012-H2") is None and b3.half_year_methods(usd_closes("2013-01-01", "2013-06-29"), "2013-H1") is None
    stats = b3.half_year_sensitivity(daily, first="2013-H1", last="2013-H2")
    assert stats["n_half_years"] == 2 and "M3_last_month" in stats["methods"]


def test_rel_stats_and_sensitivity_functions():
    a, b = {"2013-01": Fraction(110), "2013-02": Fraction(90)}, {"2013-01": Fraction(100), "2013-02": Fraction(100), "2013-03": Fraction(1)}
    st = b3.rel_stats(a, b)
    assert st["n"] == 2 and st["max_pct"] == "10.000" and st["mean_pct"] == "10.000" and st["signed_mean_pct"] == "0.000"
    assert b3.rel_stats({"2013-01": Fraction(1)}, {"2014-01": Fraction(1)}) == {"n": 0}
    a2 = b3.a2_months(BSU)
    assert a2["2013-04"] == Fraction(BSU["2013-04-30"]) and "2013-08" not in a2


# ---------------------------------------------------------------- vintage pins, bundles, publication safety
def test_pin_windows_detect_revisions_and_ignore_appended_data():
    w = b3.source_windows({"bitstamp_usd_daily": BSU, "ecb_usd_per_eur_daily": ECB})
    assert set(w) == {"bitstamp_usd_daily", "ecb_usd_per_eur_daily"}
    appended = {**BSU, "2026-09-01": Decimal(1)}
    assert b3.source_windows({"bitstamp_usd_daily": appended})["bitstamp_usd_daily"] == w["bitstamp_usd_daily"]
    revised = {**BSU, "2013-04-10": BSU["2013-04-10"] + 1}
    assert b3.source_windows({"bitstamp_usd_daily": revised})["bitstamp_usd_daily"]["sha256"] != w["bitstamp_usd_daily"]["sha256"]


def test_pin_check_statuses(world):
    cur = b3.source_windows({"bitstamp_usd_daily": BSU, "ecb_usd_per_eur_daily": ECB})
    derived = b3.derived_values_sha256({**world["btc"], **world["housing"]})
    pins = {"method_id": b3.METHOD_ID, "sources": cur, "derived": {"values_sha256": derived}}
    assert b3.check_pins(cur, derived, pins)["status"] == "MATCH"
    assert b3.check_pins(cur, derived, None)["status"] == "UNPINNED"
    rev = {**cur, "bitstamp_usd_daily": b3.source_windows({"bitstamp_usd_daily": {**BSU, "2013-04-10": Decimal(1)}})["bitstamp_usd_daily"]}
    assert b3.check_pins(rev, "other", pins)["status"] == "SOURCE_REVISED"
    assert b3.check_pins(cur, "other", pins)["status"] == "DEFECT_DERIVED_DRIFT"
    assert b3.check_pins(cur, derived, {**pins, "method_id": "OTHER"})["status"] == "METHOD_CHANGED"


def test_derived_hash_is_value_sensitive_and_stops_at_the_cutoff(world):
    base = b3.derived_values_sha256({**world["btc"], **world["housing"]})
    assert base == b3.derived_values_sha256({**world["btc"], **world["housing"]})
    s = world["housing"]["cbs_sats_per_house_bitstamp_eur_native"]
    changed = dict(world["housing"], cbs_sats_per_house_bitstamp_eur_native=replace(s, points=(replace(s.points[0], value=s.points[0].value + 1),) + s.points[1:]))
    assert b3.derived_values_sha256({**world["btc"], **changed}) != base


def test_bundles_validate_rebuild_identically_and_tamper_is_detected(world, tmp_path):
    allx = h10.all_series(world["btc"], world["housing"], world["house"])
    first = b3.write_bundles(b3.bundles(allx), tmp_path / "a")
    second = b3.write_bundles(b3.bundles(allx), tmp_path / "b")
    assert first == second and set(first) == {"btc03_A_btc_source.json", "btc03_B_btc_eur.json", "btc03_C_cbs_btc_sats.json"}
    for name in first:
        raw = (tmp_path / "a" / name).read_bytes()
        assert raw == (tmp_path / "b" / name).read_bytes() and hm.validate_bundle(json.loads(raw)) == []
    bundle = json.loads((tmp_path / "a" / "btc03_C_cbs_btc_sats.json").read_text())
    for s in bundle["series"]:
        if s["series_id"] == "bitstamp_eur_daily":
            s["observations"][0]["value"] = "1"
    assert any("lineage hash" in e for e in hm.validate_bundle(bundle))


def test_every_bitcoin_series_is_restricted_and_publication_is_denied(world):
    assert hm.ALLOWLIST == ()
    for s in list(world["housing"].values()) + [world["btc"]["bitstamp_eur_monthly_a1"], world["btc"]["bitstamp_usd_derived_eur_c1"]]:
        assert s.asset_class == "bitcoin" or s.series_id.startswith("cbs_")
        with pytest.raises(hm.PublicationDenied):
            hm.publication_gate([s])
        record = hm.ReleaseRecord("r", hm.release_hash([s]), "owner", "2026-10-22", "d", (s.series_id,))
        with pytest.raises(hm.PublicationDenied):  # even a matching release record cannot release a restricted class unaided
            hm.publication_gate([s], [record])


def test_flags_carry_method_proposed_status_and_quality(world):
    for name in ("bitstamp_usd_derived_eur_c1", "bitstamp_eur_monthly_a1"):
        for p in (q for q in world["btc"][name].points if q.value is not None):
            assert b3.METHOD_FLAG in p.flags and b3.PROPOSED_FLAG in p.flags and b3.RESEARCH_FLAG in p.flags
            assert any(f.startswith("BTC_Q") for f in p.flags)
    assert b3.METHOD_ID == "BTC03_A1_C1_V1"


def test_production_files_unchanged_and_no_bitcoin_selector_in_the_frontend():
    assert hashlib.sha256((ROOT / "frontend/public/data/monthly.json").read_bytes()).hexdigest() == \
        "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert hashlib.sha256((ROOT / "data/cbs-housing.csv").read_bytes()).hexdigest() == \
        "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    series_ts = (ROOT / "frontend/src/series.ts").read_text()
    assert "sat_per_house" in series_ts and "withheld" in series_ts


def test_committed_pin_file_holds_hashes_only_and_matches_the_method():
    pins = json.loads((ROOT / "data" / "fixtures" / "btc03" / "source_pins.json").read_text())
    assert pins["method_id"] == b3.METHOD_ID and set(pins["sources"]) == set(b3.PIN_WINDOWS)
    for name, w in pins["sources"].items():
        assert set(w) == {"first", "last", "n", "sha256"} and len(w["sha256"]) == 64 and int(w["sha256"], 16) >= 0 and w["n"] > 0
        assert b3.PIN_WINDOWS[name][0] <= w["first"] and w["last"] <= b3.PIN_WINDOWS[name][1]
    assert len(pins["derived"]["values_sha256"]) == 64 and pins["derived"]["cutoff"] == b3.RESEARCH_CUTOFF
    assert "RESEARCH PIN" in pins["status"] and "PROPOSED" in pins["status"] and "no raw third-party data" in pins["status"]
    hist10 = json.loads((ROOT / "data" / "fixtures" / "hist10" / "source_pins.json").read_text())["sources"]["ecb_usd_per_eur_daily"]
    assert pins["sources"]["ecb_usd_per_eur_daily"] == {k: hist10[k] for k in ("first", "last", "n", "sha256")}  # same ECB window as HIST-10
