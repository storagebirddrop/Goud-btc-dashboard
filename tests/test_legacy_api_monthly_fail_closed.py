"""Legacy Pages Function /api/monthly must stay fail-closed and never expose gold (ADR-001, gold HOLD)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "frontend" / "functions" / "api" / "monthly.ts"
SETUP_DOC = ROOT / "docs" / "cloudflare-setup.md"


def test_function_is_gated_and_gold_free_statically():
    src = FUNCTION.read_text(encoding="utf-8")
    assert "LEGACY_D1_API_ENABLED !== 'true'" in src
    assert "status: 404" in src
    assert "status: 503" in src and "legacy_d1_unavailable" in src
    assert "api-monthly-integration" not in src
    sql = re.search(r"prepare\(`(.*?)`\)", src, re.S).group(1)
    assert "gold" not in sql.lower()
    for field in ("gold_eur_oz", "gold_grams_per_house", "gold_index"):
        assert re.search(rf"{field}:null", src), field


def test_setup_doc_is_marked_legacy():
    head = SETUP_DOC.read_text(encoding="utf-8")[:1200]
    assert "LEGACY" in head and "ADR-001" in head and "static-pipeline.md" in head


def test_handler_behaviour_with_fake_env():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    proc = subprocess.run(
        [node, str(ROOT / "tests" / "legacy_api_monthly" / "handler_check.mjs")],
        capture_output=True, text=True, cwd=ROOT,
    )
    if "ERR_UNKNOWN_FILE_EXTENSION" in proc.stderr or "Unknown file extension" in proc.stderr:
        pytest.skip("node lacks native TypeScript type stripping (needs >= 22.18)")
    assert proc.returncode == 0, proc.stdout + proc.stderr
