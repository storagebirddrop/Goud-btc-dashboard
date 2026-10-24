"""Guard the decided static architecture (ADR-001): the dashboard reads only static JSON: /data/monthly.json and the inert, hash-pinned /data/historical.json.

No Pages Functions, no D1 or other Cloudflare bindings, no API route that could serve data
(for example gold values) outside the validated static JSON and its publication checks.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ROUTING_FILES = ("_worker.js", "_middleware.js", "_middleware.ts", "_routes.json", "_redirects")


def test_no_pages_functions_or_routing_overrides():
    assert not (FRONTEND / "functions").exists()
    for base in (FRONTEND, FRONTEND / "public"):
        for name in ROUTING_FILES:
            assert not (base / name).exists(), f"{base.name}/{name} could add a data route"


def test_frontend_reads_only_the_static_json():
    sources = [p for p in (FRONTEND / "src").rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx"}]
    assert sources
    targets = []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "/api/" not in text, f"{path.name} references an API route"
        targets += re.findall(r"fetch\(\s*([^),]+)", text)
    assert targets, "frontend must fetch the static dataset"
    # HIST-12: the one additional, inert target. It is requested only when a payload hash is pinned (tests/test_hist_12_frontend.py).
    assert set(t.strip() for t in targets) == {"'/data/monthly.json'", "'/data/historical.json'"}


def test_wrangler_config_is_static_only():
    lines = [l.strip() for l in (FRONTEND / "wrangler.toml").read_text(encoding="utf-8").splitlines()]
    active = [l for l in lines if l and not l.startswith("#")]
    keys = {l.split("=")[0].strip() for l in active}
    assert keys == {"name", "compatibility_date", "pages_build_output_dir"}, active
    assert not any(l.startswith("[") for l in active), "no binding sections (D1, KV, R2, ...)"


def test_no_d1_tooling_left_in_workflows():
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        assert "wrangler d1" not in text and "d1_databases" not in text, workflow.name
