"""BTC-07B P3: local browser acceptance driver (B01-B11). Nothing is deployed or published; everything runs on 127.0.0.1.

1. Writes SYNTHETIC fixtures (tools/btc_07b_fixtures.py) to a private directory.
2. Builds the PRODUCTION frontend unchanged (approval pin empty) and a TEST build in a temporary copy of frontend/ in which ONLY the pin list
   contains the hashes of the approved synthetic fixtures. The repository sources are never modified.
3. Runs tools/btc_07b_browser.mjs (Playwright + a real Chrome/Chromium) against both builds.

Needs: Node >= 22, `npm ci` done in frontend/, Playwright (global or NODE_PATH) and a Chrome binary (--chrome or CHROME_PATH).
Usage: python -m tools.btc_07b_browser --out-dir /private/new/dir --chrome /path/to/chrome"""
from __future__ import annotations

import argparse
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
    a = ap.parse_args(argv)
    out = Path(a.out_dir).resolve()
    if ROOT in (out, *out.parents):
        raise SystemExit("the output directory must be outside the repository")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("the output directory must be new or empty")
    if not a.chrome or not Path(a.chrome).exists():
        raise SystemExit("NOT EXECUTED: no Chrome/Chromium binary (--chrome or CHROME_PATH)")
    out.mkdir(parents=True, exist_ok=True)
    index = fx.build_fixtures(out / "fixtures")
    build_production(out / "dist-production")
    build_test(out, index["pinned"], out / "dist-test")
    env = dict(os.environ, CHROME_PATH=a.chrome, OUT_DIR=str(out / "evidence"), FIXTURES=str(out / "fixtures"), DIST_PRODUCTION=str(out / "dist-production"),
               DIST_TEST=str(out / "dist-test"), NODE_PATH=os.environ.get("NODE_PATH", subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()))
    res = subprocess.run(["node", str(ROOT / "tools/btc_07b_browser.mjs")], env=env, cwd=ROOT)
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
