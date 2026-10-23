"""BTC-07B P3 / BTC-07E-B: local browser acceptance driver (B01-B11; optional real-candidate mode R01-R05, redacted). Nothing is deployed or published; everything runs on 127.0.0.1.

1. Writes SYNTHETIC fixtures (tools/btc_07b_fixtures.py) to a private directory.
2. Builds the PRODUCTION frontend unchanged (approval pin empty) and a TEST build in a temporary copy of frontend/ in which ONLY the pin list
   contains the hashes of the approved synthetic fixtures. The repository sources are never modified.
3. Runs tools/btc_07b_browser.mjs (Playwright + a real Chrome/Chromium) against both builds.

Needs: Node >= 22, `npm ci` done in frontend/, Playwright (global or NODE_PATH) and a Chrome binary (--chrome or CHROME_PATH).
Usage: python -m tools.btc_07b_browser --out-dir /private/new/dir --chrome /path/to/chrome"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import btc_07b_fixtures as fx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PIN_LINE = "export const BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[];"


def build_production(out: Path):
    subprocess.run([str(FRONTEND / "node_modules/.bin/tsc"), "--noEmit", "-p", "."], cwd=FRONTEND, check=True)
    subprocess.run([str(FRONTEND / "node_modules/.bin/vite"), "build", "--outDir", str(out), "--emptyOutDir"], cwd=FRONTEND, check=True,
                   capture_output=True)


def build_test(work: Path, pins: list, out: Path):
    """A temporary copy of the frontend whose pin list holds the synthetic approved hashes. Only the copy is patched."""
    copy = work / "frontend-test-copy"
    copy.mkdir()
    for name in ("src", "index.html", "package.json", "tsconfig.json"):
        src = FRONTEND / name
        (shutil.copytree if src.is_dir() else shutil.copy)(src, copy / name)
    (copy / "node_modules").symlink_to(FRONTEND / "node_modules")
    btc = copy / "src/btc.ts"
    text = btc.read_text(encoding="utf-8")
    if PIN_LINE not in text:
        raise SystemExit("approval pin line not found: the test build cannot be prepared")
    btc.write_text(text.replace(PIN_LINE, "export const BTC_APPROVED_COMPOSITE_SHA256:readonly string[]=[" + ",".join(f"'{p}'" for p in pins) + "];"), encoding="utf-8")
    subprocess.run([str(copy / "node_modules/.bin/vite"), "build", "--outDir", str(out), "--emptyOutDir"], cwd=copy, check=True, capture_output=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="BTC-07B local browser acceptance (synthetic data, loopback only)")
    ap.add_argument("--out-dir", required=True, help="new private directory for fixtures, builds, screenshots and the result file")
    ap.add_argument("--chrome", default=os.environ.get("CHROME_PATH"), help="Chrome/Chromium binary")
    ap.add_argument("--real-candidate-dir", help="BTC-07E-B: directory with the PRIVATE real candidate (candidate.json + candidate_values.json from btc_06c_candidate). "
                    "The default payload is then composed from it with a TEST authorization that exists only in the temporary build; output and logs are redacted")
    ap.add_argument("--expect-candidate-sha256", help="with --real-candidate-dir: required SHA-256 of candidate.json")
    ap.add_argument("--expect-sidecar-sha256", help="with --real-candidate-dir: required SHA-256 of candidate_values.json")
    a = ap.parse_args(argv)
    out = Path(a.out_dir).resolve()
    if ROOT in (out, *out.parents):
        raise SystemExit("the output directory must be outside the repository")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("the output directory must be new or empty")
    if not a.chrome or not Path(a.chrome).exists():
        raise SystemExit("NOT EXECUTED: no Chrome/Chromium binary (--chrome or CHROME_PATH)")
    real = Path(a.real_candidate_dir).resolve() if a.real_candidate_dir else None
    if real is not None:
        if ROOT in (real, *real.parents):
            raise SystemExit("the real candidate directory must be outside the repository")
        for name, want in (("candidate.json", a.expect_candidate_sha256), ("candidate_values.json", a.expect_sidecar_sha256)):
            got = hashlib.sha256((real / name).read_bytes()).hexdigest()
            if want and got != want:
                raise SystemExit(f"REAL CANDIDATE HASH MISMATCH for {name}: refusing to run")
            print(f"real candidate {name} sha256 {got}")
    out.mkdir(parents=True, exist_ok=True)
    index = fx.build_fixtures(out / "fixtures", real)
    build_production(out / "dist-production")
    build_test(out, index["pinned"], out / "dist-test")
    real_env = {}
    if real is not None:
        real_env = {"REAL_MODE": "1", "REAL_SIDECAR": str(real / "candidate_values.json"), "REAL_PREVIEW": str(real / "candidate.json"),
                    "REAL_PAYLOAD_SHA256": index["shas"]["real_default"]}
        print(f"real default payload sha256 {index['shas']['real_default']}")
    env = dict(os.environ, **real_env, CHROME_PATH=a.chrome, OUT_DIR=str(out / "evidence"), FIXTURES=str(out / "fixtures"), DIST_PRODUCTION=str(out / "dist-production"),
               DIST_TEST=str(out / "dist-test"), NODE_PATH=os.environ.get("NODE_PATH", subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()))
    res = subprocess.run(["node", str(ROOT / "tools/btc_07b_browser.mjs")], env=env, cwd=ROOT)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
