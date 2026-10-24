"""HIST-12: local browser acceptance driver for the INERT historical interface (SYNTHETIC fixtures; loopback only; nothing is deployed or published).

1. writes SYNTHETIC fixtures (tests/hist12/fixtures.py) to a private directory outside the repository;
2. builds the PRODUCTION frontend unchanged (pin list empty, synthetic data not allowed);
3. builds a TEST copy in which ONLY the pin list holds the synthetic fixture hashes and synthetic data is allowed (the repository sources are never modified);
4. runs tests/hist12/browser.mjs (Playwright + Chrome/Chromium) against both builds.

Usage: python -m tests.hist12.browser --out-dir /private/new/dir --chrome /path/to/chrome"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.hist12 import fixtures as fx  # noqa: E402

FRONTEND = ROOT / "frontend"
PIN_LINE = "export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[];"
ALLOW_LINE = "export const HIST_ALLOW_SYNTHETIC=false;"


def vite_build(project: Path, out: Path):
    subprocess.run([str(FRONTEND / "node_modules/.bin/vite"), "build", "--outDir", str(out), "--emptyOutDir"], cwd=project, check=True, capture_output=True)


def build_production(out: Path):
    subprocess.run([str(FRONTEND / "node_modules/.bin/tsc"), "--noEmit", "-p", "."], cwd=FRONTEND, check=True)
    vite_build(FRONTEND, out)


def build_test(work: Path, pins: list, out: Path):
    copy = work / "frontend-test-copy"
    copy.mkdir()
    for name in ("src", "index.html", "package.json", "tsconfig.json"):
        src = FRONTEND / name
        (shutil.copytree if src.is_dir() else shutil.copy)(src, copy / name)
    (copy / "node_modules").symlink_to(FRONTEND / "node_modules")
    hist = copy / "src/hist.ts"
    text = hist.read_text(encoding="utf-8")
    if PIN_LINE not in text or ALLOW_LINE not in text:
        raise SystemExit("pin or synthetic-allow line not found: the test build cannot be prepared")
    text = text.replace(PIN_LINE, "export const HIST_APPROVED_PAYLOAD_SHA256:readonly string[]=[" + ",".join(f"'{p}'" for p in pins) + "];").replace(ALLOW_LINE, "export const HIST_ALLOW_SYNTHETIC=true;")
    hist.write_text(text, encoding="utf-8")
    vite_build(copy, out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="HIST-12 browser acceptance (synthetic data, loopback only)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    a = ap.parse_args(argv)
    out = Path(a.out_dir).resolve()
    if ROOT in (out, *out.parents):
        raise SystemExit("the output directory must be outside the repository")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("the output directory must be new or empty")
    if not a.chrome or not Path(a.chrome).exists():
        raise SystemExit("NOT EXECUTED: no Chrome/Chromium binary (--chrome or CHROME_PATH)")
    out.mkdir(parents=True, exist_ok=True)
    index = fx.build(out / "fixtures")
    build_production(out / "dist-production")
    build_test(out, index["pinned"], out / "dist-test")
    env = dict(os.environ, CHROME_PATH=a.chrome, OUT_DIR=str(out / "evidence"), FIXTURES=str(out / "fixtures"), DIST_PRODUCTION=str(out / "dist-production"),
               DIST_TEST=str(out / "dist-test"), LEGACY_JSON=str(ROOT / "frontend/public/data/monthly.json"), VALID_SHA=index["valid"],
               NODE_PATH=os.environ.get("NODE_PATH", subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()))
    return subprocess.run(["node", str(ROOT / "tests/hist12/browser.mjs")], env=env, cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
