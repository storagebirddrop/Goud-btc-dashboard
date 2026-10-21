import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import hist_08_bundle as hb

ROOT = Path(__file__).resolve().parents[1]
RAW = "a" * 64
STAMP = "2026-10-21T00:00:00+00:00"
MONTHS = ["2020-01", "2020-02", "2020-03"]


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def synth(sid, asset, values, ccy, unit, kind, **kw):
    return hb.source_series(sid, asset, values, frequency="monthly", currency=ccy, unit=unit, kind=kind,
                            definition_id=f"def_{sid}", source_id="fixture", raw_sha256=RAW, retrieved_at=STAMP,
                            vintage="v1", quality_of=kw.pop("quality_of", lambda p: "PROPOSED"), **kw)


def test_cbs_counts_and_ranges():
    a, b = hb.cbs_1995_1999_series(), hb.cbs_2000_series()
    assert [(o.period) for o in a.observations][::59] == ["1995-01", "1999-12"] and len(a.observations) == 60
    assert (b.observations[0].period, b.observations[-1].period, len(b.observations)) == ("2000-01", "2026-08", 320)
    assert hm.coverage_report(b)["missing"] == [] if "missing" in hm.coverage_report(b) else True
    assert a.observations[0].value == Decimal("88991") and b.observations[0].value == Decimal("157270.0")


def test_cbs_segments_stay_separate_and_flagged():
    a = hb.cbs_1995_1999_series()
    assert a.series_id != hb.cbs_2000_series().series_id
    assert "RETROSPECTIVE_EUR" in a.observations[0].flags and a.breaks[0].period == "1995-01"


def test_bundle_valid_and_deterministic():
    one = hb.bundle_bytes(hb.build_bundle([hb.cbs_1995_1999_series(), hb.cbs_2000_series()]))
    two = hb.bundle_bytes(hb.build_bundle([hb.cbs_1995_1999_series(), hb.cbs_2000_series()]))
    assert one == two and hm.validate_bundle(json.loads(one)) == []


def test_publication_allowlist_stays_empty_and_denies():
    assert hm.ALLOWLIST == ()
    with pytest.raises(hm.PublicationDenied):
        hm.publication_gate([hb.cbs_2000_series()])


def test_existing_public_data_untouched():
    assert sha("frontend/public/data/monthly.json") == "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
    assert sha("data/cbs-housing.csv") == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"


def test_grams_and_sats_over_actual_overlap_only():
    house = synth("house_eur", "housing", dict(zip(MONTHS, ["300000", "303000", "306000"])), "EUR", "EUR", "average_price")
    gold = synth("gold_eur_oz", "gold", {"2020-02": "1500", "2020-03": "1600"}, "EUR", "EUR_per_troy_oz", "spot_price")
    g = hm.grams_per_house(house, gold)
    vals = {p.period: p.value for p in g.points}
    assert "2020-01" not in vals and list(vals) == ["2020-02", "2020-03"]  # only the actual overlap, no fill
    assert abs(vals["2020-02"] - Decimal("303000") * hm.TROY_OUNCE_GRAMS / Decimal("1500")) < Decimal("1e-20")
    btc = synth("btc_eur", "bitcoin", {"2020-03": "6000"}, "EUR", "EUR_per_BTC", "spot_price")
    s = hm.sats_per_house(house, btc)
    assert {p.period: p.value for p in s.points}["2020-03"] == Decimal("306000") / Decimal("6000") * 100000000
    with pytest.raises(hm.PublicationDenied):
        hm.publication_gate([s], [hm.ReleaseRecord("r", hm.release_hash([s]), "o", "2026-01-01", "d", (s.series_id,))])


def test_nlg_gold_cannot_meet_eur_house_silently():
    house = synth("house_eur", "housing", dict(zip(MONTHS, ["1", "2", "3"])), "EUR", "EUR", "average_price")
    gold = synth("gold_nlg_oz", "gold", dict(zip(MONTHS, ["1", "2", "3"])), "NLG", "NLG_per_troy_oz", "spot_price")
    with pytest.raises(hm.ModelError):
        hm.grams_per_house(house, gold)


def test_quality_label_is_mandatory_and_validated():
    with pytest.raises(TypeError):
        hb.source_series("x_series", "gold", {"2020-01": "1"}, frequency="monthly", currency="EUR", unit="EUR",
                         kind="spot_price", definition_id="d", source_id="s", raw_sha256=RAW, retrieved_at=STAMP,
                         vintage="v")
    with pytest.raises(hm.ModelError):
        synth("x_series", "gold", {"2020-01": "1"}, "EUR", "EUR", "spot_price", quality_of=lambda p: "GREAT")


@pytest.mark.parametrize("bad", ["0", "-5", "nan", "inf", 1.5, None, ""])
def test_corrupted_values_rejected(bad):
    with pytest.raises((hm.ModelError, TypeError)):
        synth("x_series", "gold", {"2020-01": bad}, "EUR", "EUR", "spot_price")


def test_empty_and_malformed_periods_rejected():
    with pytest.raises(hm.ModelError):
        synth("x_series", "gold", {}, "EUR", "EUR", "spot_price")
    with pytest.raises(hm.ModelError):
        synth("x_series", "gold", {"2020": "1"}, "EUR", "EUR", "spot_price")


def test_corrupted_fixture_and_csv(tmp_path):
    doc = json.loads((ROOT / "data/fixtures/cbs-1995-1999-i1.json").read_text())
    bad = tmp_path / "f.json"
    doc["data"][1]["date"] = doc["data"][0]["date"]  # duplicate period
    bad.write_text(json.dumps(doc))
    with pytest.raises(hm.ModelError, match="duplicate"):
        hb.cbs_1995_1999_series(bad)
    doc = json.loads((ROOT / "data/fixtures/cbs-1995-1999-i1.json").read_text())
    doc["data"][0]["value"] = 88991.5  # float
    bad.write_text(json.dumps(doc))
    with pytest.raises(hm.ModelError, match="integer"):
        hb.cbs_1995_1999_series(bad)
    csvp = tmp_path / "c.csv"
    csvp.write_text("date,series,value\n2000-01,nl_house_avg_eur,1\n2000-01,nl_house_avg_eur,2\n")
    with pytest.raises(hm.ModelError, match="duplicate"):
        hb.cbs_2000_series(csvp)


def test_source_revision_detected():
    a = hb.cbs_2000_series()
    b = replace(a, observations=tuple(replace(o, value=o.value + 1 if o.period == "2000-01" else o.value,
                                              vintage="csv:other") for o in a.observations))
    revs = hm.detect_revisions(a, b)
    assert revs and revs[0].kind == "value_changed"


def test_annual_cannot_become_monthly():
    annual = hb.source_series("ann_series", "housing", {"2019": "1", "2020": "2"}, frequency="annual", currency="EUR",
                              unit="EUR", kind="average_price", definition_id="d", source_id="s", raw_sha256=RAW,
                              retrieved_at=STAMP, vintage="v", quality_of=lambda p: "PROPOSED")
    with pytest.raises(hm.FrequencyError):
        hm.convert_frequency(annual, "monthly")


def test_tampered_lineage_detected():
    house = synth("house_eur", "housing", dict(zip(MONTHS, ["1", "2", "3"])), "EUR", "EUR", "average_price")
    gold = synth("gold_eur_oz", "gold", dict(zip(MONTHS, ["1", "2", "3"])), "EUR", "EUR_per_troy_oz", "spot_price")
    bundle = hb.build_bundle([house, gold, hm.grams_per_house(house, gold)])
    bundle["series"][0]["observations"][0]["value"] = "9"
    assert any("lineage hash" in e for e in hm.validate_bundle(bundle))
