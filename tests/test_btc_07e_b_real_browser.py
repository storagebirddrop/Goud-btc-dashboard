"""BTC-07E-B: the real-candidate mode of the browser acceptance. These tests use a SYNTHETIC stand-in for the private candidate: they prove the code path,
the redaction and the workflow guards, not real data. The real run is the manual workflow `btc-07e-b-real-browser.yml`."""
import hashlib
import json
import re
from pathlib import Path

import pytest

from etl import btc_contract as bc
from tools import btc_07b_fixtures as fx

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/btc-07e-b-real-browser.yml"
MJS = ROOT / "tools/btc_07b_browser.mjs"
PY = ROOT / "tools/btc_07b_browser.py"


@pytest.fixture(scope="module")
def standin(tmp_path_factory):
    """A candidate directory in the exact layout of tools/btc_06c_candidate.py --out-dir, built from the synthetic vintage."""
    work = tmp_path_factory.mktemp("standin")
    preview, sidecar, _, _ = fx.synthetic_candidate(work)
    cdir = work / "candidate"
    cdir.mkdir()
    (cdir / "candidate.json").write_bytes(bc.serialize(preview))
    (cdir / "candidate_values.json").write_text(json.dumps(sidecar, sort_keys=True))
    return work, cdir, sidecar


def test_synthetic_mode_is_unchanged_and_flagged(tmp_path):
    idx = fx.build_fixtures(tmp_path / "f")
    assert idx["real_mode"] is False and "SYNTHETIC" in idx["note"]


def test_real_mode_composes_the_default_payload_from_the_candidate_and_stays_contract_valid(standin, tmp_path):
    _, cdir, sidecar = standin
    idx = fx.build_fixtures(tmp_path / "f", cdir)
    assert idx["real_mode"] is True and "REAL" in idx["note"]
    legacy = (ROOT / "frontend/public/data/monthly.json").read_bytes()
    blob = (tmp_path / "f/real_default.json").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == idx["shas"]["real_default"]
    summary = bc.validate_payload(json.loads(blob), legacy)
    assert summary["mode"] == "ACTIVE" and summary["legacy_sha256"] == bc.LEGACY_PUBLIC_SHA256
    rows = {r["period"]: r for r in json.loads(blob)["data"]}
    months = sorted(m for m in sidecar["months"] if m >= "2014-02")
    assert [p for p, r in sorted(rows.items()) if r["btc_meta"]["status"] == "PUBLISHED"] == months
    # the real default is pinned for the TEST build only; the bytes of the other fixtures stay distinct
    assert idx["shas"]["real_default"] in idx["pinned"] and idx["shas"]["unpinned_authorized_claim"] not in idx["pinned"]
    assert len(set(idx["shas"].values())) == len(idx["shas"])


def test_early_fixture_stays_synthetic_in_real_mode(standin, tmp_path):
    _, cdir, _ = standin
    idx = fx.build_fixtures(tmp_path / "f", cdir)
    early = json.loads((tmp_path / "f/real_early.json").read_text())
    assert early["btc"]["coverage"]["early_history_authorized"] is True
    assert {r["period"]: r for r in early["data"]}["2011-06"]["btc_meta"]["missing_reason"] == "RESEARCH_ONLY_HOLD"


def test_repository_pins_and_records_stay_closed():
    assert bc.ARTIFACT_RECORDS == ()
    assert "BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/btc.ts").read_text()


def test_driver_refuses_repository_paths_and_wrong_hashes(standin, tmp_path):
    from tools import btc_07b_browser as br
    _, cdir, _ = standin
    with pytest.raises(SystemExit):
        br.main(["--out-dir", str(tmp_path / "o1"), "--chrome", "/bin/true", "--real-candidate-dir", str(ROOT / "docs")])
    with pytest.raises(SystemExit) as e:
        br.main(["--out-dir", str(tmp_path / "o2"), "--chrome", "/bin/true", "--real-candidate-dir", str(cdir), "--expect-candidate-sha256", "0" * 64])
    assert "HASH MISMATCH" in str(e.value)
    assert not (tmp_path / "o2").exists(), "nothing is created before the hash check passes"


def test_real_mode_redacts_every_detail_and_skips_real_page_screenshots():
    t = MJS.read_text()
    assert "if (REAL) detail = ''" in t
    assert "if (!REAL) await page.screenshot({path: `${OUT}/B07.png`" in t
    assert all("REAL" not in line for line in t.splitlines() if "B01-" in line)  # legacy pages are unaffected
    for rid in ("R00", "R01", "R02", "R03", "R04"):
        assert f"'{rid}'" in t
    assert re.search(r"R04.*PRODUCTION build \(empty approval pins\)", t)


def test_py_driver_passes_only_paths_and_a_hash_to_the_browser_run():
    t = PY.read_text()
    assert '"REAL_MODE": "1"' in t and '"REAL_SIDECAR": str(' in t and '"REAL_PAYLOAD_SHA256": index["shas"]["real_default"]' in t


# ---------------------------------------------------------------- the workflow
def text():
    return WORKFLOW.read_text()


def test_workflow_is_manual_or_narrowly_pr_scoped_and_has_minimal_permissions():
    t = text()
    assert "workflow_dispatch:" in t and "schedule:" not in t and "push:" not in t and "pull_request_target" not in t
    # the only PR trigger: changes to this very file (a branch-only workflow cannot be dispatched before it is on the default branch)
    m = re.search(r"pull_request:\n    paths:\n((?:      - .*\n)+)", t)
    assert m and m.group(1).strip() == "- '.github/workflows/btc-07e-b-real-browser.yml'"
    assert re.search(r"^permissions:\n  contents: read\n  actions: read\n", t, re.M)
    assert "contents: write" not in t and "id-token" not in t


def test_workflow_never_deploys_publishes_or_commits():
    t = text().lower()
    for bad in ("wrangler", "cloudflare", "pages deploy", "git push", "git commit", "gh release", "--mode bootstrap", "gh api", "-x delete"):
        assert bad not in t, bad


def test_workflow_uploads_only_the_price_free_qa_files():
    t = text()
    uploads = [p for p in t.split("- name:") if "actions/upload-artifact" in p]
    assert len(uploads) == 1
    u = uploads[0]
    assert "btc-07e-b-public-qa" in u and "/qa/" in u
    for private in ("b/pkg", "b/restore", "b/candidate", "btc07eb", "btc-real-vintage", "acq/snapshot", "private-summary", "evidence"):
        assert private not in u, private
    assert "owner-download" not in u


def test_workflow_uses_the_existing_tools_and_the_external_anchor():
    t = text()
    for needed in ("tools.btc_07b_package restore", "tools.btc_06c_candidate", "tools.btc_07b_browser", "--real-candidate-dir", "--expect-sha256",
                   "PACKAGE SHA-256 DIFFERS FROM THE EXTERNAL ANCHOR", '"replay": "IDENTICAL"', "git diff --exit-code", "python -m etl.data_quality"):
        assert needed in t, needed
    assert "19abaa9b47c8172924920249304009bbea47e1c612b190666dfa28991b80d4ce" in t and "40006735985" in t


def test_workflow_prints_no_summary_file_or_candidate_content():
    t = text()
    for line in t.splitlines():
        assert not re.search(r"\bcat\b[^|\n]*(candidate|sidecar|values|payload|monthly)", line), line
    assert "candidate_values.json" not in t.replace("--real-candidate-dir", "")
