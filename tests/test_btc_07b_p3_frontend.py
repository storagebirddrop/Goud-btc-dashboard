"""BTC-07B P3: synthetic fixtures for the local browser acceptance, plus the opt-in real-browser run.

The real browser run (B01-B11) executes only when BTC07B_BROWSER=1 and a Chrome binary is given in CHROME_PATH (it needs Node, `npm ci` in frontend/ and
Playwright); otherwise it is reported as SKIPPED = NOT EXECUTED. Component/logic tests elsewhere are not browser acceptance."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from etl import btc_contract as bc
from tools import btc_07b_fixtures as fx

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    out = tmp_path_factory.mktemp("fx") / "fixtures"
    index = fx.build_fixtures(out)
    return out, index


def load(out, name):
    return json.loads((out / f"{name}.json").read_text())


def test_pinned_and_unpinned_fixtures_are_separated_and_the_legacy_hash_is_the_approved_one(fixtures):
    out, idx = fixtures
    s = idx["shas"]
    assert s["legacy"] == bc.LEGACY_PUBLIC_SHA256 and s["legacy"] not in idx["pinned"]
    assert s["unpinned_authorized_claim"] not in idx["pinned"] and s["poisoned_legacy"] not in idx["pinned"]
    assert {s[n] for n in ("real_default", "real_early", "exact", "incomplete", "pinned_bad_root", "pinned_no_meta")} == set(idx["pinned"])
    assert len(set(s.values())) == len(s), "every fixture has its own bytes"


def test_real_fixtures_are_produced_by_the_contract_and_validate_against_the_approved_legacy(fixtures):
    out, idx = fixtures
    legacy = (ROOT / "frontend/public/data/monthly.json").read_bytes()
    for name in ("real_default", "real_early"):
        blob = (out / f"{name}.json").read_bytes()
        summary = bc.validate_payload(json.loads(blob), legacy)
        assert summary["mode"] == "ACTIVE" and summary["legacy_sha256"] == bc.LEGACY_PUBLIC_SHA256
    default = load(out, "real_default")
    pub = [r for r in default["data"] if r["btc_meta"]["status"] == "PUBLISHED"]
    assert pub[0]["period"] == "2014-02" and pub[0]["btc_meta"]["quality"] == "Q2" and {r["period"]: r for r in pub}["2016-05"]["btc_meta"]["quality"] == "Q1_CANDIDATE"
    early = load(out, "real_early")
    rows = {r["period"]: r for r in early["data"]}
    assert early["btc"]["coverage"]["early_history_authorized"] is True and rows["2011-05"]["btc_meta"]["quality"] == "Q3"
    assert rows["2011-05"]["btc_per_house"] is not None and rows["2011-07"]["btc_per_house"] is not None
    assert rows["2011-06"]["btc_per_house"] is None and rows["2011-06"]["btc_meta"]["missing_reason"] == "RESEARCH_ONLY_HOLD"


def test_exact_fixture_is_the_documented_example(fixtures):
    out, _ = fixtures
    rows = {r["period"]: r for r in load(out, "exact")["data"]}
    assert list(rows) == ["2014-02", "2014-03", "2014-04"] and rows["2014-02"]["house_eur"] == 300000.0
    assert 300000 / (60000 / 1.2) == pytest.approx(6.0) and rows["2014-02"]["btc_per_house"] == 6 and rows["2014-02"]["sat_per_house"] == 600000000


def test_poison_fixtures_carry_claims_but_are_not_approved(fixtures):
    out, idx = fixtures
    p = load(out, "poisoned_legacy")
    assert all(r["sat_per_house"] == 123456789 and r["publication_authorized"] is True for r in p["data"]) and "btc" not in p
    assert load(out, "pinned_bad_root")["btc"]["contract_version"] == "btc-monthly/0"
    assert all("btc_meta" not in r for r in load(out, "pinned_no_meta")["data"])


def test_fixtures_and_builds_stay_outside_the_repository(tmp_path):
    from tools import btc_07b_browser as br
    with pytest.raises(SystemExit):
        br.main(["--out-dir", str(ROOT / "browser-out"), "--chrome", sys.executable])
    assert not (ROOT / "browser-out").exists()
    with pytest.raises(SystemExit, match="NOT EXECUTED"):
        br.main(["--out-dir", str(tmp_path / "o"), "--chrome", str(tmp_path / "no-chrome")])


@pytest.mark.skipif(os.environ.get("BTC07B_BROWSER") != "1" or not os.environ.get("CHROME_PATH"), reason="NOT EXECUTED: set BTC07B_BROWSER=1 and CHROME_PATH")
def test_real_browser_acceptance_b01_to_b11(tmp_path):
    res = subprocess.run([sys.executable, "-m", "tools.btc_07b_browser", "--out-dir", str(tmp_path / "run"), "--chrome", os.environ["CHROME_PATH"]],
                         cwd=ROOT, capture_output=True, text=True, timeout=1200)
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-2000:]
    doc = json.loads((tmp_path / "run/evidence/result.json").read_text())
    assert doc["executed"] is True and doc["failed"] == 0 and doc["total"] >= 55
