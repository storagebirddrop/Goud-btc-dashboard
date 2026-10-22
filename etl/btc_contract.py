"""btc-monthly/1: PRIVATE candidate contract for Bitcoin/satoshi housing values. NOTHING HERE PUBLISHES ANYTHING.

Two strictly separate states:
  * legacy/public: the exact current monthly.json (seven fields, no BTC extension), pinned by byte hash;
  * private candidate: the same rows plus `btc_per_house`, `sat_per_house` and `btc_meta` per month and a shared root block `btc`.

`validate_candidate` checks the candidate shape and the HOLD/null semantics, `legacy_projection_bytes` projects a candidate back to the
exact legacy payload, and `composite_release_gate` stays closed until an exact owner-approved artifact record exists (the registry
ARTIFACT_RECORDS is empty). A JSON field `publication_authorized` never grants authority: it must be false. The method itself
(CM_PRICEUSD_MONTHMEAN_C1_V1) lives in the research tooling; this module only validates what that tooling produced.
The shape is derived from the BTC-06C assignment text and the vocabulary of DATA_CONTRACT.md; the BTC-06A design drafts were not available
in the repository when this was written and must be reconciled by Project Control.
"""
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from fractions import Fraction

CONTRACT = "btc-monthly/1"
METHOD_ID = "CM_PRICEUSD_MONTHMEAN_C1_V1"
LEGACY_FIELDS = ["period", "gold_eur_oz", "house_eur", "hpi", "gold_grams_per_house", "gold_index", "hpi_index"]
BTC_FIELDS = ["btc_per_house", "sat_per_house", "btc_meta"]
LEGACY_PUBLIC_SHA256 = "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"  # approved GOLD-03 payload; never relaxed here
FIRST_VALUE_MONTH = "2014-02"  # earlier months are never numeric in this contract version
FIRST_SUPPORTED_MONTH = "2010-08"
HOLD_MONTHS = {"2011-06": "HOLD_2011_06"}  # absolute publication HOLD: always null, never connected
STATUSES = ("CANDIDATE", "HOLD", "MISSING")
QUALITIES = ("Q3", "Q2", "Q1_CANDIDATE")
MISSING_REASONS = ("NOT_APPLICABLE", "NOT_PUBLISHED", "SOURCE_UNAVAILABLE", "INCOMPLETE_PERIOD", "FAILED_VALIDATION", "LICENSE_BLOCKED", "UNVERIFIED_SOURCE")
ROOT_REQUIRED = ("contract", "status", "method_id", "parser_version", "exception_policy_version", "quality_version", "snapshot_id",
                 "derived_values_sha256", "source_windows", "cbs_input_sha256", "legacy_sha256", "first_value_month", "early_history_numeric",
                 "publication_authorized", "release_gate", "sources")
SATS_PER_BTC = 10 ** 8
ARTIFACT_RECORDS: tuple = ()  # exact owner-approved composite artifact records; EMPTY: nothing may be released


class BtcContractError(ValueError):
    """The candidate violates btc-monthly/1: fail closed."""


class ReleaseDenied(BtcContractError):
    """No exact owner-approved artifact record exists for these bytes."""


def quality_of(month: str):
    """Provisional research quality by month (Project Control PC-BTC04-4-F2): Q3 to 2014-01, Q2 to 2016-04, Q1 candidate from 2016-05."""
    if month < FIRST_SUPPORTED_MONTH:
        return None
    return "Q3" if month <= "2014-01" else "Q2" if month <= "2016-04" else "Q1_CANDIDATE"


def serialize(payload) -> bytes:
    """Same serialization as the existing static exporter, so a legacy projection can be compared byte for byte."""
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _num(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise BtcContractError(f"{label}: must be a finite positive JSON number, got {value!r}")
    return value


def legacy_projection(candidate: dict) -> dict:
    """The exact legacy payload a candidate projects to: the seven legacy fields per row, nothing else."""
    if not isinstance(candidate, dict) or not isinstance(candidate.get("data"), list):
        raise BtcContractError("candidate has no data list")
    return {"data": [{k: row[k] for k in LEGACY_FIELDS} for row in candidate["data"]]}


def legacy_projection_bytes(candidate: dict) -> bytes:
    return serialize(legacy_projection(candidate))


def validate_legacy_projection(candidate: dict, legacy_bytes: bytes, *, pinned=LEGACY_PUBLIC_SHA256) -> str:
    """The projection must equal the approved legacy payload byte for byte AND hash to the pinned value. Returns the hash."""
    if pinned is not None and sha256(legacy_bytes) != pinned:
        raise BtcContractError("the supplied legacy payload is not the pinned approved gold/CBS payload")
    got = legacy_projection_bytes(candidate)
    if got != legacy_bytes:
        raise BtcContractError("legacy projection of the candidate differs from the approved payload")
    return sha256(got)


def validate_root(root: dict) -> None:
    if not isinstance(root, dict):
        raise BtcContractError("root block `btc` missing")
    missing = [k for k in ROOT_REQUIRED if k not in root]
    if missing:
        raise BtcContractError(f"root block `btc` lacks {missing}")
    expected = {"contract": CONTRACT, "status": "PRIVATE_CANDIDATE", "method_id": METHOD_ID, "first_value_month": FIRST_VALUE_MONTH,
                "early_history_numeric": False, "release_gate": "CLOSED"}
    for key, value in expected.items():
        if root[key] != value:
            raise BtcContractError(f"btc.{key}: expected {value!r}, got {root[key]!r}")
    if root["publication_authorized"] is not False:  # a JSON flag can never grant publication authority
        raise BtcContractError("btc.publication_authorized must be false: a JSON field never authorizes publication")
    for key in ("derived_values_sha256", "cbs_input_sha256", "legacy_sha256"):
        v = root[key]
        if not (isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)):
            raise BtcContractError(f"btc.{key} is not a SHA-256")
    if root["legacy_sha256"] != LEGACY_PUBLIC_SHA256:
        raise BtcContractError("btc.legacy_sha256 is not the pinned approved payload hash")
    if not isinstance(root["source_windows"], dict) or not root["source_windows"] or not isinstance(root["sources"], list) or not root["sources"]:
        raise BtcContractError("btc.source_windows and btc.sources must be non-empty")


def validate_month(row: dict) -> str:
    """Validate one candidate row; returns its status."""
    period = row.get("period")
    if list(row) != LEGACY_FIELDS + BTC_FIELDS:
        raise BtcContractError(f"{period}: fields must be exactly {LEGACY_FIELDS + BTC_FIELDS} in this order")
    meta = row["btc_meta"]
    if not isinstance(meta, dict) or set(meta) != {"status", "quality", "missing_reason", "exception"}:
        raise BtcContractError(f"{period}: btc_meta must have exactly status, quality, missing_reason, exception")
    status, quality, reason, exc = meta["status"], meta["quality"], meta["missing_reason"], meta["exception"]
    if status not in STATUSES or (quality is not None and quality not in QUALITIES) or (reason is not None and reason not in MISSING_REASONS):
        raise BtcContractError(f"{period}: unknown status/quality/missing_reason")
    if period in HOLD_MONTHS:  # absolute HOLD: null, flagged, never a candidate
        if (status, exc) != ("HOLD", HOLD_MONTHS[period]) or row["btc_per_house"] is not None or row["sat_per_house"] is not None:
            raise BtcContractError(f"{period}: must be HOLD with null values")
    elif exc is not None or status == "HOLD":
        raise BtcContractError(f"{period}: exception/HOLD only allowed for {sorted(HOLD_MONTHS)}")
    if status == "CANDIDATE":
        if period < FIRST_VALUE_MONTH:
            raise BtcContractError(f"{period}: numeric BTC values before {FIRST_VALUE_MONTH} are not part of this contract")
        if quality != quality_of(period) or quality == "Q3" or reason is not None:
            raise BtcContractError(f"{period}: quality must be {quality_of(period)} and missing_reason null for a candidate")
        btc, sat = _num(row["btc_per_house"], f"{period} btc_per_house"), _num(row["sat_per_house"], f"{period} sat_per_house")
        if abs(Decimal(repr(float(sat))) - Decimal(repr(float(btc))) * SATS_PER_BTC) > abs(Decimal(repr(float(sat)))) * Decimal("1e-13"):
            raise BtcContractError(f"{period}: sat_per_house is not btc_per_house x 1e8")
    else:
        if row["btc_per_house"] is not None or row["sat_per_house"] is not None:
            raise BtcContractError(f"{period}: {status} month must carry null values")
        if status == "MISSING" and reason is None:
            raise BtcContractError(f"{period}: MISSING needs a missing_reason")
        if status == "HOLD" and reason != "NOT_PUBLISHED":
            raise BtcContractError(f"{period}: HOLD month uses missing_reason NOT_PUBLISHED")
        if quality != quality_of(period):
            raise BtcContractError(f"{period}: quality must be {quality_of(period)}")
    return status


def validate_candidate(candidate: dict, legacy_bytes: bytes, exact: dict = None) -> dict:
    """Full private-candidate validation. Raises BtcContractError; returns a value-free summary."""
    if not isinstance(candidate, dict) or set(candidate) != {"data", "btc"} or not isinstance(candidate["data"], list) or not candidate["data"]:
        raise BtcContractError("candidate must be {data:[...], btc:{...}}")
    validate_root(candidate["btc"])
    periods = [r.get("period") for r in candidate["data"]]
    if periods != sorted(set(periods)):
        raise BtcContractError("periods must be unique and chronological")
    legacy_hash = validate_legacy_projection(candidate, legacy_bytes)
    counts = {}
    for row in candidate["data"]:
        status = validate_month(row)
        counts[status] = counts.get(status, 0) + 1
    if candidate["btc"]["legacy_sha256"] != legacy_hash:
        raise BtcContractError("btc.legacy_sha256 differs from the projection hash")
    if exact is not None:
        check_exact(candidate, exact)
    cand = [r["period"] for r in candidate["data"] if r["btc_meta"]["status"] == "CANDIDATE"]
    return {"months": len(periods), "status_counts": counts, "candidate_first": cand[0] if cand else None, "candidate_last": cand[-1] if cand else None,
            "candidate_months": len(cand), "legacy_sha256": legacy_hash, "candidate_sha256": sha256(serialize(candidate))}


def check_exact(candidate: dict, exact: dict) -> None:
    """JSON numbers must be the exact private Decimal values after one float conversion; sats are exactly BTC x 1e8 in Decimal."""
    for row in candidate["data"]:
        p = row["period"]
        if row["btc_meta"]["status"] != "CANDIDATE":
            if p in exact:
                raise BtcContractError(f"{p}: exact values exist for a month that is not a candidate")
            continue
        try:
            btc, sat = Decimal(exact[p]["btc_per_house"]), Decimal(exact[p]["sat_per_house"])
        except (KeyError, InvalidOperation, TypeError):
            raise BtcContractError(f"{p}: exact values missing or malformed") from None
        if Fraction(sat) != Fraction(btc) * SATS_PER_BTC:  # exact rational arithmetic: independent of the ambient Decimal context
            raise BtcContractError(f"{p}: exact sat_per_house is not exact btc_per_house x 1e8")
        if row["btc_per_house"] != float(btc) or row["sat_per_house"] != float(sat):
            raise BtcContractError(f"{p}: JSON number differs from the exact value beyond one float conversion")
    extra = set(exact) - {r["period"] for r in candidate["data"] if r["btc_meta"]["status"] == "CANDIDATE"}
    if extra:
        raise BtcContractError(f"exact values for unknown months: {sorted(extra)[:3]}")


def composite_release_gate(composite_bytes: bytes, records=None) -> dict:
    """Closed by default. A composite BTC publication needs an exact owner-approved artifact record for THESE bytes."""
    records = ARTIFACT_RECORDS if records is None else tuple(records)
    candidate = json.loads(composite_bytes.decode("utf-8"))
    if serialize(candidate) != composite_bytes:
        raise BtcContractError("composite bytes are not in canonical serialization")
    validate_root(candidate.get("btc"))
    digest = sha256(composite_bytes)
    legacy_digest = sha256(legacy_projection_bytes(candidate))
    for record in records:
        if (isinstance(record, dict) and record.get("owner_approval") == "APPROVED" and record.get("composite_sha256") == digest
                and record.get("legacy_projection_sha256") == legacy_digest == LEGACY_PUBLIC_SHA256 and record.get("approved_by") and record.get("approved_on")):
            return record
    raise ReleaseDenied("no exact owner-approved artifact record for this composite payload (registry is empty by default)")
