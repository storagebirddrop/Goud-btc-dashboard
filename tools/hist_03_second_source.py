"""HIST-03 research-only second-source comparison for monthly gold 1975-01..1999-12.

Acquisition reuses tools.hist_02_acquire (allowlist, 15 MB limit, sha256, no
redirects off-allowlist). Candidates are registered into its SOURCES dict.
Parsing is strict and fail-closed (Decimal). Monthly aggregation is the plain
arithmetic mean of the available daily values per calendar month; the number of
days is recorded; no interpolation, no forward-fill, months without data stay
absent. Output is aggregates/metadata only; raw bytes stay in memory.
A comparison is NOT proof of equality: definitions may differ (see DEFINITION_NOTES).
No publication, no repository data writes, no new gold methodology.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tools import hist_02_acquire

START, END = "1975-01", "1999-12"
BOE_SERIES = "XUMAGPD"  # Bank of England IADB: gold price against US$, monthly average
BOE_CSV = ("https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?csv.x=yes"
           "&Datefrom=01/Jan/1975&Dateto=31/Dec/1999&SeriesCodes=" + BOE_SERIES +
           "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
BOE_NOTES = "https://www.bankofengland.co.uk/statistics/Pages/iadb/notesiadb/gold.aspx"

# source_id -> (url, format); granularity says how the file is interpreted.
CANDIDATES = {
    "boe-gold-usd-monthly-average": {"url": BOE_CSV, "format": "csv", "granularity": "monthly", "series": BOE_SERIES},
}
hist_02_acquire.SOURCES.update({sid: (c["url"], c["format"]) for sid, c in CANDIDATES.items()})
hist_02_acquire.SOURCES.update({"boe-gold-notes": (BOE_NOTES, "html")})

# Literature/definition status. Labels: [S]=search result only, [K]=own knowledge, nothing is VERIFIED here.
DEFINITION_NOTES = {
    "world-bank": "[S] secondary sites say 'Gold (UK), 99.5% fine, London afternoon fixing'; official Pink Sheet note not retrieved; averaging basis unverified",
    "lbma": "[S] historic tables moved behind Members' Portal (licence self-certification) from 2025-11-24; FRED removed IBA series 2022-01-31; not usable",
    "boe": "[S] BoE IADB XUMAGPD monthly average vs US$; fixing basis (AM/PM) NOT confirmed; notes page fetched in CI for definition text",
}

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MISSING_MARKERS = {"", ".", "NA", "N/A", "NaN"}
VALUE_RE = re.compile(r"\d+(\.\d+)?")


class SecondSourceError(ValueError):
    pass


def parse_date(text):
    t = text.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[ -]([A-Za-z]{3})[ -](\d{4})", t)  # 4-digit year only: no century guessing
        if not m or m.group(2).lower() not in MONTHS:
            raise SecondSourceError("UNPARSEABLE_DATE")
        d, mo, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError as exc:
        raise SecondSourceError("INVALID_DATE") from exc


def parse_points(raw, series_code, expected_unit_note=None):
    """Parse a two-column CSV 'DATE,<series_code>' into ({date: Decimal}, missing_count).

    Fail closed on: wrong header/column/series code, duplicate dates, extra columns,
    non-numeric or non-positive values. Explicit missing markers are counted, not filled.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SecondSourceError("NOT_UTF8") from exc
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise SecondSourceError("EMPTY_FILE")
    header = [c.strip().strip('"') for c in lines[0].split(",")]
    if len(header) != 2 or header[0].upper() != "DATE":
        html = lines[0].lstrip().startswith("<")
        raise SecondSourceError("UNEXPECTED_HEADER_SHAPE " + json.dumps(
            {"lines": len(lines), "first_line_chars": len(lines[0]), "looks_like_html": html,
             "first_line_prefix": None if html else lines[0][:60]}))
    if header[1] != series_code:
        raise SecondSourceError("WRONG_SERIES_COLUMN")
    points, missing = {}, 0
    for ln in lines[1:]:
        cells = [c.strip().strip('"') for c in ln.split(",")]
        if len(cells) != 2:
            raise SecondSourceError("UNEXPECTED_COLUMN_COUNT")
        d = parse_date(cells[0])
        if d in points:
            raise SecondSourceError("DUPLICATE_DATE")
        v = cells[1]
        if v in MISSING_MARKERS:
            missing += 1
            continue
        if not VALUE_RE.fullmatch(v):
            raise SecondSourceError("INVALID_VALUE")
        try:
            val = Decimal(v)
        except InvalidOperation as exc:
            raise SecondSourceError("INVALID_VALUE") from exc
        if not val.is_finite() or val <= 0:
            raise SecondSourceError("NON_POSITIVE_VALUE")
        points[d] = val
    if not points:
        raise SecondSourceError("NO_OBSERVATIONS")
    return points, missing


def aggregate_monthly(daily, start=START, end=END):
    """{date: Decimal} -> ({YYYY-MM: mean}, {YYYY-MM: n_days}); calendar months only, no filling."""
    sums, counts = {}, {}
    for d, v in daily.items():
        key = f"{d.year:04d}-{d.month:02d}"
        if not start <= key <= end:
            continue
        sums[key] = sums.get(key, Decimal(0)) + v
        counts[key] = counts.get(key, 0) + 1
    return {k: sums[k] / counts[k] for k in sorted(sums)}, {k: counts[k] for k in sorted(counts)}


def monthly_from_points(points, start=START, end=END):
    """One observation per calendar month (a provider-published monthly average); duplicates fail."""
    out = {}
    for d, v in points.items():
        key = f"{d.year:04d}-{d.month:02d}"
        if not start <= key <= end:
            continue
        if key in out:
            raise SecondSourceError("DUPLICATE_MONTH")
        out[key] = v
    return out


def days_statistics(counts):
    if not counts:
        return {"months": 0}
    vals = sorted(counts.values())
    return {"months": len(vals), "min_days": vals[0], "max_days": vals[-1], "median_days": vals[len(vals) // 2],
            "months_below_15_days": sum(1 for c in vals if c < 15)}


def coverage(other, start=START, end=END):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    present = [k for k in months if k in other]
    return {"expected": len(months), "present": len(present),
            "first": present[0] if present else None, "last": present[-1] if present else None,
            "missing_count": len(months) - len(present)}


def probe_redirect(url):
    """Diagnostic only: status and Location host/path of the first response, no redirect followed, no body read."""
    from urllib.error import HTTPError
    from urllib.parse import urlsplit
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        resp = build_opener(NoRedirect).open(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-03 probe"}), timeout=30)
        return {"status": resp.status}
    except HTTPError as exc:
        loc = exc.headers.get("Location")
        parts = urlsplit(loc) if loc else None
        return {"status": exc.code, "location_host": parts.hostname if parts else None,
                "location_path": parts.path if parts else None, "server": exc.headers.get("Server")}
    except OSError as exc:
        return {"error_class": type(exc).__name__}


def notes_snippets(raw, limit=6, width=240):
    """Definition text only (documentation page, not data): short sentences with basis keywords."""
    text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace"))
    text = re.sub(r"\s+", " ", text)
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"fix|average|morning|afternoon|daily|month", s, re.I) and 20 <= len(s):
            out.append(s[:width])
        if len(out) >= limit:
            break
    return out


def compare_candidate(wb, sid, cfg, raw):
    points, missing = parse_points(raw, cfg["series"])
    if cfg["granularity"] == "daily":
        monthly, counts = aggregate_monthly(points)
    else:
        monthly, counts = monthly_from_points(points), {k: 1 for k in monthly_from_points(points)}
    common = sorted(set(wb) & set(monthly))
    res = {"source_id": sid, "granularity": cfg["granularity"], "points": len(points),
           "explicit_missing_markers": missing, "first_point": min(points).isoformat(), "last_point": max(points).isoformat(),
           "coverage": coverage(monthly), "days_per_month": days_statistics(counts), "common_months": len(common),
           "anchors": [{"month": k, "wb": str(wb[k]), "other": str(monthly[k])} for k in
                       ("1975-01", "1980-01", "1985-01", "1990-01", "1995-01", "1999-12") if k in monthly][:12]}
    try:
        from tools.hist_03_precision import deviation_stats
    except ImportError:
        res["deviation_stats"] = "UNAVAILABLE_hist_03_precision.deviation_stats_missing"
    else:
        res["deviation_stats"] = deviation_stats({k: wb[k] for k in common}, {k: monthly[k] for k in common})
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    args = ap.parse_args(argv)
    from tools.hist_03_worldbank_validate import parse as wb_parse
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {"status": "RUNNING", "range": [START, END], "definition_notes": DEFINITION_NOTES,
               "rights_status": "UNVERIFIED", "publication_authorized": False, "candidates": [], "failures": []}
    raw_wb, rec_wb = hist_02_acquire.fetch("world-bank-gold-history")
    wb = wb_parse(raw_wb)["series"]
    summary["world_bank"] = {"sha256": rec_wb["sha256"], "bytes": rec_wb["bytes"], "months": len(wb)}
    try:
        raw_n, rec_n = hist_02_acquire.fetch("boe-gold-notes")
        summary["boe_notes"] = {"sha256": rec_n["sha256"], "bytes": rec_n["bytes"], "snippets": notes_snippets(raw_n)}
    except hist_02_acquire.AcquisitionError as exc:
        summary["failures"].append({"source_id": "boe-gold-notes", "error": str(exc)[:200],
                                    "probe": probe_redirect(BOE_NOTES)})
    for sid, cfg in CANDIDATES.items():
        try:
            raw, rec = hist_02_acquire.fetch(sid)
            res = compare_candidate(wb, sid, cfg, raw)
            res["sha256"], res["bytes"] = rec["sha256"], rec["bytes"]
            summary["candidates"].append(res)
        except (hist_02_acquire.AcquisitionError, SecondSourceError) as exc:
            summary["failures"].append({"source_id": sid, "error_class": type(exc).__name__, "error": str(exc)[:400],
                                        "probe": probe_redirect(cfg["url"])})
    summary["status"] = "COMPARED" if summary["candidates"] else "NO_CANDIDATE_COMPARED"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["candidates"] else 2


if __name__ == "__main__":
    sys.exit(main())
