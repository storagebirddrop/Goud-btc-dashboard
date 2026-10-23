"""BTC-09: static distribution and rollback-state checks. Every way private Bitcoin material or a release pin could reach a build must be caught."""
import json
import shutil

import pytest

from etl import btc_contract as bc
from tools import btc_09_distribution_check as dc

PUBLIC = dc.ROOT / "frontend/public/data/monthly.json"


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "data").mkdir(parents=True)
    (d / "assets").mkdir()
    shutil.copy(PUBLIC, d / "data/monthly.json")
    (d / "index.html").write_text("<html></html>")
    (d / "assets/app.js").write_text("console.log('x')")
    return d


def test_clean_build_passes(dist):
    assert dc.check_dist(dist, PUBLIC)["ok"]


@pytest.mark.parametrize("name", ["candidate.json", "candidate_values.json", "btc-real-vintage.tar", "snapshot_manifest.json", "cm_priceusd_daily.txt", "private.zip"])
def test_private_file_names_are_refused(dist, name):
    (dist / name).write_text("x")
    r = dc.check_dist(dist, PUBLIC)
    assert not r["ok"] and r["forbidden_file_names"]


@pytest.mark.parametrize("marker", ["CANDIDATE_VALUE", "candidate_values", "private_sidecar", "btc04e-snapshot/2"])
def test_private_markers_in_bundles_are_refused(dist, marker):
    (dist / "assets/app.js").write_text(f"var a='{marker}';")
    assert not dc.check_dist(dist, PUBLIC)["ok"]


def test_raw_daily_series_lines_are_refused(dist):
    (dist / "assets/app.js").write_text("2020-01-01:7194.89291637\n")
    r = dc.check_dist(dist, PUBLIC)
    assert not r["ok"] and r["raw_daily_series_lines_in"]


def test_a_shipped_json_that_differs_from_the_committed_one_is_refused(dist):
    doc = json.loads(PUBLIC.read_bytes())
    doc["btc"] = {"release": {"publication_authorized": True}}
    (dist / "data/monthly.json").write_text(json.dumps(doc))
    r = dc.check_dist(dist, PUBLIC)
    assert not r["ok"] and not r["shipped_json_identical_to_committed"] and not r["shipped_state"]["ok"]


def test_a_release_pin_literal_in_the_bundle_is_refused(dist):
    (dist / "assets/app.js").write_text("var p=['" + "a" * 64 + "'];")
    assert not dc.check_dist(dist, PUBLIC)["ok"]


def test_state_check_accepts_only_the_legacy_no_bitcoin_state(tmp_path):
    ts = dc.ROOT / "frontend/src/btc.ts"
    assert dc.check_state(PUBLIC, ts)["ok"]
    bad_json = tmp_path / "m.json"
    doc = json.loads(PUBLIC.read_bytes())
    doc["data"][0]["btc_per_house"] = 1
    bad_json.write_text(json.dumps(doc))
    r = dc.check_state(bad_json, ts)
    assert not r["ok"] and not r["no_bitcoin_keys"] and not r["equals_pinned_legacy_payload"]
    pinned = tmp_path / "btc.ts"
    pinned.write_text(ts.read_text().replace("BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];", "BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=['" + "b" * 64 + "'];"))
    assert not dc.check_state(PUBLIC, pinned)["frontend_pin_list_empty"]


def test_production_defaults_are_unchanged():
    assert bc.ARTIFACT_RECORDS == () and bc.sha256(PUBLIC.read_bytes()) == bc.LEGACY_PUBLIC_SHA256


# ---------------------------------------------------------------- the manual BTC-09 workflow is private-input, price-free and publishes nothing
WF = (dc.ROOT / ".github/workflows/btc-09-final-preflight.yml").read_text()


def test_workflow_is_manual_narrow_read_only_and_uploads_only_price_free_files():
    assert "workflow_dispatch" in WF and "contents: read" in WF and "contents: write" not in WF and "deployments" not in WF
    assert WF.count("paths:") == 1 and "btc-09-final-preflight.yml" in WF.split("paths:")[1].split("workflow_dispatch")[0]
    upload = WF.split("actions/upload-artifact@v4")[1]
    listed = [ln.strip() for ln in upload.splitlines() if "runner.temp" in ln]
    assert listed and all(any(n in ln for n in ("btc09-preflight.json", "btc09-distribution.json", "btc09-rollback-state.json", "result-redacted.json")) for ln in listed)
    assert "candidate" not in " ".join(listed) and "restore" not in " ".join(listed) and ".tar" not in " ".join(listed)


def test_workflow_requires_the_anchor_and_never_reacquires_or_registers_anything():
    assert "PACKAGE SHA-256 DIFFERS FROM THE EXTERNAL ANCHOR" in WF and "btc_04e_cm_replay" not in WF
    assert "ARTIFACT_RECORDS" not in WF.replace("git diff", "") and "BTC_APPROVED_COMPOSITE_SHA256" not in WF
    assert "--isolated" in WF and "EXPECT_HIST_CANDIDATE_SHA256" in WF and "HIST_COMMIT: 641151b900df1403f8b4f3879ef45028d64552f2" in WF
