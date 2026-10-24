"""HIST-12: the historical publication contract `hist-publication/1` (inert: nothing is published; the release allowlist stays empty).

A SEPARATE static payload (`historical.json`) for the approved HIST-11 scope (HD2): nominal NVM half-year medians (NLG original and a labelled retrospective EUR
denomination), CBS monthly averages 1995-01..1999-12 and the matching half-year CBS means for a comparison panel. It never touches the current public dataset.

Authority never comes from the payload itself. A payload is accepted only when ALL hold (fail closed, `HistPublicationDenied` otherwise):
  1. the SHA-256 of its exact bytes is in the supplied pin list (the frontend counterpart is `HIST_APPROVED_PAYLOAD_SHA256`, default empty);
  2. the bytes are the canonical serialization of the parsed document (no extra whitespace, fields or float formatting);
  3. an EXTERNAL `hist_model.ReleaseRecord` (default: `hist_model.ALLOWLIST`, empty) authorizes exactly these series and the content hash `release_hash(series)`;
  4. series ids, frequency, currency, unit, kind, definition, layer and the exact period range match the approved specification (no gaps, no extras);
  5. quality labels and flags are from the documented sets; provenance is complete and the lineage of every series resolves;
  6. the comparison block is disabled, or enabled only for the exact approved scope AND an external HP3 authorization (`COMPARISON_RELEASES`, empty by default);
  7. synthetic data (marker `SYNTHETIC_TEST_ONLY`) is refused in production mode, and required in test mode.
Uses the existing model (canonical JSON, Series, release_hash, publication_gate); adds no database, backend or service."""
from __future__ import annotations

import json
import re
from decimal import Decimal

from etl import hist_model as hm

SCHEMA = "hist-publication/1"
SYNTHETIC_MARKER = "SYNTHETIC_TEST_ONLY"
NLG_PER_EUR = Decimal("2.20371")
RETRO_TOLERANCE = Decimal("1e-8")  # relative; the stored EUR value is a rounded decimal string
QUALITIES = ("CONFIRMED", "PROPOSED")
FLAGS = frozenset({"RETROSPECTIVE_EUR", "VISUAL_P135_PER_PROJECT_CONTROL", "HALF_YEAR_WEIGHTED"})
ROOT_KEYS = ["schema", "release", "provenance", "series", "comparison"]
RELEASE_KEYS = ["id", "release_sha256", "authorizer", "authorized_on", "decision_ref", "series_ids", "publication_authorized", "comparison_authorized"]
SOURCE_KEYS = ["id", "title", "rights_status", "sha256", "vintage", "acquired_at"]
COMPARISON_KEYS = ["authorized", "series", "first", "last", "warning"]
COMPARISON_SERIES = ["hist_nvm_median_eur_retro_h", "hist_cbs_avg_eur_h"]
COMPARISON_WARNING = "STATISTICS_DIFFER"

# The approved series (HD2). No gold, grams, index, CPI, Bitcoin, fuel or equity series can be expressed here.
APPROVED_SERIES = {
    "hist_nvm_median_nlg_h": dict(frequency="semiannual", currency="NLG", unit="NLG", kind="median_price", definition_id="nvm_median_existing_homes_nominal",
                                  layer="normalized", first="1975-H1", last="2000-H2", count=52, required_flags=()),
    "hist_nvm_median_eur_retro_h": dict(frequency="semiannual", currency="EUR", unit="EUR", kind="median_price", definition_id="nvm_median_existing_homes_nominal_retro_eur",
                                        layer="normalized", first="1975-H1", last="2000-H2", count=52, required_flags=("RETROSPECTIVE_EUR",)),
    "hist_cbs_avg_eur_m": dict(frequency="monthly", currency="EUR", unit="EUR", kind="average_price", definition_id="cbs_average_price_existing_homes",
                               layer="normalized", first="1995-01", last="1999-12", count=60, required_flags=("RETROSPECTIVE_EUR",)),
    "hist_cbs_avg_eur_h": dict(frequency="semiannual", currency="EUR", unit="EUR", kind="average_price", definition_id="cbs_average_price_existing_homes_halfyear_weighted",
                               layer="derived", first="1995-H1", last="2000-H2", count=12, required_flags=("RETROSPECTIVE_EUR", "HALF_YEAR_WEIGHTED")),
}
COMPARISON_RELEASES: tuple = ()  # release ids for which the NVM/CBS comparison panel may be enabled (HP3); EMPTY by default, like hist_model.ALLOWLIST
_HEX = re.compile(r"[0-9a-f]{64}")


class HistPublicationDenied(hm.PublicationDenied):
    """The historical payload is not authorized (raised for every violation; the message never contains a value)."""


def _deny(message: str):
    raise HistPublicationDenied(message)


def payload_sha256(blob: bytes) -> str:
    return hm.sha256_hex(blob)


def serialize(payload: dict) -> bytes:
    return hm.canonical_json(payload)


def build_payload(series, release: dict, provenance: dict, comparison: dict) -> dict:
    """Assemble a payload document from model series (pure; no authorization: `verify_payload` is the gate)."""
    return {"schema": SCHEMA, "release": release, "provenance": provenance, "series": sorted(series, key=lambda s: s.series_id), "comparison": comparison}


def release_record(release: dict) -> hm.ReleaseRecord:
    """The model record the payload's release block claims. It is only compared with the EXTERNAL record, never trusted on its own."""
    return hm.ReleaseRecord(release_id=release["id"], release_sha256=release["release_sha256"], authorizer=release["authorizer"],
                            authorized_on=release["authorized_on"], decision_ref=release["decision_ref"], series_ids=tuple(release["series_ids"]))


def _keys(obj, expected, where):
    if not isinstance(obj, dict) or sorted(obj) != sorted(expected):
        _deny(f"{where}: unexpected structure")


def _check_series(s: hm.Series):
    spec = APPROVED_SERIES.get(s.series_id)
    if spec is None:
        _deny(f"series {s.series_id!r} is not an approved historical series")
    for field in ("frequency", "currency", "unit", "kind", "definition_id", "layer"):
        if getattr(s, field) != spec[field]:
            _deny(f"{s.series_id}: {field} differs from the approved specification")
    if s.basis != "nominal" or s.index_base is not None:
        _deny(f"{s.series_id}: only nominal, non-index series are approved")
    periods = [p.period for p in s.points]
    if periods != hm.expected_periods(spec["first"], spec["last"], spec["frequency"]) or len(periods) != spec["count"]:
        _deny(f"{s.series_id}: periods differ from the approved range (no gaps, no extra periods)")
    for p in s.points:
        if p.value is None or p.value <= 0:
            _deny(f"{s.series_id}: every approved period needs a positive value")
        if p.quality not in QUALITIES:
            _deny(f"{s.series_id}: quality label not allowed")
        flags = set(p.flags) - {SYNTHETIC_MARKER}
        if not flags <= FLAGS or not set(spec["required_flags"]) <= flags:
            _deny(f"{s.series_id}: undocumented or missing flag")


def verify_payload(blob: bytes, *, pins, records=None, comparison_releases=None, production: bool = True) -> dict:
    """Return the parsed document or raise HistPublicationDenied. `pins` are the approved payload hashes; `records` the external release records."""
    if not isinstance(blob, bytes) or payload_sha256(blob) not in tuple(pins):
        _deny("payload hash is not in the approved pin list")
    try:
        doc = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        _deny("payload is not valid JSON")
    _keys(doc, ROOT_KEYS, "root")
    if doc["schema"] != SCHEMA:
        _deny("unsupported schema")
    try:
        canonical = hm.canonical_json(doc)
    except hm.ModelError:
        _deny("payload holds a float or an unsupported value")
    if canonical != blob:
        _deny("payload is not in canonical serialization")
    synthetic = SYNTHETIC_MARKER.lower().encode() in blob.lower()
    if production and synthetic:
        _deny("synthetic fixture marker in a production candidate")
    if not production and not synthetic:
        _deny("test mode requires the synthetic marker")
    rel, prov, comp = doc["release"], doc["provenance"], doc["comparison"]
    _keys(rel, RELEASE_KEYS, "release")
    if rel["publication_authorized"] is not True or not isinstance(rel["comparison_authorized"], bool):
        _deny("release block does not claim publication")
    try:
        series = [hm.series_from_dict(raw) for raw in doc["series"]]
        for s in series:
            hm.validate_series(s)
    except (hm.ModelError, KeyError, TypeError, ValueError, AttributeError) as e:  # a malformed series document of any shape is a denial, never a crash
        _deny(f"series invalid: {type(e).__name__}")
    ids = [s.series_id for s in series]
    if ids != sorted(set(ids)) or set(ids) != set(APPROVED_SERIES) or ids != sorted(rel["series_ids"]):
        _deny("the payload must contain exactly the approved series")
    for s in series:
        _check_series(s)
        if synthetic and not all(SYNTHETIC_MARKER in p.flags for p in s.points):
            _deny("synthetic payload without the marker on every point")
    # NVM retrospective euro must be the guilder value divided by 2.20371 (denomination only)
    by_id = {s.series_id: s for s in series}
    for a, b in zip(by_id["hist_nvm_median_nlg_h"].points, by_id["hist_nvm_median_eur_retro_h"].points):
        if abs(b.value - a.value / NLG_PER_EUR) > RETRO_TOLERANCE * a.value / NLG_PER_EUR:
            _deny("retrospective euro is not the guilder value / 2.20371")
    # provenance
    if not isinstance(prov, dict) or set(prov) != {"method_ids", "sources"} or not prov["method_ids"] or not isinstance(prov["sources"], list) or not prov["sources"]:
        _deny("provenance is missing or incomplete")
    src = {}
    for item in prov["sources"]:
        _keys(item, SOURCE_KEYS, "source")
        if not all(isinstance(item[k], str) and item[k] for k in SOURCE_KEYS) or not _HEX.fullmatch(item["sha256"]) or item["id"] in src:
            _deny("source provenance incomplete")
        src[item["id"]] = item["sha256"]
    for s in series:
        for sid, digest in s.inputs:
            if sid in src:
                ok = src[sid] == digest
            elif sid in by_id:
                ok = hm.series_sha256(by_id[sid]) == digest
            else:
                ok = False
            if not ok:
                _deny(f"{s.series_id}: lineage does not resolve")
    # comparison scope (HP3)
    _keys(comp, COMPARISON_KEYS, "comparison")
    if not isinstance(comp["authorized"], bool) or comp["warning"] != COMPARISON_WARNING or comp["series"] != COMPARISON_SERIES:
        _deny("comparison block malformed")
    allowed_comparison = COMPARISON_RELEASES if comparison_releases is None else tuple(comparison_releases)
    if rel["comparison_authorized"] != comp["authorized"]:
        _deny("comparison flags are inconsistent")
    if comp["authorized"] and ((comp["first"], comp["last"]) != ("1995-H1", "2000-H2") or rel["id"] not in allowed_comparison):
        _deny("comparison is not authorized for this scope")
    # EXTERNAL authorization: the record is supplied by the caller (default: the empty allowlist), never read from the payload
    claimed = release_record(rel)
    records = hm.ALLOWLIST if records is None else tuple(records)
    if claimed not in records or claimed.release_sha256 != hm.release_hash(series):
        _deny("no matching external release record, or the content hash differs")
    hm.publication_gate(series, records=[claimed])
    return doc
