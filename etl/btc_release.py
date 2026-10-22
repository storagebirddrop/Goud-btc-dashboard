"""Opt-in release path for the extended `btc-monthly/1` payload (BTC-07B P2). Closed by default.

The legacy path stays the default and is untouched: `etl.static_export` builds the seven-field payload and
`etl.data_quality` validates it. This module adds the ONLY way an extended payload can reach a public file or pass the
production validator, and it always goes through `btc_contract.composite_release_gate`:

* an exact owner-approved artifact record for these bytes (composite, BTC selection and legacy projection hashes, fields,
  months, provenance, versions) must be registered in `btc_contract.ARTIFACT_RECORDS` (empty today);
* no JSON boolean, environment variable, URL or command-line flag can supply or replace that record. The `records`
  argument exists for synthetic tests only; the command line never reads records;
* the seven legacy fields must project to the pinned, byte-identical gold/CBS payload and pass the existing legacy validation;
* `export_composite` never writes into the committed public path: activating a release is a reviewed commit that replaces
  that file AND registers the record.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from etl import btc_contract as bc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC = ROOT / "frontend/public/data/monthly.json"
DEFAULT_CSV = ROOT / "data/cbs-housing.csv"


def gate(blob: bytes, records=None) -> dict:
    """Release gate with the same semantics as the contract: ReleaseDenied unless an exact approved record exists."""
    return bc.composite_release_gate(blob, records)


def export_composite(composite_path, output_path, *, legacy_path=DEFAULT_PUBLIC, records=None) -> dict:
    """Write the composite bytes to an explicit NEW file, only if the gate opens for exactly these bytes. Never overwrites."""
    blob = Path(composite_path).read_bytes()
    legacy = Path(legacy_path).read_bytes()
    record = gate(blob, records)
    composite = json.loads(blob.decode("utf-8"))
    bc.validate_legacy_projection(composite, legacy)  # byte-identical to the approved legacy payload
    out = Path(output_path)
    if out.resolve() == DEFAULT_PUBLIC.resolve() or out.resolve() == Path(legacy_path).resolve():
        raise bc.BtcContractError("the committed public file is replaced only by a reviewed commit, never by this tool")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "xb") as fh:
        fh.write(blob)
    return {"record_id": record["record_id"], "composite_sha256": bc.sha256(blob), "output": str(out)}


def validate_composite_state(csv_path, json_path, gold_release_record=None, *, records=None) -> int:
    """Production validation of a public JSON that carries the extended payload.

    1. the gate (canonical bytes, contract validation, exact approved record);
    2. the legacy projection is validated by the unchanged legacy production validator, so the seven fields,
       the CBS parity and the gold release record keep their existing protection. Returns the month count."""
    from etl import data_quality as dq
    blob = Path(json_path).read_bytes()
    gate(blob, records)
    composite = json.loads(blob.decode("utf-8"))
    projection = bc.legacy_projection_bytes(composite)
    if bc.sha256(projection) != bc.LEGACY_PUBLIC_SHA256:
        raise bc.BtcContractError("legacy projection is not the approved gold/CBS payload")
    with tempfile.TemporaryDirectory() as tmp:
        legacy = Path(tmp) / "legacy.json"
        legacy.write_bytes(projection)
        count, _ = dq.validate_production_state(csv_path, legacy, gold_release_record or str(ROOT / "data/gold-release-record.json"))
    return count


def main(argv=None):
    ap = argparse.ArgumentParser(description="Opt-in extended release path (closed by default; records are never read from the command line)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--composite", required=True)
    ex.add_argument("--output", required=True, help="explicit new file; the committed public file is refused")
    ex.add_argument("--legacy", default=str(DEFAULT_PUBLIC))
    va = sub.add_parser("validate")
    va.add_argument("--input", default=str(DEFAULT_CSV))
    va.add_argument("--output", default=str(DEFAULT_PUBLIC))
    a = ap.parse_args(argv)
    try:
        if a.cmd == "export":
            print(json.dumps(export_composite(a.composite, a.output, legacy_path=a.legacy), sort_keys=True))
        else:
            print(f"Validated {validate_composite_state(a.input, a.output)} months of the extended payload and its legacy projection")
    except bc.ReleaseDenied as exc:
        print(f"RELEASE DENIED: {str(exc)[:200]}")
        return 2
    except (bc.BtcContractError, OSError, ValueError) as exc:
        print(f"DEFECT {type(exc).__name__}: {str(exc)[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
