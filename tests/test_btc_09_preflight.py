"""BTC-09: private final preflight tool on a SYNTHETIC vintage (proves code, not data): regeneration under a changed calculation commit keeps every
economic value, key-path diffs are limited to the explained paths, the independent recomputation catches a tampered value, scope checks and the
release_preflight negative battery all refuse."""
import copy
import json

import pytest

from etl import btc_contract as bc
from tests import test_btc_06c_candidate as t6
from tools import btc_06c_candidate as cand
from tools import btc_09_preflight as pf

CSV, LEGACY = t6.CSV, t6.LEGACY


@pytest.fixture(scope="module")
def world(tmp_path_factory, monkeypatch_module):
    base = tmp_path_factory.mktemp("btc09")
    snap = t6.make_snapshot(base / "snap")
    monkeypatch_module.setenv("GITHUB_SHA", "a" * 40)
    hp, hs, _ = cand.build_candidate(snap, CSV, LEGACY)
    cand.write_private(base / "hist", hp, hs)
    monkeypatch_module.setenv("GITHUB_SHA", "b" * 40)
    months = [m for m in sorted(hs["months"]) if m >= "2014-02"]
    expect = (months[0], months[-1], len(months))
    rep = pf.run(snap, CSV, LEGACY, base / "hist", base / "new", expect=expect)
    return {"base": base, "snap": snap, "hp": hp, "hs": hs, "rep": rep, "expect": expect, "months": months}


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_regeneration_under_another_commit_keeps_economics_and_only_explained_paths_differ(world):
    c = world["rep"]["comparison"]
    assert c["identical_economics"] and c["value_differences"] == 0 and c["preview_row_differences"] == 0 and c["same_month_set"]
    assert c["unexplained_preview_paths"] == [] and "btc.provenance.calculation_git_commit" in c["preview_diff_paths"]
    assert world["rep"]["candidate_sha256"] != world["rep"]["historical_candidate_sha256"]  # the commit is hash-bound
    assert world["rep"]["sidecar_sha256"] == world["rep"]["historical_sidecar_sha256"]  # values do not depend on the commit
    assert world["rep"]["ok"] and world["rep"]["replay"] == "IDENTICAL"


def test_report_is_price_free(world):
    text = json.dumps(world["rep"])
    assert "btc_per_house" not in text and "sat_per_house" not in text
    sidecar = world["hs"]["months"]
    sample = sidecar[sorted(sidecar)[40]]["btc_per_house"]
    assert sample[:12] not in text


def test_a_changed_value_quality_or_unexplained_path_is_rejected(world):
    hp, hs = world["hp"], world["hs"]
    s2 = copy.deepcopy(hs)
    k = sorted(s2["months"])[60]
    s2["months"][k]["btc_per_house"] = "1"
    assert pf.compare_candidates(hp, hs, hp, s2)["identical_economics"] is False
    p2 = copy.deepcopy(hp)
    row = next(r for r in p2["data"] if r["btc_meta"]["quality"] is not None)
    row["btc_meta"]["quality"] = "Q2" if row["btc_meta"]["quality"] != "Q2" else "Q1_CANDIDATE"
    assert pf.compare_candidates(hp, hs, p2, hs)["identical_economics"] is False
    p3 = copy.deepcopy(hp)
    p3["btc"]["coverage"]["default_from"] = "2010-08"
    c = pf.compare_candidates(hp, hs, p3, hs)
    assert c["unexplained_preview_paths"] and not c["identical_economics"]
    s3 = copy.deepcopy(hs)
    s3["months"].pop(sorted(s3["months"])[0])
    assert pf.compare_candidates(hp, hs, hp, s3)["same_month_set"] is False


def test_independent_recompute_agrees_and_catches_a_tampered_sidecar(world):
    ok = pf.independent_recompute(world["snap"], CSV, world["hs"])
    assert ok["ok"] and ok["months_checked"] > 100 and ok["mismatches"] == 0
    s2 = copy.deepcopy(world["hs"])
    k = next(m for m in sorted(s2["months"]) if s2["months"][m]["private_state"] == "CANDIDATE_VALUE")
    s2["months"][k]["sat_per_house"] = str(int(float(s2["months"][k]["sat_per_house"]) * 1.0001))
    bad = pf.independent_recompute(world["snap"], CSV, s2)
    assert not bad["ok"] and bad["mismatches"] >= 1


def test_scope_report_requires_the_exact_interval_count_and_no_q3(world):
    auth = {"release_id": "S", "decision_ref": "S", "months": world["months"], "rights_review_ref": "S", "conflicting_contract_check": "VERIFIED",
            **bc.private_hashes(world["hp"], world["hs"])}
    comp = bc.compose_release(world["hp"], world["hs"], auth)
    first, last, n = world["expect"]
    assert pf.scope_report(comp, (first, last, n))["ok"]
    assert not pf.scope_report(comp, (first, last, n + 1))["ok"]
    assert not pf.scope_report(comp, ("2013-01", last, n))["ok"]


def test_release_preflight_battery_positive_and_every_negative_refused(world):
    r = world["rep"]["release_preflight"]
    assert r["ok"] and r["positive_path"] and r["reproduce_byte_identical"] and r["rollback_target_ok"] and r["record_keys_exact"] and r["registry_empty"]
    assert r["all_negative_refused"] and len(r["negative_cases"]) >= 14 and r["gate_alone_cannot_see_forged_payload"]


def test_the_tool_changes_no_production_state(world):
    assert bc.ARTIFACT_RECORDS == ()
    assert "BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in (pf.ROOT / "frontend/src/btc.ts").read_text()


# ---------------------------------------------------------------- rollback simulation with a SYNTHETIC release (never the production files)
def test_synthetic_release_then_rollback_restores_the_exact_legacy_state_and_hides_bitcoin(world, tmp_path):
    from tools import btc_09_distribution_check as dc
    legacy = CSV.parent.parent / "frontend/public/data/monthly.json"
    legacy_bytes = legacy.read_bytes()
    auth = {"release_id": "SYN-ROLLBACK", "decision_ref": "SYN-ROLLBACK", "months": world["months"], "rights_review_ref": "S", "conflicting_contract_check": "VERIFIED",
            **bc.private_hashes(world["hp"], world["hs"])}
    comp = bc.compose_release(world["hp"], world["hs"], auth)
    blob = bc.serialize(comp)
    assert bc.legacy_projection_bytes(comp) == legacy_bytes  # a release payload never alters the legacy gold/CBS fields
    rec = dict(bc.record_template(comp, auth), owner_approval="APPROVED", approved_by="syn", approved_on="n/a")
    public = tmp_path / "monthly.json"
    public.write_bytes(blob)  # the "released" state of an isolated copy
    ts = pf.ROOT / "frontend/src/btc.ts"
    released = dc.check_state(public, ts)
    assert not released["ok"] and not released["no_bitcoin_keys"] and not released["equals_pinned_legacy_payload"]
    public.write_bytes(legacy_bytes)  # rollback: restore the previous authorized payload named by the record
    assert bc.rollback_target_ok(rec, public.read_bytes()) and dc.check_state(public, ts)["ok"]
    public.write_bytes(blob[:-1])  # a partial/failed restore is detected, never accepted
    assert not bc.rollback_target_ok(rec, public.read_bytes()) and not dc.check_state(public, ts)["ok"]
