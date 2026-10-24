"""HIST-12: production parity. The inert historical implementation changes no public byte, no gold/CBS value, no BTC pin, record or identity, and no allowlist."""
import hashlib
import subprocess
from pathlib import Path

import pytest

from etl import btc_contract as bc
from etl import hist_model as hm
from tools import hist_publication as hp
from tools import btc_10_d07 as d07

ROOT = Path(__file__).resolve().parents[1]
CBS_SHA = "ad98bba942b0bc0c43ff142c7972c3e2742f53088398edb3ccde4ff422bbd8f6"  # data/cbs-housing.csv, the CBS input hash bound into the approved BTC D07 identity
C = "c11f82a83234593ace70369da07ca183c0cc3db3"  # frozen BTC calculation commit


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_legacy_public_json_and_cbs_csv_are_byte_identical_to_the_approved_ones():
    assert sha("frontend/public/data/monthly.json") == bc.LEGACY_PUBLIC_SHA256
    assert sha("data/cbs-housing.csv") == CBS_SHA


def test_btc_and_historical_defaults_stay_closed():
    assert bc.ARTIFACT_RECORDS == () and hm.ALLOWLIST == () and hp.COMPARISON_RELEASES == ()
    assert "export const BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/btc.ts").read_text()
    assert "export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[];" in (ROOT / "frontend/src/hist.ts").read_text()
    with pytest.raises(bc.BtcContractError):
        bc.composite_release_gate(b"{}")  # the BTC gate still denies by default


def test_the_gold_cbs_pipeline_still_reproduces_the_committed_public_json():
    r = subprocess.run(["python", "-m", "etl.data_quality"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]


def test_the_btc_d07_calculation_identity_is_unchanged():
    if subprocess.run(["git", "cat-file", "-e", f"{C}^{{commit}}"], cwd=ROOT, capture_output=True).returncode != 0:
        pytest.skip("NOT EXECUTED: the frozen calculation commit is not in this (shallow) checkout")
    ident = d07.calc_identity(C)
    assert ident["ok"], "calculation code differs (or an uncommitted/untracked file sits in the calculation paths) from the frozen BTC commit: the approved D07 identity would be invalidated"


def test_no_historical_data_exists_in_public_or_data_directories():
    assert not list((ROOT / "frontend/public").rglob("*hist*")) and not list((ROOT / "data").rglob("historical*"))
    assert not any(p.name == "historical.json" for p in ROOT.rglob("historical.json") if "node_modules" not in p.parts and "dist" not in p.parts)
