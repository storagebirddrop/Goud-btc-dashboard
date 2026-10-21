"""Offline tests for tools.hist_06_housing: synthetic fixtures only (prove code, not source values)."""
import json
from decimal import Decimal as D

import pytest

from tools import hist_06_housing as h


def S(name, unit, stat, freq, pairs):
    return h.make_series(name, unit, stat, freq, [(p, D(str(v))) for p, v in pairs])


def test_ordered_unique_periods_ok():
    s = S("a", "EUR", "mean", "A", [("2000", 100), ("2001", 110)])
    assert h.as_dict(s)["2001"] == D(110)


def test_unordered_periods_rejected():
    with pytest.raises(h.UnorderedPeriods):
        S("a", "EUR", "mean", "A", [("2001", 100), ("2000", 110)])


def test_duplicate_periods_rejected():
    with pytest.raises(h.DuplicatePeriod):
        S("a", "EUR", "mean", "M", [("2000-01", 1), ("2000-01", 2)])


def test_non_positive_rejected():
    with pytest.raises(h.HousingError):
        S("a", "EUR", "mean", "A", [("2000", 0)])


def test_annual_to_monthly_forbidden():
    with pytest.raises(h.ForbiddenConversion):
        h.annual_to_monthly(S("a", "EUR", "mean", "A", [("2000", 1)]))


def test_interpolation_forbidden():
    with pytest.raises(h.ForbiddenConversion):
        h.interpolate([1, None, 3])


def test_gap_not_bridged_in_growth():
    s = S("a", "EUR", "mean", "A", [("2000", 100), ("2002", 121)])
    assert h.growth(s) == {}


def test_incomplete_year_omitted_not_filled():
    pairs = [(f"2000-{m:02d}", 100) for m in range(1, 13)] + [(f"2001-{m:02d}", 100) for m in range(1, 12)]
    a = h.annual_mean_of_complete_years(S("m", "EUR", "mean", "M", pairs))
    assert [p for p, _ in a.values] == ["2000"] and a.statistic == "mean_of_monthly_means"


def test_hash_mismatch():
    import hashlib
    raw = b"abc"
    assert h.verify_sha256(raw, hashlib.sha256(raw).hexdigest())
    with pytest.raises(h.HashMismatch):
        h.verify_sha256(raw, "0" * 64)


def test_unit_mixing_rejected():
    nvm = S("n", "kEUR", "mean", "A", [("2000", 172)])
    cbs = S("c", "EUR", "mean", "A", [("2000", 172050)])
    with pytest.raises(h.UnitMismatch):
        h.overlap_rows(nvm, cbs)
    assert h.overlap_rows(h.rescale(nvm, D(1000), "EUR"), cbs)[0]["abs_diff"] == D(-50)


def test_statistic_and_currency_mixing_rejected():
    mean = S("n", "EUR", "mean", "A", [("2000", 1)])
    med = S("n", "EUR", "median", "A", [("2000", 1)])
    nlg = S("n", "NLG", "mean", "A", [("2000", 1)])
    with pytest.raises(h.UnitMismatch):
        h.overlap_rows(mean, med)
    with pytest.raises(h.UnitMismatch):
        h.overlap_rows(mean, nlg)
    with pytest.raises(h.UnitMismatch):
        h.rescale(nlg, D(1000), "EUR")


def test_nlg_to_eur_is_derived_and_exact():
    nlg = S("n", "NLG", "median", "A", [("1995", 223000)])
    e = h.nlg_to_eur(nlg)
    assert e.unit == "EUR_FROM_NLG" and h.as_dict(e)["1995"] == D(223000) / h.NLG_PER_EUR
    with pytest.raises(h.UnitMismatch):
        h.nlg_to_eur(e)
    with pytest.raises(h.UnitMismatch):
        h.overlap_rows(e, S("c", "EUR", "median", "A", [("1995", 1)]))


def test_deflate_requires_full_cpi_and_nominal():
    nom = S("n", "EUR", "mean", "A", [("2000", 100), ("2001", 110)])
    cpi = S("cpi", "INDEX_1900", "index", "A", [("2000", 100), ("2001", 105)])
    real = h.deflate(nom, cpi, 2000)
    assert h.as_dict(real)["2001"] == D(110) * 100 / 105 and real.unit == "EUR_REAL_2000"
    with pytest.raises(h.HousingError):
        h.deflate(nom, S("cpi", "INDEX_1900", "index", "A", [("2000", 100)]), 2000)
    with pytest.raises(h.UnitMismatch):
        h.deflate(real, cpi, 2000)


def test_parse_year_rows_blocks_and_negatives():
    txt = "Tabel\n1975 47\n1976 52\n1977 58\n\nrest\n1980 90 91\n"
    blocks = h.parse_year_rows(txt)
    assert [len(b) for b in blocks] == [3, 1]
    assert h.pick_value_column(blocks[0]) == {1975: D(47), 1976: D(52), 1977: D(58)}
    with pytest.raises(h.DuplicatePeriod):
        h.parse_year_rows("1975 47\n1975 48\n")
    with pytest.raises(h.UnorderedPeriods):
        h.parse_year_rows("1976 47\n1975 48\n")


def test_to_decimal_dutch_formats():
    assert h.to_decimal("223.000") == D(223000)
    assert h.to_decimal("93,5") == D("93.5")
    with pytest.raises(h.HousingError):
        h.to_decimal("abc")


def test_overlap_growth_break_on_synthetic_step():
    years = [str(y) for y in range(1995, 2011)]
    cbs = S("c", "EUR", "mean", "A", [(y, 100000 * 1.05 ** i) for i, y in enumerate(years)])
    nvm = S("n", "EUR", "mean", "A", [(y, 100000 * 1.05 ** i * (1.0 if i < 8 else 1.2)) for i, y in enumerate(years)])
    rows = h.overlap_rows(nvm, cbs)
    assert h.summarize_rows(rows)["n"] == 16
    br = h.ratio_break_scan(rows)
    assert br["split_before_period"] == "2003"
    gd = h.growth_differences(nvm, cbs)
    assert gd["max_diff_year"] == 2003
    assert h.growth_outliers(gd["diffs"]) == ["2003"]
    assert h.cumulative_drift(rows) == "20.00"


def test_break_scan_needs_enough_points():
    s = S("c", "EUR", "mean", "A", [(str(y), 100 + y) for y in range(2000, 2005)])
    assert h.ratio_break_scan(h.overlap_rows(s, s)) is None


def test_mix_effect():
    avg = S("a", "EUR", "mean", "A", [("2000", 100), ("2001", 110), ("2002", 121)])
    idx = S("i", "INDEX_CBS", "index", "A", [("2000", 100), ("2001", 105), ("2002", 110.25)])
    m = h.mix_effect(avg, idx)
    assert m["n"] == 2 and m["mean_pp"] == "5.00"


def test_cbs_annual_from_typed_rows():
    rows = [{"Perioden": "1995JJ00", "GemiddeldeVerkoopprijs_7": 93750, "PrijsindexVerkoopprijzen_1": 31.1, "AantalVerkochteWoningen_4": 154568},
            {"Perioden": "1995MM01", "GemiddeldeVerkoopprijs_7": 88991},
            {"Perioden": "1996JJ00", "GemiddeldeVerkoopprijs_7": 102607, "PrijsindexVerkoopprijzen_1": 33.0, "AantalVerkochteWoningen_4": 1}]
    avg, idx, cnt = h.cbs_annual_from_typed(rows)
    assert [p for p, _ in avg.values] == ["1995", "1996"]
    assert cnt["1995"] == D(154568)


def test_cli_digest_roundtrip(tmp_path, capsys):
    doc = {"status": "X", "defects": [], "fetch": {}, "vm": {}, "text": {}, "cbs": {}}
    p = tmp_path / "d.json"
    p.write_text(json.dumps(doc))
    assert h.main(["digest", str(p)]) == 0
    assert "status=X" in capsys.readouterr().out
