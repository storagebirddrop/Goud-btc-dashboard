"""HIST-04 research-only explanation of three World Bank vs Bank of England gold outliers.

Months: 1980-12, 1983-07, 1985-03. Reuses tools.hist_02_acquire (allowlist, 15 MB limit,
sha256, no off-allowlist redirects) and the parsers of hist_03_second_source /
hist_03_worldbank_validate (read-only imports). Decimal throughout. No interpolation, no
forward-fill: a month without data stays absent. Raw bytes stay in memory; the output holds
aggregates/metadata only (means, counts, dates of matching days, residuals).
A numeric match within TOLERANCE is evidence of reproduction, not a methodology decision.
"""
import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from statistics import median

from tools import hist_02_acquire
from tools import hist_03_second_source as ss

OUTLIER_MONTHS = ("1980-12", "1983-07", "1985-03")
TOLERANCE = Decimal("0.5")        # whole-USD rounding of the World Bank value
PLAUSIBLE_BAND = Decimal("2.0")   # residual up to this is "close but not reproduced"
CONTEXT = 3
SCALE_GUARD = Decimal("0.25")     # daily series whose monthly mean is >25% off BoE monthly is not a USD/oz gold series
MAX_DAILY_CODES = 12
CATEGORY_URL = ("https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?Travel=NIxAZxI1x"
                "&FromCategoryList=Yes&NewMeaningId=RGOLD&CategId=6&HighlightCatValueDisplay=Gold+price")
# Pattern guesses only (verified in CI by a successful parse of DATE,<code>); the category page adds more.
GUESSED_CODES = ("XUDLGPD", "XUDAGPD", "XUDLGBD", "XUMLGPD")
CODE_RE = re.compile(r"\bXU[A-Z0-9]{4,8}\b")
hist_02_acquire.SOURCES["boe-gold-category"] = (CATEGORY_URL, "html")
hist_02_acquire.SOURCES["boe-gold-notes"] = (ss.BOE_NOTES, "html")


def daily_url(code):
    return ss.BOE_CSV.replace(ss.BOE_SERIES, code)


def register_daily(code):
    sid = "boe-gold-series-" + code
    hist_02_acquire.SOURCES[sid] = (daily_url(code), "csv")
    return sid


def discover_codes(raw):
    """Series codes (+ short label) found on the gold category page; documentation text only."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    found = {}
    for m in CODE_RE.finditer(text):
        found.setdefault(m.group(0), text[m.end():m.end() + 90].strip())
    return found


def notes_facts(raw, limit=14, width=600):
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"friday|fixing|average|daily|morning|afternoon|a\.m\.|p\.m\.|observation", s, re.I):
            out.append(s[:width])
        if len(out) >= limit:
            break
    return out


def month_of(d):
    return f"{d.year:04d}-{d.month:02d}"


def month_add(key, n):
    y, m = map(int, key.split("-"))
    i = y * 12 + (m - 1) + n
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def pct(diff, base):
    return None if base == 0 else str((diff / base * 100).quantize(Decimal("0.001")))


def compare(wb_v, other_v):
    """wb - other, absolute and percent of other; None when either side is absent (no filling)."""
    if wb_v is None or other_v is None:
        return None
    d = wb_v - other_v
    return {"other": str(other_v.quantize(Decimal("0.0001"))), "diff": str(d.quantize(Decimal("0.0001"))),
            "abs_diff": str(abs(d).quantize(Decimal("0.0001"))), "pct_of_other": pct(d, other_v),
            "within_half_usd": abs(d) <= TOLERANCE}


def context_rows(wb, boe, month, k=CONTEXT):
    rows = []
    for off in range(-k, k + 1):
        m = month_add(month, off)
        c = compare(wb.get(m), boe.get(m))
        rows.append({"offset": off, "month": m, "wb": str(wb[m]) if m in wb else None,
                     "boe_monthly": str(boe[m]) if m in boe else None,
                     "diff": c["diff"] if c else None, "pct": c["pct_of_other"] if c else None})
    return rows


def shift_test(wb, boe, month):
    """WB[m] against BoE[m-1], BoE[m], BoE[m+1] (month-shift hypothesis)."""
    return {str(off): compare(wb.get(month), boe.get(month_add(month, off))) for off in (-1, 0, 1)}


def daily_variants(daily, month):
    """Mean variants of one daily series for one calendar month. Absent month -> None."""
    days = sorted((d, v) for d, v in daily.items() if month_of(d) == month)
    if not days:
        return None
    vals = [v for _, v in days]

    def mean(xs):
        return (sum(xs, Decimal(0)) / len(xs)) if xs else None

    fri = [v for d, v in days if d.weekday() == 4]
    return {"n_days": len(days), "first_date": days[0][0].isoformat(), "last_date": days[-1][0].isoformat(),
            "mean_all": mean(vals), "mean_weekdays": mean([v for d, v in days if d.weekday() < 5]),
            "mean_fridays": mean(fri), "n_fridays": len(fri),
            "last_day": days[-1][1], "first_day": days[0][1], "median": Decimal(str(median(vals))),
            "min": min(vals), "max": max(vals)}


def combined_daily(a, b):
    """Per-day mean of two daily series (e.g. AM and PM) on common dates only; no filling."""
    return {d: (a[d] + b[d]) / 2 for d in sorted(set(a) & set(b))}


VARIANT_NAMES = ("mean_all", "mean_weekdays", "mean_fridays", "last_day", "first_day", "median", "min", "max")


def elsewhere_months(wb_v, series, month, limit=12):
    """Months (other than `month`) whose value is within TOLERANCE of wb_v: tests a copy/mix-up from another
    period. Coincidence-prone (many months), so informational only, never a proof by itself."""
    return [m for m, v in sorted(series.items()) if m != month and abs(wb_v - v) <= TOLERANCE][:limit]


def monthly_vs_daily_consistency(boe_monthly, daily):
    """Does the BoE monthly average equal the arithmetic mean of the BoE daily values per month?"""
    diffs = []
    for m in sorted(boe_monthly):
        var = daily_variants(daily, m)
        if var:
            diffs.append((abs(var["mean_all"] - boe_monthly[m]), m))
    if not diffs:
        return {"months": 0}
    worst = max(diffs)
    return {"months": len(diffs), "max_abs_diff": str(worst[0].quantize(Decimal("0.0001"))), "worst_month": worst[1],
            "months_over_0_01": sum(1 for d, _ in diffs if d > Decimal("0.01"))}


def variant_report(wb_v, var):
    out = {"n_days": var["n_days"], "first_date": var["first_date"], "last_date": var["last_date"],
           "n_fridays": var["n_fridays"], "daily_min": str(var["min"]), "daily_max": str(var["max"]),
           "wb_outside_daily_range": not (var["min"] <= wb_v <= var["max"]), "variants": {}}
    for name in VARIANT_NAMES:
        v = var[name]
        out["variants"][name] = None if v is None else compare(wb_v, v)
    return out


def matching_days(daily, month, wb_v):
    """Dates in the month whose daily value is within TOLERANCE of WB (metadata: dates only)."""
    return [d.isoformat() for d, v in sorted(daily.items()) if month_of(d) == month and abs(wb_v - v) <= TOLERANCE]


def classify(wb_v, boe_cmp, shift, variants_by_series):
    """PROVEN: some hypothesis reproduces WB within 0.5 USD while BoE[m] itself does not.
    PLAUSIBLE: best residual within PLAUSIBLE_BAND but not reproduced. Otherwise UNVERIFIED."""
    if wb_v is None or boe_cmp is None:
        return {"class": "UNVERIFIED", "reason": "MISSING_INPUT", "reproductions": []}
    if boe_cmp["within_half_usd"]:
        return {"class": "NOT_AN_OUTLIER", "reason": "within 0.5 USD of BoE monthly (rounding)",
                "reproductions": []}
    hits, residuals = [], []
    for off in ("-1", "1"):
        c = shift[off]
        if c:
            (hits if c["within_half_usd"] else residuals).append(("month_shift_BoE" + off, abs(Decimal(c["diff"]))))
    for series, rep in variants_by_series.items():
        for name, c in rep["variants"].items():
            if c:
                (hits if c["within_half_usd"] else residuals).append((f"{series}:{name}", abs(Decimal(c["diff"]))))
    if hits:
        return {"class": "PROVEN", "reason": "reproduces within 0.5 USD", "reproductions": [h[0] for h in hits]}
    best = min(residuals, key=lambda x: x[1]) if residuals else None
    if best and best[1] <= PLAUSIBLE_BAND:
        return {"class": "PLAUSIBLE", "reason": f"best residual {best[1]} USD ({best[0]}) > 0.5",
                "reproductions": []}
    return {"class": "UNVERIFIED", "reason": "no tested hypothesis within band" if best else "no alternative series",
            "best_residual": None if best is None else {"hypothesis": best[0], "abs_diff": str(best[1])},
            "reproductions": []}


def analyse_month(month, wb, boe, dailies):
    wb_v = wb.get(month)
    boe_cmp = compare(wb_v, boe.get(month))
    shift = shift_test(wb, boe, month)
    variants, excluded, goldlike = {}, [], {}
    boe_v = boe.get(month)
    for code, daily in dailies.items():
        var = daily_variants(daily, month)
        if var and wb_v is not None:
            if boe_v is not None and abs(var["mean_all"] - boe_v) > boe_v * SCALE_GUARD:
                excluded.append({"series": code, "mean_all": str(var["mean_all"].quantize(Decimal("0.0001"))),
                                 "reason": "SCALE_MISMATCH_NOT_A_USD_OZ_GOLD_SERIES"})
                continue
            goldlike[code] = daily
            variants[code] = variant_report(wb_v, var)
            variants[code]["days_within_half_usd_of_wb"] = matching_days(daily, month, wb_v)
    if len(goldlike) == 2 and wb_v is not None:
        (ca, da), (cb, db) = sorted(goldlike.items())
        var = daily_variants(combined_daily(da, db), month)
        if var:
            variants[f"{ca}+{cb}"] = variant_report(wb_v, var)
    return {"month": month, "wb": None if wb_v is None else str(wb_v),
            "boe_monthly": boe_cmp, "rounding_explains": bool(boe_cmp and boe_cmp["within_half_usd"]),
            "context": context_rows(wb, boe, month), "month_shift": shift, "daily": variants,
            "excluded_series": excluded,
            "wb_value_elsewhere_in_boe_monthly": None if wb_v is None else elsewhere_months(wb_v, boe, month),
            "classification": classify(wb_v, boe_cmp, shift, variants)}


def deviation_ranking(wb, boe, top=8):
    common = sorted(set(wb) & set(boe))
    diffs = sorted(((abs(wb[m] - boe[m]), m) for m in common), reverse=True)
    return {"common_months": len(common), "months_over_half_usd": sum(1 for d, _ in diffs if d > TOLERANCE),
            "top": [{"month": m, "abs_diff": str(d.quantize(Decimal("0.0001")))} for d, m in diffs[:top]]}


def is_daily(points):
    per = {}
    for d in points:
        per[month_of(d)] = per.get(month_of(d), 0) + 1
    return bool(per) and max(per.values()) > 1


def report_lines(s):
    """Compact human-readable summary (aggregates only) for the job log."""
    L = ["REPORT status=%s wb_months=%s" % (s["status"], s.get("world_bank", {}).get("months"))]
    L.append("REPORT failures=" + json.dumps(s["failures"]))
    L.append("REPORT discovered_codes=" + json.dumps(s["discovered_codes"]))
    L.append("REPORT daily_series=" + json.dumps(s["daily_series"], sort_keys=True))
    L.append("REPORT notes=" + json.dumps(s.get("boe_notes_facts", {}).get("sentences")))
    L.append("REPORT ranking=" + json.dumps(s.get("deviation_ranking")))
    L.append("REPORT monthly_vs_daily=" + json.dumps(s.get("monthly_vs_daily")))
    for r in s["results"]:
        L.append("MONTH %s wb=%s class=%s %s repro=%s" % (r["month"], r["wb"], r["classification"]["class"],
                 r["classification"]["reason"], r["classification"]["reproductions"]))
        L.append("  boe_monthly=" + json.dumps(r["boe_monthly"]))
        for c in r["context"]:
            L.append("  ctx %+d %s wb=%s boe=%s diff=%s pct=%s" % (c["offset"], c["month"], c["wb"], c["boe_monthly"], c["diff"], c["pct"]))
        for off, c in r["month_shift"].items():
            L.append("  shift %s: %s" % (off, json.dumps(c)))
        for code, rep in r["daily"].items():
            L.append("  daily %s n=%s fri=%s %s..%s match_days=%s" % (code, rep["n_days"], rep["n_fridays"], rep["first_date"],
                     rep["last_date"], rep.get("days_within_half_usd_of_wb")))
            for name, c in rep["variants"].items():
                L.append("    %s other=%s diff=%s within=%s" % (name, c["other"], c["diff"], c["within_half_usd"]))
        L.append("  excluded=" + json.dumps(r["excluded_series"]))
        L.append("  wb_value_elsewhere_in_boe_monthly=" + json.dumps(r["wb_value_elsewhere_in_boe_monthly"]))
        for code, rep in r["daily"].items():
            L.append("  range %s: min=%s max=%s wb_outside=%s" % (code, rep["daily_min"], rep["daily_max"],
                                                                 rep["wb_outside_daily_range"]))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args(argv)
    from tools.hist_03_worldbank_validate import parse as wb_parse
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    s = {"status": "RUNNING", "months": list(OUTLIER_MONTHS), "publication_authorized": False,
         "rights_status": "UNVERIFIED", "failures": [], "discovered_codes": {}, "daily_series": {}, "results": []}
    raw_wb, rec_wb = hist_02_acquire.fetch("world-bank-gold-history")
    wb = wb_parse(raw_wb)["series"]
    s["world_bank"] = {"sha256": rec_wb["sha256"], "bytes": rec_wb["bytes"], "months": len(wb)}
    codes = list(GUESSED_CODES)
    for sid, key in (("boe-gold-notes", "boe_notes_facts"), ("boe-gold-category", "category")):
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            if key == "category":
                found = discover_codes(raw)
                s["discovered_codes"] = found
                codes += [c for c in found if c not in codes]
                s["category_page"] = {"sha256": rec["sha256"], "bytes": rec["bytes"]}
            else:
                s[key] = {"sha256": rec["sha256"], "bytes": rec["bytes"], "sentences": notes_facts(raw)}
        except hist_02_acquire.AcquisitionError as exc:
            s["failures"].append({"source_id": sid, "error": str(exc)[:200]})
    boe, dailies = {}, {}
    try:
        raw, rec = hist_02_acquire.fetch("boe-gold-usd-monthly-average")
        pts, _ = ss.parse_points(raw, ss.BOE_SERIES)
        boe = ss.monthly_from_points(pts)
        s["boe_monthly"] = {"sha256": rec["sha256"], "bytes": rec["bytes"], "months": len(boe)}
    except (hist_02_acquire.AcquisitionError, ss.SecondSourceError) as exc:
        s["failures"].append({"source_id": "boe-gold-usd-monthly-average", "error": str(exc)[:300]})
    for code in codes[:MAX_DAILY_CODES]:
        if code == ss.BOE_SERIES:
            continue
        sid = register_daily(code)
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            pts, missing = ss.parse_points(raw, code)
        except (hist_02_acquire.AcquisitionError, ss.SecondSourceError) as exc:
            s["daily_series"][code] = {"usable": False, "error": str(exc)[:160]}
            continue
        info = {"usable": True, "points": len(pts), "missing_markers": missing, "daily": is_daily(pts),
                "first": min(pts).isoformat(), "last": max(pts).isoformat(), "sha256": rec["sha256"]}
        s["daily_series"][code] = info
        if info["daily"]:
            dailies[code] = pts
    s["deviation_ranking"] = deviation_ranking(wb, boe) if boe else None
    s["monthly_vs_daily"] = {c: monthly_vs_daily_consistency(boe, d) for c, d in dailies.items()} if boe else None
    s["results"] = [analyse_month(m, wb, boe, dailies) for m in OUTLIER_MONTHS]
    s["status"] = "ANALYSED" if boe else "NO_BOE_MONTHLY"
    out.write_text(json.dumps(s, indent=2, sort_keys=True, default=str) + "\n")
    print("\n".join(report_lines(s)))
    return 0 if boe else 2


if __name__ == "__main__":
    sys.exit(main())
