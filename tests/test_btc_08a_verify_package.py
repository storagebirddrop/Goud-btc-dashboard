"""BTC-08A: the owner-side independent restore of a vintage package. SYNTHETIC package (built with the existing pack tool); proves the chain and its
failure modes, not real data. The real package is exercised by the manual workflow btc-07e-b-real-browser.yml."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import btc_07b_fixtures as fx
from tools import btc_08a_verify_package as v

ROOT = Path(__file__).resolve().parents[1]
HEAD = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def pkg(tmp_path_factory):
    work = tmp_path_factory.mktemp("pkg")
    fx.synthetic_candidate(work)  # writes work/synthetic-snapshot
    tar = work / "p.tar"
    p = subprocess.run([sys.executable, "-m", "tools.btc_07b_package", "pack", "--snapshot", str(work / "synthetic-snapshot"), "--cbs-csv", "data/cbs-housing.csv",
                        "--legacy-json", "frontend/public/data/monthly.json", "--out", str(tar)], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    return tar, v.sha(tar)


def run(capsys, args):
    rc = v.main(args)
    return rc, json.loads(capsys.readouterr().out)


def test_independent_restore_chain_passes_and_output_is_price_free(pkg, tmp_path, capsys):
    tar, anchor = pkg
    if not HEAD:
        pytest.skip("needs a git checkout")
    rc, r = run(capsys, ["--package", str(tar), "--expect-sha256", anchor, "--dest", str(tmp_path / "d"), "--calc-commit", HEAD])
    ck = r["checks"]
    for name in ("package_sha256_equals_anchor", "calculation_code_identical_to_calc_commit", "restore_verified", "restore_replay_identical", "candidate_rebuilt_replay_identical",
                 "rebuilt_equals_packed_candidate_and_sidecar", "offline_replay_identical"):
        assert ck[name] is True, name
    assert r["candidate"]["candidate_value_months"] == 151 and r["candidate"]["published_months"] == 0 and r["offline_replay"]["status"] == "IDENTICAL"
    # the isolation flag is honest: it is only true when an empty network namespace was proven
    assert ck["offline_replay_network_isolated"] == (r["network_isolation"] == "EMPTY_NETWORK_NAMESPACE_PROVEN")
    assert rc == (0 if r["all_checks_pass"] else 1)
    text = json.dumps(r)
    assert "btc_per_house" not in text and "sat_per_house" not in text


def test_expected_hashes_are_enforced(pkg, tmp_path, capsys):
    tar, anchor = pkg
    rc, r = run(capsys, ["--package", str(tar), "--expect-sha256", anchor, "--dest", str(tmp_path / "d"), "--expect-candidate-sha256", "0" * 64])
    assert rc == 1 and r["checks"]["expected_candidate_matches"] is False and r["all_checks_pass"] is False


def test_wrong_anchor_stops_before_any_extraction(pkg, tmp_path, capsys):
    tar, _ = pkg
    rc, r = run(capsys, ["--package", str(tar), "--expect-sha256", "0" * 64, "--dest", str(tmp_path / "d")])
    assert rc == 2 and r["checks"] == {"package_sha256_equals_anchor": False}
    assert not (tmp_path / "d").exists()


def test_a_calculation_commit_that_is_not_available_or_differs_is_refused(pkg, tmp_path, capsys):
    tar, anchor = pkg
    rc, r = run(capsys, ["--package", str(tar), "--expect-sha256", anchor, "--dest", str(tmp_path / "d"), "--calc-commit", "1" * 40])
    assert rc == 3 and r["checks"]["calculation_code_identical_to_calc_commit"] is False and r["commit_available_locally"] is False
    assert not (tmp_path / "d").exists()


def test_destination_inside_the_repository_is_refused(pkg):
    tar, anchor = pkg
    with pytest.raises(SystemExit):
        v.main(["--package", str(tar), "--expect-sha256", anchor, "--dest", str(ROOT / "docs/x")])
