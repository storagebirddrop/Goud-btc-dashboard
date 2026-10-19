"""DATA-01C review-only append-first monthly observation validator.

No ETL, network, filesystem, public schema migration or publication path.
All numeric values are canonical positive base-10 decimal strings (no floats).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation

CONTRACT = "DATA-01C-monthly-review-v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
MONTH = re.compile(r"^([0-9]{4})-(0[1-9]|1[0-2])$")
METRIC = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")
FIELDS = {"period", "metric", "value", "source_identity_sha256",
          "methodology_version", "completeness_status", "observation_status"}
CLASSIFICATIONS = ("UNCHANGED", "APPEND_CANDIDATE", "PENDING", "LATE_ARRIVAL",
                   "REVISION_REVIEW", "BLOCKED")
ALLOWED_COMPLETENESS = {"COMPLETE", "INCOMPLETE", "SOURCE_UNAVAILABLE"}
ALLOWED_STATUS = {"FINAL", "PROVISIONAL"}
GOLD_METRICS = {"gold_index", "gold_grams_per_house"}
CBS_METRICS = {"house_eur", "hpi", "hpi_index"}
BTC_RESEARCH = {"btc_eur_research"}
METRICS = GOLD_METRICS | CBS_METRICS | BTC_RESEARCH


class ObservationError(ValueError):
    pass


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def month_number(period):
    if not isinstance(period, str) or not MONTH.fullmatch(period):
        raise ObservationError("INVALID_PERIOD")
    y, m = map(int, period.split("-"))
    if y < 1900:
        raise ObservationError("INVALID_PERIOD")
    return y * 12 + m - 1


def decimal_value(value):
    if not isinstance(value, str) or not DECIMAL.fullmatch(value):
        raise ObservationError("INVALID_DECIMAL_REPRESENTATION")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ObservationError("INVALID_DECIMAL_REPRESENTATION") from exc
    if not number.is_finite() or number <= 0 or format(number, "f") != value:
        raise ObservationError("INVALID_DECIMAL_REPRESENTATION")
    return value


def validate_observation(row):
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ObservationError("INVALID_OBSERVATION_FIELDS")
    month_number(row["period"])
    metric = row["metric"]
    if not isinstance(metric, str) or not METRIC.fullmatch(metric) or metric not in METRICS:
        raise ObservationError("UNAUTHORIZED_METRIC")
    if metric in BTC_RESEARCH and row["methodology_version"] != "RESEARCH_ONLY":
        raise ObservationError("BTC_NOT_APPROVED")
    for field in ("source_identity_sha256",):
        if not isinstance(row[field], str) or not HEX.fullmatch(row[field]):
            raise ObservationError("INVALID_SOURCE_HASH_REFERENCE")
    if not isinstance(row["methodology_version"], str) or not VERSION.fullmatch(row["methodology_version"]):
        raise ObservationError("INVALID_METHODOLOGY_VERSION")
    if row["completeness_status"] not in ALLOWED_COMPLETENESS:
        raise ObservationError("INVALID_COMPLETENESS_STATUS")
    if row["observation_status"] not in ALLOWED_STATUS:
        raise ObservationError("INVALID_OBSERVATION_STATUS")
    if row["value"] is None:
        if row["completeness_status"] == "COMPLETE":
            raise ObservationError("COMPLETE_VALUE_MISSING")
    else:
        decimal_value(row["value"])
    return row


def _key(row):
    return row["period"], row["metric"]


def _index(rows, label):
    if not isinstance(rows, list):
        raise ObservationError("INVALID_DATASET")
    result = {}
    for row in rows:
        validate_observation(row)
        key = _key(row)
        if key in result:
            raise ObservationError("DUPLICATE_" + label)
        result[key] = row
    return result


def _manifest_status(hashref, manifest_evidence):
    if manifest_evidence is None:
        return "MANIFEST_NOT_PROVIDED"
    if not isinstance(manifest_evidence, dict):
        return "MANIFEST_NOT_VERIFIED"
    if hashref not in manifest_evidence:
        return "MANIFEST_NOT_PROVIDED"
    item = manifest_evidence[hashref]
    if not isinstance(item, dict) or item.get("verified") is not True:
        return "MANIFEST_NOT_VERIFIED"
    if item.get("source_identity_sha256") != hashref:
        return "MANIFEST_NOT_VERIFIED"
    return None


def validate(approved, candidate, *, approved_through, as_of_period,
             approved_metrics, methodology_by_metric, manifest_evidence=None,
             permitted_future=False):
    """Return deterministic content-addressed review; never mutate either input.

    manifest_evidence is an explicitly supplied independent verification registry,
    not an assertion inferred from a syntactically valid SHA.
    """
    old = _index(approved, "APPROVED")
    new = _index(candidate, "CANDIDATE")
    boundary = month_number(approved_through)
    today = month_number(as_of_period)
    if not isinstance(approved_metrics, (list, tuple)) or not approved_metrics:
        raise ObservationError("INVALID_METRIC_POLICY")
    if len(approved_metrics) != len(set(approved_metrics)) or not set(approved_metrics) <= METRICS:
        raise ObservationError("INVALID_METRIC_POLICY")
    if not isinstance(methodology_by_metric, dict) or set(methodology_by_metric) != set(approved_metrics):
        raise ObservationError("INVALID_METHODOLOGY_POLICY")
    for metric, method in methodology_by_metric.items():
        if not isinstance(method, str) or not VERSION.fullmatch(method):
            raise ObservationError("INVALID_METHODOLOGY_POLICY")
        if metric in BTC_RESEARCH and method != "RESEARCH_ONLY":
            raise ObservationError("BTC_NOT_APPROVED")
    if permitted_future is not False:
        raise ObservationError("FUTURE_POLICY_NOT_APPROVED")
    # The last approved month is an explicit review boundary, not inferred from candidate dates.
    if any(month_number(p) > boundary for p, m in old):
        raise ObservationError("APPROVED_BEYOND_BOUNDARY")
    all_keys = sorted(set(old) | set(new))
    items = []
    for period, metric in all_keys:
        before, after = old.get((period, metric)), new.get((period, metric))
        reasons = []
        if metric not in approved_metrics:
            reasons.append("UNAUTHORIZED_METRIC")
        if before is not None and after is None:
            reasons.append("MISSING_APPROVED_OBSERVATION")
        if after is not None:
            if after["methodology_version"] != methodology_by_metric.get(metric):
                reasons.append("UNAPPROVED_METHODOLOGY")
            if month_number(period) > today:
                reasons.append("FUTURE_PERIOD")
            manifest_problem = _manifest_status(after["source_identity_sha256"], manifest_evidence)
            if manifest_problem:
                reasons.append(manifest_problem)
        if reasons:
            kind = "BLOCKED"
        elif after["completeness_status"] != "COMPLETE" or after["observation_status"] != "FINAL":
            kind = "PENDING" if before is None else "REVISION_REVIEW"
            if before is not None:
                reasons.append("APPROVED_OBSERVATION_NOT_FINAL")
        elif before is not None:
            if (before["value"] == after["value"] and
                    before["source_identity_sha256"] == after["source_identity_sha256"] and
                    before["methodology_version"] == after["methodology_version"] and
                    before["completeness_status"] == after["completeness_status"] and
                    before["observation_status"] == after["observation_status"]):
                kind = "UNCHANGED"
            else:
                kind = "REVISION_REVIEW"
                for field in ("value", "source_identity_sha256", "methodology_version",
                              "completeness_status", "observation_status"):
                    if before[field] != after[field]:
                        reasons.append("CHANGED_" + field.upper())
        elif month_number(period) <= boundary:
            kind = "LATE_ARRIVAL"
            reasons.append("HISTORICAL_MISSING_OBSERVATION")
        else:
            kind = "APPEND_CANDIDATE"
        items.append({"period": period, "metric": metric, "classification": kind,
                      "reason_codes": sorted(set(reasons))})
    # For each configured metric, detect holes in its approved historical coverage,
    # while allowing explicit missing rows with a SOURCE_UNAVAILABLE status.
    for metric in approved_metrics:
        existing = sorted(month_number(p) for p, m in old if m == metric)
        if existing:
            for number in range(existing[0], min(existing[-1], boundary) + 1):
                if number not in existing:
                    y, mo = divmod(number, 12)
                    items.append({"period": f"{y:04d}-{mo+1:02d}", "metric": metric,
                                  "classification": "BLOCKED",
                                  "reason_codes": ["UNEXPECTED_HISTORICAL_GAP"]})
        proposed = sorted(month_number(p) for p, m in new if m == metric and month_number(p) > boundary)
        if proposed:
            for number in range(boundary + 1, max(proposed) + 1):
                if number not in proposed:
                    y, mo = divmod(number, 12)
                    items.append({"period": f"{y:04d}-{mo+1:02d}", "metric": metric,
                                  "classification": "BLOCKED",
                                  "reason_codes": ["UNEXPECTED_APPEND_GAP"]})
    items.sort(key=lambda x: (x["period"], x["metric"], x["classification"]))
    counts = {name: sum(item["classification"] == name for item in items)
              for name in CLASSIFICATIONS}
    status = ("BLOCKED" if counts["BLOCKED"] else
              "REVIEW_REQUIRED" if counts["REVISION_REVIEW"] or counts["LATE_ARRIVAL"] else
              "PENDING" if counts["PENDING"] else "APPEND_REVIEW")
    return {"contract_version": CONTRACT, "approved_sha256": digest(approved),
            "candidate_sha256": digest(candidate), "approved_through": approved_through,
            "as_of_period": as_of_period, "validation_status": status,
            "counts": counts, "classifications": items,
            "publication_authorized": False, "manifest_evidence_mode":
            "EXPLICIT_VERIFIED_REGISTRY" if manifest_evidence is not None else "NOT_PROVIDED"}
