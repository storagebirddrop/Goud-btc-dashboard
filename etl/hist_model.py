"""ARCH-02 research-grade historical data model (PROPOSED, not wired into production).

Four logical layers, stored as versioned files plus SHA-256 hashes (no database, ADR-001):
  1. source observations  (Series.layer == "source": provenance per value)
  2. normalized series    (Series.layer == "normalized": documented transformations, lineage)
  3. derived comparisons  (Series.layer == "derived": grams, sats, relative performance)
  4. publication layer    (ReleaseRecord allowlist, default EMPTY, fail-closed)

Nothing here imports or alters etl/static_export.py. There is no interpolation, forward fill or
annual-to-monthly conversion anywhere; a missing period stays None. Arithmetic is Decimal only.
"""
from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext

from etl.asset_quality import NLG_PER_EUR, SATOSHIS_PER_BTC, TROY_OUNCE_GRAMS

PREC = 34
SCHEMA = "hist-model/1"
FREQUENCIES = ("annual", "semiannual", "monthly", "daily")
CURRENCIES = ("NLG", "EUR", "USD", "INDEX", "NONE")  # NONE: dimensional results such as gram, satoshi
LAYERS = ("source", "normalized", "derived")
ASSET_CLASSES = ("housing", "gold", "bitcoin", "equity", "fx", "cpi")
# Definition kinds are never mixed implicitly. basis separates nominal from real.
KINDS = ("average_price", "median_price", "constant_quality_index", "spot_price", "price_return", "total_return",
         "fx_rate", "cpi", "transaction_count", "transaction_value", "statistic_ratio", "growth_ratio")
BASES = ("nominal", "real")
INCOMPATIBLE_KINDS = (frozenset({"average_price", "constant_quality_index"}),
                      frozenset({"average_price", "median_price"}),  # different statistics: only statistic_ratio() may relate them
                      frozenset({"median_price", "constant_quality_index"}),
                      frozenset({"price_return", "total_return"}))
QUALITY = ("CONFIRMED", "PROPOSED", "INFERRED", "UNRESOLVED")  # best to worst
RESTRICTED_CLASSES = ("bitcoin", "equity")
RESTRICTED_TOKENS = frozenset({"btc", "bitcoin", "sat", "sats", "satoshi", "sp500", "spx", "aex", "equity"})

_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")
_FLAG = re.compile(r"[A-Z0-9_:/=.-]{1,64}")
_HEX = re.compile(r"[0-9a-f]{64}")
_PERIOD = {"annual": re.compile(r"\d{4}"), "semiannual": re.compile(r"\d{4}-H[12]"), "monthly": re.compile(r"\d{4}-\d{2}"),
           "daily": re.compile(r"\d{4}-\d{2}-\d{2}")}


class ModelError(ValueError):
    """Any violation of a model invariant; always carries a clear message."""


class FrequencyError(ModelError): ...
class CurrencyMismatch(ModelError): ...
class DefinitionMismatch(ModelError): ...
class OverlapError(ModelError): ...
class RevisionError(ModelError): ...
class PublicationDenied(ModelError): ...


# ---- numbers, periods ----------------------------------------------------------------------------
def to_decimal(value, name="value") -> Decimal:
    """Decimal-string (or Decimal) only. Floats, bools, NaN and Infinity are rejected."""
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and value == value.strip() and value:
        try:
            result = Decimal(value)
        except InvalidOperation:
            raise ModelError(f"{name}: not a decimal string: {value!r}") from None
    else:
        raise ModelError(f"{name}: must be a Decimal string, got {type(value).__name__}")
    if not result.is_finite():
        raise ModelError(f"{name}: not finite")
    return result


def dec_str(value: Decimal) -> str:
    """Canonical decimal text: no exponent, no trailing zeros ('1.50' and '1.5' are the same value)."""
    text = format(value, "f")  # exact, independent of the active context precision
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def period_key(period, frequency) -> int:
    if frequency not in FREQUENCIES:
        raise FrequencyError(f"unknown frequency {frequency!r}")
    if not isinstance(period, str) or not _PERIOD[frequency].fullmatch(period):
        raise FrequencyError(f"period {period!r} is not a valid {frequency} period")
    try:
        if frequency == "annual":
            return date(int(period), 1, 1).year
        if frequency == "semiannual":
            return date(int(period[:4]), 1, 1).year * 2 + int(period[6]) - 1
        if frequency == "monthly":
            year, month = int(period[:4]), int(period[5:])
            return date(year, month, 1).year * 12 + month - 1
        return date.fromisoformat(period).toordinal()
    except ValueError:
        raise FrequencyError(f"period {period!r} is not a real {frequency} period") from None


def period_label(key: int, frequency: str) -> str:
    if frequency == "annual":
        return f"{key:04d}"
    if frequency == "semiannual":
        return f"{key // 2:04d}-H{key % 2 + 1}"
    if frequency == "monthly":
        return f"{key // 12:04d}-{key % 12 + 1:02d}"
    return date.fromordinal(key).isoformat()


def expected_periods(first, last, frequency):
    low, high = period_key(first, frequency), period_key(last, frequency)
    if low > high:
        raise FrequencyError(f"range start {first} is after end {last}")
    return [period_label(k, frequency) for k in range(low, high + 1)]


def worst_quality(*labels) -> str:
    return max(labels, key=QUALITY.index)


# ---- data classes --------------------------------------------------------------------------------
@dataclass(frozen=True)
class Observation:
    """Layer 1: one original measurement with full provenance."""
    series_id: str
    period: str
    value: Decimal
    currency: str
    unit: str
    definition_id: str
    source_id: str
    raw_sha256: str
    retrieved_at: str
    vintage: str
    quality: str
    flags: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "value", to_decimal(self.value, f"{self.series_id} {self.period}"))
        object.__setattr__(self, "flags", tuple(self.flags))


@dataclass(frozen=True)
class Point:
    """Layers 2 and 3: a value (or an explicit gap, value None) with carried quality and flags."""
    period: str
    value: Decimal | None
    quality: str
    flags: tuple = ()

    def __post_init__(self):
        if self.value is not None:
            object.__setattr__(self, "value", to_decimal(self.value, f"point {self.period}"))
        object.__setattr__(self, "flags", tuple(self.flags))


@dataclass(frozen=True)
class Break:
    """Documented methodology or definition break; carried through every derivation."""
    period: str
    reason: str


@dataclass(frozen=True)
class Series:
    series_id: str
    layer: str
    asset_class: str
    frequency: str
    currency: str
    unit: str
    definition_id: str
    kind: str
    basis: str = "nominal"
    index_base: str | None = None  # "YYYY[-MM[-DD]]=100"; required when currency == "INDEX"
    breaks: tuple = ()
    observations: tuple = ()  # layer 1 only
    points: tuple = ()  # layers 2 and 3
    inputs: tuple = ()  # ((series_id, series_sha256), ...) lineage
    transforms: tuple = ()  # ordered, documented transformation records (dicts)


@dataclass(frozen=True)
class Revision:
    series_id: str
    period: str
    kind: str  # value_changed | hash_changed | dropped
    old_value: str
    new_value: str | None
    old_vintage: str
    new_vintage: str


@dataclass(frozen=True)
class ReleaseRecord:
    """Layer 4: owner authorization tying approved series ids to the exact bytes (hash) reviewed."""
    release_id: str
    release_sha256: str
    authorizer: str
    authorized_on: str
    decision_ref: str
    series_ids: tuple
    restricted_authorized: tuple = ()  # bitcoin/equity ids that the record explicitly authorizes


ALLOWLIST: tuple = ()  # default EMPTY: nothing is published until a ReleaseRecord is added here or passed in


# ---- canonical serialization and hashing ---------------------------------------------------------
def _plain(obj):
    if isinstance(obj, Decimal):
        return dec_str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, float):
        raise ModelError("floats are not allowed in canonical output")
    return obj


def canonical_json(obj) -> bytes:
    """Sorted keys, compact separators, Decimal strings, ASCII, trailing newline (as tools/data_01_source_pin)."""
    return (json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def series_sha256(series: Series) -> str:
    return sha256_hex(canonical_json(series))


def release_hash(members) -> str:
    return sha256_hex(canonical_json({s.series_id: series_sha256(s) for s in members}))


def series_from_dict(raw: dict) -> Series:
    """Inverse of canonical serialization; unknown keys are rejected."""
    allowed = {f.name for f in fields(Series)}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ModelError(f"unexpected series keys: {sorted(set(raw) - allowed) if isinstance(raw, dict) else raw}")
    data = dict(raw)
    data["breaks"] = tuple(Break(**b) for b in data.get("breaks", ()))
    data["observations"] = tuple(Observation(**o) for o in data.get("observations", ()))
    data["points"] = tuple(Point(p["period"], None if p["value"] is None else p["value"], p["quality"],
                                 p.get("flags", ())) for p in data.get("points", ()))
    data["inputs"] = tuple(tuple(i) for i in data.get("inputs", ()))
    data["transforms"] = tuple(data.get("transforms", ()))
    return Series(**data)


# ---- validators ----------------------------------------------------------------------------------
def _rows(series: Series):
    return series.observations if series.layer == "source" else series.points


def _check_meta(s: Series):
    sid = s.series_id
    checks = ((isinstance(sid, str) and _ID.fullmatch(sid), "series_id must match [a-z][a-z0-9_]{0,63}"),
              (s.layer in LAYERS, f"layer must be one of {LAYERS}"),
              (s.asset_class in ASSET_CLASSES, f"asset_class must be one of {ASSET_CLASSES}"),
              (s.frequency in FREQUENCIES, f"frequency must be one of {FREQUENCIES}"),
              (s.currency in CURRENCIES, f"currency must be one of {CURRENCIES}"),
              (isinstance(s.unit, str) and s.unit, "unit is required"),
              (isinstance(s.definition_id, str) and s.definition_id, "definition_id is required"),
              (s.kind in KINDS, f"kind must be one of {KINDS}"),
              (s.basis in BASES, f"basis must be one of {BASES}"))
    for ok, message in checks:
        if not ok:
            raise ModelError(f"{sid}: {message}")
    if s.currency == "INDEX" and not (s.index_base and s.index_base.endswith("=100")):
        raise CurrencyMismatch(f"{sid}: an index series needs an explicit index_base such as '2000-01=100'")
    if s.currency != "INDEX" and s.index_base is not None:
        raise CurrencyMismatch(f"{sid}: index_base is only valid for currency INDEX")
    seen = set()
    for b in s.breaks:
        period_key(b.period, s.frequency)
        if not b.reason or b.period in seen:
            raise ModelError(f"{sid}: break needs a reason and a unique period ({b.period})")
        seen.add(b.period)
    if s.layer == "source":
        if s.points or s.inputs or s.transforms or not s.observations:
            raise ModelError(f"{sid}: a source series holds observations only (no points, inputs, transforms)")
    elif s.observations or not s.points or not s.inputs or not s.transforms:
        raise ModelError(f"{sid}: a {s.layer} series needs points, lineage inputs and transforms, no observations")


def _check_observation(s: Series, o: Observation):
    where = f"{s.series_id} {o.period}"
    if (o.series_id, o.currency, o.unit, o.definition_id) != (s.series_id, s.currency, s.unit, s.definition_id):
        raise CurrencyMismatch(f"{where}: observation currency/unit/definition differs from the series")
    if not (isinstance(o.source_id, str) and o.source_id and isinstance(o.vintage, str) and o.vintage):
        raise ModelError(f"{where}: provenance (source_id, vintage) is required")
    if not (isinstance(o.raw_sha256, str) and _HEX.fullmatch(o.raw_sha256)):
        raise ModelError(f"{where}: raw_sha256 must be 64 lowercase hex characters")
    try:
        stamp = datetime.fromisoformat(o.retrieved_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ModelError(f"{where}: retrieved_at must be an ISO-8601 timestamp") from None
    if stamp.tzinfo is None:
        raise ModelError(f"{where}: retrieved_at needs a timezone")


def validate_series(s: Series) -> None:
    """Raise ModelError on the first violation: ids, order, frequency, units, provenance, quality, flags."""
    _check_meta(s)
    previous = None
    for row in _rows(s):
        key = period_key(row.period, s.frequency)
        if previous is not None and key == previous:
            raise ModelError(f"{s.series_id}: duplicate period {row.period}")
        if previous is not None and key < previous:
            raise ModelError(f"{s.series_id}: periods not in ascending order at {row.period}")
        previous = key
        if row.value is None and s.layer == "source":
            raise ModelError(f"{s.series_id} {row.period}: source observations need a value; a gap is an absent period")
        if row.value is not None and (not row.value.is_finite() or row.value <= 0):
            raise ModelError(f"{s.series_id} {row.period}: value must be positive and finite")
        if row.quality not in QUALITY:
            raise ModelError(f"{s.series_id} {row.period}: quality must be one of {QUALITY}")
        if any(not isinstance(f, str) or not _FLAG.fullmatch(f) for f in row.flags):
            raise ModelError(f"{s.series_id} {row.period}: malformed flag in {row.flags!r}")
        if s.layer == "source":
            _check_observation(s, row)
    if s.layer == "source" and len({o.vintage for o in s.observations}) != 1:
        raise RevisionError(f"{s.series_id}: one series object holds exactly one vintage")
    for ref in s.inputs:
        if len(ref) != 2 or not _ID.fullmatch(str(ref[0])) or not _HEX.fullmatch(str(ref[1])):
            raise ModelError(f"{s.series_id}: malformed lineage input {ref!r}")


def coverage_report(s: Series, start=None, end=None) -> dict:
    """Explicit completeness report. Gaps are listed, never filled."""
    present = [r.period for r in _rows(s) if r.value is not None]
    if not present and (start is None or end is None):
        raise ModelError(f"{s.series_id}: no values and no explicit expected range")
    first, last = start or present[0], end or present[-1]
    expected = expected_periods(first, last, s.frequency)
    have = set(present)
    missing = [p for p in expected if p not in have]
    outside = [p for p in present if p not in set(expected)]
    return {"series_id": s.series_id, "frequency": s.frequency, "start": first, "end": last,
            "expected": len(expected), "present": len(expected) - len(missing), "missing": missing,
            "outside_range": outside, "complete": not missing,
            "coverage": dec_str(Decimal(len(expected) - len(missing)) / Decimal(len(expected)))}


def convert_frequency(series: Series, target: str):
    """Guard, not a converter: frequencies are never converted (no annual->monthly, no up-sampling).

    Daily -> monthly exists only as the documented aggregation monthly_mean().
    """
    raise FrequencyError(f"{series.series_id}: {series.frequency} -> {target} conversion is not allowed; "
                         "annual values stay annual, gaps stay null (use monthly_mean for daily sources)")


def detect_revisions(old: Series, new: Series) -> tuple:
    """Compare two vintages of one source series. Revisions are flagged, never overwritten."""
    if old.layer != "source" or new.layer != "source" or old.series_id != new.series_id:
        raise RevisionError("revision detection needs two source vintages of the same series_id")
    validate_series(old)
    validate_series(new)
    ov, nv = old.observations[0].vintage, new.observations[0].vintage
    fresh = {o.period: o for o in new.observations}
    found = []
    for o in old.observations:
        n = fresh.get(o.period)
        if n is None:
            kind = "dropped"
        elif n.value != o.value:
            kind = "value_changed"
        elif n.raw_sha256 != o.raw_sha256:
            kind = "hash_changed"
        else:
            continue
        found.append(Revision(old.series_id, o.period, kind, dec_str(o.value),
                              None if n is None else dec_str(n.value), ov, nv))
    if ov == nv and found:
        raise RevisionError(f"{old.series_id}: vintage {ov!r} was re-issued with different content")
    return tuple(found)


def require_no_revisions(revisions) -> None:
    if revisions:
        listing = ", ".join(f"{r.period}:{r.kind}" for r in revisions[:5])
        raise RevisionError(f"{revisions[0].series_id}: {len(revisions)} source revision(s) need human "
                            f"review before acceptance ({listing})")


# ---- layer 2: documented normalizations ----------------------------------------------------------
def _vals(s: Series) -> dict:
    return {r.period: r for r in _rows(s) if r.value is not None}


def _union_breaks(*series, month=False) -> tuple:
    """Carry every input break through, one entry per period (reasons joined)."""
    merged: dict = {}
    for s in series:
        for b in s.breaks:
            period = b.period[:7] if month else b.period
            merged.setdefault(period, []).append(f"{s.series_id}: {b.reason}")
    return tuple(Break(p, "; ".join(r)) for p, r in sorted(merged.items()))


def _build(base: Series, series_id, layer, points, inputs, transform, **changes) -> Series:
    out = Series(series_id=series_id, layer=layer, asset_class=changes.pop("asset_class", base.asset_class),
                 frequency=changes.pop("frequency", base.frequency), currency=changes.pop("currency", base.currency),
                 unit=changes.pop("unit", base.unit), definition_id=changes.pop("definition_id", base.definition_id),
                 kind=changes.pop("kind", base.kind), basis=changes.pop("basis", base.basis),
                 index_base=changes.pop("index_base", None), breaks=changes.pop("breaks", base.breaks),
                 points=tuple(points), inputs=tuple((s.series_id, series_sha256(s)) for s in inputs),
                 transforms=tuple(base.transforms) + (transform,) if base.layer != "source" else (transform,))
    validate_series(out)
    return out


def _gap(period) -> Point:
    return Point(period, None, "UNRESOLVED", ("MISSING_INPUT",))


def redenominate_nlg_to_eur(s: Series, *, series_id: str) -> Series:
    """Apply the fixed constant 2.20371 NLG/EUR exactly once and record it."""
    validate_series(s)
    if any(t.get("op") == "redenominate" for t in s.transforms):
        raise CurrencyMismatch(f"{s.series_id}: redenomination already applied; it must be applied exactly once")
    if s.currency != "NLG":
        raise CurrencyMismatch(f"{s.series_id}: redenomination needs currency NLG, got {s.currency}")
    with localcontext() as ctx:
        ctx.prec = PREC
        points = [Point(r.period, r.value / NLG_PER_EUR, r.quality, tuple(sorted(set(r.flags) | {"REDENOMINATED"})))
                  if r.value is not None else r for r in _rows(s)]
    step = {"op": "redenominate", "from": "NLG", "to": "EUR", "constant": dec_str(NLG_PER_EUR),
            "formula": "eur = nlg / constant", "applied": 1}
    return _build(s, series_id, "normalized", points, [s], step, currency="EUR",
                  unit=s.unit.replace("NLG", "EUR", 1), breaks=s.breaks)


def convert_currency(price: Series, rate: Series, *, to_currency: str, series_id: str) -> Series:
    """price / rate with an explicit rate series quoted '<FROM>_per_<TO>' at the same frequency."""
    validate_series(price)
    validate_series(rate)
    if {price.currency, to_currency} == {"NLG", "EUR"}:
        raise CurrencyMismatch("NLG/EUR is a fixed redenomination, not a market rate; use redenominate_nlg_to_eur")
    if price.currency in ("INDEX", "NONE") or rate.kind != "fx_rate":
        raise CurrencyMismatch("conversion needs a monetary price and an fx_rate series")
    if rate.unit != f"{price.currency}_per_{to_currency}":
        raise CurrencyMismatch(f"rate unit {rate.unit!r} cannot convert {price.currency} to {to_currency} "
                               f"(expected {price.currency}_per_{to_currency})")
    if rate.frequency != price.frequency:
        raise FrequencyError(f"rate is {rate.frequency}, price is {price.frequency}: aggregate the rate first")
    pv, rv = _vals(price), _vals(rate)
    if not set(pv) & set(rv):
        raise OverlapError(f"{price.series_id} and {rate.series_id} share no period")
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for p in (r.period for r in _rows(price)):
            if p in pv and p in rv:
                points.append(Point(p, pv[p].value / rv[p].value, worst_quality(pv[p].quality, rv[p].quality),
                                    tuple(sorted(set(pv[p].flags) | set(rv[p].flags)))))
            else:
                points.append(_gap(p))
    step = {"op": "convert_currency", "from": price.currency, "to": to_currency, "rate_series": rate.series_id,
            "rate_unit": rate.unit, "formula": "value / rate"}
    return _build(price, series_id, "normalized", points, [price, rate], step, currency=to_currency,
                  unit=price.unit.replace(price.currency, to_currency, 1),
                  breaks=_union_breaks(price, rate))


def monthly_mean(daily: Series, *, min_coverage: Decimal, series_id: str) -> Series:
    """Arithmetic monthly mean of daily values. min_coverage (share of calendar days) is explicit and recorded.

    A month below the threshold becomes an explicit null, never a partial or filled value.
    """
    validate_series(daily)
    if daily.frequency != "daily":
        raise FrequencyError(f"{daily.series_id}: monthly_mean needs a daily series")
    threshold = to_decimal(min_coverage, "min_coverage")
    if not 0 < threshold <= 1:
        raise ModelError("min_coverage must be in (0, 1]")
    groups: dict = {}
    if not _vals(daily):
        raise ModelError(f"{daily.series_id}: no daily values to aggregate")
    for r in _vals(daily).values():
        groups.setdefault(r.period[:7], []).append(r)
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for month in expected_periods(min(groups), max(groups), "monthly"):
            rows = groups.get(month, [])
            total = monthrange(int(month[:4]), int(month[5:]))[1]
            if rows and Decimal(len(rows)) / total >= threshold:
                points.append(Point(month, sum(r.value for r in rows) / len(rows),
                                    worst_quality(*(r.quality for r in rows)),
                                    tuple(sorted({f for r in rows for f in r.flags} | {f"DAYS:{len(rows)}/{total}"}))))
            else:
                points.append(Point(month, None, "UNRESOLVED", ("INSUFFICIENT_DAILY_COVERAGE",)))
    step = {"op": "monthly_mean", "rule": "arithmetic mean of available days", "min_coverage": dec_str(threshold)}
    return _build(daily, series_id, "normalized", points, [daily], step, frequency="monthly",
                  breaks=_union_breaks(daily, month=True))


def weighted_half_year_mean(price: Series, weights: Series, *, series_id: str) -> Series:
    """Transaction-weighted semiannual mean of monthly averages: sum(price*weight)/sum(weight).

    Both inputs are monthly and aligned. A half-year needs all six months with positive weights; an incomplete
    half-year becomes an explicit null, never a partial value. This is the only monthly -> semiannual step.
    """
    validate_series(price)
    validate_series(weights)
    if price.frequency != "monthly" or weights.frequency != "monthly":
        raise FrequencyError("weighted_half_year_mean needs monthly price and monthly weights")
    _expect(price, "price", kind="average_price")
    _expect(weights, "weights", kind="transaction_count")
    pv, wv = _vals(price), _vals(weights)
    halves: dict = {}
    for month in sorted(set(pv) | set(wv)):
        half = f"{month[:4]}-H{1 if int(month[5:]) <= 6 else 2}"
        halves.setdefault(half, []).append(month)
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for half in expected_periods(min(halves, key=lambda h: period_key(h, "semiannual")),
                                     max(halves, key=lambda h: period_key(h, "semiannual")), "semiannual"):
            first = 1 if half.endswith("H1") else 7
            months = [f"{half[:4]}-{m:02d}" for m in range(first, first + 6)]
            if all(m in pv and m in wv for m in months):
                total = sum(wv[m].value for m in months)
                mean = sum(pv[m].value * wv[m].value for m in months) / total
                points.append(Point(half, mean, worst_quality(*(pv[m].quality for m in months), *(wv[m].quality for m in months)),
                                    tuple(sorted({f for m in months for f in pv[m].flags} | {"MONTHS:6/6"}))))
            else:
                points.append(Point(half, None, "UNRESOLVED", ("INCOMPLETE_HALF_YEAR",)))
    step = {"op": "weighted_half_year_mean", "formula": "sum(price*count)/sum(count) over the six months",
            "weights": weights.series_id}
    return _build(price, series_id, "normalized", points, [price, weights], step, frequency="semiannual",
                  breaks=_union_breaks(price, month=False))


def statistic_ratio(median: Series, mean: Series, *, series_id: str) -> Series:
    """Ratio median / mean of two DIFFERENT statistics at the same frequency, currency and unit.

    The relative gap in percent is (ratio - 1) * 100; the ratio is stored because model values must be positive.
    It documents how far apart the NVM median and the CBS mean are. It is not a conversion or a combined
    series; the result has kind statistic_ratio and carries the flag STATISTICS_DIFFER.
    """
    validate_series(median)
    validate_series(mean)
    _expect(median, "median", kind="median_price")
    _expect(mean, "mean", kind="average_price")
    if median.currency != mean.currency or median.unit != mean.unit:
        raise CurrencyMismatch(f"{median.series_id} ({median.currency}/{median.unit}) vs {mean.series_id} "
                               f"({mean.currency}/{mean.unit}): compare in one currency and unit")
    if median.frequency != mean.frequency:
        raise FrequencyError(f"{median.frequency} vs {mean.frequency}: frequencies are never converted or mixed")
    if median.basis != mean.basis:
        raise DefinitionMismatch("nominal and real series cannot be compared")
    vm, vc = _vals(median), _vals(mean)
    common = sorted(set(vm) & set(vc), key=lambda p: period_key(p, median.frequency))
    if not common:
        raise OverlapError(f"{median.series_id} and {mean.series_id} have no overlapping period")
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for p in expected_periods(common[0], common[-1], median.frequency):
            if p in vm and p in vc:
                value = vm[p].value / vc[p].value
                points.append(Point(p, value, worst_quality(vm[p].quality, vc[p].quality),
                                    tuple(sorted(set(vm[p].flags) | set(vc[p].flags) | {"STATISTICS_DIFFER"}))))
            else:
                points.append(_gap(p))
    step = {"op": "statistic_ratio", "formula": "median / mean", "gap_percent": "(ratio - 1) * 100", "span": [common[0], common[-1]],
            "caveat": "median of broker-related sales vs mean of registered sales: not the same statistic"}
    return _build(median, series_id, "derived", points, [median, mean], step, currency="NONE", unit="ratio",
                  kind="statistic_ratio", definition_id="derived_statistic_ratio",
                  breaks=_union_breaks(median, mean))


_PER_YEAR = {"annual": 1, "semiannual": 2, "monthly": 12}


def growth_ratio(s: Series, *, basis: str, series_id: str) -> Series:
    """value / value one step (sequential) or one year (year_over_year) earlier; percent growth = (ratio - 1) * 100.

    The predecessor must be the exact previous period of the same series; a missing predecessor gives an
    explicit null. The first periods without a predecessor are simply absent, never filled.
    """
    validate_series(s)
    if s.frequency not in _PER_YEAR:
        raise FrequencyError(f"{s.series_id}: growth needs annual, semiannual or monthly data")
    if basis not in ("sequential", "year_over_year"):
        raise ModelError("basis must be 'sequential' or 'year_over_year'")
    if s.currency == "INDEX" or s.kind in ("statistic_ratio", "growth_ratio"):
        raise DefinitionMismatch(f"{s.series_id}: growth of a {s.kind} series is not defined here")
    lag = 1 if basis == "sequential" else _PER_YEAR[s.frequency]
    vals = _vals(s)
    keys = {p: period_key(p, s.frequency) for p in vals}
    by_key = {k: p for p, k in keys.items()}
    first = min(keys.values()) + lag
    last = max(keys.values())
    if first > last:
        raise OverlapError(f"{s.series_id}: too short for {basis} growth")
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for k in range(first, last + 1):
            p = period_label(k, s.frequency)
            q = by_key.get(k - lag)
            if p in vals and q is not None:
                points.append(Point(p, vals[p].value / vals[q].value, worst_quality(vals[p].quality, vals[q].quality),
                                    tuple(sorted(set(vals[p].flags) | set(vals[q].flags)))))
            else:
                points.append(_gap(p))
    step = {"op": "growth_ratio", "basis": basis, "lag_periods": lag, "formula": "value / value[t-lag]",
            "growth_percent": "(ratio - 1) * 100"}
    return _build(s, series_id, "derived", points, [s], step, currency="NONE", unit="ratio",
                  kind="growth_ratio", definition_id=f"derived_growth_{basis}", breaks=s.breaks)


def rebase_index(s: Series, base_period: str, *, series_id: str) -> Series:
    """Rebase to 100 at an explicit period. The result is an index and cannot be read as a price."""
    validate_series(s)
    base = _vals(s).get(base_period)
    if base is None:
        raise OverlapError(f"{s.series_id}: no value at base period {base_period}")
    with localcontext() as ctx:
        ctx.prec = PREC
        points = [Point(r.period, r.value * 100 / base.value, r.quality, r.flags) if r.value is not None else r
                  for r in _rows(s)]
    step = {"op": "rebase_index", "base_period": base_period, "formula": "value * 100 / value[base]"}
    return _build(s, series_id, "normalized", points, [s], step, currency="INDEX", unit="index_points",
                  index_base=f"{base_period}=100")


def deflate(s: Series, cpi: Series, *, base_period: str, series_id: str) -> Series:
    """Nominal -> real with an explicit CPI series; the result carries basis 'real' and is never mixed with nominal."""
    validate_series(s)
    validate_series(cpi)
    if s.basis != "nominal" or cpi.kind != "cpi" or cpi.frequency != s.frequency:
        raise DefinitionMismatch("deflate needs a nominal series and a cpi series of the same frequency")
    cv = _vals(cpi)
    if base_period not in cv:
        raise OverlapError(f"{cpi.series_id}: no CPI value at base period {base_period}")
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for r in _rows(s):
            c = cv.get(r.period)
            points.append(Point(r.period, r.value * cv[base_period].value / c.value, worst_quality(r.quality, c.quality),
                                r.flags) if r.value is not None and c is not None else _gap(r.period))
    step = {"op": "deflate", "cpi_series": cpi.series_id, "base_period": base_period,
            "formula": "value * cpi[base] / cpi[t]"}
    return _build(s, series_id, "normalized", points, [s, cpi], step, basis="real", breaks=_union_breaks(s, cpi),
                  unit=f"{s.unit}@{base_period}")


# ---- layer 3: derived comparisons ----------------------------------------------------------------
def _expect(s: Series, role: str, *, kind=None, unit=None, currencies=None):
    if kind and s.kind != kind:
        raise DefinitionMismatch(f"{role} {s.series_id}: kind {s.kind!r}, expected {kind!r}")
    if unit and s.unit != unit:
        raise CurrencyMismatch(f"{role} {s.series_id}: unit {s.unit!r}, expected {unit!r}")
    if currencies and s.currency not in currencies:
        raise CurrencyMismatch(f"{role} {s.series_id}: currency {s.currency!r} not in {currencies}")


def _derived_class(a: Series, b: Series) -> str:
    for s in (a, b):
        if s.asset_class in RESTRICTED_CLASSES:
            return s.asset_class
    return a.asset_class


def _combine(a: Series, b: Series, fn, *, series_id, step, **changes) -> Series:
    validate_series(a)
    validate_series(b)
    if a.frequency != b.frequency:
        raise FrequencyError(f"{a.frequency} vs {b.frequency}: frequencies are never converted or mixed")
    if a.basis != b.basis:
        raise DefinitionMismatch(f"{a.basis} vs {b.basis}: nominal and real series cannot be combined")
    if frozenset({a.kind, b.kind}) in INCOMPATIBLE_KINDS:
        raise DefinitionMismatch(f"definition kinds {a.kind!r} and {b.kind!r} cannot be mixed")
    va, vb = _vals(a), _vals(b)
    common = sorted(set(va) & set(vb), key=lambda p: period_key(p, a.frequency))
    if not common:
        raise OverlapError(f"{a.series_id} and {b.series_id} have no overlapping period")
    points = []
    with localcontext() as ctx:
        ctx.prec = PREC
        for p in expected_periods(common[0], common[-1], a.frequency):
            if p in va and p in vb:
                points.append(Point(p, fn(va[p].value, vb[p].value), worst_quality(va[p].quality, vb[p].quality),
                                    tuple(sorted(set(va[p].flags) | set(vb[p].flags)))))
            else:
                points.append(_gap(p))
    step = {**step, "span": [common[0], common[-1]]}
    return _build(a, series_id, "derived", points, [a, b], step, asset_class=_derived_class(a, b),
                  breaks=_union_breaks(a, b), **changes)


def grams_per_house(house: Series, gold: Series, *, series_id="grams_per_house") -> Series:
    """house * 31.1034768 / gold_price_per_oz, same currency and same basis."""
    _expect(house, "house", kind="average_price", currencies=("EUR", "NLG", "USD"))
    _expect(gold, "gold", kind="spot_price", unit=f"{house.currency}_per_troy_oz")
    return _combine(house, gold, lambda h, g: h * TROY_OUNCE_GRAMS / g, series_id=series_id,
                    step={"op": "grams_per_house", "formula": "house * 31.1034768 / gold_per_oz"},
                    currency="NONE", unit="gram", kind="spot_price", definition_id="derived_grams_per_house")


def sats_per_house(house: Series, btc: Series, *, series_id="sats_per_house") -> Series:
    """house_eur / btc_eur * 100000000 (derivation only; publication stays denied without a release record)."""
    _expect(house, "house", kind="average_price", currencies=("EUR",), unit="EUR")
    _expect(btc, "btc", kind="spot_price", unit="EUR_per_BTC")
    return _combine(house, btc, lambda h, b: h / b * SATOSHIS_PER_BTC, series_id=series_id,
                    step={"op": "sats_per_house", "formula": "house_eur / btc_eur * 100000000"},
                    currency="NONE", unit="satoshi", kind="spot_price", definition_id="derived_sats_per_house")


def common_base_period(a: Series, b: Series, base_period=None) -> str:
    """The shared baseline, detected from the actual overlap. Non-overlapping ranges are refused."""
    if a.frequency != b.frequency:
        raise FrequencyError(f"{a.frequency} vs {b.frequency}: no common baseline")
    common = sorted(set(_vals(a)) & set(_vals(b)), key=lambda p: period_key(p, a.frequency))
    if not common:
        raise OverlapError(f"{a.series_id} and {b.series_id} do not overlap; no common baseline exists")
    if base_period is not None and base_period not in common:
        raise OverlapError(f"base period {base_period} is outside the overlap {common[0]}..{common[-1]}")
    return base_period or common[0]


def rebase_pair(a: Series, b: Series, base_period=None):
    base = common_base_period(a, b, base_period)
    return (rebase_index(a, base, series_id=f"{a.series_id}_idx"), rebase_index(b, base, series_id=f"{b.series_id}_idx"))


def relative_performance(a_idx: Series, h_idx: Series, *, series_id="relative_performance") -> Series:
    """100 * A_index / housing_index; both must be rebased to the SAME explicit base (value 100 there)."""
    for s in (a_idx, h_idx):
        validate_series(s)
        if s.currency != "INDEX":
            raise CurrencyMismatch(f"{s.series_id}: relative performance needs index series; rebase_index is the explicit step")
    if a_idx.index_base != h_idx.index_base:
        raise CurrencyMismatch(f"index bases differ ({a_idx.index_base} vs {h_idx.index_base}); "
                               "rebase both to a common base with rebase_pair")
    base = a_idx.index_base[:-4]
    for s in (a_idx, h_idx):
        v = _vals(s).get(base)
        if v is None or v.value != 100:
            raise CurrencyMismatch(f"{s.series_id}: value at base {base} is not 100")
    return _combine(a_idx, h_idx, lambda a, h: Decimal(100) * (a / 100) / (h / 100), series_id=series_id,
                    step={"op": "relative_performance", "base_period": base,
                          "formula": "100 * A_index / housing_index"},
                    currency="INDEX", unit="index_points", index_base=f"{base}=100",
                    definition_id="derived_relative_performance")


def relative_performance_from_levels(a: Series, h: Series, base_period=None, **kw) -> Series:
    return relative_performance(*rebase_pair(a, h, base_period), **kw)


# ---- layer 4: publication gate -------------------------------------------------------------------
def is_restricted(s: Series) -> bool:
    ids = [s.series_id] + [i[0] for i in s.inputs]
    tokens = {t for i in ids for t in re.split(r"[^a-z0-9]+", i.lower())}
    return s.asset_class in RESTRICTED_CLASSES or bool(tokens & RESTRICTED_TOKENS)


def validate_release(r: ReleaseRecord) -> None:
    ok = (isinstance(r.release_id, str) and r.release_id and isinstance(r.authorizer, str) and r.authorizer.strip()
          and isinstance(r.decision_ref, str) and r.decision_ref.strip() and isinstance(r.release_sha256, str)
          and _HEX.fullmatch(r.release_sha256) and r.series_ids and set(r.restricted_authorized) <= set(r.series_ids))
    if not ok:
        raise PublicationDenied(f"release record {getattr(r, 'release_id', '?')!r} is incomplete")
    try:
        date.fromisoformat(r.authorized_on)
    except (TypeError, ValueError):
        raise PublicationDenied(f"release {r.release_id}: authorized_on must be an ISO date") from None


def publication_gate(candidates, records=None) -> tuple:
    """Return the candidates a release record approves, else raise PublicationDenied (fail-closed)."""
    records = ALLOWLIST if records is None else tuple(records)
    by_id = {}
    for s in candidates:
        if s.series_id in by_id:
            raise PublicationDenied(f"duplicate candidate {s.series_id}")
        by_id[s.series_id] = s
    owner = {}
    for r in records:
        validate_release(r)
        for sid in r.series_ids:
            if sid in owner:
                raise PublicationDenied(f"{sid} is listed by two release records")
            owner[sid] = r
    for sid, s in by_id.items():
        r = owner.get(sid)
        if r is None:
            raise PublicationDenied(f"{sid}: not on the publication allowlist (default is empty)")
        if s.layer == "source":
            raise PublicationDenied(f"{sid}: raw source observations are never published")
        if is_restricted(s) and sid not in r.restricted_authorized:
            raise PublicationDenied(f"{sid}: bitcoin/equity series need explicit authorization in release {r.release_id}")
        if any(p.quality == "UNRESOLVED" and p.value is not None for p in s.points):
            raise PublicationDenied(f"{sid}: carries UNRESOLVED quality values")
        validate_series(s)
    for r in {id(owner[s]): owner[s] for s in by_id}.values():
        missing = [i for i in r.series_ids if i not in by_id]
        if missing:
            raise PublicationDenied(f"release {r.release_id}: members {missing} not supplied; hash cannot be verified")
        if release_hash([by_id[i] for i in r.series_ids]) != r.release_sha256:
            raise PublicationDenied(f"release {r.release_id}: content hash differs from the authorized hash")
    return tuple(by_id[k] for k in sorted(by_id))


def publication_rows(approved) -> dict:
    """PROPOSED monthly.json-style projection of approved series (Decimal strings, null for gaps)."""
    approved = list(approved)
    if any(s.frequency != "monthly" for s in approved):
        raise FrequencyError("publication rows are monthly only; annual series stay annual")
    periods = sorted({p.period for s in approved for p in s.points})
    lookup = {s.series_id: {p.period: p.value for p in s.points} for s in approved}
    return {"data": [{"period": p, **{k: (None if v.get(p) is None else dec_str(v[p])) for k, v in sorted(lookup.items())}}
                     for p in periods]}


# ---- bundles (used by tools/hist_model_check.py) -------------------------------------------------
def validate_bundle(bundle: dict) -> list:
    """Return a list of violation messages (empty when clean). Never raises for model violations."""
    errors = []
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        return [f"bundle schema must be {SCHEMA!r}"]
    parsed = {}
    for raw in bundle.get("series", []):
        try:
            s = series_from_dict(raw)
            validate_series(s)
            parsed[s.series_id] = s
        except (ModelError, TypeError, KeyError) as exc:
            errors.append(f"series {raw.get('series_id', '?') if isinstance(raw, dict) else '?'}: {exc}")
    for s in parsed.values():
        for sid, digest in s.inputs:
            if sid not in parsed:
                errors.append(f"{s.series_id}: lineage input {sid} is not in the bundle")
            elif series_sha256(parsed[sid]) != digest:
                errors.append(f"{s.series_id}: lineage hash of {sid} does not match")
    for raw in bundle.get("releases", []):
        try:
            record = ReleaseRecord(**{**raw, "series_ids": tuple(raw["series_ids"]),
                                      "restricted_authorized": tuple(raw.get("restricted_authorized", ()))})
            publication_gate([parsed[i] for i in record.series_ids if i in parsed], [record])
        except (ModelError, TypeError, KeyError) as exc:
            errors.append(f"release {raw.get('release_id', '?') if isinstance(raw, dict) else '?'}: {exc}")
    return errors
