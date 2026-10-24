"""HIST-13: PRIVATE browser verification of the REAL historical candidate against the HIST-12 gate. Run only in a private, access-controlled environment.

Builds the production frontend unchanged (empty pins) and a TEST copy whose pin list holds the hashes of the in-memory-authorized preflight payloads (and of the unauthorized
candidate, to prove the structural gate). Serves the real payloads over loopback only. Output is REDACTED: pass/fail per check, no value, no screenshot, no stored page.

Usage: python -m tests.hist13.private_browser --candidate-dir PRIVATE_DIR --out-dir NEW_DIR_OUTSIDE_REPO --chrome PATH   (PRIVATE_DIR from hist_13_candidate --write-preflight)"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.hist12 import browser as hb  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    a = ap.parse_args(argv)
    cand = Path(a.candidate_dir).resolve()
    out = Path(a.out_dir).resolve()
    for p in (cand, out):
        if ROOT in (p, *p.parents):
            raise SystemExit("private directories must be outside the repository")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("the output directory must be new or empty")
    if not a.chrome or not Path(a.chrome).exists():
        raise SystemExit("UNVERIFIED_PRIVATE_BROWSER: no Chrome/Chromium binary")
    out.mkdir(parents=True, exist_ok=True)
    sha = lambda n: hashlib.sha256((cand / n).read_bytes()).hexdigest()
    pins = [sha("preflight_on.json"), sha("preflight_off.json"), sha("historical.candidate.json")]
    hb.build_production(out / "dist-production")
    hb.build_test(out, pins, out / "dist-test", allow_synthetic=False)
    env = dict(os.environ, CHROME_PATH=a.chrome, CAND_DIR=str(cand), DIST_PRODUCTION=str(out / "dist-production"), DIST_TEST=str(out / "dist-test"),
               LEGACY_JSON=str(ROOT / "frontend/public/data/monthly.json"),
               NODE_PATH=os.environ.get("NODE_PATH", subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()))
    return subprocess.run(["node", str(ROOT / "tests/hist13/private_browser.mjs")], env=env, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
