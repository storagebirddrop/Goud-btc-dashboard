import csv
import hashlib
import io
import json
import shutil
import zipfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import hist_08_bundle as hb
from tools import hist_09_bundle as h9

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "fixtures" / "hist09"
CSV = ROOT / "data" / "cbs-housing.csv"


@pytest.fixture(scope="module")
def built():
    return h9.build_all(INPUTS)


def zip_rows():
    with zipfile.ZipFile(INPUTS / h9.CBS_ZIP_NAME) as z:
        return list(csv.DictReader(io.StringIO(z.read("Observations.csv").decode("utf-8-sig")), delimiter=";"))


def dutch(text):
    return Fraction(text.replace(".", "").replace(",", "."))


def corrupted_inputs(tmp_path, mutate):
    """Copy the inputs and rewrite Observations.csv inside the CBS zip through mutate(list_of_rows)."""
    d = tmp_path / "in"
    shutil.copytree(INPUTS, d)
    with zipfile.ZipFile(INPUTS / h9.CBS_ZIP_NAME) as z:
        members = {n: z.read(n) for n in z.namelist()}
    rows = list(csv.DictReader(io.StringIO(members["Observations.csv"].decode("utf-8-sig")), delimiter=";"))
    rows = mutate(rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["Id", "Measure", "Perioden", "Value", "StringValue", "ValueAttribute"],
                       delimiter=";", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    members["Observations.csv"] = buf.getvalue().encode("utf-8")
    with zipfile.ZipFile(d / h9.CBS_ZIP_NAME, "w") as z:
        for n, b in members.items():
            z.writestr(n, b)
    return d


# ---- package integrity and source hashes ----
def test_package_manifest_and_pins_verify():
    validation = h9.verify_package(INPUTS)
    assert validation["nvm_total_observations"] == 52 and validation["cbs_monthly_observations"] == 72
    assert hashlib.sha256((INPUTS / h9.CBS_ZIP_NAME).read_bytes()).hexdigest() == h9.CBS_ZIP_SHA256


def test_corrupted_package_is_rejected(tmp_path):
    d = tmp_path / "in"
    shutil.copytree(INPUTS, d)
    nvm = d / "HIST09_NVM_1975_2000_RESEARCH.csv"
    nvm.write_text(nvm.read_text().replace("88900", "88901", 1))
    with pytest.raises(h9.InputError, match="manifest"):
        h9.verify_package(d)
    shutil.copy(INPUTS / "HIST09_NVM_1975_2000_RESEARCH.csv", nvm)
    (d / h9.CBS_ZIP_NAME).write_bytes((d / h9.CBS_ZIP_NAME).read_bytes() + b"x")
    with pytest.raises(h9.InputError, match="zip"):
        h9.verify_package(d)


def test_extra_or_missing_manifest_entry_is_rejected(tmp_path):
    d = tmp_path / "in"
    shutil.copytree(INPUTS, d)
    manifest = json.loads((d / "SHA256_MANIFEST.json").read_text())
    manifest.pop("hist09_finalize.py")
    (d / "SHA256_MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(h9.InputError, match="manifest lists"):
        h9.verify_package(d)


# ---- counts, values, units ----
def test_nvm_52_half_years_preserved_in_nlg(built):
    series, _ = built
    nvm = series["nvm_median_nlg_halfyear"]
    assert (nvm.frequency, nvm.currency, nvm.unit, nvm.kind) == ("semiannual", "NLG", "NLG", "median_price")
    assert [o.period for o in nvm.observations] == hm.expected_periods("1975-H1", "2000-H2", "semiannual")
    assert len(nvm.observations) == 52
    values = {o.period: o.value for o in nvm.observations}
    # independently typed from the owner-supplied page 136 screenshot and the first rows of the csv
    assert values["1975-H1"] == Decimal("88900") and values["1995-H1"] == Decimal("220000")
    for period, expected in {"1995-H2": 227800, "1996-H1": 240900, "1996-H2": 250500, "1997-H1": 265100,
                             "1997-H2": 271600, "1998-H1": 283400, "1998-H2": 301000, "1999-H1": 328000,
                             "1999-H2": 352200, "2000-H1": 381700, "2000-H2": 394100}.items():
        assert values[period] == Decimal(expected)
    assert sum("VISUAL_P136_SESSION_REVIEW" in o.flags for o in nvm.observations) == 11
    assert sum("VISUAL_P135_PER_PROJECT_CONTROL" in o.flags for o in nvm.observations) == 41


def test_cbs_72_months_and_three_measures_preserved(built):
    series, _ = built
    price, count, value = (series[k] for k in ("cbs_avg_price_1995_2000", "cbs_sold_homes_1995_2000",
                                               "cbs_total_value_1995_2000"))
    for s in (price, count, value):
        assert [o.period for o in s.observations] == hm.expected_periods("1995-01", "2000-12", "monthly")
        assert len(s.observations) == 72
    assert (price.unit, count.unit, value.unit) == ("EUR", "homes", "EUR_million")
    rows = zip_rows()
    for series_obj, measure in ((price, "M001534"), (count, "M001532_2"), (value, "M001535")):
        official = {r["Perioden"]: dutch(r["Value"]) for r in rows if r["Measure"] == measure and "MM" in r["Perioden"]
                    and "1995" <= r["Perioden"][:4] <= "2000"}
        assert {o.period.replace("-", "MM"): Fraction(o.value) for o in series_obj.observations} == official
    assert price.observations[0].value == Decimal("88991") and count.observations[0].value == Decimal("8793")


def test_hist09_monthly_csv_equals_zip_values(built):
    series, _ = built
    price = {o.period: o.value for o in series["cbs_avg_price_1995_2000"].observations}
    for r in csv.DictReader((INPUTS / "HIST09_CBS_1995_2000_MONTHLY.csv").open()):
        assert price[r["period"].replace("MM", "-")] == Decimal(r["average_sale_price_eur"])


# ---- aggregation, conversion, overlap ----
def test_weighted_half_year_mean_is_exact_independent_recalculation(built):
    series, _ = built
    half = {p.period: p.value for p in series["cbs_avg_price_eur_halfyear"].points}
    rows = zip_rows()
    for year, h, months in ((1995, 1, range(1, 7)), (1996, 1, range(1, 7)), (2000, 2, range(7, 13))):
        price = {r["Perioden"]: dutch(r["Value"]) for r in rows if r["Measure"] == "M001534"}
        count = {r["Perioden"]: dutch(r["Value"]) for r in rows if r["Measure"] == "M001532_2"}
        keys = [f"{year}MM{m:02d}" for m in months]
        expected = sum(price[k] * count[k] for k in keys) / sum(count[k] for k in keys)  # exact Fraction
        got = Fraction(half[f"{year}-H{h}"])
        assert abs(got - expected) < Fraction(1, 10**25)
    assert len(half) == 12


def test_nlg_to_eur_is_denomination_only(built):
    series, _ = built
    eur = {p.period: p.value for p in series["nvm_median_eur_halfyear"].points}
    assert abs(Fraction(eur["1975-H1"]) - Fraction(88900) / Fraction("2.20371")) < Fraction(1, 10 ** 25)  # context-independent
    assert abs(eur["1995-H1"] - Decimal("99831.64754")) < Decimal("1e-5")
    s = series["nvm_median_eur_halfyear"]
    assert s.basis == "nominal" and s.transforms[0]["op"] == "redenominate" and s.transforms[0]["applied"] == 1
    with pytest.raises(hm.CurrencyMismatch):  # exactly once
        hm.redenominate_nlg_to_eur(s, series_id="again")


def test_overlap_12_of_12_reproducible_and_matches_summary(built):
    series, _ = built
    assert h9.verify_against_overlap_csv(series, INPUTS) == 12
    gaps = [(p.period, (p.value - 1) * 100) for p in series["nvm_over_cbs_ratio_halfyear"].points]
    pct = [g for _, g in gaps]
    assert len(pct) == 12 and sum(g > 0 for g in pct) == 11 and gaps[-1][0] == "2000-H2" and gaps[-1][1] < 0
    assert abs(sum(pct) / 12 - Decimal("7.1272521667")) < Decimal("1e-5")
    assert abs(min(pct) - Decimal("-0.088511")) < Decimal("1e-5") and abs(max(pct) - Decimal("10.521447")) < Decimal("1e-5")


def test_representative_overlap_records_independent_recalculation():
    rows = zip_rows()
    price = {r["Perioden"]: dutch(r["Value"]) for r in rows if r["Measure"] == "M001534"}
    count = {r["Perioden"]: dutch(r["Value"]) for r in rows if r["Measure"] == "M001532_2"}
    nvm = {"1995-H1": 220000, "1996-H1": 240900}
    for half, months in (("1995-H1", range(1, 7)), ("1996-H1", range(1, 7))):
        keys = [f"{half[:4]}MM{m:02d}" for m in months]
        cbs = sum(price[k] * count[k] for k in keys) / sum(count[k] for k in keys)
        gap = (Fraction(nvm[half]) / Fraction("2.20371") / cbs - 1) * 100
        csv_row = next(r for r in csv.DictReader((INPUTS / "HIST09_NVM_CBS_OVERLAP_1995_2000.csv").open())
                       if r["period"] == half)
        assert f"{float(gap):.6f}" == csv_row["nvm_vs_cbs_pct"]


def test_growth_ratios_and_no_growth_before_predecessor(built):
    series, _ = built
    seq = {p.period: p.value for p in series["cbs_half_growth_sequential"].points}
    yoy = {p.period: p.value for p in series["cbs_half_growth_year_over_year"].points}
    assert "1995-H1" not in seq and "1995-H2" in seq and "1995-H2" not in yoy
    assert min(yoy) == "1996-H1" and min(seq) == "1995-H2" and len(seq) == 11 and len(yoy) == 10


# ---- statistic separation, frequencies ----
def test_median_and_mean_are_never_the_same_statistic(built):
    series, _ = built
    nvm, cbs = series["nvm_median_eur_halfyear"], series["cbs_avg_price_eur_halfyear"]
    assert (nvm.kind, cbs.kind) == ("median_price", "average_price") and nvm.definition_id != cbs.definition_id
    with pytest.raises(hm.DefinitionMismatch):
        hm._combine(nvm, cbs, lambda a, b: a - b, series_id="x_diff", step={"op": "x"})
    with pytest.raises(hm.DefinitionMismatch):
        hm.statistic_ratio(cbs, nvm, series_id="swapped")
    ratio = series["nvm_over_cbs_ratio_halfyear"]
    assert ratio.kind == "statistic_ratio" and all("STATISTICS_DIFFER" in p.flags for p in ratio.points)


def test_frequencies_are_never_substituted(built):
    series, _ = built
    for s, target in ((series["nvm_median_nlg_halfyear"], "monthly"), (series["cbs_avg_price_1995_2000"], "semiannual"),
                      (series["cbs_avg_price_eur_halfyear"], "annual")):
        with pytest.raises(hm.FrequencyError):
            hm.convert_frequency(s, target)
    with pytest.raises(hm.FrequencyError):  # semiannual NVM vs monthly CBS
        hm.statistic_ratio(series["nvm_median_eur_halfyear"], series["cbs_avg_price_1995_2000"], series_id="bad")
    with pytest.raises(hm.FrequencyError):
        hm.weighted_half_year_mean(series["cbs_avg_price_eur_halfyear"], series["cbs_sold_homes_1995_2000"], series_id="bad")
    for bad in ("2000", "2000-01", "2000-H3", "2000H1"):
        with pytest.raises(hm.FrequencyError):
            hm.period_key(bad, "semiannual")
    assert hm.period_label(hm.period_key("1999-H2", "semiannual"), "semiannual") == "1999-H2"


def test_incomplete_half_year_becomes_null_not_a_partial_value(built):
    series, _ = built
    price, count = series["cbs_avg_price_1995_2000"], series["cbs_sold_homes_1995_2000"]
    from dataclasses import replace
    cut = replace(price, observations=tuple(o for o in price.observations if o.period != "1996-03"))
    out = hm.weighted_half_year_mean(cut, count, series_id="cut_half")
    by = {p.period: p for p in out.points}
    assert by["1996-H1"].value is None and "INCOMPLETE_HALF_YEAR" in by["1996-H1"].flags
    assert by["1995-H1"].value is not None


# ---- negative tests on source data ----
def test_missing_month_in_cbs_zip_fails(tmp_path):
    d = corrupted_inputs(tmp_path, lambda rows: [r for r in rows if not (r["Perioden"] == "1997MM05" and r["Measure"] == "M001534")])
    with pytest.raises(h9.InputError, match="72 months"):
        h9.read_cbs_zip(d)


def test_duplicate_and_empty_cbs_observation_fail(tmp_path):
    dup = next(r for r in zip_rows() if r["Perioden"] == "1997MM05" and r["Measure"] == "M001534")
    d = corrupted_inputs(tmp_path, lambda rows: rows + [dup])
    with pytest.raises(h9.InputError, match="duplicate"):
        h9.read_cbs_zip(d)
    d2 = corrupted_inputs(tmp_path / "b", lambda rows: [dict(r, Value="") if (r["Perioden"], r["Measure"]) == ("1997MM05", "M001534") else r for r in rows])
    with pytest.raises(h9.InputError, match="missing official value"):
        h9.read_cbs_zip(d2)


def test_non_positive_cbs_value_fails(tmp_path):
    d = corrupted_inputs(tmp_path, lambda rows: [dict(r, Value="-5") if (r["Perioden"], r["Measure"]) == ("1997MM05", "M001532_2") else r for r in rows])
    with pytest.raises(h9.InputError, match="non-positive"):
        h9.read_cbs_zip(d)


def test_monthly_counts_not_matching_official_quarter_fail(tmp_path):
    d = corrupted_inputs(tmp_path, lambda rows: [dict(r, Value="9.999") if (r["Perioden"], r["Measure"]) == ("1997MM05", "M001532_2") else r for r in rows])
    cbs = h9.read_cbs_zip(d)
    with pytest.raises(h9.InputError, match="quarterly count"):
        h9.check_quarter_counts(cbs)


def test_corrupted_nvm_csv_fails(tmp_path):
    src = (INPUTS / "HIST09_NVM_1975_2000_RESEARCH.csv").read_text().splitlines()
    cases = {
        "missing": [l for i, l in enumerate(src) if i != 10],
        "duplicate": src + [src[5]],
        "negative": [l.replace("88900", "-88900") if i == 1 else l for i, l in enumerate(src)],
        "wrong_table": [l.replace("OTB_2001_Table_B3.8", "OTHER") if i == 3 else l for i, l in enumerate(src)],
        "wrong_p136": [l.replace(",227800,", ",227801,") for l in src],
    }
    for name, lines in cases.items():
        d = tmp_path / name
        d.mkdir()
        (d / "HIST09_NVM_1975_2000_RESEARCH.csv").write_text("\n".join(lines) + "\n")
        with pytest.raises(hm.ModelError):
            h9.read_nvm_csv(d)


def test_overlap_csv_tampering_detected(built, tmp_path):
    series, _ = built
    d = tmp_path / "in"
    shutil.copytree(INPUTS, d)
    f = d / "HIST09_NVM_CBS_OVERLAP_1995_2000.csv"
    f.write_text(f.read_text().replace("9.644481", "9.644482"))
    with pytest.raises(h9.InputError, match="differs from the bundle"):
        h9.verify_against_overlap_csv(series, d)


# ---- integration with HIST-08, determinism, safety ----
def test_hist08_cbs_series_reconcile_without_conflict(built):
    series, _ = built
    out = h9.reconcile_with_hist08({"price": series["cbs_avg_price_1995_2000"]}, hist08_csv=CSV)
    assert out == {"fixture_1995_1999": 60, "csv_2000": 12}


def test_hist08_conflict_is_detected(built, tmp_path):
    series, _ = built
    bad = tmp_path / "c.csv"
    lines = CSV.read_text().splitlines()
    bad.write_text("\n".join(l.replace("157270.0", "157271.0") if l.startswith("2000-01,nl_house_avg_eur,") else l for l in lines) + "\n")
    with pytest.raises(h9.InputError, match="conflicts"):
        h9.reconcile_with_hist08({"price": series["cbs_avg_price_1995_2000"]}, hist08_csv=bad)


def test_bundles_validate_and_are_deterministic(tmp_path):
    first = h9.write_outputs(h9.build_all(INPUTS)[1], tmp_path / "a")
    second = h9.write_outputs(h9.build_all(INPUTS)[1], tmp_path / "b")
    assert first == second
    for name in first:
        a, b = (tmp_path / "a" / name).read_bytes(), (tmp_path / "b" / name).read_bytes()
        assert a == b and hm.validate_bundle(json.loads(a)) == []
    assert [len(v["series"]) for v in first.values()] == [2, 4, 11]


def test_bundle_lineage_tamper_detected(tmp_path):
    h9.write_outputs(h9.build_all(INPUTS)[1], tmp_path)
    bundle = json.loads((tmp_path / "hist09_C_overlap.json").read_text())
    bundle["series"][2]["observations"][0]["value"] = "1"
    assert any("lineage hash" in e for e in hm.validate_bundle(bundle))


def test_publication_allowlist_empty_and_gate_denies(built):
    series, _ = built
    assert hm.ALLOWLIST == ()
    for s in series.values():
        with pytest.raises(hm.PublicationDenied):
            hm.publication_gate([s])


def test_existing_public_data_untouched():
    assert hashlib.sha256((ROOT / "frontend/public/data/monthly.json").read_bytes()).hexdigest() == \
        "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"


# ---- ARCH-02 frequency-conversion contract (pre-merge audit) ----
from dataclasses import replace  # noqa: E402


def _flip(series, **changes):
    """Series copy with consistent observation metadata (currency/unit) for contract tests."""
    obs_changes = {k: v for k, v in changes.items() if k in ("currency", "unit")}
    rows = tuple(replace(o, **obs_changes) for o in series.observations) if obs_changes else series.observations
    return replace(series, observations=rows, **changes)


@pytest.mark.parametrize("source", ["annual", "semiannual", "monthly", "daily"])
@pytest.mark.parametrize("target", ["annual", "semiannual", "monthly", "daily"])
def test_convert_frequency_rejects_every_pair(source, target):
    sample = {"annual": "2000", "semiannual": "2000-H1", "monthly": "2000-01", "daily": "2000-01-01"}[source]
    s = hb.source_series("x_series", "housing", {sample: "1"}, frequency=source, currency="EUR", unit="EUR",
                         kind="average_price", definition_id="d", source_id="s", raw_sha256="a" * 64,
                         retrieved_at="2026-10-22T00:00:00+00:00", vintage="v", quality_of=lambda p: "PROPOSED")
    with pytest.raises(hm.FrequencyError):
        hm.convert_frequency(s, target)


def test_monthly_is_produced_only_by_the_documented_daily_mean():
    import re
    code = (ROOT / "etl" / "hist_model.py").read_text()
    assert len(re.findall(r'frequency="monthly"', code)) == 1 and 'frequency="semiannual"' in code
    assert code.count("def weighted_half_year_mean") == 1
    assert not re.search(r"def\s+\w*(expand|upsample|to_monthly|spread|distribute)", code, re.I)


def test_nvm_halfyear_and_annual_cannot_become_monthly(built):
    series, _ = built
    nvm = series["nvm_median_eur_halfyear"]
    with pytest.raises(hm.FrequencyError):
        hm.weighted_half_year_mean(nvm, series["cbs_sold_homes_1995_2000"], series_id="bad")
    with pytest.raises(hm.FrequencyError):
        hm.monthly_mean(nvm, min_coverage=Decimal("1"), series_id="bad")
    with pytest.raises(hm.FrequencyError):
        hm.weighted_half_year_mean(series["cbs_avg_price_1995_2000"], nvm, series_id="bad")


@pytest.mark.parametrize("label,price_changes,weight_changes,error", [
    ("gold-labelled price", {"asset_class": "gold"}, {}, hm.DefinitionMismatch),
    ("bitcoin-labelled price", {"asset_class": "bitcoin"}, {}, hm.DefinitionMismatch),
    ("equity-labelled price", {"asset_class": "equity"}, {}, hm.DefinitionMismatch),
    ("cpi-labelled price", {"asset_class": "cpi"}, {}, hm.DefinitionMismatch),
    ("gold-labelled weights", {}, {"asset_class": "gold"}, hm.DefinitionMismatch),
    ("spot price kind", {"kind": "spot_price"}, {}, hm.DefinitionMismatch),
    ("median price kind", {"kind": "median_price"}, {}, hm.DefinitionMismatch),
    ("index kind", {"kind": "constant_quality_index"}, {}, hm.DefinitionMismatch),
    ("total return kind", {"kind": "total_return"}, {}, hm.DefinitionMismatch),
    ("price used as weights", {}, {"kind": "average_price", "currency": "EUR", "unit": "EUR"}, hm.DefinitionMismatch),
    ("transaction value as weights", {}, {"kind": "transaction_value", "currency": "EUR", "unit": "EUR_million"}, hm.DefinitionMismatch),
    ("weights in wrong unit", {}, {"unit": "pieces"}, hm.CurrencyMismatch),
    ("real vs nominal basis", {"basis": "real"}, {}, hm.DefinitionMismatch),
])
def test_weighted_half_year_mean_refuses_misuse(built, label, price_changes, weight_changes, error):
    series, _ = built
    price = _flip(series["cbs_avg_price_1995_2000"], **price_changes)
    weights = _flip(series["cbs_sold_homes_1995_2000"], **weight_changes)
    with pytest.raises(error):
        hm.weighted_half_year_mean(price, weights, series_id="misuse")


def test_weighted_half_year_mean_refuses_derived_and_non_monthly_inputs(built):
    series, _ = built
    count = series["cbs_sold_homes_1995_2000"]
    price = series["cbs_avg_price_1995_2000"]
    derived = hm._combine(price, price, lambda a, b: a, series_id="derived_price", step={"op": "copy"})
    assert derived.layer == "derived" and derived.kind == "average_price" and derived.frequency == "monthly"
    with pytest.raises(hm.DefinitionMismatch, match="derived"):  # derived layer cannot be re-aggregated
        hm.weighted_half_year_mean(derived, count, series_id="m")
    for frequency in ("annual", "semiannual", "daily"):
        with pytest.raises(hm.FrequencyError):
            hm.weighted_half_year_mean(replace(series["cbs_avg_price_1995_2000"], frequency=frequency), count, series_id="m")


def test_incomplete_or_misaligned_months_never_give_a_value(built):
    series, _ = built
    price, count = series["cbs_avg_price_1995_2000"], series["cbs_sold_homes_1995_2000"]
    for drop_price, drop_count in (("1996-03", None), (None, "1996-03"), ("1996-01", "1996-06")):
        p = replace(price, observations=tuple(o for o in price.observations if o.period != drop_price))
        c = replace(count, observations=tuple(o for o in count.observations if o.period != drop_count))
        by = {x.period: x for x in hm.weighted_half_year_mean(p, c, series_id="gaps").points}
        assert by["1996-H1"].value is None and "INCOMPLETE_HALF_YEAR" in by["1996-H1"].flags
        assert by["1996-H2"].value is not None
    # a price series that starts mid-half-year cannot yield that half-year
    late = replace(price, observations=tuple(o for o in price.observations if o.period >= "1995-04"))
    assert {x.period: x for x in hm.weighted_half_year_mean(late, count, series_id="late").points}["1995-H1"].value is None


def test_zero_or_negative_weight_cannot_enter(built):
    series, _ = built
    count = series["cbs_sold_homes_1995_2000"]
    for bad in ("0", "-1"):
        rows = (replace(count.observations[0], value=Decimal(bad)),) + count.observations[1:]
        with pytest.raises(hm.ModelError):
            hm.weighted_half_year_mean(series["cbs_avg_price_1995_2000"], replace(count, observations=rows), series_id="w")


def test_breaks_on_price_or_weights_are_carried_to_the_half_year(built):
    series, _ = built
    price = replace(series["cbs_avg_price_1995_2000"], breaks=(hm.Break("1996-03", "definition note"),))
    count = replace(series["cbs_sold_homes_1995_2000"], breaks=(hm.Break("1996-09", "count note"),))
    out = hm.weighted_half_year_mean(price, count, series_id="with_breaks")
    assert [(b.period, "definition note" in b.reason or "count note" in b.reason) for b in out.breaks] == [("1996-H1", True), ("1996-H2", True)]
    assert hm.validate_bundle(json.loads(hb.bundle_bytes(hb.build_bundle([price, count, out])))) == []


def test_source_kind_and_currency_must_be_coherent(built):
    series, _ = built
    for series_id, changes in (("count_in_eur", dict(currency="EUR", unit="EUR")),
                               ("value_none", dict(kind="transaction_value", currency="NONE", unit="EUR_million")),
                               ("ratio_in_eur", dict(kind="statistic_ratio", currency="EUR", unit="EUR"))):
        with pytest.raises(hm.CurrencyMismatch):
            hm.validate_series(_flip(replace(series["cbs_sold_homes_1995_2000"], series_id=series_id), **changes))
    with pytest.raises(hm.CurrencyMismatch):
        hm.validate_series(_flip(series["cbs_avg_price_1995_2000"], currency="NONE", unit="homes"))


def test_statistic_ratio_refuses_other_classes_and_mixed_units(built):
    series, _ = built
    nvm, cbs = series["nvm_median_eur_halfyear"], series["cbs_avg_price_eur_halfyear"]
    with pytest.raises(hm.DefinitionMismatch):
        hm.statistic_ratio(nvm, replace(cbs, asset_class="gold"), series_id="r")
    with pytest.raises(hm.CurrencyMismatch):  # NLG median against a EUR mean
        hm.statistic_ratio(series["nvm_median_nlg_halfyear"], cbs, series_id="r")


def test_weighted_mean_precision_and_determinism(built):
    series, _ = built
    price, count = series["cbs_avg_price_1995_2000"], series["cbs_sold_homes_1995_2000"]
    one = hm.weighted_half_year_mean(price, count, series_id="rep")
    two = hm.weighted_half_year_mean(price, count, series_id="rep")
    assert hm.canonical_json(one) == hm.canonical_json(two)
    p = {o.period: Fraction(o.value) for o in price.observations}
    c = {o.period: Fraction(o.value) for o in count.observations}
    months = [f"1998-{m:02d}" for m in range(7, 13)]
    exact = sum(p[m] * c[m] for m in months) / sum(c[m] for m in months)
    got = Fraction({x.period: x.value for x in one.points}["1998-H2"])
    assert abs(got - exact) < Fraction(1, 10**28)  # 34-digit Decimal precision, not float
