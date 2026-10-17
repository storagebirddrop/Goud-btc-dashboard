from scripts.check_governance_docs import check


def test_governance_inventory_and_links():
    assert check() == []

def test_governance_checker_rejects_broken_links_and_approval_drift(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil
    from scripts import check_governance_docs as audit

    original = audit.ROOT
    (tmp_path / "docs" / "governance").mkdir(parents=True)
    for name in audit.REQUIRED:
        relative = Path(name) if name == "AGENTS.md" else Path("docs/governance") / name
        shutil.copyfile(original / relative, tmp_path / relative)
    shutil.copyfile(original / "README.md", tmp_path / "README.md")
    shutil.copyfile(original / "docs/next-phase.md", tmp_path / "docs/next-phase.md")
    for extra in ("data/README.md", "docs/methodology.md", "docs/static-pipeline.md", "CONTRIBUTING.md", "SECURITY.md"):
        destination = tmp_path / extra
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / extra, destination)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.check() == []

    decisions = tmp_path / "docs/governance/DECISIONS.md"
    decisions.write_text(decisions.read_text().replace(
        "| ADR-004 | `PROPOSED`", "| ADR-004 | `DECIDED`"
    ))
    (tmp_path / "AGENTS.md").write_text(
        (tmp_path / "AGENTS.md").read_text() + "\n[broken](missing-governance.md)\n"
    )
    errors = audit.check()
    assert any("ADR-004" in error for error in errors)
    assert any("missing-governance.md" in error for error in errors)

def test_v31_nonretroactive_merge_and_access_limits():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    change = (root / "docs/governance/CHANGE_CONTROL.md").read_text(encoding="utf-8")
    hierarchy = (root / "docs/governance/DOCUMENT_HIERARCHY.md").read_text(encoding="utf-8")
    for label in ("GROEN", "ORANJE", "ROOD"):
        assert label in change
    assert "UNVERIFIED_ACCESS" in agents
    assert "UNVERIFIED_ACCESS" in change
    assert "niet retroactief" in change.lower()
    assert "dezelfde PR" in hierarchy
    assert "CI" in agents and "menselijke review" in agents
