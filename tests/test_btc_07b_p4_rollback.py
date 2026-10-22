"""BTC-07B P4: local release / rollback rehearsal (sandbox only, synthetic data). No Cloudflare deployment, no public rollback."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from etl import btc_contract as bc
from tools import btc_07b_rehearsal as R

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "frontend/public/data/monthly.json"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return R.rehearse(tmp_path_factory.mktemp("reh") / "sandbox")


def test_rehearsal_passes_every_step_and_is_marked_sandbox_only(run):
    assert run["status"] == "REHEARSAL_PASSED_LOCAL_SYNTHETIC" and run["scope"].startswith("SANDBOX_ONLY")
    inv, act, fail, back = run["steps"]
    assert inv["live_unchanged"] and inv["no_output_written"] and set(inv["outcomes"].values()) == {"REFUSED"}
    assert act["live_is_composite"] and act["months_validated"] == 320 and act["default_registry_denies_it"] is True
    assert fail["result"] == "FAILED_AS_INJECTED" and fail["live_unchanged"] and fail["temp_files_left"] == []
    assert back["equals_approved_legacy"] and back["composite_projection_equals_legacy"] and back["default_validator_months"] == 320


def test_gold_and_cbs_hashes_match_before_and_after_and_the_gate_stays_closed(run):
    assert run["base"]["legacy_sha256"] == run["final"]["repo_legacy_sha256"] == bc.LEGACY_PUBLIC_SHA256
    assert run["base"]["csv_sha256"] == run["final"]["repo_csv_sha256"] == "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"
    assert run["base"]["registry_records"] == run["final"]["registry_records"] == 0 and bc.ARTIFACT_RECORDS == ()


def test_the_repository_public_files_are_untouched_by_the_rehearsal(run):
    assert hashlib.sha256(LEGACY.read_bytes()).hexdigest() == bc.LEGACY_PUBLIC_SHA256
    status = subprocess.run(["git", "status", "--porcelain", "--", "frontend/public", "data"], cwd=ROOT, capture_output=True, text=True).stdout
    assert status.strip() == ""


def test_the_sandbox_must_be_outside_the_repository_and_new(tmp_path):
    with pytest.raises(R.RehearsalError, match="outside"):
        R.sandbox(ROOT / "tmp-rehearsal")
    used = tmp_path / "used"
    used.mkdir()
    (used / "f").write_text("x")
    with pytest.raises(R.RehearsalError, match="new or empty"):
        R.sandbox(used)
    assert not (ROOT / "tmp-rehearsal").exists()


def test_activate_is_atomic_and_leaves_no_temp_file_when_the_switch_fails(tmp_path):
    live, staged = tmp_path / "live.json", tmp_path / "staged.json"
    live.write_bytes(b"old")
    staged.write_bytes(b"new")

    def boom(*a, **k):
        raise OSError("injected")
    with pytest.raises(OSError):
        R.activate(staged, live, replace=boom)
    assert live.read_bytes() == b"old" and [p.name for p in tmp_path.iterdir() if p.name.startswith(".switch-")] == []
    R.activate(staged, live)
    assert live.read_bytes() == b"new"


def test_rollback_refuses_a_backup_that_is_not_the_approved_legacy(tmp_path):
    live, backup = tmp_path / "live.json", tmp_path / "backup.json"
    live.write_bytes(b"composite")
    backup.write_bytes(b"not the approved legacy bytes")
    with pytest.raises(R.RehearsalError, match="approved legacy"):
        R.rollback(backup, live)


def test_cli_prints_price_free_evidence_and_refuses_a_repository_path(tmp_path, capsys):
    assert R.main(["--work-dir", str(tmp_path / "sb")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"].startswith("REHEARSAL_PASSED")
    assert R.main(["--work-dir", str(ROOT / "sandbox-in-repo")]) == 1
    assert not (ROOT / "sandbox-in-repo").exists()
