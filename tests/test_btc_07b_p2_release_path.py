"""BTC-07B P2: the existing composite release gate is connected to the exporter side (`etl.btc_release`) and to the production validator
(`etl.data_quality.validate_production_state`). Everything here is SYNTHETIC: synthetic Coin Metrics/ECB data, synthetic approval records
that live only inside the test process, output only in tmp directories. No real publication, no real record, registry stays empty."""
import hashlib
import json
from pathlib import Path

import pytest

from etl import btc_contract as bc
from etl import btc_release as br
from etl import data_quality as dq
from tools import btc_06c_candidate as cand
import test_btc_06c_candidate as t6

ROOT = Path(__file__).resolve().parents[1]
CSV, LEGACY = t6.CSV, t6.LEGACY
LEGACY_SHA = "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"
MONTHS = ["2014-02", "2014-03", "2014-04", "2014-05"]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    base = tmp_path_factory.mktemp("btc07b_p2")
    snap = t6.make_snapshot(base / "snap")
    preview, sidecar, _ = cand.build_candidate(snap, CSV, LEGACY)
    auth = {"release_id": "SYN-REL-07B", "decision_ref": "SYN-DEC-07B", "months": MONTHS, "rights_review_ref": "SYN-RIGHTS",
            "conflicting_contract_check": "VERIFIED"}
    composite = bc.compose_release(preview, sidecar, auth)
    blob = bc.serialize(composite)
    record = bc.record_template(composite, auth)
    record.update(owner_approval="APPROVED", approved_by="synthetic-test-owner", approved_on="2026-01-01")
    return {"base": base, "preview": preview, "sidecar": sidecar, "auth": auth, "composite": composite, "blob": blob, "record": record}


def write(path, blob):
    Path(path).write_bytes(blob)
    return path


def recompose(world, months, **over):
    auth = dict(world["auth"], months=months, **over)
    comp = bc.compose_release(world["preview"], world["sidecar"], auth)
    return comp, auth


# ------------------------------------------------------------------ the registry and the defaults stay closed
def test_registry_is_empty_and_legacy_public_data_unchanged():
    assert bc.ARTIFACT_RECORDS == ()
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest() == LEGACY_SHA
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    assert dq.validate_production_state(CSV, LEGACY)[0] == 320  # unchanged legacy path, default


def test_release_module_never_reads_records_from_env_json_argv_or_url():
    text = (ROOT / "etl/btc_release.py").read_text(encoding="utf-8")
    assert "os.environ" not in text and "getenv" not in text and "import os" not in text and "urlopen" not in text and "requests" not in text
    with pytest.raises(SystemExit):
        br.main(["export", "--composite", "c", "--output", "o", "--records", "r.json"])


# ------------------------------------------------------------------ export side
def test_default_export_is_denied_and_writes_nothing(world, tmp_path, capsys):
    comp = write(tmp_path / "composite.json", world["blob"])
    out = tmp_path / "out" / "monthly.json"
    assert br.main(["export", "--composite", str(comp), "--output", str(out)]) == 2
    assert "RELEASE DENIED" in capsys.readouterr().out and not out.exists()


def test_exact_synthetic_record_exports_identical_bytes_once_and_never_into_the_public_path(world, tmp_path):
    comp = write(tmp_path / "composite.json", world["blob"])
    out = tmp_path / "isolated" / "monthly.json"
    res = br.export_composite(comp, out, records=[world["record"]])
    assert out.read_bytes() == world["blob"] and res["composite_sha256"] == hashlib.sha256(world["blob"]).hexdigest()
    with pytest.raises(FileExistsError):
        br.export_composite(comp, out, records=[world["record"]])  # never overwrites
    with pytest.raises(bc.BtcContractError):
        br.export_composite(comp, br.DEFAULT_PUBLIC, records=[world["record"]])  # the committed public file is not written by this tool
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest() == LEGACY_SHA


@pytest.mark.parametrize("label", ["wrong_composite_hash", "wrong_selection_hash", "wrong_legacy_hash", "fewer_months", "extra_month", "june_exception",
                                   "pending", "fields", "early", "release_id", "snapshot", "cbs", "versions", "rights_ref", "contract_check"])
def test_every_partial_record_is_denied(world, label):
    r = dict(world["record"])
    mut = {"wrong_composite_hash": {"composite_sha256": "0" * 64}, "wrong_selection_hash": {"btc_selection_sha256": "1" * 64},
           "wrong_legacy_hash": {"legacy_projection_sha256": "2" * 64}, "fewer_months": {"authorized_months": r["authorized_months"][1:]},
           "extra_month": {"authorized_months": r["authorized_months"] + ["2014-06"]}, "june_exception": {"exceptions": []},
           "pending": {"owner_approval": "PENDING"}, "fields": {"authorized_fields": ["btc_per_house"]}, "early": {"early_history_authorized": True},
           "release_id": {"release_id": "OTHER"}, "snapshot": {"snapshot_manifest_sha256": "3" * 64}, "cbs": {"cbs_input_sha256": "4" * 64},
           "versions": {"quality_version": "x"}, "rights_ref": {"review_refs": {"rights": "other", "contract_check": "VERIFIED"}},
           "contract_check": {"review_refs": {"rights": r["review_refs"]["rights"], "contract_check": "UNVERIFIED"}}}[label]
    r.update(mut)
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(world["blob"], records=[r])


def test_no_json_flag_env_variable_or_old_gold_approval_opens_the_gate(world, monkeypatch, tmp_path):
    for k in ("BTC_PUBLICATION_ENABLED", "BTC_PUBLICATION_APPROVAL", "GOLD_PUBLICATION_ENABLED", "GOLD_PUBLICATION_APPROVAL", "PUBLICATION_AUTHORIZED"):
        monkeypatch.setenv(k, "true" if "ENABLED" in k or "AUTHORIZED" in k else "APPROVED")
    # the payload itself claims authorization (JSON boolean) but there is no record
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(world["blob"])
    comp = write(tmp_path / "c.json", world["blob"])
    assert br.main(["export", "--composite", str(comp), "--output", str(tmp_path / "o.json")]) == 2
    # a preview (publication_authorized=false) is refused even with a matching-looking record
    blob = bc.serialize(world["preview"])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(blob, records=[world["record"]])


def test_june_2011_cannot_be_authorized_or_published(world):
    with pytest.raises(bc.BtcContractError):
        recompose(world, ["2011-06"])
    row = {r["period"]: r for r in world["composite"]["data"]}["2011-06"]
    assert row["btc_per_house"] is None and row["sat_per_house"] is None and row["btc_meta"]["missing_reason"] == "RESEARCH_ONLY_HOLD"


def test_a_composite_with_extra_published_months_needs_a_new_record_no_automatic_extension(world):
    comp, auth = recompose(world, MONTHS + ["2014-06"])
    with pytest.raises(bc.ReleaseDenied):
        bc.composite_release_gate(bc.serialize(comp), records=[world["record"]])
    new = bc.record_template(comp, auth)
    new.update(owner_approval="APPROVED", approved_by="synthetic-test-owner", approved_on="2026-01-01")
    assert bc.composite_release_gate(bc.serialize(comp), records=[new]) is new  # only an exact new record opens it


def test_the_seven_legacy_fields_are_protected_byte_for_byte(world):
    tampered = json.loads(world["blob"].decode())
    tampered["data"][100]["gold_index"] = (tampered["data"][100]["gold_index"] or 100.0) + 0.001
    blob = bc.serialize(tampered)
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(blob, records=[world["record"]])
    tampered = json.loads(world["blob"].decode())
    tampered["data"][5]["house_eur"] += 1
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(bc.serialize(tampered), records=[world["record"]])


def test_noncanonical_bytes_are_refused(world):
    pretty = json.dumps(json.loads(world["blob"].decode()), indent=1).encode()
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(pretty, records=[world["record"]])


# ------------------------------------------------------------------ production validator side
def test_validator_denies_the_extended_payload_by_default(world, tmp_path):
    pub = write(tmp_path / "monthly.json", world["blob"])
    with pytest.raises(bc.ReleaseDenied):
        dq.validate_production_state(CSV, pub)


def test_validator_accepts_the_extended_payload_only_with_the_exact_record(world, tmp_path, monkeypatch):
    pub = write(tmp_path / "monthly.json", world["blob"])
    monkeypatch.setattr(bc, "ARTIFACT_RECORDS", (world["record"],))  # synthetic, in-process only
    count, report = dq.validate_production_state(CSV, pub)
    assert count == 320 and report is None
    changed = json.loads(world["blob"].decode())
    changed["data"][-1]["btc_meta"]["flags"] = ["REVIEW_2017_12"]
    pub2 = write(tmp_path / "changed.json", bc.serialize(changed))
    with pytest.raises(bc.BtcContractError):
        dq.validate_production_state(CSV, pub2)  # a changed byte no longer matches the record


def test_validator_cli_path_and_legacy_default_are_unchanged(world, tmp_path, capsys):
    pub = write(tmp_path / "monthly.json", world["blob"])
    assert br.main(["validate", "--input", str(CSV), "--output", str(pub)]) == 2
    assert "RELEASE DENIED" in capsys.readouterr().out
    assert br.main(["validate", "--input", str(CSV), "--output", str(LEGACY)]) == 1  # legacy bytes are not an extended payload


def test_validator_rejects_a_legacy_projection_that_differs_even_with_a_matching_record(world, tmp_path, monkeypatch):
    comp = json.loads(world["blob"].decode())
    comp["data"][10]["hpi"] = comp["data"][10]["hpi"] + 1
    blob = bc.serialize(comp)
    rec = dict(world["record"], composite_sha256=hashlib.sha256(blob).hexdigest())
    monkeypatch.setattr(bc, "ARTIFACT_RECORDS", (rec,))
    with pytest.raises(bc.BtcContractError):
        dq.validate_production_state(CSV, write(tmp_path / "m.json", blob))


def test_exporter_and_validator_default_files_stay_free_of_btc_text():
    import re
    for name in ("etl/static_export.py",):
        assert not re.search(r"btc|bitcoin|satoshi|sat_per_house", (ROOT / name).read_text(encoding="utf-8"), re.I)
