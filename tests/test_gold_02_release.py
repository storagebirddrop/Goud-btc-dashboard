import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl.gold_monthly import build_candidate
from etl.gold_02_release import make_bundle
from etl.gold_publication_candidate import sha


def fixture():
    housing = Path("data/cbs-housing.csv")
    public = Path("frontend/public/data/monthly.json")  # published GOLD-03 JSON = pinned baseline
    rows = json.loads(public.read_bytes())["data"]
    months = [r["period"] for r in rows]
    homes = {r["period"]: D(str(r["house_eur"])) for r in rows}
    gold = {m: D("300") + D(i) for i, m in enumerate(months)}
    fx = {m: D("1.2") for m in months}
    return housing, public, build_candidate(gold, fx, homes, {m: 20 for m in months})


def bundle(candidate=None):
    housing, public, generated = fixture()
    return make_bundle(housing, public, candidate or generated,
        wb_sha256="a" * 64, ecb_sha256="b" * 64,
        commit="f" * 40, run_id="12345", generated_at="2026-10-19T12:00:00+00:00")


def test_gold02_full_coverage_and_reproducible_manifest():
    a, b = bundle(), bundle()
    assert a == b
    rows = json.loads(a["monthly.gold-release-review.json"])["data"]
    manifest = json.loads(a["manifest.json"])
    diff = json.loads(a["diff.json"])
    assert len(rows) == 320
    assert rows[0]["period"] == "2000-01" and rows[-1]["period"] == "2026-08"
    assert rows[0]["gold_index"] == 100
    assert all(r["gold_eur_oz"] is None for r in rows)
    assert manifest["status"] == "REVIEW_ONLY / NOT_DEPLOYED"
    assert manifest["release_authorized"] is False
    assert manifest["candidate_json_sha256"] == sha(a["monthly.gold-release-review.json"])
    assert manifest["coverage"]["complete"] == 320
    assert manifest["coverage"]["pending"] == 0
    assert diff["changed_months"] == 320
    assert all(x["fields"] and set(x["fields"]) <= {"gold_index", "gold_grams_per_house"}
               for x in diff["changes"])


def test_gold02_missing_month_blocks():
    _, _, candidate = fixture()
    candidate["coverage"].pop(15)
    with pytest.raises(ValueError, match="Gold coverage"):
        bundle(candidate)


def test_gold02_invalid_formula_blocks():
    _, _, candidate = fixture()
    candidate["data"][0]["gold_index"] = "101"
    with pytest.raises(ValueError, match="Candidate formula mismatch"):
        bundle(candidate)


def test_gold02_unexpected_source_revision_blocks():
    _, _, candidate = fixture()
    candidate["data"][5]["house_eur"] = "1"
    with pytest.raises(ValueError, match="CBS candidate/public mismatch"):
        bundle(candidate)


def test_gold02_no_raw_public_fields():
    rows = json.loads(bundle()["monthly.gold-release-review.json"])["data"]
    assert all(set(r) == {"period", "house_eur", "hpi", "hpi_index",
                          "gold_eur_oz", "gold_index", "gold_grams_per_house"} for r in rows)
    assert all(r["gold_eur_oz"] is None for r in rows)


def test_gold02_published_baseline_requires_exact_reproduction():
    """Against the published GOLD-03 JSON: identical candidate -> 0 changes; any other -> blocked."""
    from etl.gold_publication_candidate import APPROVED_PUBLIC_JSON_SHA256
    housing, published = Path("data/cbs-housing.csv"), Path("frontend/public/data/monthly.json")
    assert sha(published.read_bytes()) == APPROVED_PUBLIC_JSON_SHA256
    _, _, synthetic = fixture()
    # Synthetic inputs differ from the published values in every month: full-change path still works.
    out = make_bundle(housing, published, synthetic, wb_sha256="a" * 64, ecb_sha256="b" * 64,
                      commit="f" * 40, run_id="1", generated_at="2026-10-21T00:00:00+00:00")
    assert json.loads(out["diff.json"])["changed_months"] >= 319
    assert json.loads(out["manifest.json"])["diff"]["reproduces_published_bytes"] is False
