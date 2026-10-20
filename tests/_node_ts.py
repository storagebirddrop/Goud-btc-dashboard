"""Run frontend TypeScript logic (frontend/src/series.ts) with Node's built-in type stripping.

Locally the tests skip when Node is too old; in CI (CI=true) a missing or old Node is a failure, so the
frontend logic tests can never be skipped silently there.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SERIES_TS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "series.ts"


def _node():
    node = shutil.which("node")
    if not node:
        return None
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return node if (int(v[0]), int(v[1])) >= (22, 6) else None


def need_node():
    node = _node()
    if node:
        return node
    if os.environ.get("CI"):
        pytest.fail("Node >= 22.6 is required in CI to run the frontend logic tests (add actions/setup-node)")
    pytest.skip("needs Node >= 22.6 to run TypeScript directly")


def run_series(body):
    script = f"import * as S from {json.dumps(SERIES_TS.as_uri())};\n{body}"
    res = subprocess.run([need_node(), "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])
