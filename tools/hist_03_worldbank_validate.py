"""HIST-03 research-only validation of the World Bank Pink Sheet GOLD series.

Fetches only the approved World Bank source through tools.hist_02_acquire.fetch
(no FRED, no fallback), parses the 'Monthly Prices' sheet with a parameterised
copy of the logic in etl/sources/worldbank_gold.py (that module is untouched),
and validates 1975-01..1999-12 strictly. Raw bytes stay in memory; output is
metadata only. No interpolation, no publication, no repository data writes.

Single sources of truth (HIST-03 consolidation):
- World Bank acquisition: tools.hist_02_acquire.fetch (no second download path).
- Month enumeration: tools.hist_02_coverage.month_range (expected_months delegates).
- Canonical series hash: canonical_sha256 below; fingerprint() below feeds both
  validate() and tools.hist_03_independent_parse (which re-exports it).

Deliberate deviation from the production parser etl/sources/worldbank_gold.py
(left untouched): this validator is STRICT (date format 'YYYYMmm' only, exactly one
GOLD column, duplicates/unparseable dates/invalid values are reported and fail the
run, range 1975-01..1999-12), whereas the production parser accepts Excel serials
and 'YYYY-MM', skips rows before 2000-01 and records problems less strictly.
The two are intentionally not merged; this module never feeds production data.
"""
import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tools.hist_02_coverage import month_range

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
SHEET = "Monthly Prices"
START, END = "1975-01", "1999-12"
UNIT_RE = re.compile(r"troy\s*oz", re.I)
ANCHORS = ("1975-01", "1979-12", "1980-01", "1980-09", "1985-01", "1990-01",
           "1995-01", "1996-01", "1998-01", "1999-01", "1999-08", "1999-12")


class ValidationError(ValueError):
    pass


def read_rows(raw, sheet=SHEET):
    """Return rows (dict col->text) of the worksheet whose name equals `sheet`."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//x:t", NS)) for si in root.findall("x:si", NS)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = wb.findall(".//x:sheets/x:sheet", NS)
        el = next((s for s in sheets if s.attrib["name"] == sheet), None)
        if el is None:
            raise ValidationError("SHEET_NOT_FOUND " + repr([s.attrib["name"] for s in sheets]))
        rid = el.attrib["{" + NS["r"] + "}id"]
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(x for x in rels if x.attrib["Id"] == rid).attrib["Target"].lstrip("/")
        root = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
        rows = []
        for row in root.findall(".//x:sheetData/x:row", NS):
            cells = {}
            for c in row.findall("x:c", NS):
                col = "".join(ch for ch in c.attrib.get("r", "") if ch.isalpha())
                v = c.find("x:v", NS)
                inl = c.find("x:is", NS)
                val = (v.text or "") if v is not None else ("".join(t.text or "" for t in inl.findall(".//x:t", NS)) if inl is not None else "")
                if c.attrib.get("t") == "s" and val:
                    val = shared[int(val)]
                cells[col] = val
            rows.append(cells)
        return rows


def _period(rawdate):
    """Strict World Bank format 'YYYYMmm' (e.g. 1975M01); returns YYYY-MM or None."""
    m = re.fullmatch(r"(\d{4})M(\d{2})", rawdate)
    if not m or not 1 <= int(m.group(2)) <= 12:
        return None
    return f"{m.group(1)}-{m.group(2)}"


def parse(raw, start=START, end=END):
    rows = read_rows(raw)
    header = next((i for i, r in enumerate(rows) if any(str(v).strip().upper() == "GOLD" for v in r.values())), None)
    if header is None:
        raise ValidationError("GOLD_COLUMN_NOT_FOUND")
    gold_cols = [k for k, v in rows[header].items() if str(v).strip().upper() == "GOLD"]
    if len(gold_cols) != 1:
        raise ValidationError("AMBIGUOUS_GOLD_COLUMN " + repr(gold_cols))  # fail closed, never pick one silently
    goldcol = gold_cols[0]
    if goldcol == "A":
        raise ValidationError("DATE_COLUMN_OVERLAPS_GOLD")
    series, all_periods, bad_dates, invalid, dups, unit_texts = {}, [], [], [], [], []
    seen_data = False
    all_values = {}  # every parseable observation (any period); used only for aggregate precision statistics
    for n, r in enumerate(rows[header + 1:], header + 2):
        d = str(r.get("A", "")).strip()
        v = str(r.get(goldcol, "")).strip()
        period = _period(d) if d else None
        if period is None:
            if not seen_data and v:
                unit_texts.append(v)  # unit row(s) sit between header and first observation
            elif d and seen_data:
                bad_dates.append({"row": n, "date": d})
            continue
        seen_data = True
        if period in all_periods:
            dups.append(period)
        all_periods.append(period)
        try:
            all_values[period] = Decimal(v)
        except InvalidOperation:
            pass
        if start <= period <= end:
            try:
                val = Decimal(v)
                if not val.is_finite() or val <= 0:
                    raise ValueError("nonpositive/nonfinite")
            except (InvalidOperation, ValueError) as e:
                invalid.append({"row": n, "period": period, "value": v, "reason": str(e)})
                continue
            series[period] = val
    return {"gold_column": goldcol, "header_text": rows[header][goldcol], "unit_texts": unit_texts,
            "series": series, "all_periods": all_periods, "bad_dates": bad_dates,
            "invalid": invalid, "duplicates": dups, "all_values": all_values}


def expected_months(start=START, end=END):
    return month_range(start, end)


def canonical_sha256(series, months):
    text = "".join(f"{p},{format(series[p], 'f')}\n" for p in months)
    return hashlib.sha256(text.encode()).hexdigest()


def fingerprint(p, start=START, end=END):
    """Aggregate facts of a parsed workbook (metadata only); shared by validate() and the cross-check."""
    s = p["series"]
    months = [m for m in expected_months(start, end) if m in s]
    ap = p["all_periods"]
    return {
        "count_in_range": len(s), "first_in_range": min(s) if s else None, "last_in_range": max(s) if s else None,
        "gold_column": p["gold_column"], "header_text": p["header_text"],
        "unit_accepted": next((u for u in p["unit_texts"] if UNIT_RE.search(u)), None),
        "sheet_period_count": len(ap), "sheet_first_period": ap[0] if ap else None,
        "sheet_last_period": ap[-1] if ap else None,
        "canonical_series_sha256": canonical_sha256(s, months),
        "non_integer_count_in_range": sum(1 for v in s.values() if v != v.to_integral_value()),
    }


def precision_stats(values, start=START, end=END):
    """Aggregate decimal-place histograms per segment (counts only, never values)."""
    seg = {"before_range": {}, "in_range": {}, "after_range": {}}
    for period, v in values.items():
        if not v.is_finite():
            continue
        name = "before_range" if period < start else ("in_range" if period <= end else "after_range")
        places = str(max(0, -v.as_tuple().exponent))
        seg[name][places] = seg[name].get(places, 0) + 1
    return seg


def validate(raw, start=START, end=END):
    """Return metadata summary; raise ValidationError on structural violations."""
    p = parse(raw, start, end)
    months = expected_months(start, end)
    s = p["series"]
    fp = fingerprint(p, start, end)
    unit = fp["unit_accepted"]
    missing = [m for m in months if m not in s]
    problems = []
    if unit is None:
        problems.append("UNIT_NOT_TROY_OUNCE")
    if missing:
        problems.append("MISSING_MONTHS")
    if p["duplicates"]:
        problems.append("DUPLICATE_MONTHS")
    if p["invalid"]:
        problems.append("INVALID_VALUES")
    if p["bad_dates"]:
        problems.append("UNPARSEABLE_DATES")
    summary = {
        "worksheet": SHEET, "gold_column": p["gold_column"], "header_text": p["header_text"],
        "unit_rows_literal": p["unit_texts"], "unit_accepted": unit,
        "date_format": "YYYYMmm (e.g. 1975M01)", "workbook_sha256": hashlib.sha256(raw).hexdigest(),
        "sheet_first_period": fp["sheet_first_period"], "sheet_last_period": fp["sheet_last_period"],
        "sheet_period_count": fp["sheet_period_count"], "range": [start, end], "expected_count": len(months),
        "count_in_range": fp["count_in_range"], "first_in_range": fp["first_in_range"],
        "last_in_range": fp["last_in_range"], "missing_months": missing, "duplicate_months": p["duplicates"], "invalid_rows": p["invalid"],
        "unparseable_dates": p["bad_dates"],
        "min": str(min(s.values())) if s else None, "max": str(max(s.values())) if s else None,
        "anchors": [{"month": m, "value": str(s[m])} for m in ANCHORS if m in s][:12],
        "non_integer_count_in_range": fp["non_integer_count_in_range"],
        "decimal_places_histogram": precision_stats(p["all_values"], start, end),
        "problems": problems, "rights_status": "UNVERIFIED", "publication_authorized": False,
    }
    if not problems:
        summary["canonical_series_sha256"] = fp["canonical_series_sha256"]
    summary["status"] = "VALIDATED" if not problems else "FAILED"
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--independent-parser", choices=["openpyxl"],
                    help="re-parse the same bytes with a second parser; any difference fails the run")
    args = ap.parse_args(argv)
    from tools.hist_02_acquire import fetch, AcquisitionError
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw, record = fetch("world-bank-gold-history")
    except AcquisitionError as exc:
        out.write_text(json.dumps({"status": "ACQUISITION_FAILED", "error": str(exc)}, indent=2) + "\n")
        print("ACQUISITION_FAILED", exc)
        return 3
    try:
        summary = validate(raw)
    except Exception as exc:  # parse failure: report class, no fallback
        summary = {"status": "PARSE_FAILED", "error_class": type(exc).__name__, "error": str(exc),
                   "workbook_sha256": record["sha256"], "bytes": record["bytes"]}
    if args.independent_parser and summary["status"] == "VALIDATED":
        from tools.hist_03_independent_parse import crosscheck
        summary["independent_parser"] = crosscheck(raw)
        if summary["independent_parser"]["status"] != "MATCH":
            summary["status"] = "CROSSCHECK_FAILED"
    summary["fetch"] = {k: record[k] for k in ("url", "sha256", "bytes", "http_status")}
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "VALIDATED" else 2


if __name__ == "__main__":
    sys.exit(main())
