"""BTC-10 / D07: private release-artifact preparation (SYNTHETIC vintage: proves code, not data) and the deterministic release change-set check.
Every way the release could silently widen, drift from the frozen calculation commit or smuggle a pin/record must fail closed."""
import copy
import json
import re
import shutil
import subprocess

import pytest

from etl import btc_contract as bc
from tests import test_btc_06c_candidate as t6
from tools import btc_06c_candidate as cand
from tools import btc_10_changeset_check as cs
from tools import btc_10_d07 as d07

CSV, LEGACY = t6.CSV, t6.LEGACY
ROOT = d07.ROOT
C_SHA = "a" * 40


@pytest.fixture(scope="module")
def mp():
    m = pytest.MonkeyPatch()
    yield m
    m.undo()


@pytest.fixture(scope="module")
def world(tmp_path_factory, mp):
    base = tmp_path_factory.mktemp("btc10")
    snap = t6.make_snapshot(base / "snap")
    mp.setenv("GITHUB_SHA", "9" * 40)
    hp, hs, _ = cand.build_candidate(snap, CSV, LEGACY)
    cand.write_private(base / "hist", hp, hs)
    mp.delenv("GITHUB_SHA")
    manifest, template = d07.prepare(snap, CSV, LEGACY, base / "hist", base / "priv1", C_SHA, check_identity=False)
    return {"base": base, "snap": snap, "hp": hp, "hs": hs, "manifest": manifest, "template": template}


# ---------------------------------------------------------------- D07 preparation
def test_manifest_is_ok_price_free_and_not_authorized(world):
    m = world["manifest"]
    assert m["ok"] and m["status"] == "NOT AUTHORIZED FOR PUBLICATION" and m["record_status"] == "PENDING" and m["registry_empty"]
    text = json.dumps(m)
    assert "btc_per_house" not in text and "sat_per_house" not in text
    sidecar = world["hs"]["months"]
    assert sidecar[sorted(sidecar)[40]]["btc_per_house"][:12] not in text
    assert m["proposed_identity"]["state"].startswith("PROPOSED") and m["calculation"]["commit"] == C_SHA


def test_template_is_complete_unapproved_and_bound_to_C_and_the_private_inputs(world):
    t, m = world["template"], world["manifest"]
    assert set(t) == bc.RECORD_KEYS and t["owner_approval"] == "PENDING" and t["approved_by"] == "" and t["approved_on"] == ""
    assert t["calculation_git_commit"] == C_SHA and [k for k, v in t.items() if v == bc.PENDING] == ["owner_approval"]
    assert t["candidate_preview_sha256"] == m["hashes"]["candidate_preview_sha256"] and t["private_sidecar_sha256"] == m["hashes"]["private_sidecar_sha256"]
    assert t["composite_sha256"] == t["public_payload_sha256"] == m["hashes"]["public_composite_sha256"]
    assert len(t["authorized_months"]) == 151 and t["authorized_months"][0] == "2014-02" and t["authorized_months"][-1] == "2026-08"
    with pytest.raises(bc.ReleaseDenied):  # an unapproved template never opens the gate
        bc.composite_release_gate((world["base"] / "priv1/monthly.composite.json").read_bytes(), records=[t])


def test_private_bytes_stay_in_the_private_directory_and_equal_the_manifest(world):
    priv = world["base"] / "priv1"
    blob = (priv / "monthly.composite.json").read_bytes()
    assert bc.sha256(blob) == world["manifest"]["hashes"]["public_composite_sha256"]
    assert bc.sha256((priv / "candidate/candidate.json").read_bytes()) == world["manifest"]["hashes"]["candidate_preview_sha256"]
    assert ROOT not in (priv, *priv.parents)


def test_second_preparation_is_byte_identical_and_other_ids_change_only_the_composite(world):
    m2, t2 = d07.prepare(world["snap"], CSV, LEGACY, world["base"] / "hist", world["base"] / "priv2", C_SHA, check_identity=False)
    assert m2["hashes"] == world["manifest"]["hashes"] and t2 == world["template"]
    ids = dict(d07.PROPOSED_IDS, release_id="BTC-REL-2026-10-002")
    m3, _ = d07.prepare(world["snap"], CSV, LEGACY, world["base"] / "hist", world["base"] / "priv3", C_SHA, ids=ids, check_identity=False)
    assert m3["hashes"]["public_composite_sha256"] != world["manifest"]["hashes"]["public_composite_sha256"]
    assert m3["hashes"]["private_sidecar_sha256"] == world["manifest"]["hashes"]["private_sidecar_sha256"]


def test_a_changed_historical_value_or_other_snapshot_fails_the_manifest(world, tmp_path):
    hs = copy.deepcopy(world["hs"])
    hs["months"][sorted(hs["months"])[70]]["btc_per_house"] = "1"
    cand.write_private(tmp_path / "hist_bad", world["hp"], hs)
    m, _ = d07.prepare(world["snap"], CSV, LEGACY, tmp_path / "hist_bad", tmp_path / "priv", C_SHA, check_identity=False)
    assert not m["ok"] and not m["comparison_with_historical"]["identical_economics"]


def test_calculation_identity_requires_the_frozen_commit_and_clean_calculation_code():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert d07.calc_identity(head)["calc_paths_identical_to_C"]
    with pytest.raises(d07.D07Error):
        d07.calc_identity("b" * 40)
    with pytest.raises(d07.D07Error):
        d07.calc_identity("not-a-sha")
    with pytest.raises(d07.D07Error):
        d07.prepare("x", "y", "z", "h", "p", "c" * 40)  # unknown commit: refused before anything is read


def test_production_defaults_are_unchanged():
    assert bc.ARTIFACT_RECORDS == () and "BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/btc.ts").read_text()


# ---------------------------------------------------------------- release change-set check (C -> R)
FILES = ["etl/btc_contract.py", "frontend/src/btc.ts", "frontend/public/data/monthly.json", "tools/btc_06c_candidate.py", "tools/btc_04e_cm_replay.py",
         "frontend/src/main.tsx"]


def git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    for f in FILES:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, tmp_path / f)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/note.md").write_text("x")
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "C")
    return tmp_path


@pytest.fixture(scope="module")
def release(world):
    ids = {"release_id": "TEST-REL-1", "decision_ref": "TEST-DEC-1", "rights_review_ref": "TEST-RIGHTS-1"}
    preview, sidecar = world["hp"], world["hs"]
    months = [m for m in sorted(sidecar["months"]) if m >= "2014-02"]
    auth = {**ids, "months": months, "conflicting_contract_check": "VERIFIED", **bc.private_hashes(preview, sidecar)}
    comp = bc.compose_release(preview, sidecar, auth)
    return {"comp": comp, "blob": bc.serialize(comp), "auth": auth}


def approved(release, commit, **over):
    rec = dict(bc.record_template(release["comp"], release["auth"]), owner_approval="APPROVED", approved_by="Owner Person", approved_on="2026-11-01")
    prov = release["comp"]["btc"]["provenance"]
    assert prov["calculation_git_commit"]
    rec.update(calculation_git_commit=commit)
    rec.update(over)
    return rec


def make_release(repo, release, mutate=None, record_over=None):
    C = git(repo, "rev-parse", "HEAD")
    rec = approved(release, C, **(record_over or {}))
    # the record binds the commit inside the composite provenance too: rebuild the composite with commit C
    comp = copy.deepcopy(release["comp"])
    comp["btc"]["provenance"]["calculation_git_commit"] = C
    blob = bc.serialize(comp)
    rec.update(composite_sha256=bc.sha256(blob), public_payload_sha256=bc.sha256(blob), provenance_sha256=bc.sha256(bc.serialize(comp["btc"]["provenance"])))
    (repo / "frontend/public/data/monthly.json").write_bytes(blob)
    p = repo / "etl/btc_contract.py"
    p.write_text(p.read_text().replace("ARTIFACT_RECORDS: tuple = ()", f"ARTIFACT_RECORDS: tuple = ({rec!r},)", 1))
    t = repo / "frontend/src/btc.ts"
    t.write_text(t.read_text().replace("BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];", f"BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=['{rec['composite_sha256']}'];", 1))
    if mutate:
        mutate(repo, rec)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "R")
    return C, git(repo, "rev-parse", "HEAD"), rec


def run_check(repo, release, mutate=None, record_over=None, record_transform=None):
    C, R, rec = make_release(repo, release, mutate, record_over)
    return cs.check(repo, C, R, record_transform(rec) if record_transform else rec)


def test_a_release_that_changes_only_the_authorized_locations_passes(repo, release):
    r = run_check(repo, release, lambda rp, rec: (rp / "docs/note.md").write_text("release notes"))
    assert r["ok"], r["problems"]


@pytest.mark.parametrize("name,problem,mutate", [
    ("other_etl_logic", "contract_rest_identical", lambda rp, rec: (rp / "etl/btc_contract.py").write_text((rp / "etl/btc_contract.py").read_text() + "\nPATCHED = 1\n")),
    ("calc_tool", "calculation_code_changed", lambda rp, rec: (rp / "tools/btc_06c_candidate.py").write_text((rp / "tools/btc_06c_candidate.py").read_text() + "\n# x\n")),
    ("replay_tool", "calculation_code_changed", lambda rp, rec: (rp / "tools/btc_04e_cm_replay.py").write_text((rp / "tools/btc_04e_cm_replay.py").read_text() + "\n# x\n")),
    ("other_frontend_file", "unauthorized_paths", lambda rp, rec: (rp / "frontend/src/main.tsx").write_text((rp / "frontend/src/main.tsx").read_text() + "\n// x\n")),
    ("frontend_logic_next_to_pin", "pins_rest_identical", lambda rp, rec: (rp / "frontend/src/btc.ts").write_text((rp / "frontend/src/btc.ts").read_text().replace("BTC_HOLD_MONTHS:readonly string[]=['2011-06'];", "BTC_HOLD_MONTHS:readonly string[]=[];", 1))),
    ("second_pin", "pins_exactly_the_composite", lambda rp, rec: (rp / "frontend/src/btc.ts").write_text((rp / "frontend/src/btc.ts").read_text().replace(f"['{rec['composite_sha256']}']", f"['{rec['composite_sha256']}','{'e' * 64}']", 1))),
    ("workflow_file", "unauthorized_paths", lambda rp, rec: ((rp / ".github/workflows").mkdir(parents=True), (rp / ".github/workflows/x.yml").write_text("x"))),
    ("registry_second_record", "registry_exactly_the_record", lambda rp, rec: (rp / "etl/btc_contract.py").write_text((rp / "etl/btc_contract.py").read_text().replace(f"({rec!r},)", f"({rec!r},{rec!r})", 1))),
])
def test_any_other_change_is_rejected(repo, release, name, problem, mutate):
    r = run_check(repo, release, mutate)
    assert not r["ok"] and problem in r["problems"], (name, r["problems"])


def test_a_public_payload_that_is_not_the_recorded_one_is_rejected(repo, release):
    r = run_check(repo, release, lambda rp, rec: (rp / "frontend/public/data/monthly.json").write_bytes((rp / "frontend/public/data/monthly.json").read_bytes() + b" "))
    assert not r["ok"] and "public_equals_record" in r["problems"]


@pytest.mark.parametrize("over,problem", [({"owner_approval": "PENDING"}, "record"), ({"approved_by": ""}, "record"), ({"approved_by": "SYNTHETIC-OWNER"}, "record")])
def test_unapproved_or_synthetic_records_are_rejected(repo, release, over, problem):
    r = run_check(repo, release, record_over=over)
    assert not r["ok"] and problem in r["problems"]


def test_a_record_bound_to_another_calculation_commit_or_with_extra_fields_is_rejected(repo, release):
    r = run_check(repo, release, record_over={"calculation_git_commit": "d" * 40})
    assert not r["ok"] and "record" in r["problems"]
    r = run_check(repo, release, record_transform=lambda rec: dict(rec, extra="x"))
    assert not r["ok"] and "record" in r["problems"]


def test_a_record_that_differs_from_the_registered_one_is_rejected(repo, release):
    r = run_check(repo, release, record_transform=lambda rec: dict(rec, approved_on="2026-12-24"))
    assert not r["ok"] and "registry_exactly_the_record" in r["problems"]


# ---------------------------------------------------------------- the manual BTC-10 workflow is private-input, price-free and publishes/registers nothing
WF = (ROOT / ".github/workflows/btc-10-d07-artifact.yml").read_text()


def test_workflow_is_manual_narrow_read_only_and_uploads_only_price_free_files():
    assert "workflow_dispatch" in WF and "contents: read" in WF and "contents: write" not in WF and "deployments" not in WF
    assert WF.count("paths:") == 1 and "btc-10-d07-artifact.yml" in WF.split("paths:")[1].split("workflow_dispatch")[0]
    listed = [ln.strip() for ln in WF.split("actions/upload-artifact@v4")[1].splitlines() if "runner.temp" in ln]
    assert listed and all(any(n in ln for n in ("d07-manifest.json", "d07-record-template.json", "d07-distribution.json", "d07-rollback-state.json", "result-redacted.json")) for ln in listed)
    joined = " ".join(listed)
    assert "private" not in joined and "composite" not in joined and "candidate" not in joined and ".tar" not in joined


def test_workflow_freezes_C_requires_the_anchor_and_registers_nothing():
    assert "CALC_COMMIT: c11f82a83234593ace70369da07ca183c0cc3db3" in WF and "--calc-commit \"$CALC_COMMIT\"" in WF and "--isolated" in WF
    assert "PACKAGE SHA-256 DIFFERS FROM THE EXTERNAL ANCHOR" in WF and "btc_04e_cm_replay" not in WF and "BTC_APPROVED_COMPOSITE_SHA256" not in WF
    assert "ARTIFACT_RECORDS" not in WF.replace("git diff", "")
    assert "--private-dir \"$RUNNER_TEMP" in WF
