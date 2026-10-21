"""Deterministic checks for committed housing CSV and public JSON.

This module verifies internal consistency, not independent source accuracy.

Gold release mode (record based) reports FIVE SEPARATE levels; none is derived
from another, and a SHA-256 only proves file identity, never correctness:
  HASH VERIFIED       artifact sha256 and CBS csv sha256, computed by this code.
  CONTENT VALIDATED   structural/numeric invariants, computed by this code.
  ATTESTED BY RECORD, NOT VERIFIED BY CODE: SOURCE (World Bank/ECB hashes),
  METHODOLOGY APPROVED (ADR-004), PUBLICATION AUTHORIZED (release_authorization).
The preflight never reports an authorized publication.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

from etl.static_export import build, gold_enabled


GOLD_PUBLIC_FIELDS = ("gold_grams_per_house", "gold_index")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PERIOD = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(T.*)?")
EXIT_PREFLIGHT_NOT_AUTHORIZED = 3
RECORD_KEYS = ("schema_version", "artifact", "fields_published", "methodology", "sources",
               "candidate_validation", "release_authorization")


def _finite_positive(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0)


def _check_pinned_public_gold(rows, expected_rows):
    """Structural checks of a pinned public JSON-v1 gold payload, no private inputs.

    Every non-gold field must equal build(csv) exactly (gold_eur_oz stays null).
    gold_index and gold_grams_per_house must form a contiguous block from 2000-01
    (trailing months may be null: pending publication), index base 2000-01 == 100,
    and satisfy grams * index / house_eur == constant (ADR-004: grams = house /
    (EUR/oz / g-per-oz), index = 100 * EUR/oz / EUR/oz[2000-01]). This cannot prove
    the raw gold/FX inputs; the release record's sha256 identifies the reviewed bytes.
    """
    if len(rows) != len(expected_rows):
        raise ValueError("Pinned gold JSON month coverage differs from CSV")
    const = None
    gap = False
    for index, (row, exp) in enumerate(zip(rows, expected_rows)):
        if not isinstance(row, dict) or set(row) != set(exp):
            raise ValueError("Unexpected monthly record schema")
        if any(row[k] != exp[k] for k in exp if k not in GOLD_PUBLIC_FIELDS):
            raise ValueError(f"Non-gold field differs from validated CSV at {exp['period']}")
        idx, grams = row["gold_index"], row["gold_grams_per_house"]
        if idx is None and grams is None:
            gap = True
            continue
        if idx is None or grams is None or gap or row["period"] < "2000-01":
            raise ValueError(f"Gold fields missing, partial, non-contiguous or pre-2000 at {row['period']}")
        if not (_finite_positive(idx) and _finite_positive(grams)):
            raise ValueError(f"Invalid gold value at {row['period']}")
        if row["period"] == "2000-01" and idx != 100:
            raise ValueError("Incorrect gold index basis")
        k = grams * idx / row["house_eur"]
        if const is None:
            const = k
        elif abs(k - const) > abs(const) * 1e-9:
            raise ValueError(f"Gold index / grams-per-house inconsistent at {row['period']}")
    if const is None or next(r for r in rows if r["gold_index"] is not None)["period"] != "2000-01":
        raise ValueError("Gold index basis 2000-01 missing")


def _exact(obj, keys, name):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError(f"Release record: {name} must be an object with exactly keys {sorted(keys)}")
    return obj


def _sha(value, name):
    if not (isinstance(value, str) and _SHA256.fullmatch(value)):
        raise ValueError(f"Release record: {name} must be 64 lowercase hex characters")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Release record: {name} must be a non-empty string")
    return value


def _load_record(record):
    if isinstance(record, (str, Path)):
        record = json.loads(Path(record).read_text(encoding="utf-8"))
    return record


def _check_record_schema(record, *, strict):
    """Exact schema. strict=True also demands release_authorization AUTHORIZED."""
    _exact(record, RECORD_KEYS, "record")
    if record["schema_version"] != 1 or isinstance(record["schema_version"], bool):
        raise ValueError("Release record: unsupported schema_version")
    art = _exact(record["artifact"], ("sha256", "months", "first_period", "last_period"), "artifact")
    _sha(art["sha256"], "artifact.sha256")
    if isinstance(art["months"], bool) or not isinstance(art["months"], int) or art["months"] < 1:
        raise ValueError("Release record: artifact.months must be a positive integer")
    for key in ("first_period", "last_period"):
        if not (isinstance(art[key], str) and _PERIOD.fullmatch(art[key])):
            raise ValueError(f"Release record: artifact.{key} must be YYYY-MM")
    if record["fields_published"] != ["gold_index", "gold_grams_per_house"]:
        raise ValueError('Release record: fields_published must be exactly ["gold_index","gold_grams_per_house"]')
    meth = _exact(record["methodology"], ("adr", "status"), "methodology")
    if meth != {"adr": "ADR-004", "status": "ACCEPTED"}:
        raise ValueError("Release record: methodology must be ADR-004 / ACCEPTED")
    src = _exact(record["sources"], ("worldbank_workbook_sha256", "ecb_sha256", "cbs_csv_sha256"), "sources")
    for key, value in src.items():
        _sha(value, f"sources.{key}")
    cv = _exact(record["candidate_validation"], ("candidate_sha256", "review_run", "result"),
                "candidate_validation")
    _sha(cv["candidate_sha256"], "candidate_validation.candidate_sha256")
    _text(cv["review_run"], "candidate_validation.review_run")
    if cv["result"] != "PASS":
        raise ValueError("Release record: candidate_validation.result must be PASS")
    auth = _exact(record["release_authorization"], ("status", "authorized_by", "authorized_at", "reference"),
                  "release_authorization")
    if auth["status"] not in ("AUTHORIZED", "NOT_AUTHORIZED"):
        raise ValueError("Release record: release_authorization.status must be AUTHORIZED or NOT_AUTHORIZED")
    if strict:
        if auth["status"] != "AUTHORIZED":
            raise ValueError("Release record: release is NOT_AUTHORIZED")
        _text(auth["authorized_by"], "release_authorization.authorized_by")
        _text(auth["reference"], "release_authorization.reference")
        at = auth["authorized_at"]
        if not (isinstance(at, str) and _DATE.fullmatch(at)):
            raise ValueError("Release record: release_authorization.authorized_at must be an ISO date")
        try:
            datetime.fromisoformat(at)
        except ValueError:
            raise ValueError("Release record: release_authorization.authorized_at must be an ISO date") from None
    return record


def _check_rows(rows, gold_mode):
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


def _check_release(csv_path, json_path, record, *, authorize, committed=False):
    """Shared hash/content checks; authorize=False is the NON-authorizing preflight.

    committed=True is the CI check of the committed JSON against the committed record: it
    only changes the wording of the report (the status is reported, never granted here)."""
    record = _check_record_schema(_load_record(record), strict=authorize)
    art, cv, src = record["artifact"], record["candidate_validation"], record["sources"]
    if cv["candidate_sha256"] != art["sha256"]:
        raise ValueError("Release record: candidate_sha256 differs from artifact.sha256")
    raw_bytes = Path(json_path).read_bytes()
    artifact_sha = hashlib.sha256(raw_bytes).hexdigest()
    if artifact_sha != art["sha256"]:
        raise ValueError("Public JSON bytes differ from release record artifact sha256 (pinned sha256)")
    cbs_sha = hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()
    if cbs_sha != src["cbs_csv_sha256"]:
        raise ValueError("CBS csv sha256 differs from release record sources.cbs_csv_sha256")
    payload = json.loads(raw_bytes.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(
        ValueError(f"Non-finite JSON number: {token}")))
    if not isinstance(payload, dict) or set(payload) != {"data"}:
        raise ValueError("Unexpected public JSON schema")
    rows = payload["data"]
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise ValueError("Empty or invalid public data")
    if (len(rows) != art["months"] or rows[0].get("period") != art["first_period"]
            or rows[-1].get("period") != art["last_period"]):
        raise ValueError("Public JSON months/first/last period differ from release record artifact")
    _check_pinned_public_gold(rows, build(csv_path)["data"])
    _check_rows(rows, True)
    auth = record["release_authorization"]
    return {
        "months": len(rows),
        "publication_authorized": bool(authorize),
        "hash_verified": {"artifact_sha256": artifact_sha, "cbs_csv_sha256": cbs_sha},
        "content_validated": ["JSON-v1 schema and non-gold fields == build(csv)", "gold_eur_oz null",
                              "contiguous gold block from 2000-01, index 2000-01 == 100",
                              "grams * index / house_eur constant"],
        "attested_not_verified": {
            "SOURCE": {"worldbank_workbook_sha256": src["worldbank_workbook_sha256"],
                       "ecb_sha256": src["ecb_sha256"], "candidate_review_run": cv["review_run"]},
            "METHODOLOGY APPROVED": "ADR-004 / ACCEPTED (per record)",
            "PUBLICATION AUTHORIZED": (
                f"{auth['status']} by {auth['authorized_by']} at {auth['authorized_at']} ({auth['reference']})"
                if authorize else
                f"RELEASE STATUS PER RECORD: {auth['status']} (committed-data check, not an authorization; "
                f"reference: {auth['reference']})" if committed else
                "PUBLICATION NOT AUTHORIZED (preflight never authorizes)"),
        },
    }


def validate_gold_release_record_preflight(csv_path, json_path, gold_release_record):
    """Rehearsal: same hash/content checks, needs no env/approval flag, NEVER authorizes."""
    return _check_release(csv_path, json_path, gold_release_record, authorize=False)


DEFAULT_RELEASE_RECORD = "data/gold-release-record.json"


def validate_gold_release_committed(csv_path, json_path, gold_release_record, *, require_authorized=False,
                                    require_env=True):
    """CI check of the COMMITTED public JSON against the COMMITTED release record.

    Hash equality with the record AND with the code pin (APPROVED_PUBLIC_JSON_SHA256) plus all
    content checks; any gold value the record does not identify fails. The record status is
    reported, not required (a prepared release is NOT_AUTHORIZED). require_authorized=True is
    the release gate: env flags and an AUTHORIZED record are then mandatory."""
    from etl.gold_publication_candidate import APPROVED_PUBLIC_JSON_SHA256
    if require_authorized and require_env and not gold_enabled():
        raise ValueError("Release gate requires GOLD_PUBLICATION_ENABLED=true and "
                         "GOLD_PUBLICATION_APPROVAL=APPROVED")
    report = _check_release(csv_path, json_path, gold_release_record, authorize=require_authorized,
                            committed=True)
    if report["hash_verified"]["artifact_sha256"] != APPROVED_PUBLIC_JSON_SHA256:
        raise ValueError("Public JSON sha256 differs from the code pin APPROVED_PUBLIC_JSON_SHA256")
    return report


def public_json_has_gold(json_path):
    """True when any row of the public JSON carries a non-null gold field (raw or derived)."""
    payload = json.loads(Path(json_path).read_bytes().decode("utf-8"))
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return False
    return any(isinstance(r, dict) and any(r.get(k) is not None for k in GOLD_PUBLIC_FIELDS + ("gold_eur_oz",))
               for r in rows)


def validate_production_state(csv_path, json_path, gold_release_record=DEFAULT_RELEASE_RECORD):
    """Default production check (python -m etl.data_quality without gold flags).

    Without any gold value in the public JSON: unchanged (JSON == build(csv), gold null).
    With gold values: valid ONLY when the committed release record is AUTHORIZED (authorizer, ISO
    date, reference) AND the JSON sha256 equals the record AND the code pin
    APPROVED_PUBLIC_JSON_SHA256 AND all content checks pass. The authorization lives in the
    committed record, so no env flag is needed here. A NOT_AUTHORIZED record, a missing record,
    a changed byte or any gold the record does not identify fails."""
    if not public_json_has_gold(json_path):
        return validate(csv_path, json_path), None
    if not Path(gold_release_record).is_file():
        raise ValueError(f"Public JSON carries gold but release record {gold_release_record} is missing")
    report = validate_gold_release_committed(csv_path, json_path, gold_release_record,
                                             require_authorized=True, require_env=False)
    return report["months"], report


def validate_gold_release(csv_path, json_path, gold_release_record, *, gold_approved=False):
    """Authorized release validation: approval flag + env flags + AUTHORIZED record."""
    if gold_approved is not True or not gold_enabled():
        raise ValueError("Gold validation requires approval flag, GOLD_PUBLICATION_ENABLED=true and "
                         "GOLD_PUBLICATION_APPROVAL=APPROVED for a gold release record")
    return _check_release(csv_path, json_path, gold_release_record, authorize=True)


def format_gold_release_report(report):
    att = report["attested_not_verified"]
    hv = report["hash_verified"]
    return "\n".join([
        f"HASH VERIFIED (by code): artifact sha256 {hv['artifact_sha256']}, CBS csv sha256 {hv['cbs_csv_sha256']}",
        "CONTENT VALIDATED (by code): " + "; ".join(report["content_validated"]),
        "ATTESTED BY RECORD, NOT VERIFIED BY CODE:",
        f"  SOURCE: {json.dumps(att['SOURCE'], sort_keys=True)}",
        f"  METHODOLOGY APPROVED: {att['METHODOLOGY APPROVED']}",
        f"  PUBLICATION AUTHORIZED: {att['PUBLICATION AUTHORIZED']}",
    ])


def validate(csv_path, json_path, *, gold_candidate=None, gold_approved=False,
             gold_release_record=None):
    """Validate the public JSON against the source CSV.

    Default (gold_candidate None, gold_approved False): behaviour is unchanged,
    JSON must equal build(csv) and every gold field must be null.

    Opt-in gold candidate mode requires ALL of: gold_approved is True, the same
    env flags as static_export.gold_enabled(), and a gold candidate that passes
    static_export.validate_gold. The JSON must then equal
    build(csv, gold_candidate, approved) exactly; gold_eur_oz stays null and only
    gold_index / gold_grams_per_house may be filled.

    Opt-in release-record mode (gold_release_record: dict or path of a strict JSON
    approval record) is an ADDITIONAL release control for an artifact that was
    already content-validated in candidate mode and separately authorized; see
    validate_gold_release. Candidate and record are mutually exclusive. Any
    partial combination is rejected rather than silently falling back.
    """
    record_mode = gold_release_record is not None
    gold_mode = gold_candidate is not None or gold_approved is not False or record_mode
    if gold_mode and (gold_candidate is not None) == record_mode:
        raise ValueError("Gold validation requires exactly one of a gold candidate or a gold release record")
    if record_mode:
        return validate_gold_release(csv_path, json_path, gold_release_record,
                                     gold_approved=gold_approved)["months"]
    if gold_mode:
        if gold_approved is not True or not gold_enabled():
            raise ValueError("Gold validation requires approval flag, GOLD_PUBLICATION_ENABLED=true, "
                             "GOLD_PUBLICATION_APPROVAL=APPROVED and exactly one of a gold candidate "
                             "or a gold release record")
        expected = build(csv_path, gold_candidate=gold_candidate, gold_publication_approved=True)
    else:
        expected = build(csv_path)
    raw = Path(json_path).read_bytes().decode("utf-8")
    payload = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(
        ValueError(f"Non-finite JSON number: {token}")))
    if not isinstance(payload, dict) or set(payload) != {"data"}:
        raise ValueError("Unexpected public JSON schema")
    rows = payload["data"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty or invalid public data")
    if payload != expected:
        raise ValueError("Public JSON differs from validated source CSV or calculated indices")
    _check_rows(rows, gold_mode)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Verify committed CSV/JSON integrity and completeness")
    parser.add_argument("--input", default="data/cbs-housing.csv")
    parser.add_argument("--output", default="frontend/public/data/monthly.json")
    parser.add_argument("--gold-candidate", default=None)
    parser.add_argument("--approve-gold", action="store_true")
    parser.add_argument("--gold-release-record", default=None, metavar="PATH",
                        help="strict JSON approval record for a reviewed public gold JSON-v1 artifact "
                             "(alternative to --gold-candidate; needs --approve-gold and env flags)")
    parser.add_argument("--committed", action="store_true",
                        help="with --gold-release-record: CI check of the committed JSON against the committed "
                             "record and the code pin; reports the record status. With --approve-gold it is the "
                             "release gate (env flags + AUTHORIZED record required)")
    parser.add_argument("--preflight", action="store_true",
                        help="with --gold-release-record: rehearsal that never authorizes publication "
                             f"(prints PUBLICATION NOT AUTHORIZED, exit code {EXIT_PREFLIGHT_NOT_AUTHORIZED})")
    args = parser.parse_args()
    if args.committed:
        if (not args.gold_release_record or args.gold_candidate or args.preflight):
            parser.error("--committed requires --gold-release-record and excludes --gold-candidate/--preflight")
        report = validate_gold_release_committed(args.input, args.output, args.gold_release_record,
                                                 require_authorized=args.approve_gold)
        print(format_gold_release_report(report))
        print(f"Validated {report['months']} consecutive months, both CBS series, schema and committed release record")
        return
    if args.preflight:
        if not args.gold_release_record or args.gold_candidate or args.approve_gold:
            parser.error("--preflight requires --gold-release-record and excludes --gold-candidate/--approve-gold")
        report = validate_gold_release_record_preflight(args.input, args.output, args.gold_release_record)
        print(format_gold_release_report(report))
        print("PUBLICATION NOT AUTHORIZED")
        sys.exit(EXIT_PREFLIGHT_NOT_AUTHORIZED)
    if args.gold_release_record:
        if args.gold_candidate:
            raise ValueError("Gold validation requires exactly one of a gold candidate or a gold release record")
        report = validate_gold_release(args.input, args.output, args.gold_release_record,
                                       gold_approved=args.approve_gold)
        print(format_gold_release_report(report))
        print(f"Validated {report['months']} consecutive months, both CBS series, schema and release record")
        return
    candidate = None
    if args.gold_candidate:
        candidate = json.loads(Path(args.gold_candidate).read_text(encoding="utf-8"))
    elif not args.approve_gold:
        count, report = validate_production_state(args.input, args.output)
        if report:
            print(format_gold_release_report(report))
        print(f"Validated {count} consecutive months, both CBS series, schema and "
              + ("authorized gold release record" if report else "JSON/CSV parity"))
        return
    count = validate(args.input, args.output, gold_candidate=candidate,
                     gold_approved=args.approve_gold)
    print(f"Validated {count} consecutive months, both CBS series, schema and JSON/CSV parity")


if __name__ == "__main__":
    main()
