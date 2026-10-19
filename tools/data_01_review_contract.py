"""DATA-01A proposal-only validator. No production imports, I/O or publication."""
import hashlib
import json
import math
from datetime import date

class ReviewBlocked(ValueError):
    pass

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def inspect(previous, incoming, *, source_id, approved_source_id,
            raw_bytes, expected_sha, complete_through, publish=False):
    if publish:
        raise ReviewBlocked("PUBLICATION_NOT_AUTHORIZED")
    if source_id != approved_source_id:
        raise ReviewBlocked("SOURCE_SWITCH_REQUIRES_APPROVAL")
    if not isinstance(raw_bytes, bytes) or not raw_bytes or digest(raw_bytes) != expected_sha:
        raise ReviewBlocked("SOURCE_HASH_MISMATCH")
    if not isinstance(previous, list) or not isinstance(incoming, list):
        raise ReviewBlocked("INVALID_PAYLOAD")
    def parse(rows):
        result = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"period", "metric", "value", "currency", "fx_direction"}:
                raise ReviewBlocked("INVALID_PAYLOAD")
            p, m, v = row["period"], row["metric"], row["value"]
            try:
                if not isinstance(p, str) or len(p) != 7 or p[4] != "-" or date.fromisoformat(p+"-01").strftime("%Y-%m") != p:
                    raise ValueError
            except (TypeError, ValueError):
                raise ReviewBlocked("INVALID_PERIOD") from None
            if not isinstance(m, str) or not m or isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or v <= 0:
                raise ReviewBlocked("INVALID_VALUE")
            if row["currency"] != "EUR" or row["fx_direction"] != "USD_PER_EUR":
                raise ReviewBlocked("FX_DIRECTION_OR_CURRENCY")
            k = (p, m)
            if k in result:
                raise ReviewBlocked("DUPLICATE_PERIOD_METRIC")
            result[k] = v
        return result
    old, new = parse(previous), parse(incoming)
    if not isinstance(complete_through, str) or len(complete_through) != 7:
        raise ReviewBlocked("INVALID_COMPLETENESS_CUTOFF")
    revisions = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    if revisions:
        raise ReviewBlocked("HISTORICAL_REVISION_REVIEW_REQUIRED")
    missing = sorted(old.keys() - new.keys())
    if missing:
        raise ReviewBlocked("MISSING_APPROVED_OBSERVATIONS")
    pending = sorted(k for k in new.keys() - old.keys() if k[0] > complete_through)
    if pending:
        raise ReviewBlocked("INCOMPLETE_OR_FUTURE_MONTH")
    additions = sorted(new.keys() - old.keys())
    periods = sorted({k[0] for k in new})
    if periods:
        y, m = map(int, periods[0].split("-"))
        expected = []
        while f"{y:04d}-{m:02d}" <= periods[-1]:
            expected.append(f"{y:04d}-{m:02d}")
            m += 1
            if m == 13:
                y, m = y+1, 1
        if periods != expected:
            raise ReviewBlocked("MISSING_SOURCE_MONTH")
    # Never return prices or a publishable dataset from this design validator.
    return {"status": "REVIEW_ONLY", "append_count": len(additions),
            "existing_count": len(old), "source_sha256": digest(raw_bytes)}
