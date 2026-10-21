"""Validate a hist-model/1 JSON research bundle (ARCH-02). Read-only; exit 1 on any violation, 2 on unreadable input.

Usage: python tools/hist_model_check.py BUNDLE.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl import hist_model  # noqa: E402


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: hist_model_check.py BUNDLE.json", file=sys.stderr)
        return 2
    try:
        bundle = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read bundle: {exc}", file=sys.stderr)
        return 2
    errors = hist_model.validate_bundle(bundle)
    for error in errors:
        print(f"VIOLATION {error}")
    if errors:
        return 1
    print(f"OK {len(bundle['series'])} series, {len(bundle.get('releases', []))} release(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
