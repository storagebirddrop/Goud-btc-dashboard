"""HIST-13: the private historical candidate builder. The inputs are the hash-pinned HIST-09 package already in the repository; the tests assert hashes, counts and
booleans only (never print or upload a value), and prove that the builder writes outside the repository, stays deterministic and keeps every gate closed."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from etl import hist_model as hm
from tools import hist_09_bundle as hb9
from tools import hist_13_candidate as hc
from tools import hist_publication as hp

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data/fixtures/hist09"
PROD_CSV = ROOT / "data/cbs-housing.csv"
CANDIDATE_SHA256 = "e35a28946feb2612cf994fbc78cdffd70815af63740c9314dfb036ab01ba2d51"  # identity of the candidate built from the pinned inputs
RELEASE_SHA256 = "99e6f998b3d8ed7f10099110b48b0d87a9da2fba7367212527577ffb86be95c0"


@pytest.fixture(scope="module")
def built():
    files, extra, report = hc.build_all(INPUTS, PROD_CSV)
    return {"files": files, "extra": extra, "report": report, "doc": json.loads(files["historical.candidate.json"])}


def test_the_candidate_identity_is_pinned_and_the_report_is_ok(built):
    r = built["report"]
    assert hc.sha(built["files"]["historical.candidate.json"]) == r["candidate_sha256"] == CANDIDATE_SHA256, "candidate identity changed"
    assert r["release_sha256"] == RELEASE_SHA256 and r["ok"]
    assert r["counts"] == {"nvm_half_years": 52, "cbs_months": 60, "comparison_half_years": 12}


def test_coverage_periods_frequencies_and_series_are_exactly_the_approved_scope(built):
    assert [s["series_id"] for s in built["doc"]["series"]] == sorted(hp.APPROVED_SERIES)
    for s in built["doc"]["series"]:
        spec = hp.APPROVED_SERIES[s["series_id"]]
        assert [p["period"] for p in s["points"]] == hm.expected_periods(spec["first"], spec["last"], spec["frequency"])
        assert (s["frequency"], s["currency"], s["kind"], s["layer"]) == (spec["frequency"], spec["currency"], spec["kind"], spec["layer"])
        assert {p["quality"] for p in s["points"]} == {"CONFIRMED"}


def test_independent_recalculation_agrees_everywhere(built):
    ind = built["report"]["independent_recalculation"]
    assert ind["ok"] and all(ind[k] for k in ("nvm_nlg_equal", "nvm_eur_equal", "cbs_months_equal", "cbs_half_equal", "periods_aligned", "mean_median_separate")) and ind["production_2000_equal"] is True


def test_the_page_135_qualification_is_preserved_and_flags_are_documented(built):
    flags = {s["series_id"]: sum(1 for p in s["points"] if "VISUAL_P135_PER_PROJECT_CONTROL" in p["flags"]) for s in built["doc"]["series"]}
    assert flags["hist_nvm_median_nlg_h"] == flags["hist_nvm_median_eur_retro_h"] == 41 and flags["hist_cbs_avg_eur_m"] == flags["hist_cbs_avg_eur_h"] == 0
    assert all(set(p["flags"]) <= hp.FLAGS for s in built["doc"]["series"] for p in s["points"])


def test_the_candidate_is_closed_and_cannot_authorize_itself(built):
    rel = built["doc"]["release"]
    assert rel["publication_authorized"] is False and rel["comparison_authorized"] is False and {rel["authorizer"], rel["authorized_on"], rel["decision_ref"]} == {"PENDING"}
    blob = built["files"]["historical.candidate.json"]
    for kw in (dict(pins=[hc.sha(blob)], records=[]), dict(pins=[]), dict(pins=[hc.sha(blob)], records=[hp.release_record(rel)])):
        with pytest.raises((hp.HistPublicationDenied, hm.PublicationDenied, ValueError)):
            hp.verify_payload(blob, **kw)
    assert hm.ALLOWLIST == () and hp.COMPARISON_RELEASES == ()


def test_contract_validation_and_the_negative_battery(built):
    v = built["report"]["contract"]
    assert v["ok"] and v["negative_harness_control_noop_mutation_passes"] and v["negative_passed"] == v["negative_total"] >= 21
    assert all(built["report"]["negative_cases"].values()) and v["preflight_comparison_on_passes_only_with_external_hp3"]


def test_the_release_record_template_is_unapproved_and_price_free(built):
    t = json.loads(built["files"]["historical.release-record.template.json"])
    assert {t["owner_approval"], t["approved_by"], t["approved_on"], t["decision_ref"], t["frontend_pin"], t["allowlist_entry"]} == {"PENDING"} and t["comparison_authorized"] is False
    assert t["candidate_sha256"] == CANDIDATE_SHA256 and t["release_id"].endswith("(PROPOSED)")
    free = b"".join(built["files"][n] for n in ("historical.manifest.json", "historical.release-record.template.json", "historical.validation-report.json"))
    longs = {p["value"] for s in built["doc"]["series"] if s["series_id"] in ("hist_nvm_median_eur_retro_h", "hist_cbs_avg_eur_h") for p in s["points"]}
    assert not any(v.encode() in free for v in longs), "a restricted value reached a price-free document"


def test_rebuild_is_byte_identical_in_a_separate_process(built, tmp_path):
    out = tmp_path.parent / (tmp_path.name + "_priv")
    r = subprocess.run([sys.executable, "-m", "tools.hist_13_candidate", "--inputs", str(INPUTS), "--out-dir", str(out), "--production-csv", str(PROD_CSV)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    try:
        for name, blob in built["files"].items():
            assert (out / name).read_bytes() == blob, name
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_tampered_or_missing_inputs_block_the_build(tmp_path):
    bad = tmp_path / "hist09"
    shutil.copytree(INPUTS, bad)
    p = bad / "HIST09_NVM_1975_2000_RESEARCH.csv"
    p.write_bytes(p.read_bytes().replace(b",88900,", b",88901,", 1))
    with pytest.raises(hb9.InputError):
        hc.build_series(bad)
    (bad / "85773NED-202609220630.zip").unlink()
    with pytest.raises((hb9.InputError, FileNotFoundError, OSError)):
        hc.build_series(bad)


def test_the_cli_refuses_outputs_inside_the_repository_or_a_served_directory(tmp_path):
    for target in (ROOT / "docs" / "hist13_out", ROOT / "frontend" / "public" / "x", tmp_path / "public" / "x", tmp_path / "dist"):
        r = subprocess.run([sys.executable, "-m", "tools.hist_13_candidate", "--inputs", str(INPUTS), "--out-dir", str(target)], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode != 0 and not target.exists(), target


def test_no_historical_candidate_or_payload_exists_in_the_repository_and_gates_stay_closed():
    assert not [p for p in ROOT.rglob("historical.*") if "node_modules" not in p.parts]
    assert not list((ROOT / "frontend/public").rglob("*hist*"))
    assert "export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/hist.ts").read_text()
