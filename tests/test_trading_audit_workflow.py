"""Guard against literal escaped newlines in Actions YAML.

A prior workflow accidentally contained the two characters backslash+n,
which Python unit tests did not detect.
"""
from pathlib import Path


def test_trading_audit_workflow_has_real_line_breaks():
    workflow = Path(".github/workflows/trading-btc-audit.yml").read_text()
    assert "\\n" not in workflow
    assert "\n      - name: Diagnose FX calendar gaps (no conversion)\n" in workflow
    assert "\n        run: python -m etl.btc_fx_calendar_audit trading-source/data/history.csv\n" in workflow
    assert "\n          path: |\n            trading-btc-audit-report.json\n            btc-fx-calendar-report.json\n" in workflow
    assert "  workflow_dispatch:\n" in workflow
    assert "  push:\n" in workflow
