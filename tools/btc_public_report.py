"""BTC-07B P0: positive allowlist for everything BTC research tooling may print or upload in public CI.

The full research summary (price-bearing diagnostics) stays on the runner in a private directory. Only `public_summary(R)` may be
written to an uploaded directory or printed to the public log. It is built key by key from explicitly reviewed metadata (statuses,
counts, dates, hashes, booleans). Nothing is copied by default: an unknown key simply does not exist in the output.

`assert_price_free` is a second, independent backstop over the finished document: no floats, no decimal numbers in strings, no
unreviewed key names, no oversized content. A failure raises; the caller must then write nothing public.
"""
from __future__ import annotations

import json
import re

SCHEMA = "btc04e-public-summary/1"
MAX_BYTES = 40_000
MAX_STR = 300
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MONTH = re.compile(r"^\d{4}-\d{2}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECIMAL_IN_TEXT = re.compile(r"\d[\d_,]*\.\d")  # any decimal number or scientific notation in free text
LONG_NUMBER = re.compile(r"\d{7,}")  # a long digit run is not a count, a date or a version in this project's public reports
HASH_RUN = re.compile(r"((?=[0-9]*[a-f])[0-9a-f]{16,})")  # hashes contain digit runs; a pure digit string never qualifies
ENUM = re.compile(r"^[A-Za-z0-9_:/\-]{1,80}$")


class PublicReportError(ValueError):
    pass


def _has_long_number(s: str) -> bool:
    return any(LONG_NUMBER.search(part) for i, part in enumerate(HASH_RUN.split(s)) if i % 2 == 0)


def safe_text(text, limit=200) -> str:
    """Free text (exception messages) for public logs: decimal numbers and long digit runs are replaced, length is bounded."""
    s = str(text)[:limit]
    s = DECIMAL_IN_TEXT.sub("#", s)
    return "".join(part if i % 2 else LONG_NUMBER.sub("#", part) for i, part in enumerate(HASH_RUN.split(s)))


def _enum(x):
    return x if isinstance(x, str) and ENUM.match(x) else None


def _hex(x):
    return x if isinstance(x, str) and HEX64.match(x) else None


def _period(x):
    return x if isinstance(x, str) and (MONTH.match(x) or DAY.match(x)) else None


def _count(x):
    return x if isinstance(x, int) and not isinstance(x, bool) and 0 <= x < 10_000_000 else None


def _bool(x):
    return x if isinstance(x, bool) else None


def _pick(src, spec) -> dict:
    out = {}
    if isinstance(src, dict):
        for key, conv in spec.items():
            if key in src:
                out[key] = conv(src[key])
    return out


def _list(src, conv, limit=12) -> list:
    return [v for v in (conv(x) for x in (src or [])[:limit]) if v is not None] if isinstance(src, list) else []


def _month_meta(m) -> dict:
    """Quality/eligibility metadata of one month. The research `value` field is never copied."""
    spec = {"quality": _enum, "status": _enum, "exception": _enum, "release_eligibility": _enum, "daily_complete": _bool,
            "has_value": _bool, "days": _count, "calendar_days": _count, "stale_days": _count}
    out = _pick(m, spec)
    corr = (m or {}).get("corroboration") if isinstance(m, dict) else None
    if isinstance(corr, dict):
        out["corroboration"] = {k: _bool(v) for k, v in corr.items() if k in ("bitstamp_usd", "bitstamp_eur_native")}
    return out


def _tolerance(text, bound=1e-9):
    """Numeric agreement as a verdict. The measured difference itself is not published."""
    try:
        return float(text) < bound
    except (TypeError, ValueError):
        return False


def _independent(node) -> dict:
    out = {}
    for month, v in (node or {}).items() if isinstance(node, dict) else []:
        if _period(month) and isinstance(v, dict):
            out[month] = {"status": _enum(v.get("status")), "btc_agrees": _tolerance(v.get("btc_rel_diff")) if v.get("status") == "OK" else None,
                          "sats_agrees": _tolerance(v.get("sats_rel_diff")) if v.get("status") == "OK" else None}
    return out


def _corroboration(node) -> dict:
    out = {}
    if not isinstance(node, dict):
        return out
    for key, v in node.items():
        if key.startswith(("cm_", "usd_")) and key != "usd_months_over_1pct" and isinstance(v, dict):
            out[key] = _pick(v, {"n": _count, "first": _period, "last": _period, "max_at": _period})
    over = node.get("usd_months_over_1pct")
    if isinstance(over, dict):
        out["usd_months_over_1pct"] = {"n": _count(over.get("n")), "over_5pct": _list(over.get("over_5pct"), _period, 40)}
    return out


def public_summary(R: dict) -> dict:
    """Reviewed, price-free projection of the full research summary."""
    if not isinstance(R, dict):
        raise PublicReportError("summary is not an object")
    acq = R.get("acquisition")
    out = {"schema": SCHEMA, "caveat": "research only; nothing published; no price, derived BTC value or ratio in this document",
           "method_id": _enum(R.get("method_id")), "status": _enum(R.get("status")), "mode": _enum(R.get("mode")),
           "missing_sources": _list(R.get("missing_sources"), _enum)}
    fails = R.get("failures")
    out["failures"] = [safe_text(f) for f in fails[:10]] if isinstance(fails, list) else []
    if isinstance(R.get("error"), str):
        out["error"] = safe_text(R["error"], 160)
    out["acquisition"] = _pick(acq, {"pages": _count, "response_sha256": _hex, "first": _period, "last": _period, "n": _count,
                                      "retrieved_at_utc": lambda x: x if isinstance(x, str) and re.match(r"^\d{4}-\d{2}-\d{2}T[0-9:+\-]{8,14}$", x) else None})
    if isinstance(acq, dict):
        out["acquisition"]["page_hashes"] = len(acq.get("page_sha256") or [])
        out["acquisition"]["provider_gap_days"] = len(acq.get("provider_gaps") or [])
    obs = R.get("observations_used")
    out["observations_used"] = _pick(obs, {"first": _period, "last": _period, "n": _count, "missing_calendar_days": _count})
    if isinstance(obs, dict):
        out["observations_used"]["missing_sample"] = _list(obs.get("missing_sample"), _period, 10)
    out["rebuild_identical"] = _bool(R.get("rebuild_identical"))
    out["derived_values_sha256"] = _hex(R.get("derived_values_sha256"))
    vc = R.get("vintage_check") if isinstance(R.get("vintage_check"), dict) else {}
    out["vintage_check"] = {"status": _enum(vc.get("status")),
                            "sources": {k: _enum(v) for k, v in (vc.get("sources") or {}).items() if _enum(k) and isinstance(v, str)}
                            if isinstance(vc.get("sources"), dict) else {}}
    pc = R.get("pins_candidate") if isinstance(R.get("pins_candidate"), dict) else {}
    out["pins_candidate"] = {**_pick(pc, {"method_id": _enum, "parser_version": _enum, "exception_policy_version": _enum,
                                          "quality_version": _enum, "pinned_on": _period}),
                             "sources": {k: _pick(v, {"sha256": _hex, "n": _count, "first": _period, "last": _period})
                                         for k, v in (pc.get("sources") or {}).items() if _enum(k) and isinstance(v, dict)}
                             if isinstance(pc.get("sources"), dict) else {},
                             "derived": _pick(pc.get("derived"), {"values_sha256": _hex, "cutoff": _period})}
    cov = R.get("coverage")
    out["coverage"] = {k: {**_pick(v, {"first": _period, "last": _period, "n": _count, "n_null": _count}),
                           "null_sample": _list(v.get("null_sample"), _period, 8)}
                       for k, v in cov.items() if _enum(k) and isinstance(v, dict)} if isinstance(cov, dict) else {}
    qm = R.get("quality_months")
    out["quality_months"] = {k: _count(v) for k, v in qm.items() if _enum(k)} if isinstance(qm, dict) else {}
    out["chart_segments"] = [_pick(s, {"first": _period, "last": _period, "n": _count}) for s in (R.get("chart_segments") or [])[:40]
                             if isinstance(s, dict)]
    out["june_2011"] = _month_meta(R.get("june_2011"))
    out["stale_runs"] = [_pick(s, {"first": _period, "last": _period, "days": _count}) for s in (R.get("stale_runs") or [])[:25]
                         if isinstance(s, dict)]  # the repeated price (`value`) is private
    cal = R.get("ecb_calendar")
    out["ecb_calendar"] = _pick(cal, {"weekend_days_with_rate": _count, "target_holidays_missing": _count,
                                       "unexpected_missing_business_days": _count, "unexpected_in_validation_window": _count})
    if isinstance(cal, dict):
        out["ecb_calendar"]["unexpected_sample"] = _list(cal.get("unexpected_sample"), _period, 10)
        out["ecb_calendar"]["unexpected_by_month"] = {k: _count(v) for k, v in (cal.get("unexpected_by_month") or {}).items() if _period(k)}
    out["independent"] = _independent(R.get("independent"))
    out["corroboration"] = _corroboration(R.get("corroboration"))
    qs = R.get("quality_metadata_sample")
    out["quality_metadata_sample"] = {m: _month_meta(v) for m, v in qs.items() if _period(m)} if isinstance(qs, dict) else {}
    snap = R.get("snapshot")
    out["snapshot"] = _pick(snap, {"snapshot_id": _enum, "total_bytes": _count, "location": _safe_label, "durable_storage": _enum})
    if isinstance(snap, dict) and isinstance(snap.get("bytes"), dict):
        out["snapshot"]["bytes"] = {k: _count(v) for k, v in snap["bytes"].items() if _enum(k) or re.match(r"^[A-Za-z0-9_.\-]{1,60}$", str(k))}
    rep = R.get("replay_from_private_snapshot")
    out["replay_from_private_snapshot"] = _pick(rep, {"status": _enum, "snapshot_id": _enum, "derived_values_sha256": _hex, "raw_source_bytes": _enum})
    rev = R.get("revision_detection")
    out["revision_detection"] = _pick(rev, {"status": _enum, "unchanged": _count, "revised": _count, "missing": _count,
                                             "inserted_in_window": _count, "new_after_window": _count})
    if isinstance(rev, dict):
        out["revision_detection"]["window"] = _list(rev.get("window"), _period, 2)
        for k in ("revised_days", "missing_days", "inserted_days"):
            out["revision_detection"][k] = _list(rev.get(k), _period, 10)
    mu = R.get("monthly_update")
    out["monthly_update"] = _pick(mu, {"history": _enum, "baseline_last_complete_month": _period, "processed": _bool, "release_gate": _enum,
                                       "baseline_snapshot_id": _enum, "new_vintage_snapshot_id": _enum})
    if isinstance(mu, dict):
        out["monthly_update"]["months_added"] = _list(mu.get("months_added"), _period, 40)
    out["source_notes"] = len(R.get("source_notes") or []) if isinstance(R.get("source_notes"), list) else 0  # text may echo provider output
    assert_price_free(out)
    return out


def _safe_label(x):
    return x if isinstance(x, str) and re.match(r"^[A-Za-z0-9 _()\-]{1,80}$", x) else None


ALLOWED_TOP_KEYS = frozenset({
    "schema", "caveat", "method_id", "status", "mode", "missing_sources", "failures", "error", "acquisition", "observations_used",
    "rebuild_identical", "derived_values_sha256", "vintage_check", "pins_candidate", "coverage", "quality_months", "chart_segments",
    "june_2011", "stale_runs", "ecb_calendar", "independent", "corroboration", "quality_metadata_sample", "snapshot",
    "replay_from_private_snapshot", "revision_detection", "monthly_update", "source_notes"})
FORBIDDEN_KEYS = frozenset({"value", "values", "price", "btc_eur", "btc_usd_month", "btc_per_house", "btc_per_house_exact", "sats_per_house",
                            "sats_per_house_exact", "house_eur", "model_value", "gold_eur_oz", "sat_per_house", "raw", "daily", "sample"})


def assert_price_free(node) -> None:
    """Independent backstop over a finished public document. Raises on anything that could carry a price or a derived BTC value."""
    if not isinstance(node, dict) or set(node) - ALLOWED_TOP_KEYS or node.get("schema") != SCHEMA:
        raise PublicReportError("public summary: unknown or missing top-level keys")
    assert_value_free(node)


def assert_value_free(node, path="$") -> None:
    """Leaf-level check for any structure that will be printed in a public log (no schema requirement)."""
    if path == "$" and len(json.dumps(node, sort_keys=True, default=str).encode()) > MAX_BYTES:
        raise PublicReportError("public summary: too large")
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str) or k in FORBIDDEN_KEYS or DECIMAL_IN_TEXT.search(k) or _has_long_number(k):
                raise PublicReportError(f"public summary: forbidden key at {path}")
            assert_value_free(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            assert_value_free(v, f"{path}[{i}]")
    elif isinstance(node, float):
        raise PublicReportError(f"public summary: float at {path}")
    elif isinstance(node, str):
        if len(node) > MAX_STR or DECIMAL_IN_TEXT.search(node) or _has_long_number(node):
            raise PublicReportError(f"public summary: numeric or oversized text at {path}")
    elif not (node is None or isinstance(node, (bool, int))):
        raise PublicReportError(f"public summary: unsupported type at {path}")


def load_public(path) -> dict:
    """Read a public summary for printing. Anything that is not a valid public summary is refused (a private summary cannot be printed)."""
    doc = json.loads(open(path, encoding="utf-8").read())
    assert_price_free(doc)
    return doc
