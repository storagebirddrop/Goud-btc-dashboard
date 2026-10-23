"""btc-monthly/1: contract validator for the Bitcoin/satoshi housing extension. NOTHING HERE PUBLISHES ANYTHING.

Reconciled with the accepted BTC-06 documents (data contract draft, production methodology draft, Project Control decisions).

Two strictly separate states of the SAME public vocabulary:
  * legacy/public: the exact current monthly.json (seven fields, no BTC extension), pinned by byte hash;
  * extended payload: legacy fields + `btc_per_house`, `sat_per_house`, `btc_meta` per month + root block `btc`.
    - PREVIEW (`release.publication_authorized=false`): private, every BTC value is null and withheld; the candidate values live in a private
      sidecar and carry PRIVATE candidate states that never appear in the public enum;
    - ACTIVE (`publication_authorized=true`): only valid together with an exact owner-approved artifact record (`composite_release_gate`).
Public `btc_meta.status` is exactly PUBLISHED | WITHHELD | MISSING. A JSON flag never grants authority. June 2011 is always
WITHHELD / RESEARCH_ONLY_HOLD with two nulls. The registry ARTIFACT_RECORDS is EMPTY: the release gate is closed by default.
"""
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation

CONTRACT = "btc-monthly/1"
METHOD_ID = "CM_PRICEUSD_MONTHMEAN_C1_V1"
LEGACY_FIELDS = ["period", "gold_eur_oz", "house_eur", "hpi", "gold_grams_per_house", "gold_index", "hpi_index"]
BTC_FIELDS = ["btc_per_house", "sat_per_house", "btc_meta"]
META_KEYS = ["quality", "status", "missing_reason", "flags"]
LEGACY_PUBLIC_SHA256 = "1afb0bf924cb284a7f818fbe99084fd042f594c6e46b6498c9c399373f91d8cd"  # approved GOLD-03 payload; never relaxed here
SUPPORTED_FROM = "2010-08"
DEFAULT_FROM = "2014-02"  # STANDARD_2014_02: earlier numeric history needs its own authorization
HOLD_MONTHS = {"2011-06": "RESEARCH_ONLY_HOLD"}
SATS_PER_BTC = 10 ** 8
MAX_SAFE_SAT = 2 ** 53
REPRESENTATION_LOSS_SAT = Decimal("0.25")  # per field, in satoshi equivalents
CONSISTENCY_SAT = Decimal("0.5")  # public BTC x 1e8 against public SAT
STATUSES = ("PUBLISHED", "WITHHELD", "MISSING")  # the future PUBLIC enum; private candidate states live elsewhere
REASON_STATUS = {"RESEARCH_ONLY_HOLD": "WITHHELD", "BEFORE_SUPPORTED_MONTH": "MISSING", "NOT_AUTHORIZED_PERIOD": "WITHHELD",
                 "PUBLICATION_NOT_AUTHORIZED": "WITHHELD", "RIGHTS_NOT_CLEARED": "WITHHELD", "INCOMPLETE_PERIOD": "MISSING",
                 "SOURCE_NOT_PUBLISHED": "MISSING", "SOURCE_UNAVAILABLE": "MISSING", "FAILED_VALIDATION": "MISSING"}
REASON_PRIORITY = ("RESEARCH_ONLY_HOLD", "BEFORE_SUPPORTED_MONTH", "NOT_AUTHORIZED_PERIOD", "RIGHTS_NOT_CLEARED", "PUBLICATION_NOT_AUTHORIZED",
                   "INCOMPLETE_PERIOD", "SOURCE_NOT_PUBLISHED", "SOURCE_UNAVAILABLE", "FAILED_VALIDATION")
QUALITIES = ("Q3", "Q2", "Q1_CANDIDATE")
# Registered review notes (evidence in docs/research/BTC_02_HISTORY.md: 2015-05 first thin Coinbase EUR month, 2015-08 largest Kraken EUR
# deviation, 2017-12 largest deviation of several comparators; early months: limited constituent/reconstruction provenance, PC-BTC04-4-F3/F7).
FLAG_REVIEW_MONTH = {"REVIEW_2015_05": "2015-05", "REVIEW_2015_08": "2015-08", "REVIEW_2017_12": "2017-12"}
FLAG_EARLY = "EARLY_HISTORY_LIMITED_PROVENANCE"
FLAGS = (FLAG_EARLY, *FLAG_REVIEW_MONTH)
PRIVATE_STATES = ("CANDIDATE_VALUE", "NO_CANDIDATE_VALUE")  # private sidecar vocabulary: NEVER a public btc_meta.status
ROOT_KEYS = ["contract_version", "method_id", "parser_version", "quality_version", "exception_policy_version", "units", "coverage", "release",
             "provenance", "sources", "rights"]
PROVENANCE_KEYS = ["snapshot_format", "snapshot_id", "snapshot_manifest_sha256", "calculation_git_commit", "cbs_input_sha256", "cm_daily_sha256",
                   "ecb_daily_sha256", "source_windows", "derived_values_sha256", "derived_cutoff", "cm_raw_retention", "ecb_raw_retention",
                   "vintage_reference_utc", "time_basis"]
SOURCE_IDS = ["coinmetrics_community_priceusd", "ecb_exr_d_usd", "cbs_85773NED_csv"]
UNITS = {"btc_per_house": "BTC/home", "sat_per_house": "satoshi/home"}
RECORD_STATUS = "AUTHORIZED_EXACT_CANDIDATE"
RECORD_SCHEMA = "btc-release-record/2"  # BTC-08B: the record binds the whole release identity, not only the composite bytes
ROLLBACK_STATE = "LEGACY_GOLD_CBS_NO_BTC"  # the previously authorized public state a withdrawal returns to (the pinned legacy payload)
PENDING = "PENDING"  # template placeholder for fields the OWNER fills; a record carrying it never opens the gate
RECORD_KEYS = frozenset([
    "schema", "record_id", "owner_approval", "status", "release_id", "decision_ref", "approved_by", "approved_on", "composite_sha256",
    "public_payload_sha256", "btc_selection_sha256", "legacy_projection_sha256", "snapshot_manifest_sha256", "snapshot_id", "calculation_git_commit",
    "provenance_sha256", "cbs_input_sha256", "candidate_preview_sha256", "private_sidecar_sha256", "method_id", "quality_version",
    "exception_policy_version", "authorized_fields", "authorized_months", "authorized_qualities", "quality_by_month_sha256", "exceptions",
    "early_history_authorized", "review_refs", "rollback_ref"])
ARTIFACT_RECORDS: tuple = ()  # exact owner-approved composite artifact records; EMPTY: nothing may be released


class BtcContractError(ValueError):
    """The payload violates btc-monthly/1: fail closed."""


class ReleaseDenied(BtcContractError):
    """No exact owner-approved artifact record exists for these bytes."""


def quality_of(month: str):
    """Evidence class by month (PC-BTC04-4-F2): Q3 to 2014-01, Q2 to 2016-04, Q1 candidate from 2016-05; null before the first supported month."""
    if month < SUPPORTED_FROM:
        return None
    return "Q3" if month <= "2014-01" else "Q2" if month <= "2016-04" else "Q1_CANDIDATE"


def flags_for(month: str) -> list:
    out = [FLAG_EARLY] if SUPPORTED_FROM <= month < DEFAULT_FROM else []
    out += [f for f, m in FLAG_REVIEW_MONTH.items() if m == month]
    return sorted(out)


def serialize(payload) -> bytes:
    """Same serialization as the existing static exporter, so a legacy projection can be compared byte for byte."""
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _is_sha(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _num(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise BtcContractError(f"{label}: must be a finite positive JSON number, got {value!r}")
    return value


# ------------------------------------------------------------------ legacy projection
def legacy_projection(payload: dict) -> dict:
    """The exact legacy payload an extended payload projects to: the seven legacy fields per row, no root `btc`."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise BtcContractError("payload has no data list")
    try:
        return {"data": [{k: row[k] for k in LEGACY_FIELDS} for row in payload["data"]]}
    except (KeyError, TypeError):
        raise BtcContractError("a row lacks the legacy fields") from None


def legacy_projection_bytes(payload: dict) -> bytes:
    return serialize(legacy_projection(payload))


def validate_legacy_projection(payload: dict, legacy_bytes: bytes, *, pinned=LEGACY_PUBLIC_SHA256) -> str:
    """The projection must equal the approved legacy payload byte for byte AND hash to the pinned value. Returns the hash."""
    if pinned is not None and sha256(legacy_bytes) != pinned:
        raise BtcContractError("the supplied legacy payload is not the pinned approved gold/CBS payload")
    got = legacy_projection_bytes(payload)
    if got != legacy_bytes:
        raise BtcContractError("legacy projection of the payload differs from the approved payload")
    return sha256(got)


# ------------------------------------------------------------------ root block
def validate_root(root: dict) -> str:
    """Validate the shared `btc` block. Returns 'PREVIEW' or 'ACTIVE' (the claim in the payload; authority comes only from the record)."""
    if not isinstance(root, dict) or list(root) != ROOT_KEYS:
        raise BtcContractError(f"root block `btc` must have exactly the keys {ROOT_KEYS} in this order")
    for key, want in (("contract_version", CONTRACT), ("method_id", METHOD_ID)):
        if root[key] != want:
            raise BtcContractError(f"btc.{key}: expected {want!r}, got {root[key]!r}")
    for key in ("parser_version", "quality_version", "exception_policy_version"):
        if not isinstance(root[key], str) or not root[key]:
            raise BtcContractError(f"btc.{key} missing")
    if root["units"] != UNITS:
        raise BtcContractError("btc.units must be exactly the documented units")
    cov, rel, prov, rights = root["coverage"], root["release"], root["provenance"], root["rights"]
    if not isinstance(cov, dict) or list(cov) != ["supported_from", "default_from", "authorized_from", "authorized_through", "early_history_authorized"]:
        raise BtcContractError("btc.coverage has the wrong keys")
    if (cov["supported_from"], cov["default_from"]) != (SUPPORTED_FROM, DEFAULT_FROM) or not isinstance(cov["early_history_authorized"], bool):
        raise BtcContractError("btc.coverage supported_from/default_from/early_history_authorized invalid")
    if not isinstance(rel, dict) or list(rel) != ["id", "decision_ref", "publication_authorized"] or not isinstance(rel["publication_authorized"], bool):
        raise BtcContractError("btc.release has the wrong keys")
    if not isinstance(prov, dict) or list(prov) != PROVENANCE_KEYS:
        raise BtcContractError(f"btc.provenance must have exactly {PROVENANCE_KEYS}")
    for key in ("snapshot_manifest_sha256", "cbs_input_sha256", "cm_daily_sha256", "ecb_daily_sha256", "derived_values_sha256"):
        if not _is_sha(prov[key]):
            raise BtcContractError(f"btc.provenance.{key} is not a SHA-256 (placeholders are refused)")
    commit = prov["calculation_git_commit"]
    if not (isinstance(commit, str) and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)):
        raise BtcContractError("btc.provenance.calculation_git_commit must be a 40-hex commit")
    if prov["snapshot_format"] != "btc04e-snapshot/2" or not str(prov["snapshot_id"]).startswith("btc04e-"):
        raise BtcContractError("btc.provenance snapshot format/id invalid")
    if prov["cm_raw_retention"] != "RETAINED" or prov["ecb_raw_retention"] != "NOT_RETAINED":
        raise BtcContractError("btc.provenance raw retention must state the real situation (CM RETAINED, ECB NOT_RETAINED)")
    if prov["time_basis"] != "CM_ACQUISITION_REFERENCE" or not isinstance(prov["vintage_reference_utc"], str) or not isinstance(prov["derived_cutoff"], str):
        raise BtcContractError("btc.provenance time basis/reference/cutoff invalid")
    wins = prov["source_windows"]
    if not isinstance(wins, dict) or set(wins) != {"cm_priceusd_daily", "ecb_usd_per_eur_daily"} or not all(
            isinstance(w, dict) and set(w) == {"first", "last", "n", "sha256"} and _is_sha(w["sha256"]) for w in wins.values()):
        raise BtcContractError("btc.provenance.source_windows invalid")
    sources = root["sources"]
    if not isinstance(sources, list) or [s.get("id") for s in sources if isinstance(s, dict)] != SOURCE_IDS or not all(
            list(s) == ["id", "metric", "url", "license_url", "attribution"] and all(isinstance(v, str) and v for v in s.values()) for s in sources):
        raise BtcContractError("btc.sources must list exactly the three sources with id, metric, url, license_url, attribution")
    if not isinstance(rights, dict) or list(rights) != ["assessment", "review_ref", "scope", "conflicting_contract_check"] \
            or rights["assessment"] != "CONDITIONAL" or rights["scope"] != "NON_COMMERCIAL" \
            or rights["conflicting_contract_check"] not in ("UNVERIFIED", "VERIFIED"):
        raise BtcContractError("btc.rights invalid")
    active = rel["publication_authorized"]
    if not active:
        if (rel["id"], rel["decision_ref"], cov["authorized_from"], cov["authorized_through"], cov["early_history_authorized"], rights["review_ref"]) != (
                None, None, None, None, False, None) or rights["conflicting_contract_check"] != "UNVERIFIED":
            raise BtcContractError("a preview (publication_authorized=false) carries no release id, decision, authorized range or rights review")
        return "PREVIEW"
    for label, v in (("release.id", rel["id"]), ("release.decision_ref", rel["decision_ref"]), ("coverage.authorized_from", cov["authorized_from"]),
                     ("coverage.authorized_through", cov["authorized_through"]), ("rights.review_ref", rights["review_ref"])):
        if not isinstance(v, str) or not v:
            raise BtcContractError(f"an active payload needs {label}")
    if rights["conflicting_contract_check"] != "VERIFIED":
        raise BtcContractError("an active payload needs a completed rights contract check")
    return "ACTIVE"


# ------------------------------------------------------------------ months
def validate_month(row: dict, root: dict, mode: str) -> str:
    """Validate one row against the public vocabulary. Returns its public status."""
    period = row.get("period")
    if list(row) != LEGACY_FIELDS + BTC_FIELDS:
        raise BtcContractError(f"{period}: fields must be exactly {LEGACY_FIELDS + BTC_FIELDS} in this order")
    meta = row["btc_meta"]
    if not isinstance(meta, dict) or list(meta) != META_KEYS:
        raise BtcContractError(f"{period}: btc_meta must have exactly {META_KEYS} in this order")
    quality, status, reason, flags = meta["quality"], meta["status"], meta["missing_reason"], meta["flags"]
    if status not in STATUSES:
        raise BtcContractError(f"{period}: status must be one of {STATUSES}, got {status!r}")
    if quality != quality_of(period):
        raise BtcContractError(f"{period}: quality must be {quality_of(period)!r}")
    if not isinstance(flags, list) or flags != sorted(set(flags)) or any(f not in FLAGS for f in flags):
        raise BtcContractError(f"{period}: flags must be a sorted unique list of registered notes {FLAGS}")
    if flags != flags_for(period):
        raise BtcContractError(f"{period}: flags must be exactly {flags_for(period)}")
    btc, sat = row["btc_per_house"], row["sat_per_house"]
    if status == "PUBLISHED":
        if mode != "ACTIVE":
            raise BtcContractError(f"{period}: PUBLISHED is not allowed in a preview")
        if reason is not None:
            raise BtcContractError(f"{period}: PUBLISHED carries no missing_reason")
        early = root["coverage"]["early_history_authorized"]
        if period in HOLD_MONTHS or quality is None or (quality == "Q3" and not early) or (period < DEFAULT_FROM and not early):
            raise BtcContractError(f"{period}: not eligible for publication")
        if not (root["coverage"]["authorized_from"] <= period <= root["coverage"]["authorized_through"]):
            raise BtcContractError(f"{period}: outside the authorized range")
        _num(btc, f"{period} btc_per_house")
        _num(sat, f"{period} sat_per_house")
        if sat >= MAX_SAFE_SAT:
            raise BtcContractError(f"{period}: sat_per_house exceeds the safe integer range")
        if abs(Decimal(repr(float(btc))) * SATS_PER_BTC - Decimal(repr(float(sat)))) >= CONSISTENCY_SAT:
            raise BtcContractError(f"{period}: public BTC and SAT differ by 0.5 satoshi or more")
    else:
        if btc is not None or sat is not None:
            raise BtcContractError(f"{period}: {status} month must carry two null values")
        if reason not in REASON_STATUS or REASON_STATUS[reason] != status:
            raise BtcContractError(f"{period}: missing_reason {reason!r} does not belong to status {status}")
    expected = None  # deterministic main reason by priority for the cases the calendar itself decides
    if period in HOLD_MONTHS:
        expected = HOLD_MONTHS[period]
    elif period < SUPPORTED_FROM:
        expected = "BEFORE_SUPPORTED_MONTH"
    if expected is not None and (status, reason) != (REASON_STATUS[expected], expected):
        raise BtcContractError(f"{period}: must be {REASON_STATUS[expected]} / {expected}")
    if expected is None and reason in ("RESEARCH_ONLY_HOLD", "BEFORE_SUPPORTED_MONTH"):
        raise BtcContractError(f"{period}: {reason} is reserved for its calendar months")
    if status == "WITHHELD" and reason == "PUBLICATION_NOT_AUTHORIZED" and mode == "ACTIVE":
        raise BtcContractError(f"{period}: PUBLICATION_NOT_AUTHORIZED cannot appear in an authorized payload")
    if mode == "PREVIEW" and period >= DEFAULT_FROM and status == "WITHHELD" and reason not in ("PUBLICATION_NOT_AUTHORIZED", "RIGHTS_NOT_CLEARED"):
        raise BtcContractError(f"{period}: a preview withholds standard-profile months for the release gate")
    return status


def validate_payload(payload: dict, legacy_bytes: bytes, exact: dict = None) -> dict:
    """Validate an extended payload (preview or active). Raises BtcContractError; returns a value-free summary.
    Passing validation proves shape and invariants only: authority for an ACTIVE payload comes solely from `composite_release_gate`."""
    if not isinstance(payload, dict) or list(payload) != ["data", "btc"] or not isinstance(payload["data"], list) or not payload["data"]:
        raise BtcContractError("payload must be {data:[...], btc:{...}}")
    mode = validate_root(payload["btc"])
    periods = [r.get("period") for r in payload["data"]]
    if periods != sorted(set(periods)):
        raise BtcContractError("periods must be unique and chronological")
    legacy_hash = validate_legacy_projection(payload, legacy_bytes)
    counts, reasons = {}, {}
    published = []
    for row in payload["data"]:
        status = validate_month(row, payload["btc"], mode)
        counts[status] = counts.get(status, 0) + 1
        reason = row["btc_meta"]["missing_reason"]
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        if status == "PUBLISHED":
            published.append(row["period"])
    if mode == "ACTIVE" and not published:
        raise BtcContractError("an active payload publishes at least one month")
    if published and (published[0] != payload["btc"]["coverage"]["authorized_from"] or published[-1] != payload["btc"]["coverage"]["authorized_through"]):
        raise BtcContractError("coverage.authorized_from/through must be the first/last published month")
    if exact is not None:
        check_precision(payload, exact)
    return {"mode": mode, "months": len(periods), "status_counts": counts, "reason_counts": reasons, "published_months": len(published),
            "legacy_sha256": legacy_hash, "payload_sha256": sha256(serialize(payload)), "btc_selection_sha256": btc_selection_sha256(payload)}


def btc_selection_sha256(payload: dict) -> str:
    """Hash of the selected BTC values AND the month metadata (quality, status, reason, flags): a changed HOLD/quality selection changes it."""
    lines = []
    for row in payload["data"]:
        m = row["btc_meta"]
        lines.append("|".join([row["period"], "" if row["btc_per_house"] is None else repr(row["btc_per_house"]),
                               "" if row["sat_per_house"] is None else repr(row["sat_per_house"]), str(m["quality"]), m["status"],
                               str(m["missing_reason"]), ",".join(m["flags"])]) + "\n")
    return sha256("".join(lines).encode())


# ------------------------------------------------------------------ precision (private exact values)
def check_precision(payload: dict, exact: dict) -> None:
    """Representation loss of the public JSON numbers against the canonical Decimal values (exact rational arithmetic).

    Per field |public - canonical| < 0.25 satoshi equivalent, public BTC x 1e8 within 0.5 satoshi of public SAT, SAT < 2^53, and the exact
    sidecar itself is consistent: SAT = BTC x 1e8 exactly. A month that is not PUBLISHED must not appear in a published selection."""
    months = (exact or {}).get("months") if isinstance(exact, dict) else None
    if not isinstance(months, dict):
        raise BtcContractError("exact sidecar has no `months`")
    from fractions import Fraction
    published = set()
    for row in payload["data"]:
        p = row["period"]
        if row["btc_meta"]["status"] != "PUBLISHED":
            continue
        published.add(p)
        try:
            btc, sat = Fraction(Decimal(months[p]["btc_per_house"])), Fraction(Decimal(months[p]["sat_per_house"]))
        except (KeyError, InvalidOperation, TypeError):
            raise BtcContractError(f"{p}: exact values missing or malformed") from None
        if sat != btc * SATS_PER_BTC:
            raise BtcContractError(f"{p}: canonical SAT is not canonical BTC x 1e8")
        if abs(Fraction(row["btc_per_house"]) - btc) * SATS_PER_BTC >= Fraction(REPRESENTATION_LOSS_SAT):
            raise BtcContractError(f"{p}: JSON btc_per_house loses 0.25 satoshi equivalent or more")
        if abs(Fraction(row["sat_per_house"]) - sat) >= Fraction(REPRESENTATION_LOSS_SAT):
            raise BtcContractError(f"{p}: JSON sat_per_house loses 0.25 satoshi or more")
    if not published <= set(months):
        raise BtcContractError("published months without exact values")


def reparse_decimal(blob: bytes) -> dict:
    """Parse serialized bytes with Decimal floats: the representation check must run on what is actually written."""
    return json.loads(blob.decode("utf-8"), parse_float=Decimal)


# ------------------------------------------------------------------ composing and releasing (closed by default)
def compose_release(preview: dict, sidecar: dict, authorization: dict) -> dict:
    """Build the ACTIVE composite from a PREVIEW, the private sidecar and an authorization (release id, decision, exact months, rights refs).

    Only authorized months receive values; other standard-profile months become NOT_AUTHORIZED_PERIOD. Representation loss is checked on the bytes
    that would be written. The result is NOT released: `composite_release_gate` still needs an exact owner record."""
    months = sorted(authorization["months"])
    if not months or len(set(months)) != len(months):
        raise BtcContractError("authorized months must be a non-empty unique list")
    early = bool(authorization.get("early_history_authorized", False))
    values = sidecar["months"]
    out = json.loads(json.dumps(preview))
    for row in out["data"]:
        p = row["period"]
        if p in months:
            if p in HOLD_MONTHS or p not in values or (p < DEFAULT_FROM and not early):
                raise BtcContractError(f"{p}: cannot be authorized for publication")
            row["btc_per_house"], row["sat_per_house"] = float(Decimal(values[p]["btc_per_house"])), float(Decimal(values[p]["sat_per_house"]))
            row["btc_meta"]["status"], row["btc_meta"]["missing_reason"] = "PUBLISHED", None
        elif row["btc_meta"]["missing_reason"] in ("PUBLICATION_NOT_AUTHORIZED", "RIGHTS_NOT_CLEARED"):
            row["btc_meta"]["status"], row["btc_meta"]["missing_reason"] = "WITHHELD", "NOT_AUTHORIZED_PERIOD"
    missing = set(months) - {r["period"] for r in out["data"]}
    if missing:
        raise BtcContractError(f"authorized months not in the calendar: {sorted(missing)[:3]}")
    root = out["btc"]
    root["coverage"].update(authorized_from=months[0], authorized_through=months[-1], early_history_authorized=early)
    root["release"].update(id=authorization["release_id"], decision_ref=authorization["decision_ref"], publication_authorized=True)
    root["rights"].update(review_ref=authorization["rights_review_ref"], conflicting_contract_check=authorization["conflicting_contract_check"])
    validate_payload(out, legacy_projection_bytes(out), exact=None)
    check_precision(out, sidecar)
    # the representation check must hold for the bytes as written: re-read them with Decimal floats
    reread = reparse_decimal(serialize(out))
    for row in reread["data"]:
        if row["btc_meta"]["status"] == "PUBLISHED":
            exact = sidecar["months"][row["period"]]
            if abs(row["btc_per_house"] - Decimal(exact["btc_per_house"])) * SATS_PER_BTC >= REPRESENTATION_LOSS_SAT:
                raise BtcContractError(f"{row['period']}: serialized btc_per_house loses 0.25 satoshi or more")
    return out


def private_hashes(preview: dict, sidecar: dict) -> dict:
    """Hashes of the PRIVATE candidate objects (preview and values sidecar) exactly as tools.btc_06c_candidate writes them. Put them in the
    authorization given to `record_template`; they are recorded for reproducibility and checked by `reproduce_composite`, never by the public gate."""
    return {"candidate_preview_sha256": sha256(serialize(preview)), "private_sidecar_sha256": sha256(serialize(sidecar))}


def quality_by_month(composite: dict) -> dict:
    """{month: quality} for the PUBLISHED months: the quality class each month is released under."""
    return {r["period"]: r["btc_meta"]["quality"] for r in composite["data"] if r["btc_meta"]["status"] == "PUBLISHED"}


def record_template(composite: dict, authorization: dict) -> dict:
    """The record an OWNER would have to approve for exactly these bytes (the approval itself is never created here).

    Binds: the public payload bytes, the BTC selection, the legacy projection, the source snapshot (id, manifest, provenance block), the calculation
    commit, the CBS input, the private candidate/sidecar hashes (from `authorization`, else PENDING), the methodology versions, the exact months,
    the exact quality classes (and their month-by-month hash), the exceptions, the rights references, the release identity and the rollback target."""
    blob = serialize(composite)
    prov = composite["btc"]["provenance"]
    pub = [r["period"] for r in composite["data"] if r["btc_meta"]["status"] == "PUBLISHED"]
    quals = quality_by_month(composite)
    return {"schema": RECORD_SCHEMA, "record_id": authorization["release_id"], "owner_approval": "PENDING", "status": RECORD_STATUS,
            "release_id": authorization["release_id"], "decision_ref": authorization["decision_ref"], "approved_by": "", "approved_on": "",
            "composite_sha256": sha256(blob), "public_payload_sha256": sha256(blob),
            "btc_selection_sha256": btc_selection_sha256(composite), "legacy_projection_sha256": sha256(legacy_projection_bytes(composite)),
            "snapshot_manifest_sha256": prov["snapshot_manifest_sha256"], "snapshot_id": prov["snapshot_id"], "calculation_git_commit": prov["calculation_git_commit"],
            "provenance_sha256": sha256(serialize(prov)), "cbs_input_sha256": prov["cbs_input_sha256"],
            "candidate_preview_sha256": authorization.get("candidate_preview_sha256", PENDING), "private_sidecar_sha256": authorization.get("private_sidecar_sha256", PENDING),
            "method_id": composite["btc"]["method_id"], "quality_version": composite["btc"]["quality_version"],
            "exception_policy_version": composite["btc"]["exception_policy_version"], "authorized_fields": ["btc_per_house", "sat_per_house"],
            "authorized_months": pub, "authorized_qualities": sorted(set(quals.values())), "quality_by_month_sha256": sha256(serialize(quals)),
            "exceptions": sorted(HOLD_MONTHS), "early_history_authorized": composite["btc"]["coverage"]["early_history_authorized"],
            "review_refs": {"rights": composite["btc"]["rights"]["review_ref"], "contract_check": composite["btc"]["rights"]["conflicting_contract_check"]},
            "rollback_ref": {"previous_public_sha256": LEGACY_PUBLIC_SHA256, "state": ROLLBACK_STATE}}


def reproduce_composite(record: dict, preview_bytes: bytes, sidecar_bytes: bytes) -> bytes:
    """Independent regeneration (release preflight, PRIVATE inputs): rebuild the composite from the private preview and sidecar using ONLY what the
    record states, and require byte-identical output. Raises BtcContractError on any difference; returns the regenerated bytes."""
    if not isinstance(record, dict):
        raise BtcContractError("record is not an object")
    if sha256(preview_bytes) != record.get("candidate_preview_sha256") or sha256(sidecar_bytes) != record.get("private_sidecar_sha256"):
        raise BtcContractError("the private candidate or sidecar is not the one the record binds")
    refs = record.get("review_refs") or {}
    auth = {"release_id": record["release_id"], "decision_ref": record["decision_ref"], "months": list(record["authorized_months"]),
            "rights_review_ref": refs.get("rights"), "conflicting_contract_check": refs.get("contract_check"),
            "early_history_authorized": record.get("early_history_authorized", False)}
    regenerated = serialize(compose_release(json.loads(preview_bytes.decode("utf-8")), json.loads(sidecar_bytes.decode("utf-8")), auth))
    if sha256(regenerated) != record.get("composite_sha256") or sha256(regenerated) != record.get("public_payload_sha256"):
        raise BtcContractError("regenerated composite differs from the record (not reproducible from the pinned private inputs)")
    return regenerated


def rollback_target_ok(record: dict, public_state_bytes: bytes) -> bool:
    """A withdrawal returns to the previously authorized public state: the bytes must be the pinned legacy payload the record names."""
    ref = record.get("rollback_ref") if isinstance(record, dict) else None
    return (isinstance(ref, dict) and ref == {"previous_public_sha256": LEGACY_PUBLIC_SHA256, "state": ROLLBACK_STATE}
            and sha256(public_state_bytes) == ref["previous_public_sha256"])


def _record_matches(record, composite: dict, blob: bytes) -> bool:
    if not isinstance(record, dict) or set(record) != RECORD_KEYS or record.get("schema") != RECORD_SCHEMA:
        return False  # exact key set: no missing and no extra (unreviewed) field
    if record.get("owner_approval") != "APPROVED" or record.get("status") != RECORD_STATUS:
        return False
    if not record.get("approved_by") or not record.get("approved_on") or not record.get("record_id"):
        return False
    root = composite["btc"]
    prov = root["provenance"]
    published = [r["period"] for r in composite["data"] if r["btc_meta"]["status"] == "PUBLISHED"]
    quals = quality_by_month(composite)
    checks = (
        record.get("composite_sha256") == sha256(blob) == record.get("public_payload_sha256"),
        record.get("snapshot_id") == prov["snapshot_id"] and record.get("calculation_git_commit") == prov["calculation_git_commit"],
        record.get("provenance_sha256") == sha256(serialize(prov)),
        _is_sha(record.get("candidate_preview_sha256")) and _is_sha(record.get("private_sidecar_sha256")),  # owner-supplied; checked by reproduce_composite
        record.get("authorized_qualities") == sorted(set(quals.values())) and set(quals.values()) <= set(QUALITIES)
        and record.get("quality_by_month_sha256") == sha256(serialize(quals)),
        record.get("rollback_ref") == {"previous_public_sha256": LEGACY_PUBLIC_SHA256, "state": ROLLBACK_STATE},
        record.get("btc_selection_sha256") == btc_selection_sha256(composite),
        record.get("legacy_projection_sha256") == sha256(legacy_projection_bytes(composite)) == LEGACY_PUBLIC_SHA256,
        record.get("snapshot_manifest_sha256") == prov["snapshot_manifest_sha256"],
        record.get("cbs_input_sha256") == prov["cbs_input_sha256"],
        (record.get("method_id"), record.get("quality_version"), record.get("exception_policy_version")) ==
        (root["method_id"], root["quality_version"], root["exception_policy_version"]),
        record.get("authorized_fields") == ["btc_per_house", "sat_per_house"],
        record.get("authorized_months") == published and published == sorted(set(published)),
        record.get("exceptions") == sorted(HOLD_MONTHS) and not set(HOLD_MONTHS) & set(published),
        record.get("early_history_authorized") is root["coverage"]["early_history_authorized"],
        (record.get("release_id"), record.get("decision_ref")) == (root["release"]["id"], root["release"]["decision_ref"]),
        isinstance(record.get("review_refs"), dict) and record["review_refs"].get("rights") == root["rights"]["review_ref"]
        and record["review_refs"].get("contract_check") == root["rights"]["conflicting_contract_check"] == "VERIFIED",
    )
    return all(checks)


def composite_release_gate(composite_bytes: bytes, records=None) -> dict:
    """Closed by default. An extended payload may only be released with an exact owner-approved record for THESE bytes: matching hashes of
    the composite, the BTC selection and the legacy projection, the authorized fields and months (exceptions excluded), the provenance
    binding and the metadata. A JSON flag, a partial match or an old gold approval never opens it."""
    records = ARTIFACT_RECORDS if records is None else tuple(records)
    try:
        composite = json.loads(composite_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BtcContractError("composite is not valid JSON") from None
    if serialize(composite) != composite_bytes:
        raise BtcContractError("composite bytes are not in canonical serialization")
    legacy = legacy_projection_bytes(composite)
    validate_payload(composite, legacy)
    if composite["btc"]["release"]["publication_authorized"] is not True:
        raise ReleaseDenied("the payload is a preview: it cannot be released")
    for record in records:
        if _record_matches(record, composite, composite_bytes):
            return record
    raise ReleaseDenied("no exact owner-approved artifact record for this composite payload (registry is empty by default)")
