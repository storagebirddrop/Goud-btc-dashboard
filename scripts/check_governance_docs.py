"""Check governance inventory and relative Markdown links (offline, stdlib only)."""
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "PROJECT_SCOPE.md", "METHODOLOGY.md", "DATA_SOURCES.md",
    "ARCHITECTURE.md", "PROJECT_STATUS.md", "DECISIONS.md",
    "DATA_CONTRACT.md", "VERIFICATION_LOG.md", "CHANGE_CONTROL.md",
    "HANDOVER.md", "TASK_TEMPLATE.md", "REVIEW_CHECKLIST.md",
    "README_GOVERNANCE.md", "DOCUMENT_HIERARCHY.md", "CONFLICT_MATRIX.md",
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP = ("http://", "https://", "mailto:", "#", "data:")


def check():
    errors = []
    for name in REQUIRED:
        path = ROOT / name if name == "AGENTS.md" else ROOT / "docs" / "governance" / name
        if not path.is_file():
            errors.append(f"Missing: {path.relative_to(ROOT)}")
    for path in [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "docs" / "next-phase.md", *(ROOT / "docs" / "governance").glob("*.md")]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # Ignore fenced code blocks: sample URLs are not actual navigation.
        text = re.sub(r"(?ms)^\s*```.*?^\s*```", "", text)
        for match in LINK.finditer(text):
            href = match.group(1).strip().split()[0].strip("<>")
            if href.startswith(SKIP):
                continue
            target = (path.parent / unquote(href.split("#", 1)[0])).resolve()
            if not target.is_relative_to(ROOT.resolve()) or not target.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link {href}")
    # Explicit semantic gate: a documentation-only PR must not silently turn\n    # pending economic choices into approved decisions.\n    decisions = (ROOT / "docs" / "governance" / "DECISIONS.md")\n    if decisions.is_file():\n        decision_text = decisions.read_text(encoding="utf-8")\n        for adr in ("ADR-004", "ADR-007", "ADR-008", "ADR-009"):\n            lines = [line for line in decision_text.splitlines() if line.startswith("| " + adr + " |")]\n            if len(lines) != 1 or "PROPOSED" not in lines[0]:\n                errors.append(f"{adr}: unexpected approval or missing proposal status")\n        if "Geen weekend-/feestdag-carry-forward" not in decision_text and "Geen forward fill" not in (ROOT / "docs" / "governance" / "METHODOLOGY.md").read_text(encoding="utf-8"):\n            errors.append("Missing explicit prohibition on unapproved FX carry-forward")\n    return errors\n

if __name__ == "__main__":
    errors = check()
    if errors:
        raise SystemExit("\n".join(errors))
    print("Governance inventory and relative Markdown links: PASS")
