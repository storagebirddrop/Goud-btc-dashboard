"""Guardrails for the scheduled CBS updater's publication privileges."""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/update-static-data.yml"


def test_cbs_updater_is_read_only_and_review_gated():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in content
    assert "contents: write" not in content
    assert "actions/upload-artifact@v4" in content
    assert "cbs-validated-candidate" in content
    assert "if-no-files-found: error" in content
    assert "git push" not in content
    assert "git commit" not in content
    assert "create-pull-request" not in content


def test_cbs_updater_runs_validation_before_artifact_upload():
    content = WORKFLOW.read_text(encoding="utf-8")
    assert content.index("Verify generated source and public JSON parity") < content.index(
        "Upload validated CBS candidate for manual review"
    )
    assert content.index("Validate generated payload") < content.index(
        "Upload validated CBS candidate for manual review"
    )
