"""HIST-03 research-only precision / deviation analysis (aggregates only).

Pure functions plus a CI entry point. No publication, no repository data writes,
no full series in any output. Raw workbook bytes stay in memory.
"""
import re
from decimal import Decimal
from statistics import median

SUBPERIODS = (("1975-79", "1975-01", "1979-12"), ("1980-84", "1980-01", "1984-12"),
              ("1985-89", "1985-01", "1989-12"), ("1990-94", "1990-01", "1994-12"),
              ("1995-99", "1995-01", "1999-12"))
ROUNDING_HALF_WIDTH = Decimal("0.5")  # assumption (i): values rounded to whole USD
GRAMS_PER_TROY_OZ = Decimal("31.1034768")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


class PrecisionError(ValueError):
    pass


def _check(series, name):
    if not isinstance(series, dict):
        raise PrecisionError(f"INVALID_INPUT {name} not a dict")
    for k, v in series.items():
        if not isinstance(k, str) or not _MONTH.fullmatch(k):
            raise PrecisionError(f"INVALID_MONTH_KEY {name}")
        if not isinstance(v, Decimal) or not v.is_finite():
            raise PrecisionError(f"INVALID_VALUE {name} {k}")


def _f(x):
    return None if x is None else float(round(x, 6))


def _block(rows):
    """rows: list of (month, diff, rel_pct). Aggregates only."""
    if not rows:
        return {"n": 0, "mean_signed_diff": None, "mean_abs": None, "median_abs": None, "max_abs": None,
                "mean_rel_pct": None, "median_rel_pct": None, "max_rel_pct": None, "share_within_0_5_usd": None}
    n = len(rows)
    diffs = [r[1] for r in rows]
    abs_d = [abs(d) for d in diffs]
    rel = [abs(r[2]) for r in rows]
    return {"n": n, "mean_signed_diff": _f(sum(diffs) / n), "mean_abs": _f(sum(abs_d) / n),
            "median_abs": _f(median(abs_d)), "max_abs": _f(max(abs_d)),
            "mean_rel_pct": _f(sum(rel) / n), "median_rel_pct": _f(median(rel)), "max_rel_pct": _f(max(rel)),
            "share_within_0_5_usd": _f(Decimal(sum(1 for d in abs_d if d <= ROUNDING_HALF_WIDTH)) / n)}


def deviation_stats(wb, other):
    """Compare two month->Decimal dicts on common months. diff = wb - other (USD/oz);
    relative = |diff| / |other| * 100 (%). Fail-closed on empty overlap / zero reference."""
    _check(wb, "wb")
    _check(other, "other")
    common = sorted(set(wb) & set(other))
    if not common:
        raise PrecisionError("NO_COMMON_MONTHS")
    rows = []
    for m in common:
        if other[m] == 0:
            raise PrecisionError("ZERO_REFERENCE_VALUE")
        d = wb[m] - other[m]
        rows.append((m, d, d / other[m] * 100))
    out = _block(rows)
    out["only_wb"] = len(set(wb) - set(other))
    out["only_other"] = len(set(other) - set(wb))
    out["subperiods"] = {name: _block([r for r in rows if lo <= r[0] <= hi]) for name, lo, hi in SUBPERIODS}
    top = sorted(rows, key=lambda r: (-abs(r[1]), r[0]))[:3]
    out["top3_abs_diff"] = [{"month": m, "diff": _f(d)} for m, d, _ in top]
    return out
