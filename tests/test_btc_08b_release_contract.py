"""BTC-08B: the release record v2 (btc-release-record/2), month- and quality-scoped authorization, provenance binding, independent regeneration and
rollback target. SYNTHETIC vintage (proves code, not data). Every case is a way a release could be widened, forged or confused; each must fail closed."""
import json
import re
from pathlib import Path

import pytest

from etl import btc_contract as bc
from tests import test_btc_06c_candidate as t6
from tools import btc_06c_candidate as cand

ROOT = Path(__file__).resolve().parents[1]
CSV, LEGACY = t6.CSV, t6.LEGACY


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    base = tmp_path_factory.mktemp("btc08b")
    snap = t6.make_snapshot(base / "snap")
    preview, sidecar, _ = cand.build_candidate(snap, CSV, LEGACY)
    months = [m for m in sorted(sidecar["months"]) if m >= "2014-02"]
    return {"base": base, "snap": snap, "preview": preview, "sidecar": sidecar, "months": months}


def auth_for(world, months, **over):
    a = {"release_id": "SYN-08B", "decision_ref": "SYN-DEC-08B", "months": months, "rights_review_ref": "SYN-RIGHTS", "conflicting_contract_check": "VERIFIED",
         **bc.private_hashes(world["preview"], world["sidecar"])}
    a.update(over)
    return a


def release(world, months=None, **over):
    a = auth_for(world, world["months"] if months is None else months, **over)
    comp = bc.compose_release(world["preview"], world["sidecar"], a)
    rec = bc.record_template(comp, a)
    rec.update(owner_approval="APPROVED", approved_by="synthetic-owner", approved_on="2026-01-01")
    return {"auth": a, "composite": comp, "blob": bc.serialize(comp), "record": rec}


@pytest.fixture(scope="module")
def full(world):
    return release(world)


def denied(blob, record):
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(blob, records=[record])


# ---------------------------------------------------------------- the record is complete, exact and default-deny
def test_template_has_exactly_the_documented_keys_and_opens_the_gate_only_when_owner_filled(full):
    assert set(full["record"]) == bc.RECORD_KEYS and full["record"]["schema"] == bc.RECORD_SCHEMA
    assert bc.composite_release_gate(full["blob"], records=[full["record"]]) is full["record"]
    pending = bc.record_template(full["composite"], {k: v for k, v in full["auth"].items() if not k.endswith("_sha256")})
    pending.update(owner_approval="APPROVED", approved_by="x", approved_on="y")
    assert pending["candidate_preview_sha256"] == bc.PENDING == pending["private_sidecar_sha256"]
    denied(full["blob"], pending)  # the unfilled template never opens the gate, even with an approver


def test_registry_and_default_stay_closed(full):
    assert bc.ARTIFACT_RECORDS == ()
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(full["blob"])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(full["blob"], records=[])


@pytest.mark.parametrize("extra", [{"owner_note": "ok"}, {"approved": True}, {"publication_authorized": True}])
def test_unreviewed_extra_fields_deny(full, extra):
    denied(full["blob"], {**full["record"], **extra})


@pytest.mark.parametrize("missing", sorted(bc.RECORD_KEYS))
def test_every_missing_field_denies(full, missing):
    denied(full["blob"], {k: v for k, v in full["record"].items() if k != missing})


@pytest.mark.parametrize("edit", [
    {"schema": "btc-release-record/1"}, {"schema": ""},
    {"public_payload_sha256": "0" * 64}, {"snapshot_id": "btc04e-0000000000000000"}, {"calculation_git_commit": "0" * 40}, {"provenance_sha256": "0" * 64},
    {"quality_by_month_sha256": "0" * 64}, {"authorized_qualities": ["Q2"]}, {"authorized_qualities": ["Q1_CANDIDATE"]}, {"authorized_qualities": ["Q3", "Q2", "Q1_CANDIDATE"]},
    {"authorized_qualities": []}, {"authorized_qualities": "Q2"},
    {"rollback_ref": {"previous_public_sha256": "0" * 64, "state": bc.ROLLBACK_STATE}}, {"rollback_ref": {"previous_public_sha256": bc.LEGACY_PUBLIC_SHA256, "state": "OTHER"}},
    {"rollback_ref": None}, {"rollback_ref": {"previous_public_sha256": bc.LEGACY_PUBLIC_SHA256}},
    {"candidate_preview_sha256": bc.PENDING}, {"candidate_preview_sha256": "A" * 64}, {"candidate_preview_sha256": "a" * 63},
    {"private_sidecar_sha256": bc.PENDING}, {"private_sidecar_sha256": None}, {"private_sidecar_sha256": 7},
])
def test_each_new_binding_field_is_enforced(full, edit):
    denied(full["blob"], {**full["record"], **edit})


# ---------------------------------------------------------------- month scope and quality scope
def test_one_month_cannot_authorize_another(world):
    a, b = release(world, ["2014-02"]), release(world, ["2014-03"])
    assert bc.composite_release_gate(a["blob"], records=[a["record"]]) is a["record"]
    denied(b["blob"], a["record"])
    denied(a["blob"], b["record"])
    both = release(world, ["2014-02", "2014-03"])
    denied(both["blob"], a["record"])  # a wider composite needs its own record


def test_a_q2_only_release_cannot_carry_q1_months_and_the_reverse(world):
    q2 = [m for m in world["months"] if m <= "2016-04"]
    q1 = [m for m in world["months"] if m >= "2016-05"]
    r2, r1, rall = release(world, q2), release(world, q1), release(world)
    assert r2["record"]["authorized_qualities"] == ["Q2"] and r1["record"]["authorized_qualities"] == ["Q1_CANDIDATE"]
    assert rall["record"]["authorized_qualities"] == ["Q1_CANDIDATE", "Q2"]
    for blob, rec in ((rall["blob"], r2["record"]), (rall["blob"], r1["record"]), (r2["blob"], r1["record"]), (r1["blob"], r2["record"]), (r2["blob"], rall["record"])):
        denied(blob, rec)
    # even a record whose bytes/month fields were regenerated for the wide composite cannot keep a narrower quality statement
    denied(rall["blob"], {**rall["record"], "authorized_qualities": ["Q2"]})
    denied(rall["blob"], {**rall["record"], "authorized_qualities": ["Q1_CANDIDATE"]})


def test_a_forged_quality_label_is_refused_by_the_contract_itself(full):
    forged = json.loads(json.dumps(full["composite"]))
    next(r for r in forged["data"] if r["period"] == "2020-02")["btc_meta"]["quality"] = "Q2"
    with pytest.raises((bc.BtcContractError, bc.ReleaseDenied)):
        bc.composite_release_gate(bc.serialize(forged), records=[full["record"]])
    with pytest.raises(bc.BtcContractError):
        bc.validate_payload(forged, bc.legacy_projection_bytes(forged))


def test_early_q3_history_needs_its_own_flag_and_record(world):
    with pytest.raises(bc.BtcContractError):
        release(world, ["2013-05", "2014-02"])


def test_june_2011_stays_unauthorizable(world):
    with pytest.raises(bc.BtcContractError):
        release(world, ["2011-06"], early_history_authorized=True)


# ---------------------------------------------------------------- a candidate cannot authorize itself; claims in the payload never open anything
def test_nothing_inside_the_payload_can_supply_the_record(full, world):
    for path in (lambda c: c["btc"]["release"].update(record=full["record"]), lambda c: c["btc"].update(record=full["record"]),
                 lambda c: c.update(artifact_records=[full["record"]])):
        forged = json.loads(json.dumps(full["composite"]))
        path(forged)
        with pytest.raises((bc.BtcContractError, bc.ReleaseDenied)):
            bc.composite_release_gate(bc.serialize(forged), records=[])
        with pytest.raises((bc.BtcContractError, bc.ReleaseDenied)):
            bc.composite_release_gate(bc.serialize(forged))
    preview_flagged = json.loads(json.dumps(world["preview"]))
    preview_flagged["btc"]["release"]["publication_authorized"] = True
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(bc.serialize(preview_flagged), records=[full["record"]])


# ---------------------------------------------------------------- provenance binding and mixed vintages
def test_a_record_for_one_vintage_never_releases_another_vintage(world, full, tmp_path):
    cm = t6.cm_daily()
    cm["2020-03-10"] = cm["2020-03-10"] + 1  # a later vintage that revised one historical day
    snap2 = t6.make_snapshot(tmp_path / "snap2", cm=cm)
    preview2, sidecar2, _ = cand.build_candidate(snap2, CSV, LEGACY)
    w2 = {"preview": preview2, "sidecar": sidecar2, "months": world["months"]}
    other = release(w2)
    assert other["record"]["snapshot_id"] != full["record"]["snapshot_id"] and other["record"]["provenance_sha256"] != full["record"]["provenance_sha256"]
    denied(other["blob"], full["record"])
    denied(full["blob"], other["record"])
    # mixing: v1 provenance with v2 values (or the reverse) is a different payload and has no record
    mixed = json.loads(json.dumps(other["composite"]))
    mixed["btc"]["provenance"] = full["composite"]["btc"]["provenance"]
    denied(bc.serialize(mixed), full["record"])
    denied(bc.serialize(mixed), other["record"])


def test_calculation_commit_is_bound(full):
    forged = json.loads(json.dumps(full["composite"]))
    forged["btc"]["provenance"]["calculation_git_commit"] = "1" * 40
    denied(bc.serialize(forged), full["record"])


# ---------------------------------------------------------------- reproducibility (rebuild, restart, independent regeneration)
def test_composition_is_deterministic_and_regenerable_from_the_pinned_private_inputs(world, full):
    again = release(world)
    assert again["blob"] == full["blob"] and again["record"] == full["record"]
    preview_b, sidecar_b = bc.serialize(world["preview"]), bc.serialize(world["sidecar"])
    assert bc.reproduce_composite(full["record"], preview_b, sidecar_b) == full["blob"]


def test_regeneration_refuses_other_private_inputs_or_a_changed_record(world, full):
    preview_b, sidecar_b = bc.serialize(world["preview"]), bc.serialize(world["sidecar"])
    changed_sidecar = json.loads(sidecar_b)
    k = sorted(changed_sidecar["months"])[5]
    changed_sidecar["months"][k]["btc_per_house"] = "1.5"
    with pytest.raises(bc.BtcContractError):
        bc.reproduce_composite(full["record"], preview_b, bc.serialize(changed_sidecar))
    with pytest.raises(bc.BtcContractError):
        bc.reproduce_composite(full["record"], preview_b + b" ", sidecar_b)
    with pytest.raises(bc.BtcContractError):
        bc.reproduce_composite({**full["record"], "authorized_months": full["record"]["authorized_months"][:-1]}, preview_b, sidecar_b)
    with pytest.raises(bc.BtcContractError):
        bc.reproduce_composite({**full["record"], "release_id": "OTHER"}, preview_b, sidecar_b)
    with pytest.raises(bc.BtcContractError):
        bc.reproduce_composite("not a record", preview_b, sidecar_b)


# ---------------------------------------------------------------- withdrawal and rollback
def test_withdrawal_returns_to_the_pinned_legacy_state_without_mixed_data(full):
    legacy = LEGACY.read_bytes()
    assert bc.rollback_target_ok(full["record"], legacy) and bc.sha256(legacy) == bc.LEGACY_PUBLIC_SHA256
    assert bc.legacy_projection_bytes(full["composite"]) == legacy  # the composite's non-BTC content IS the rollback state
    assert not bc.rollback_target_ok(full["record"], full["blob"])  # the composite is not a valid rollback target
    assert not bc.rollback_target_ok(full["record"], legacy.replace(b"2000-01", b"2000-02", 1))
    assert not bc.rollback_target_ok({**full["record"], "rollback_ref": {"previous_public_sha256": "0" * 64, "state": bc.ROLLBACK_STATE}}, legacy)
    assert not bc.rollback_target_ok(None, legacy)
    # withdrawing the record (empty registry) denies the very same bytes again
    assert bc.composite_release_gate(full["blob"], records=[full["record"]])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(full["blob"], records=[])


# ---------------------------------------------------------------- attribution (UI constants and payload sources)
BTC_TS = (ROOT / "frontend/src/btc.ts").read_text(encoding="utf-8")
MAIN_TSX = (ROOT / "frontend/src/main.tsx").read_text(encoding="utf-8")


def ts_const(name):
    m = re.search(rf"export const {name}[^=]*=\s*'((?:[^'\\]|\\.)*)'", BTC_TS)
    assert m, name
    return m.group(1)


def test_ui_attribution_distinguishes_sources_roles_modifications_and_non_endorsement():
    a, mod = ts_const("BTC_ATTRIBUTION_TEXT"), ts_const("BTC_MODIFICATION_TEXT")
    for must in ("Coin Metrics Community", "PriceUSD", "CC BY-NC 4.0", "EXR.D.USD.EUR.SP00.A", "bron: ECB", "85773NED", "eigen berekeningen",
                 "geen publicatie van Coin Metrics, de ECB of het CBS", "Geen bronorganisatie onderschrijft"):
        assert must in a, must
    for must in ("Wijzigingen ten opzichte van de bronnen", "volledige UTC-kalendermaand", "geen interpolatie", "gedeeld door de maandgemiddelde ECB-koers", "USD-afgeleide",
                 "CBS-gemiddelde verkoopprijs", "ruwe dagreeksen worden niet verspreid"):
        assert must in mod, must
    assert "native" in ts_const("BTC_DERIVED_TEXT") and "geen beursslotkoers" in ts_const("BTC_DERIVED_TEXT")


def test_ui_shows_the_source_vintage_and_the_modification_notice_from_the_payload_only():
    assert "BTC_MODIFICATION_TEXT" in MAIN_TSX and "data-btc-vintage" in MAIN_TSX and "root.provenance.snapshot_id" in MAIN_TSX
    # the vintage fields come from the validated payload root; a payload without them activates nothing
    assert re.search(r"snapshot_id", BTC_TS) and re.search(r"vintage_reference_utc", BTC_TS)


def test_payload_sources_carry_role_and_modification_wording(full):
    by_id = {s["id"]: s["attribution"] for s in full["composite"]["btc"]["sources"]}
    assert "Gewijzigd" in by_id["coinmetrics_community_priceusd"] and "geen publicatie van of onderschrijving door Coin Metrics" in by_id["coinmetrics_community_priceusd"]
    assert "bron: ECB" in by_id["ecb_exr_d_usd"] and "geen officiële ECB-publicatie" in by_id["ecb_exr_d_usd"]
    assert "eigen berekeningen" in by_id["cbs_85773NED_csv"] and "geen CBS-publicatie" in by_id["cbs_85773NED_csv"]
