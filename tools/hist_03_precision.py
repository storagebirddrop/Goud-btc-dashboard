"""HIST-03 research-only precision / deviation analysis (aggregates only).

Pure functions plus a CI entry point. No publication, no repository data writes,
no full series in any output. Raw workbook bytes stay in memory.
"""
import argparse
import io
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
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


# ---------------------------------------------------------------------------
# (3) Rounding sensitivity for "gram gold per average Dutch house"
# gram = house_eur * 31.1034768 / gold_eur_oz; gram is inversely proportional to the gold price,
# so a relative price error e gives a relative gram error of -e/(1+e).
# ---------------------------------------------------------------------------
def gram_error_for(price, abs_error):
    """Relative error in gram-per-house (fraction) for a price (USD/oz) that is `abs_error` USD/oz too high
    (negative abs_error = too low). Same house price and FX assumed. Exact: price/(price+err) - 1."""
    if not isinstance(price, Decimal) or not isinstance(abs_error, Decimal) or not price.is_finite() or not abs_error.is_finite():
        raise PrecisionError("INVALID_INPUT")
    if price <= 0 or price + abs_error <= 0:
        raise PrecisionError("NONPOSITIVE_PRICE")
    e = abs_error / price
    return -e / (1 + e)


def _pctl(sorted_vals, q):
    """Nearest-rank percentile (q in (0,1])."""
    return sorted_vals[max(0, math.ceil(q * len(sorted_vals)) - 1)]


def _agg(vals):
    if not vals:
        return {"n": 0, "max": None, "median": None, "p95": None}
    s = sorted(vals)
    return {"n": len(s), "max": _f(s[-1]), "median": _f(median(s)), "p95": _f(_pctl(s, 0.95))}


def rounding_sensitivity(prices):
    """THEORETICAL bound under assumption (i): values rounded to whole USD, i.e. |error| <= 0.5 USD/oz.
    Per month: rel_price_bound_pct = 0.5/price*100; gram_error_pct = worst-case |gram error| (the
    price-too-low side, +b/(1-b), is the larger one). Aggregates only. Not a measured source deviation."""
    _check(prices, "prices")
    if not prices:
        raise PrecisionError("EMPTY_INPUT")
    rows = []
    for m in sorted(prices):
        p = prices[m]
        if p <= ROUNDING_HALF_WIDTH:
            raise PrecisionError("PRICE_NOT_ABOVE_ROUNDING_BOUND")
        rel = ROUNDING_HALF_WIDTH / p * 100
        gram = max(abs(gram_error_for(p, ROUNDING_HALF_WIDTH)), abs(gram_error_for(p, -ROUNDING_HALF_WIDTH))) * 100
        rows.append((m, rel, gram))

    def block(sel):
        return {"rel_price_bound_pct": _agg([r[1] for r in sel]), "gram_error_pct": _agg([r[2] for r in sel])}
    out = {"basis": "THEORETICAL (assumption: values rounded to whole USD; not a measured deviation)"}
    out.update(block(rows))
    out["subperiods"] = {name: block([r for r in rows if lo <= r[0] <= hi]) for name, lo, hi in SUBPERIODS}
    worst = max(rows, key=lambda r: (r[2], r[0]))
    out["worst_month"] = {"month": worst[0], "gram_error_pct": _f(worst[2])}
    return out


# ---------------------------------------------------------------------------
# (2) Raw-XML cell analysis of the workbook (aggregates / metadata only)
# ---------------------------------------------------------------------------
_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_BUILTIN_FMT = {0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 9: "0%", 10: "0.00%", 11: "0.00E+00",
                12: "# ?/?", 13: "# ??/??", 37: "#,##0 ;(#,##0)", 38: "#,##0 ;[Red](#,##0)",
                39: "#,##0.00;(#,##0.00)", 40: "#,##0.00;[Red](#,##0.00)", 48: "##0.0E+0", 49: "@"}
_PERIOD = re.compile(r"\d{4}M\d{2}")


def format_shows_decimals(code):
    """Classify an Excel number format: 'general' (shows stored digits), 'decimals', 'integer', 'text', 'other'."""
    if code is None:
        return "unknown"
    c = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code).split(";")[0]
    if c.strip().lower() == "general":
        return "general"
    if c.strip() == "@":
        return "text"
    if re.search(r"\.[0#?]", c):
        return "decimals"
    if re.search(r"[0#]", c):
        return "integer"
    return "other"


class _Book:
    def __init__(self, raw):
        self.z = zipfile.ZipFile(io.BytesIO(raw))
        names = self.z.namelist()
        self.shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
            self.shared = ["".join(t.text or "" for t in si.findall(".//x:t", _NS)) for si in root.findall("x:si", _NS)]
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))
        self.sheet_paths = {}
        for s in wb.findall(".//x:sheets/x:sheet", _NS):
            target = next(x for x in rels if x.attrib["Id"] == s.attrib["{" + _NS["r"] + "}id"]).attrib["Target"].lstrip("/")
            self.sheet_paths[s.attrib["name"]] = target if target.startswith("xl/") else "xl/" + target
        self.fmt_codes, self.xf_fmt = {}, []
        if "xl/styles.xml" in names:
            st = ET.fromstring(self.z.read("xl/styles.xml"))
            for nf in st.findall(".//x:numFmts/x:numFmt", _NS):
                self.fmt_codes[int(nf.attrib["numFmtId"])] = nf.attrib.get("formatCode", "")
            xfs = st.find("x:cellXfs", _NS)
            self.xf_fmt = [int(xf.attrib.get("numFmtId", "0")) for xf in (xfs if xfs is not None else [])]

    def sheet_xml(self, name):
        return self.z.read(self.sheet_paths[name])

    def cells(self, name):
        """Yield dicts per cell: col, row, t, s, v (raw text or None), text (resolved), has_f, f_round."""
        root = ET.fromstring(self.sheet_xml(name))
        for c in root.findall(".//x:sheetData/x:row/x:c", _NS):
            ref = c.attrib.get("r", "")
            col = "".join(ch for ch in ref if ch.isalpha())
            row = int("".join(ch for ch in ref if ch.isdigit()) or 0)
            v = c.find("x:v", _NS)
            inl = c.find("x:is", _NS)
            f = c.find("x:f", _NS)
            raw_v = v.text if v is not None else None
            t = c.attrib.get("t", "n")
            if t == "s" and raw_v:
                text = self.shared[int(raw_v)]
            elif inl is not None:
                text = "".join(x.text or "" for x in inl.findall(".//x:t", _NS))
            else:
                text = raw_v or ""
            yield {"col": col, "row": row, "t": t, "s": c.attrib.get("s"), "v": raw_v, "text": text,
                   "has_f": f is not None, "f_round": f is not None and "ROUND" in (f.text or "").upper()}

    def format_of(self, s):
        if s is None or not s.isdigit() or int(s) >= len(self.xf_fmt):
            return 0, _BUILTIN_FMT[0]
        fid = self.xf_fmt[int(s)]
        return fid, self.fmt_codes.get(fid, _BUILTIN_FMT.get(fid))


def _raw_is_integer(v):
    """True if the raw <v> text is a whole number written without '.', 'E' (strict textual test)."""
    return v is not None and re.fullmatch(r"-?\d+", v.strip()) is not None


def _decimals_in_raw(v):
    v = v.strip()
    return len(re.split("[eE]", v.split(".")[1])[0]) if "." in v else 0


def _header_row(rows_by_row):
    for r in sorted(rows_by_row):
        if any(c["text"].strip().upper() == "GOLD" for c in rows_by_row[r].values()):
            return r
    return None


def analyse_monthly_sheet(raw, sheet="Monthly Prices"):
    """2a, 2b, 2e: raw <v> analysis for the GOLD column and for every other column, by header name."""
    book = _Book(raw)
    by_row = {}
    for c in book.cells(sheet):
        by_row.setdefault(c["row"], {})[c["col"]] = c
    hr = _header_row(by_row)
    if hr is None:
        raise PrecisionError("GOLD_HEADER_NOT_FOUND")
    headers = {col: c["text"].strip() for col, c in by_row[hr].items()}
    gold_cols = [col for col, h in headers.items() if h.upper() == "GOLD"]
    if len(gold_cols) != 1:
        raise PrecisionError("AMBIGUOUS_GOLD_COLUMN")
    gcol = gold_cols[0]
    data_rows = sorted(r for r in by_row if r > hr and "A" in by_row[r] and _PERIOD.fullmatch(by_row[r]["A"]["text"].strip()))
    per_col = {}
    for col, h in headers.items():
        if col == "A":
            continue
        n = nonint = non_numeric = 0
        for r in data_rows:
            c = by_row[r].get(col)
            if c is None or c["v"] is None or c["v"] == "":
                continue
            if c["t"] != "n" or not re.fullmatch(r"-?[0-9.eE+-]+", c["v"].strip()):
                non_numeric += 1  # text / '..' placeholders
                continue
            n += 1
            if not _raw_is_integer(c["v"]):
                nonint += 1
        per_col[f"{col}:{h}"] = {"numeric_cells": n, "non_integer_cells": nonint, "non_numeric_cells": non_numeric}
    types, styles, decs, formulas, round_f = {}, {}, {}, 0, 0
    gold_rows = {}
    for r in data_rows:
        c = by_row[r].get(gcol)
        if c is None:
            continue
        types[c["t"]] = types.get(c["t"], 0) + 1
        fid, code = book.format_of(c["s"])
        key = f"s={c['s']} numFmtId={fid} formatCode={code!r} -> {format_shows_decimals(code)}"
        styles[key] = styles.get(key, 0) + 1
        if c["v"] is not None and c["t"] == "n":
            d = str(_decimals_in_raw(c["v"]))
            decs[d] = decs.get(d, 0) + 1
            gold_rows[r] = c["v"]
        formulas += c["has_f"]
        round_f += c["f_round"]
    # 2e: independent regex over the raw sheet XML text (no XML parser)
    text = book.sheet_xml(sheet).decode("utf-8", "replace")
    rx = {}
    pat = r'<(?:\w+:)?c\b[^>]*?\br="' + re.escape(gcol) + r'(\d+)"[^>]*?(?:/>|>(.*?)</(?:\w+:)?c>)'
    for m in re.finditer(pat, text, re.S):
        vm = re.search(r"<(?:\w+:)?v>([^<]*)</(?:\w+:)?v>", m.group(2) or "")
        if vm:
            rx[int(m.group(1))] = vm.group(1)
    rows_set = set(data_rows)
    rx_rows = {r: v for r, v in rx.items() if r in rows_set}
    return {"header_row": hr, "gold_column": gcol, "data_rows": len(data_rows),
            "gold": {"cell_types_t": types, "style_numfmt": styles, "raw_v_decimal_places_histogram": decs,
                     "cells_with_formula": formulas, "formulas_containing_ROUND": round_f,
                     "numeric_cells_non_integer_raw": sum(1 for v in gold_rows.values() if not _raw_is_integer(v))},
            "regex_check": {"cells_matched_in_data_rows": len(rx_rows),
                            "cells_with_dot_or_E": sum(1 for v in rx_rows.values() if re.search(r"[.eE]", v)),
                            "mismatch_vs_xml_parse": sum(1 for r, v in gold_rows.items() if rx_rows.get(r) != v)},
            "all_columns": per_col}


def analyse_other_sheets(raw, monthly_gold=None, max_text=300):
    """2c: sheet names, GOLD description line, annual-sheet decimals and annual-vs-monthly-mean comparison."""
    book = _Book(raw)
    out = {"sheet_names": list(book.sheet_paths)}
    desc = next((n for n in book.sheet_paths if "description" in n.lower() or "note" in n.lower()), None)
    lines = []
    if desc:
        by_row = {}
        for c in book.cells(desc):
            by_row.setdefault(c["row"], []).append(c["text"].strip())
        for r in sorted(by_row):
            joined = " | ".join(t for t in by_row[r] if t)
            if re.search(r"\bgold\b|round|decimal", joined, re.I):
                lines.append(joined[:max_text])
    out["description_sheet"] = desc
    out["description_gold_lines"] = lines[:8]
    ann = next((n for n in book.sheet_paths if "annual" in n.lower() and "nominal" in n.lower()), None) or \
        next((n for n in book.sheet_paths if "annual" in n.lower()), None)
    out["annual_sheet"] = ann
    if not ann:
        return out
    by_row = {}
    for c in book.cells(ann):
        by_row.setdefault(c["row"], {})[c["col"]] = c
    hr = _header_row(by_row)
    gcols = [col for col, c in by_row[hr].items() if c["text"].strip().upper() == "GOLD"] if hr else []
    if len(gcols) != 1:
        out["annual"] = {"error": "GOLD_HEADER_NOT_FOUND_OR_AMBIGUOUS"}
        return out
    g = gcols[0]
    years = {}
    units = [by_row[r][g]["text"] for r in sorted(by_row) if hr < r <= hr + 3 and g in by_row[r] and by_row[r][g]["text"]]
    for r in sorted(by_row):
        a = by_row[r].get("A")
        if r > hr and a and re.fullmatch(r"\d{4}", a["text"].strip().split(".")[0]) and g in by_row[r] and by_row[r][g]["v"]:
            years[a["text"].strip().split(".")[0]] = by_row[r][g]["v"]
    dec_hist = {}
    for v in years.values():
        d = str(_decimals_in_raw(v))
        dec_hist[d] = dec_hist.get(d, 0) + 1
    res = {"unit_rows": units[:2], "years_with_value": len(years), "first_year": min(years) if years else None,
           "last_year": max(years) if years else None, "raw_v_decimal_places_histogram": dec_hist,
           "non_integer_annual_values": sum(1 for v in years.values() if not _raw_is_integer(v))}
    if monthly_gold:
        diffs = []
        for y, v in years.items():
            ms = [monthly_gold.get(f"{y}-{m:02d}") for m in range(1, 13)]
            if "1975" <= y <= "1999" and all(x is not None for x in ms):
                try:
                    diffs.append(abs(sum(ms) / 12 - Decimal(v)))
                except Exception:
                    pass
        res["annual_vs_monthly_mean_1975_1999"] = {
            "n_years": len(diffs), "mean_abs": _f(sum(diffs) / len(diffs)) if diffs else None,
            "max_abs": _f(max(diffs)) if diffs else None,
            "years_within_0_5": sum(1 for d in diffs if d <= ROUNDING_HALF_WIDTH)}
    out["annual"] = res
    return out


def workbook_metadata(raw):
    """2d: docProps core/app fields (version/date indication)."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    out = {}
    for part, wanted in (("docProps/core.xml", ("creator", "lastModifiedBy", "created", "modified")),
                         ("docProps/app.xml", ("Application", "AppVersion", "Company"))):
        if part not in z.namelist():
            out[part] = "ABSENT"
            continue
        found = {}
        for el in ET.fromstring(z.read(part)).iter():
            tag = el.tag.split("}")[-1]
            if tag in wanted and el.text:
                found[tag] = el.text.strip()[:120]
        out[part] = found
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--workbook", help="read this local workbook instead of downloading it")
    args = ap.parse_args(argv)
    from tools.hist_02_acquire import AcquisitionError
    from tools.hist_03_worldbank_validate import parse, load_workbook
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw, record = load_workbook(args.workbook)
    except AcquisitionError as exc:
        out.write_text(json.dumps({"status": "ACQUISITION_FAILED", "error": str(exc)}, indent=2) + "\n")
        print("ACQUISITION_FAILED", exc)
        return 3
    summary = {"status": "ANALYSED", "workbook_sha256": record["sha256"], "bytes": record["bytes"],
               "label": "RESEARCH ONLY; aggregates/metadata only; rights UNVERIFIED; no publication"}
    parsed = parse(raw)
    allv = parsed["all_values"]
    for key, fn in (("monthly_sheet_xml", lambda: analyse_monthly_sheet(raw)),
                    ("other_sheets", lambda: analyse_other_sheets(raw, allv)),
                    ("metadata", lambda: workbook_metadata(raw)),
                    ("parser_noninteger_count_all_periods", lambda: sum(1 for v in allv.values() if v != v.to_integral_value())),
                    ("rounding_sensitivity_1975_1999", lambda: rounding_sensitivity(parsed["series"]))):
        try:
            summary[key] = fn()
        except Exception as exc:  # report, do not hide; no fallback
            summary[key] = {"error_class": type(exc).__name__, "error": str(exc)[:300]}
            summary["status"] = "PARTIAL"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
