import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import btc_03_housing as b3
from tools import btc_04e_cm_replay as c
from tools import hist_08_bundle as hb
from tools import hist_09_bundle as h9

ROOT = Path(__file__).resolve().parents[1]
RAW = "d" * 64
STAMP = "2026-10-22T10:00:00+00:00"


def days(first, last):
    d, end = date.fromisoformat(first), date.fromisoformat(last)
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def px(day, base="100"):
    d = date.fromisoformat(day)
    return Decimal(base) + Decimal((d.year - 2010) * 40 + d.month * 7) + Decimal(d.day) / Decimal(4)


CM = {d: px(d) for d in days("2010-07-18", "2014-03-20")}  # starts mid-July, ends in a partial March
ECB = {d: Decimal("1.25") + Decimal(date.fromisoformat(d).day % 5) / Decimal(100) for d in days("2010-01-01", "2014-03-20")
       if date.fromisoformat(d).weekday() < 5}


def house():
    months = [f"{y}-{m:02d}" for y in (2010, 2011, 2012, 2013, 2014) for m in range(1, 13) if f"{y}-{m:02d}" <= "2014-03"]
    return hb.source_series("cbs_house", "housing", {m: str(200000 + 1000 * i) for i, m in enumerate(months)}, frequency="monthly",
                            currency="EUR", unit="EUR", kind="average_price", definition_id=h9.CBS_DEFINITION, source_id="syn",
                            raw_sha256=RAW, retrieved_at=STAMP, vintage="v", quality_of=lambda p: "CONFIRMED")


@pytest.fixture(scope="module")
def built():
    return c.build_from_daily(CM, ECB, house(), STAMP)


def vals(s):
    return {p.period: p.value for p in s.points}


# ---------------------------------------------------------------- adapter
def page(entries, **extra):
    return {"data": entries, **extra}


def entry(day="2013-01-01", value="13.5", **kw):
    e = {"asset": "btc", "time": f"{day}T00:00:00.000000000Z", "PriceUSD": value}
    e.update(kw)
    return e


def test_parse_page_accepts_canonical_midnight_utc():
    rows, nxt = c.parse_page(page([entry()]))
    assert rows == [("2013-01-01", Decimal("13.5"))] and nxt is None


@pytest.mark.parametrize("ts", ["2013-01-01T12:00:00.000000000Z", "2013-01-01T00:00:00+02:00", "2013-01-01", "2013-02-30T00:00:00Z", 5, None])
def test_wrong_utc_timestamp_is_rejected(ts):
    with pytest.raises(c.Btc04eError):
        c.parse_page(page([{"asset": "btc", "time": ts, "PriceUSD": "1"}]))


@pytest.mark.parametrize("bad", ["0", "-5", "NaN", "Infinity", "abc", 1.5, True, [1]])
def test_zero_negative_nonfinite_and_float_prices_are_rejected(bad):
    with pytest.raises(c.Btc04eError):
        c.parse_page(page([entry(value=bad)]))


def test_wrong_asset_and_malformed_payload_rejected():
    for payload in ({"data": [entry(asset="eth")]}, {"nodata": []}, [], {"data": "x"}):
        with pytest.raises(c.Btc04eError):
            c.parse_page(payload)


def test_missing_price_field_is_a_provider_gap_not_a_price():
    rows, _ = c.parse_page(page([{"asset": "btc", "time": "2013-01-02T00:00:00Z"}]))
    assert rows == [("2013-01-02", None)]
    daily, gaps = c.merge_rows(rows)
    assert daily == {} and gaps == ["2013-01-02"]


def test_duplicate_same_value_collapses_and_conflict_fails_closed():
    daily, _ = c.merge_rows([("2013-01-01", Decimal("5")), ("2013-01-01", Decimal("5.0"))])
    assert daily == {"2013-01-01": Decimal("5")}
    with pytest.raises(c.Btc04eError):
        c.merge_rows([("2013-01-01", Decimal("5")), ("2013-01-01", Decimal("5.01"))])
    with pytest.raises(c.Btc04eError):
        c.merge_rows([("2013-01-01", Decimal("5")), ("2013-01-01", None)])


def test_pagination_url_must_stay_on_official_https_endpoint():
    with pytest.raises(c.Btc04eError):
        c.parse_page(page([], next_page_url="http://community-api.coinmetrics.io/v4/x"))
    with pytest.raises(c.Btc04eError):
        c.parse_page(page([], next_page_url="https://evil.example/v4/x"))


class Resp:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status_code, self.headers = payload, status, headers or {}
        self.content = json.dumps(payload).encode()

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_fetch_paginates_backs_off_and_records_hashes():
    nxt = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?next_page_token=abc"
    s = Session([Resp({}, 429, {"Retry-After": "3"}), Resp(page([entry("2013-01-01")], next_page_url=nxt)),
                 Resp(page([entry("2013-01-02", "14")]))])
    waits = []
    acq = c.fetch_priceusd(s, start="2013-01-01", end="2013-01-02", sleep=waits.append)
    assert acq["n"] == 2 and acq["pages"] == 2 and acq["first"] == "2013-01-01" and len(acq["page_sha256"]) == 2
    assert waits[0] == 3.0 and s.calls[2][1] is None and acq["query"]["metrics"] == "PriceUSD"


def test_fetch_fails_on_repeated_error_loop_and_out_of_range():
    with pytest.raises(c.Btc04eError):
        c.fetch_priceusd(Session([Resp({}, 503)] * 6), start="2013-01-01", end="2013-01-02", sleep=lambda _: None)
    nxt = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?x=1"
    with pytest.raises(c.Btc04eError):
        c.fetch_priceusd(Session([Resp(page([entry()], next_page_url=nxt))] * 3), start="2013-01-01", end="2013-01-02", sleep=lambda _: None)
    with pytest.raises(c.Btc04eError):
        c.fetch_priceusd(Session([Resp(page([entry("2013-02-01")]))]), start="2013-01-01", end="2013-01-02", sleep=lambda _: None)
    with pytest.raises(c.Btc04eError):
        c.fetch_priceusd(Session([Resp(page([]))]), start="2013-01-01", end="2013-01-02", sleep=lambda _: None)


# ---------------------------------------------------------------- completeness, calendar, stale
def test_missing_utc_day_makes_the_month_null_and_is_reported():
    d = {k: v for k, v in CM.items() if k != "2012-05-15"}
    assert c.missing_days(d, max(d)) == ["2012-05-15"]
    b = c.build_from_daily(d, ECB, house(), STAMP)
    assert vals(b["cm_priceusd_monthly"])["2012-05"] is None and vals(b["cbs_btc_per_house_cm_c1"])["2012-05"] is None
    assert vals(b["cm_priceusd_monthly"])["2012-04"] is not None  # neighbours untouched, nothing carried across


def test_partial_first_and_current_months_are_null(built):
    m = vals(built["cm_priceusd_monthly"])
    assert m["2010-07"] is None and m["2014-03"] is None and m["2010-08"] is not None


def test_leap_february_needs_29_days():
    leap = {d: px(d) for d in days("2012-01-01", "2012-03-31") if d != "2012-02-29"}
    assert vals(c.build_from_daily({**CM, **{k: v for k, v in CM.items()}}, ECB, house(), STAMP)["cm_priceusd_monthly"])["2012-02"] is not None
    without = {k: v for k, v in CM.items() if k != "2012-02-29"}
    assert vals(c.build_from_daily(without, ECB, house(), STAMP)["cm_priceusd_monthly"])["2012-02"] is None
    assert leap and c.missing_days(leap, "2012-03-31") == ["2012-02-29"]


def test_current_partial_day_is_cut():
    assert max(c.cut_to_complete(CM, "2013-06-10")) == "2013-06-09"


def test_ecb_holidays_vs_unexpected_missing_business_days():
    assert {date(2013, 3, 29), date(2013, 4, 1), date(2013, 5, 1), date(2013, 12, 25)} <= c.target_holidays(2013)
    ecb = {d: Decimal("1.3") for d in days("2013-03-25", "2013-04-05") if date.fromisoformat(d).weekday() < 5}
    del ecb["2013-03-29"], ecb["2013-04-01"]  # Good Friday and Easter Monday: no fixing
    rep = c.ecb_calendar_report(ecb)
    assert rep["unexpected_missing_business_days"] == 0 and rep["target_holidays_missing"] == 2
    del ecb["2013-04-03"]
    rep = c.ecb_calendar_report(ecb)
    assert rep["unexpected_sample"] == ["2013-04-03"] and rep["unexpected_by_month"] == {"2013-04": 1}
    ecb["2013-04-06"] = Decimal("1.3")  # Saturday
    assert c.ecb_calendar_report(ecb)["weekend_days_with_rate"] == 1


def test_stale_runs_are_flagged_not_rejected():
    d = dict(CM)
    for day in days("2010-12-20", "2011-01-10"):
        d[day] = Decimal("0.3")
    runs = c.stale_runs(d)
    assert runs and runs[0]["days"] == 22 and runs[0]["first"] == "2010-12-20"
    b = c.build_from_daily(d, ECB, house(), STAMP)
    assert vals(b["cm_priceusd_monthly"])["2011-01"] is not None  # flat prices alone never exclude a month
    meta = c.month_metadata(b, d)
    assert meta["2011-01"]["stale_days"] > 0 and meta["2011-01"]["exception"] is None


# ---------------------------------------------------------------- economics
def test_exact_values_quote_direction_and_nulls(built):
    month = "2012-02"
    n = 29
    usd = sum(Fraction(CM[f"{month}-{i:02d}"]) for i in range(1, n + 1)) / n
    fx = [Fraction(v) for k, v in ECB.items() if k[:7] == month]
    eur = usd / (sum(fx) / len(fx))  # USD per EUR: divide
    got = vals(built["cm_btc_eur_equivalent_c1"])[month]
    assert abs(Fraction(got) / eur - 1) < Fraction(1, 10 ** 30)
    assert vals(built["cm_btc_eur_equivalent_c1"])["2010-07"] is None
    wrong = eur * (sum(fx) / len(fx)) ** 2
    assert abs(Fraction(got) / wrong - 1) > Fraction(1, 10)  # multiplying instead of dividing would be wrong


def test_incorrect_fx_quote_direction_is_refused():
    inverted = hm.Series("fx", "source", "fx", "daily", "EUR", "EUR_per_USD", "x", "fx_rate", "nominal", None, (),
                         tuple(hm.Observation("fx", d, Decimal("0.8"), "EUR", "EUR_per_USD", "x", "s", RAW, STAMP, "v", "CONFIRMED", ())
                               for d in list(ECB)[:40]))
    monthly = hm.monthly_mean(inverted, min_coverage=Decimal("0.1"), series_id="fxm")
    cm = c.cm_daily_series(CM, RAW, STAMP)
    with pytest.raises(hm.ModelError):
        hm.convert_currency(hm.monthly_mean(cm, min_coverage=Decimal(1), series_id="m"), monthly, to_currency="EUR", series_id="o")


def test_sat_conversion_is_exact_in_any_decimal_context(built):
    with localcontext() as ctx:
        ctx.prec = 80
        b = c.build_from_daily(CM, ECB, house(), STAMP)
        for p, q in zip(b["cbs_btc_per_house_cm_c1"].points, b["cbs_sats_per_house_cm_c1"].points):
            if p.value is not None:
                assert Fraction(q.value) == Fraction(p.value) * 10 ** 8
            else:
                assert q.value is None
    assert hb  # imported for series construction


def test_wrong_housing_statistic_is_refused():
    nvm = hb.source_series("nvm", "housing", {"1999-H1": "100000"}, frequency="semiannual", currency="EUR", unit="EUR", kind="median_price",
                           definition_id=h9.NVM_DEFINITION, source_id="syn", raw_sha256=RAW, retrieved_at=STAMP, vintage="v",
                           quality_of=lambda p: "CONFIRMED")
    with pytest.raises(c.Btc04eError):
        c.build(c.cm_daily_series(CM, RAW, STAMP), c.ecb_series(ECB, RAW, STAMP), nvm)


def test_unsupported_early_period_has_no_quality_or_value(built):
    with pytest.raises(c.Btc04eError):
        c.quality_of_month("2010-07")
    meta = c.month_metadata(built, CM)
    assert meta["2010-07"]["status"] == "UNSUPPORTED_EARLY_PERIOD" and meta["2010-07"]["release_eligibility"] == "NONE"


def test_quality_boundaries_follow_the_project_control_decision():
    assert [c.quality_of_month(m) for m in ("2010-08", "2014-01", "2014-02", "2016-04", "2016-05", "2026-08")] == [
        "Q3", "Q3", "Q2", "Q2", "Q1_CANDIDATE", "Q1_CANDIDATE"]


def test_method_flag_is_distinct_from_btc_03(built):
    flags = built["cm_priceusd_daily"].observations[40].flags
    assert c.METHOD_FLAG in flags and b3.METHOD_FLAG not in flags and c.RESEARCH_FLAG in flags
    assert c.METHOD_ID != b3.METHOD_ID


# ---------------------------------------------------------------- June 2011 exception
def test_june_2011_is_research_only_hold_and_never_connected(built):
    meta = c.month_metadata(built, CM)["2011-06"]
    assert meta["exception"] == "HOLD_2011_06" and meta["release_eligibility"] == "RESEARCH_ONLY_HOLD"
    assert any("EXC:HOLD_2011_06" in o.flags for o in built["cm_priceusd_daily"].observations if o.period.startswith("2011-06"))
    segs = c.chart_segments(built)
    assert [s["last"] for s in segs][0] == "2011-05" and segs[1]["first"] == "2011-07"
    assert vals(built["cm_priceusd_monthly"])["2011-06"] is not None  # computed for research, flagged, not published or bridged


def test_chart_segments_split_at_any_null():
    d = {k: v for k, v in CM.items() if k != "2012-05-15"}
    segs = c.chart_segments(c.build_from_daily(d, ECB, house(), STAMP))
    assert any(s["last"] == "2012-04" for s in segs) and any(s["first"] == "2012-06" for s in segs)


# ---------------------------------------------------------------- vintage pins and replay
def windows(cm=CM, ecb=ECB):
    return c.source_windows({"cm_priceusd_daily": cm, "ecb_usd_per_eur_daily": ecb})


def pins_for(b, cm=CM):
    return {"method_id": c.METHOD_ID, "parser_version": c.PARSER_VERSION, "exception_policy_version": c.EXCEPTION_POLICY_VERSION,
            "quality_version": c.QUALITY_VERSION, "sources": windows(cm),
            "derived": {"values_sha256": c.derived_values_sha256(b, "2014-02"), "cutoff": "2014-02"}}


def test_same_bytes_same_method_identical_values_and_match(built):
    again = c.build_from_daily(CM, ECB, house(), STAMP)
    assert c.derived_values_sha256(again) == c.derived_values_sha256(built)
    cur = windows()
    pins = pins_for(built)
    pins["sources"] = {k: v for k, v in cur.items()}
    assert c.check_pins(cur, pins["derived"]["values_sha256"], pins)["status"] == "MATCH"


def test_appended_data_outside_the_pin_window_changes_nothing(built):
    pins = pins_for(built)
    extended = dict(CM)
    for d in days("2014-03-21", "2014-06-30"):
        extended[d] = px(d)
    # window pins stop at 2026-08-31 in production; restrict this test pin to the synthetic range
    c_win = {"cm_priceusd_daily": c.h10.window_hash(CM, "2010-07-18", "2014-03-20"), "ecb_usd_per_eur_daily": c.h10.window_hash(ECB, "2010-01-01", "2014-03-20")}
    pins["sources"] = c_win
    grown = {"cm_priceusd_daily": c.h10.window_hash(extended, "2010-07-18", "2014-03-20"), "ecb_usd_per_eur_daily": c_win["ecb_usd_per_eur_daily"]}
    b2 = c.build_from_daily(extended, ECB, house(), STAMP)
    assert c.derived_values_sha256(b2, "2014-02") == pins["derived"]["values_sha256"]
    assert c.check_pins(grown, c.derived_values_sha256(b2, "2014-02"), pins)["status"] == "MATCH"


def test_changed_old_price_is_source_revised(built):
    pins = pins_for(built)
    revised = dict(CM)
    revised["2011-03-03"] += Decimal("0.01")
    assert c.check_pins(windows(revised), "x", pins)["status"] == "SOURCE_REVISED"


def test_identical_input_different_derived_is_defect_drift(built):
    assert c.check_pins(windows(), "0" * 64, pins_for(built))["status"] == "DEFECT_DERIVED_DRIFT"


@pytest.mark.parametrize("field", ["method_id", "parser_version", "exception_policy_version", "quality_version"])
def test_changed_method_or_policy_version_is_method_changed(built, field):
    pins = pins_for(built)
    pins[field] = "OTHER"
    res = c.check_pins(windows(), c.derived_values_sha256(built, "2014-02"), pins)
    assert res["status"] == "METHOD_CHANGED" and field in res["changed"]


def test_unpinned_and_missing_window_are_not_match(built):
    assert c.check_pins(windows(), "x", None)["status"] == "UNPINNED"
    pins = pins_for(built)
    del pins["sources"]["ecb_usd_per_eur_daily"]
    assert c.check_pins(windows(), c.derived_values_sha256(built, "2014-02"), pins)["status"] == "UNPINNED"


def test_snapshot_round_trip_replays_identically_and_fails_closed(tmp_path, built):
    man = {"coinmetrics": {"retrieved_at_utc": STAMP}, "derived_values_sha256": c.derived_values_sha256(built)}
    c.write_snapshot(tmp_path, {"cm_priceusd_daily": CM, "ecb_usd_per_eur_daily": ECB}, man)
    assert c.replay(tmp_path, house())["status"] == "IDENTICAL"
    f = tmp_path / "cm_priceusd_daily.txt"
    original = f.read_text()
    f.write_text(original.replace("2012-02-10:", "2012-02-10:9", 1))  # corrupted
    with pytest.raises(c.Btc04eError):
        c.read_snapshot(tmp_path)
    f.write_text(original[:-40])  # truncated
    with pytest.raises(c.Btc04eError):
        c.read_snapshot(tmp_path)
    f.unlink()  # missing
    with pytest.raises(c.Btc04eError):
        c.read_snapshot(tmp_path)
    with pytest.raises(c.Btc04eError):
        c.read_snapshot(tmp_path / "nowhere")


def test_replay_with_wrong_recorded_hash_reports_different(tmp_path, built):
    man = {"coinmetrics": {"retrieved_at_utc": STAMP}, "derived_values_sha256": "0" * 64}
    c.write_snapshot(tmp_path, {"cm_priceusd_daily": CM, "ecb_usd_per_eur_daily": ECB}, man)
    assert c.replay(tmp_path, house())["status"] == "DIFFERENT"


def test_manifest_records_required_vintage_fields(built):
    acq = {"source": c.PROVIDER, "metric": "PriceUSD", "url": c.BASE_URL, "query": c.query("2010-07-18", "2014-03-20"), "retrieved_at_utc": STAMP,
           "pages": 1, "page_sha256": ["a" * 64], "response_sha256": "b" * 64, "first": "2010-07-18", "last": "2014-03-20", "n": len(CM),
           "provider_gaps": [], "daily": CM}
    man = c.manifest(acq, RAW, ECB, c.derived_values_sha256(built), windows(), "deadbeef")
    for key in ("method_id", "parser_version", "git_commit", "derived_values_sha256", "exception_policy_version", "quality_version", "source_windows"):
        assert key in man
    cm = man["coinmetrics"]
    assert cm["canonical_daily_sha256"] == c.canonical_daily_sha256(CM) and cm["query"]["metrics"] == "PriceUSD" and cm["url"] == c.BASE_URL


# ---------------------------------------------------------------- independent recalculation and leakage
def test_independent_check_agrees_and_marks_nulls(built):
    out = c.independent_check(CM, ECB, built, house(), ("2010-08", "2011-06", "2013-01", "2014-03", "2009-01"))
    assert out["2010-08"]["status"] == "OK" and float(out["2010-08"]["btc_rel_diff"]) < 1e-30
    assert float(out["2013-01"]["sats_rel_diff"]) < 1e-30 and out["2011-06"]["status"] == "OK"
    assert out["2014-03"]["status"] == "NULL_INCOMPLETE_BTC_MONTH" and out["2009-01"]["status"] == "NO_CBS_MONTH"


def test_independent_check_detects_a_wrong_model_value(built):
    from dataclasses import replace
    s = built["cbs_btc_per_house_cm_c1"]
    pts = tuple(replace(p, value=p.value * 2) if p.period == "2012-02" else p for p in s.points)
    out = c.independent_check(CM, ECB, {**built, "cbs_btc_per_house_cm_c1": replace(s, points=pts)}, house(), ("2012-02", "2012-03"))
    assert float(out["2012-02"]["btc_rel_diff"]) > 0.5 and float(out["2012-03"]["btc_rel_diff"]) < 1e-30


def test_no_public_leakage_and_production_files_unchanged():
    assert hashlib.sha256((ROOT / "frontend/public/data/monthly.json").read_bytes()).hexdigest() == \
        "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert hashlib.sha256((ROOT / "data/cbs-housing.csv").read_bytes()).hexdigest() == \
        "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    assert hm.ALLOWLIST == ()
    text = (ROOT / "frontend/public/data/monthly.json").read_text().lower()
    assert "btc" not in text and "sat_per_house" not in text and "priceusd" not in text
    src = (ROOT / "frontend/src/main.tsx").read_text().lower()
    assert "priceusd" not in src and "coinmetrics" not in src


def test_publication_of_research_series_is_denied(built):
    with pytest.raises(hm.PublicationDenied):
        hm.publication_gate([built["cbs_btc_per_house_cm_c1"]])


def test_tool_does_not_name_public_data_paths():
    src = (ROOT / "tools/btc_04e_cm_replay.py").read_text()
    for literal in ("frontend/public", "monthly.json", "cbs-housing.csv"):
        assert literal not in src


def test_cm_adapter_reference_rate_module_is_untouched():
    assert "ReferenceRate" in (ROOT / "etl/sources/coinmetrics.py").read_text()


def test_missing_pin_file_is_unpinned_and_corrupt_file_fails_closed(tmp_path):
    assert c.load_pins(None) is None and c.load_pins(tmp_path / "absent.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(c.Btc04eError):
        c.load_pins(bad)
    bad.write_text("[]")
    with pytest.raises(c.Btc04eError):
        c.load_pins(bad)


def test_committed_pin_file_is_hashes_only_and_ecb_equals_earlier_phases():
    pins = json.loads((ROOT / "data/fixtures/btc04e/source_pins.json").read_text())
    assert pins["method_id"] == c.METHOD_ID and pins["parser_version"] == c.PARSER_VERSION
    assert pins["exception_policy_version"] == c.EXCEPTION_POLICY_VERSION and pins["quality_version"] == c.QUALITY_VERSION
    b3pins = json.loads((ROOT / "data/fixtures/btc03/source_pins.json").read_text())["sources"]["ecb_usd_per_eur_daily"]
    h10pins = json.loads((ROOT / "data/fixtures/hist10/source_pins.json").read_text())["sources"]["ecb_usd_per_eur_daily"]
    ecb = pins["sources"]["ecb_usd_per_eur_daily"]
    assert (ecb["sha256"], ecb["n"]) == (b3pins["sha256"], b3pins["n"]) == (h10pins["sha256"], h10pins["n"])
    text = json.dumps(pins)
    assert "USD_per_BTC" not in text and not any(len(k) == 10 and k[4] == "-" for k in pins)


# ---------------------------------------------------------------- review corrections: enforced vintage, HOLD boundary, ECB integrity
def good_run(**over):
    R = {"vintage_check": {"status": "MATCH"}, "replay_from_private_snapshot": {"status": "IDENTICAL"}, "rebuild_identical": True,
         "ecb_calendar": {"unexpected_in_validation_window": 0, "weekend_days_with_rate": 0}}
    R.update(over)
    return R


def test_normal_validation_succeeds_only_on_a_clean_match():
    R = c.finalize(good_run(), "validate")
    assert R["status"] == "COMPLETE_RESEARCH" and R["failures"] == [] and R["mode"] == "validate"


@pytest.mark.parametrize("status", ["SOURCE_REVISED", "DEFECT_DERIVED_DRIFT", "METHOD_CHANGED", "UNPINNED", None, "SOMETHING_NEW"])
def test_any_non_match_vintage_fails_normal_validation(status):
    R = c.finalize(good_run(vintage_check={"status": status}), "validate")
    assert R["status"] == "VALIDATION_FAILED" and any("vintage_check" in f for f in R["failures"])


def test_missing_vintage_key_cannot_pass():
    R = good_run()
    del R["vintage_check"]
    assert c.finalize(R, "validate")["status"] == "VALIDATION_FAILED"


@pytest.mark.parametrize("mode", ["validate", "bootstrap"])
@pytest.mark.parametrize("bad", [{"replay_from_private_snapshot": {"status": "DIFFERENT"}}, {"rebuild_identical": False},
                                 {"ecb_calendar": {"unexpected_in_validation_window": 2, "weekend_days_with_rate": 0}},
                                 {"ecb_calendar": {"unexpected_in_validation_window": 0, "weekend_days_with_rate": 1}}])
def test_replay_rebuild_and_ecb_failures_fail_in_every_mode(mode, bad):
    assert c.finalize(good_run(**bad), mode)["status"] == "VALIDATION_FAILED"


def test_bootstrap_is_explicit_and_never_reports_complete_research():
    R = c.finalize(good_run(vintage_check={"status": "UNPINNED"}), "bootstrap")
    assert R["status"] == "BOOTSTRAP_PINS_CANDIDATE" and R["status"] != "COMPLETE_RESEARCH"
    with pytest.raises(c.Btc04eError):
        c.finalize(good_run(), "other")


@pytest.mark.parametrize("status", ["SOURCE_REVISED", "DEFECT_DERIVED_DRIFT", "METHOD_CHANGED", "UNPINNED"])
def test_a_reported_pin_mismatch_cannot_end_in_a_successful_run(monkeypatch, tmp_path, status):
    monkeypatch.setattr(c, "run", lambda args: good_run(vintage_check={"status": status}, missing_sources=[]))
    out = tmp_path / "s.json"
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out)]) == 1  # default mode is validate
    assert json.loads(out.read_text())["status"] == "VALIDATION_FAILED"
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out), "--mode", "validate"]) == 1


def test_match_exits_zero_and_bootstrap_must_be_selected_explicitly(monkeypatch, tmp_path):
    out = tmp_path / "s.json"
    monkeypatch.setattr(c, "run", lambda args: good_run(missing_sources=[]))
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out)]) == 0
    monkeypatch.setattr(c, "run", lambda args: good_run(vintage_check={"status": "UNPINNED"}, missing_sources=[]))
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out)]) == 1
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out), "--mode", "bootstrap"]) == 0
    assert json.loads(out.read_text())["status"] == "BOOTSTRAP_PINS_CANDIDATE"
    with pytest.raises(SystemExit):
        c.main(["--cbs-csv", "x.csv", "--summary-out", str(out), "--mode", "skip"])


def test_incomplete_sources_and_defects_exit_nonzero(monkeypatch, tmp_path):
    out = tmp_path / "s.json"
    monkeypatch.setattr(c, "run", lambda args: {"status": "INCOMPLETE", "missing_sources": ["ecb"]})
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out), "--mode", "bootstrap"]) == 1

    def boom(args):
        raise c.Btc04eError("pin file unreadable")
    monkeypatch.setattr(c, "run", boom)
    assert c.main(["--cbs-csv", "x.csv", "--summary-out", str(out), "--mode", "bootstrap"]) == 1
    assert json.loads(out.read_text())["status"] == "FAILED"


def test_workflow_runs_validate_by_default_and_never_ignores_failure():
    wf = (ROOT / ".github/workflows/btc-04e-cm-replay.yml").read_text()
    assert '--mode "${BTC04E_MODE:-validate}"' in wf and "default: validate" in wf
    assert "continue-on-error" not in wf and "|| true" not in wf


# ---- June 2011 at the export boundary
def test_month_eligibility_is_explicit_and_hold_always_wins():
    assert c.month_eligibility("2011-06") == "RESEARCH_ONLY_HOLD"
    assert c.month_eligibility("2011-06", approvals={"2011-06"}) == "RESEARCH_ONLY_HOLD"
    assert c.month_eligibility("2011-05") == "RESEARCH_ONLY" and c.month_eligibility("2010-07") == "NONE"
    assert c.month_eligibility("2011-05", approvals={"2011-05"}) == "RELEASE_ELIGIBLE"
    assert c.RELEASE_APPROVALS == frozenset()


def test_default_export_selects_nothing(built):
    assert c.candidate_values(built) == {}


def test_future_export_selector_cannot_include_june_2011(built):
    every = {m for m, v in vals(built["cbs_btc_per_house_cm_c1"]).items() if v is not None}
    assert "2011-06" in every  # the diagnostic value still exists for research
    with pytest.raises(c.Btc04eError):
        c.candidate_values(built, approved=every)
    with pytest.raises(c.Btc04eError):
        c.candidate_values(built, approved={"2011-06"})
    ok = c.candidate_values(built, approved={"2011-05", "2011-07"})
    assert sorted(ok) == ["2011-05", "2011-07"] and "2011-06" not in ok
    assert [m for m in sorted(every) if c.month_eligibility(m, approvals=every) == "RELEASE_ELIGIBLE"].count("2011-06") == 0
    with pytest.raises(c.Btc04eError):
        c.candidate_values(built, approved={"2010-07"})  # null / unsupported month


def test_june_2011_is_hold_in_metadata_and_outside_chart_segments(built):
    meta = c.month_metadata(built, CM)
    assert meta["2011-06"]["release_eligibility"] == "RESEARCH_ONLY_HOLD" and meta["2011-05"]["release_eligibility"] == "RESEARCH_ONLY"
    segs = c.chart_segments(built)
    assert segs and all(not (s["first"] <= "2011-06" <= s["last"]) for s in segs)
    assert vals(built["cbs_btc_per_house_cm_c1"])["2011-06"] is not None  # internal diagnostic value is preserved


# ---- ECB calendar integrity
def test_unexpected_missing_ecb_business_day_blocks_that_month_only():
    ecb = {k: v for k, v in ECB.items() if k != "2012-05-15"}  # a Tuesday, not a TARGET holiday
    assert c.blocked_ecb_months(ecb) == ["2012-05"]
    b = c.build_from_daily(CM, ecb, house(), STAMP)
    assert vals(b["ecb_usd_per_eur_monthly"])["2012-05"] is None and vals(b["cbs_btc_per_house_cm_c1"])["2012-05"] is None
    assert vals(b["cbs_btc_per_house_cm_c1"])["2012-04"] is not None and vals(b["cbs_btc_per_house_cm_c1"])["2012-06"] is not None
    assert vals(b["cm_priceusd_monthly"])["2012-05"] is not None  # the BTC leg is intact; only the FX leg is blocked


def test_target_holidays_and_weekends_do_not_block_a_month():
    ecb = {k: v for k, v in ECB.items() if k not in ("2012-04-06", "2012-04-09", "2012-05-01")}  # Good Friday, Easter Monday, 1 May
    assert c.blocked_ecb_months(ecb) == []
    b = c.build_from_daily(CM, ecb, house(), STAMP)
    assert vals(b["cbs_btc_per_house_cm_c1"])["2012-04"] is not None and vals(b["cbs_btc_per_house_cm_c1"])["2012-05"] is not None
    rep = c.ecb_calendar_report(ecb)
    assert rep["unexpected_missing_business_days"] == 0 and rep["target_holidays_missing"] >= 3 and rep["weekend_days_with_rate"] == 0


def test_validation_window_count_drives_the_run_status():
    ecb = {k: v for k, v in ECB.items() if k != "2012-05-15"}
    cal = c.ecb_calendar_report(ecb)
    assert cal["unexpected_in_validation_window"] == 1
    assert c.finalize(good_run(ecb_calendar=cal), "validate")["status"] == "VALIDATION_FAILED"
    clean = c.ecb_calendar_report(ECB)
    assert clean["unexpected_in_validation_window"] == 0
    assert c.finalize(good_run(ecb_calendar=clean), "validate")["status"] == "COMPLETE_RESEARCH"


def test_weekend_fixing_is_reported_and_fails_validation():
    ecb = dict(ECB)
    ecb["2012-05-19"] = Decimal("1.3")  # Saturday
    cal = c.ecb_calendar_report(ecb)
    assert cal["weekend_days_with_rate"] == 1 and c.finalize(good_run(ecb_calendar=cal), "validate")["status"] == "VALIDATION_FAILED"


def test_blocking_does_not_change_the_pinned_derived_hash_when_the_calendar_is_clean(built):
    assert c.blocked_ecb_months(ECB) == []
    assert c.derived_values_sha256(c.build_from_daily(CM, ECB, house(), STAMP)) == c.derived_values_sha256(built)
