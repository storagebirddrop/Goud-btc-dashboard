import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl.gold_monthly import build_candidate
from etl.gold_publication_candidate import render, sha, APPROVED_CBS_SHA256, APPROVED_PUBLIC_JSON_SHA256
from etl.static_export import build


def approved():
    housing = Path("data/cbs-housing.csv")
    raw = housing.read_bytes()
    baseline = Path("frontend/public/data/monthly.json").read_bytes()
    assert sha(raw) == APPROVED_CBS_SHA256
    assert sha(baseline) == APPROVED_PUBLIC_JSON_SHA256
    return housing, raw, baseline


def synthetic():
    housing, raw, baseline = approved()
    months = [r["period"] for r in json.loads(baseline)["data"]]
    homes = {r["period"]: D(str(r["house_eur"])) for r in json.loads(baseline)["data"]}
    gold = {m: D("300") + D(i) for i, m in enumerate(months)}
    fx = {m: D("1.2") for m in months}
    counts = {m: 20 for m in months}
    return housing, raw, baseline, build_candidate(gold, fx, homes, counts)


def test_full_320_month_gold_export_only_derived():
    housing, raw, baseline, candidate = synthetic()
    output, manifest = render(raw, baseline, candidate, housing_path=housing,
                              gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)
    rows = json.loads(output)["data"]
    previous = json.loads(baseline)["data"]
    assert len(rows) == 320
    assert [r["period"] for r in rows] == [r["period"] for r in previous]
    assert rows[0]["period"] == "2000-01"
    assert rows[0]["gold_index"] == 100
    assert all(r["gold_eur_oz"] is None for r in rows)
    assert all(r["gold_index"] is not None and r["gold_grams_per_house"] is not None for r in rows)
    assert all(all(r[k] == old[k] for k in ("house_eur", "hpi", "hpi_index"))
               for r, old in zip(rows, previous))
    assert all(set(r) == set(previous[0]) for r in rows)
    assert json.loads(manifest)["candidate_json_sha256"] == sha(output)
    assert (output, manifest) == render(raw, baseline, candidate, housing_path=housing,
                                       gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)


def test_baseline_drift_fails_closed():
    housing, raw, baseline, candidate = synthetic()
    with pytest.raises(ValueError, match="APPROVED_CBS_BASELINE_HASH_MISMATCH"):
        render(raw + b" ", baseline, candidate, housing_path=housing,
               gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)


def test_missing_gold_month_fails_closed():
    housing, raw, baseline, candidate = synthetic()
    candidate["coverage"].pop(30)
    with pytest.raises(ValueError, match="Gold coverage"):
        render(raw, baseline, candidate, housing_path=housing,
               gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)


def test_unapproved_source_gap_fails_closed():
    housing, raw, baseline, candidate = synthetic()
    candidate["coverage"][10]["status"] = "missing_historical"
    with pytest.raises(ValueError, match="Historical gold source gap"):
        render(raw, baseline, candidate, housing_path=housing,
               gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)


def test_gold_formula_tampering_fails_closed():
    housing, raw, baseline, candidate = synthetic()
    candidate["data"][0]["gold_index"] = "101"
    with pytest.raises(ValueError, match="Candidate formula mismatch"):
        render(raw, baseline, candidate, housing_path=housing,
               gold_source_sha256="a" * 64, ecb_source_sha256="b" * 64)
