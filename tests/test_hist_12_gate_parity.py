"""HIST-12: the TypeScript gate and the Python contract agree on the synthetic fixture set (see tests/hist12/gate_parity.py). Skipped = NOT EXECUTED when the frontend
dependencies are missing (the CI `frontend` job runs the same check after `npm ci`)."""
import os

import pytest

from tests.hist12 import gate_parity as gp


@pytest.mark.skipif(not gp.available(), reason="NOT EXECUTED: node or frontend/node_modules missing")
def test_typescript_gate_equals_python_contract_on_all_synthetic_fixtures():
    r = gp.run()
    accepted = sorted(n for n in r["names"] if r["ts"][n]["pinned_synth"])
    assert accepted == ["valid", "valid_nocmp"]
    for n in r["names"]:
        t = r["ts"][n]
        assert t["pinned_synth"] == r["py"][n], n
        assert not (t["pinned_prod"] or t["empty_pins"] or t["wrong_hash"] or t["null_hash"]), (n, t)


@pytest.mark.skipif(os.environ.get("HIST12_BROWSER") != "1" or not os.environ.get("CHROME_PATH"), reason="NOT EXECUTED: set HIST12_BROWSER=1 and CHROME_PATH (Playwright)")
def test_browser_acceptance(tmp_path):
    from tests.hist12 import browser
    assert browser.main(["--out-dir", str(tmp_path / "out"), "--chrome", os.environ["CHROME_PATH"]]) == 0
