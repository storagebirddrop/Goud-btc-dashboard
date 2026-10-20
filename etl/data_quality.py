"""Deterministic checks for committed housing CSV and public JSON.

This module verifies internal consistency, not independent source accuracy.
"""
import argparse
import json
import math
from pathlib import Path

from etl.static_export import build, gold_enabled


def validate(csv_path, json_path, *, gold_candidate=None, gold_approved=False):
    """Validate the public JSON against the source CSV.

    Default (gold_candidate None, gold_approved False): behaviour is unchanged,
    JSON must equal build(csv) and every gold field must be null.

    Opt-in gold mode requires ALL of: gold_approved is True, the same env flags
    as static_export.gold_enabled(), and a gold candidate that passes
    static_export.validate_gold. The JSON must then equal
    build(csv, gold_candidate, approved) exactly; gold_eur_oz stays null and only
    gold_index / gold_grams_per_house may be filled. Any partial combination is
    rejected rather than silently falling back.
    """
    gold_mode = gold_candidate is not None or gold_approved is not False
    if gold_mode:
        if gold_approved is not True or gold_candidate is None or not gold_enabled():
            raise ValueError("Gold validation requires approval flag, GOLD_PUBLICATION_ENABLED=true, "
                             "GOLD_PUBLICATION_APPROVAL=APPROVED and a gold candidate")
        expected = build(csv_path, gold_candidate=gold_candidate, gold_publication_approved=True)
    else:
        expected = build(csv_path)
    raw = Path(json_path).read_text(encoding="utf-8")
    payload = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(
        ValueError(f"Non-finite JSON number: {token}")))
    if not isinstance(payload, dict) or set(payload) != {"data"}:
        raise ValueError("Unexpected public JSON schema")
    rows = payload["data"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty or invalid public data")
    if payload != expected:
        raise ValueError("Public JSON differs from validated source CSV or calculated indices")
    if any(set(row) != {"period", "gold_eur_oz", "house_eur", "hpi",
                       "gold_grams_per_house", "gold_index", "hpi_index"} for row in rows):
        raise ValueError("Unexpected monthly record schema")
    for row in rows:
        for key in ("house_eur", "hpi", "hpi_index"):
            value = row[key]
            if row["period"] < "2000-01" and key in ("hpi", "hpi_index") and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Invalid numeric type for {key}")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid {key} at {row['period']}")
        for key in ("gold_eur_oz", "gold_grams_per_house", "gold_index"):
            if gold_mode and key != "gold_eur_oz":
                value = row[key]
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                          or not math.isfinite(value) or value <= 0):
                    raise ValueError(f"Invalid {key} at {row['period']}")
                continue
            if row[key] is not None:
                raise ValueError(f"Unexpected unverified gold value at {row['period']}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Verify committed CSV/JSON integrity and completeness")
    parser.add_argument("--input", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="frontend/public/data/monthly.json")
    parser.add_argument("--gold-candidate", default=None)
    parser.add_argument("--approve-gold", action="store_true")
    args = parser.parse_args()
    candidate = None
    if args.gold_candidate:
        candidate = json.loads(Path(args.gold_candidate).read_text(encoding="utf-8"))
    count = validate(args.input, args.output, gold_candidate=candidate,
                     gold_approved=args.approve_gold)
    print(f"Validated {count} consecutive months, both CBS series, schema and JSON/CSV parity")


if __name__ == "__main__":
    main()
