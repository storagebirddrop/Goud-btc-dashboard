"""HIST-04 research-only: reachability and usability of historical USD/NLG (1975-01..1998-12) sources.

Context: the Fed G.5 package/DDP route failed (XML zip 404, DDP 400). That is a failed ROUTE, not evidence
that the data does not exist. This module probes other official routes from CI and, where a file is
reachable, parses it strictly with Decimal and reports aggregates only.

Rules: no interpolation, no forward-fill, no synthetic rates, no ECU proxy, no source authorization.
Missing markers are counted, never filled. Quote direction is asserted from the file text AND from value
plausibility (NLG per USD is ~1.4..4.1 in 1971-1998; USD per NLG would be ~0.24..0.72); a conflict or an
undeterminable direction fails closed. Acquisition reuses tools.hist_02_acquire.fetch (exact-URL
allowlist, 15 MB limit, sha256); raw bytes stay in memory; output is aggregates and short definition
quotes only. Nothing here is a methodology decision or a publication.
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
import zipfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tools import hist_02_acquire

START, END = "1975-01", "1998-12"
FIXED_NLG_PER_EUR = Decimal("2.20371")
MISSING = {"", ".", "ND", "NA", "N/A", "NC", "NaN", "nan", "-"}
VALUE_RE = re.compile(r"\d+(\.\d+)?")
BOUNDS = {"NLG_PER_USD": (Decimal("1.0"), Decimal("6.0")), "USD_PER_NLG": (Decimal("0.15"), Decimal("1.0"))}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

H10 = "https://www.federalreserve.gov/releases/h10/hist/"
BIS_API = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_XRU/1.0/"
# id -> (url, format, group). Groups: fed, cbs, fred, bis, imf, oecd, dnb, fixed.
CANDIDATES = {
    "fed-h10-hist-index": (H10, "html", "fed"),
    "fed-h10-thru89": (H10 + "thru89.htm", "html", "fed"),
    "fed-h10-about": ("https://www.federalreserve.gov/releases/h10/about.htm", "html", "fed"),
    "fed-disclaimer": ("https://www.federalreserve.gov/disclaimer.htm", "html", "fed"),
    "fed-h10-dat89-ne-txt": (H10 + "dat89_ne.txt", "txt", "fed"),
    "fed-h10-dat96-ne-txt": (H10 + "dat96_ne.txt", "txt", "fed"),
    "fed-h10-dat89-ne-htm": (H10 + "dat89_ne.htm", "html", "fed"),
    "fed-h10-dat96-ne-htm": (H10 + "dat96_ne.htm", "html", "fed"),
    "fred-exneus-txt": ("https://fred.stlouisfed.org/data/EXNEUS.txt", "txt", "fred"),
    "fred-exneus-page": ("https://fred.stlouisfed.org/series/EXNEUS", "html", "fred"),
    "cbs-7139shfo-info": ("https://opendata.cbs.nl/ODataApi/OData/7139SHFO/TableInfos", "json", "cbs"),
    "cbs-7139shfo-props": ("https://opendata.cbs.nl/ODataApi/OData/7139SHFO/DataProperties", "json", "cbs"),
    "cbs-7139shfo-data": ("https://opendata.cbs.nl/ODataApi/OData/7139SHFO/TypedDataSet", "json", "cbs"),
    "cbs-copyright": ("https://www.cbs.nl/en-gb/about-us/website/copyright", "html", "cbs"),
    "bis-xru-monthly-zip": ("https://www.bis.org/statistics/full_webstats_xru_current_dataflow_csv.zip", "zip", "bis"),
    "bis-xru-daily-zip": ("https://www.bis.org/statistics/full_webstats_xru_current_d_dataflow_csv_row.zip", "zip", "bis"),
    "bis-api-m-nl": (BIS_API + "M.NL?format=csv", "csv", "bis"),
    "bis-api-d-nl": (BIS_API + "D.NL?format=csv", "csv", "bis"),
    "bis-api-all-nl": (BIS_API + "*.NL?format=csv", "csv", "bis"),
    "imf-api-er-nld": ("https://api.imf.org/external/sdmx/2.1/data/IMF.STA,ER/NLD.XDC_USD.PA_RT.M?startPeriod=1975-01&endPeriod=1998-12&format=sdmx-csv", "csv", "imf"),
    "imf-legacy-ifs": ("https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.NL.ENDA_XDC_USD_RATE", "json", "imf"),
    "oecd-finmark-nld": ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/NLD.M.CCUS......?startPeriod=1975-01&endPeriod=1998-12&format=csvfilewithlabels", "csv", "oecd"),
    "dnb-statistics": ("https://www.dnb.nl/statistieken/", "html", "dnb"),
    "dnb-statistics-en": ("https://www.dnb.nl/en/statistics/", "html", "dnb"),
    "dnb-guilder-exchange": ("https://www.dnb.nl/en/money-exchange/exchanging-guilder-banknotes/", "html", "dnb"),
    "fixed-ecb-pr981231": ("https://www.ecb.europa.eu/press/pr/date/1998/html/pr981231_2.en.html", "html", "fixed"),
    "fixed-eurlex-celex": ("https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:31998R2866", "html", "fixed"),
    "fixed-eurlex-eli": ("https://eur-lex.europa.eu/eli/reg/1998/2866/oj/eng", "html", "fixed"),
    "fixed-ukleg-2866": ("https://www.legislation.gov.uk/eur/1998/2866/data.html", "html", "fixed"),
}
hist_02_acquire.SOURCES.update({k: (v[0], v[1]) for k, v in CANDIDATES.items()})


class NlgSourceError(ValueError):
    """Real parser/integrity defect (fail closed); never raised for mere unreachability."""


# ---------------------------------------------------------------- text helpers
def strip_tags(raw_text):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw_text)
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#160;", " "), ("&lt;", "<"), ("&gt;", ">")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def page_facts(raw, keywords, link_filter, max_sentences=8, max_links=25):
    text = raw.decode("utf-8", "replace")
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    plain = strip_tags(text)
    sentences = []
    for s in re.split(r"(?<=[.!?])\s+", plain):
        if re.search(keywords, s, re.I) and 25 <= len(s):
            sentences.append(s[:260])
        if len(sentences) >= max_sentences:
            break
    links = []
    for h in re.findall(r"""(?i)href\s*=\s*["']([^"'#]+)""", text):
        if re.search(link_filter, h, re.I) and h not in links:
            links.append(h[:160])
    return {"title": strip_tags(title.group(1))[:120] if title else None, "sentences": sentences,
            "links": links[:max_links], "link_count_matching": len(links)}


def extract_fixed_rate(raw):
    """Find 2.20371 near a guilder/Netherlands mention in an official page; return a short exact quote."""
    plain = strip_tags(raw.decode("utf-8", "replace"))
    for m in re.finditer(r"2[.,]20371", plain):
        ctx = plain[max(0, m.start() - 110): m.end() + 110]
        if re.search(r"guilder|Netherlands|Dutch|NLG", ctx, re.I):
            return {"status": "FOUND", "value": str(Decimal(m.group().replace(",", "."))), "equals_expected": Decimal(m.group().replace(",", ".")) == FIXED_NLG_PER_EUR,
                    "quote": ctx}
    return {"status": "NOT_FOUND_IN_PAGE", "text_chars": len(plain)}


# ---------------------------------------------------------------- dates, values
def to_decimal(text):
    t = text.strip()
    if not VALUE_RE.fullmatch(t):
        raise NlgSourceError("INVALID_VALUE")
    try:
        v = Decimal(t)
    except InvalidOperation as exc:
        raise NlgSourceError("INVALID_VALUE") from exc
    if not v.is_finite() or v <= 0:
        raise NlgSourceError("NON_POSITIVE_VALUE")
    return v


DATE_RES = [
    ("iso", re.compile(r"(\d{4})-(\d{2})-(\d{2})")),
    ("compact", re.compile(r"(\d{4})(\d{2})(\d{2})(?=\s)")),
    ("slash", re.compile(r"(\d{1,2})/\s?(\d{1,2})/\s?(\d{2}|\d{4})")),
    ("monname", re.compile(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{4})")),
    ("dmonname", re.compile(r"(\d{1,2})[- ]([A-Za-z]{3})[- ](\d{2}|\d{4})")),
]


def _year(text, century):
    if len(text) == 4:
        return int(text)
    if century is None:
        raise NlgSourceError("TWO_DIGIT_YEAR_WITHOUT_EXPLICIT_CENTURY")
    return century + int(text)


def _make_date(y, m, d):
    try:
        return date(y, m, d)
    except ValueError as exc:
        raise NlgSourceError("INVALID_DATE") from exc


def _split_row(line):
    s = line.strip()
    for kind, rx in DATE_RES:
        m = rx.match(s)
        if m:
            rest = s[m.end():].split()
            if len(rest) == 1:
                return kind, m.groups(), rest[0]
    return None


def _resolve(kind, g, century, slash_order):
    if kind == "iso" or kind == "compact":
        return _make_date(int(g[0]), int(g[1]), int(g[2]))
    if kind == "slash":
        a, b, y = int(g[0]), int(g[1]), _year(g[2], century)
        return _make_date(y, a, b) if slash_order == "MDY" else _make_date(y, b, a)
    if kind == "monname":
        if g[0].lower() not in MONTHS:
            raise NlgSourceError("INVALID_MONTH_NAME")
        return _make_date(int(g[2]), MONTHS[g[0].lower()], int(g[1]))
    if g[1].lower() not in MONTHS:
        raise NlgSourceError("INVALID_MONTH_NAME")
    return _make_date(_year(g[2], century), MONTHS[g[1].lower()], int(g[0]))


def parse_dated_text(raw, century=None, slash_order=None):
    """Fixed-text 'date  value' file (Fed H.10 history, FRED txt). Returns dict; fails closed.

    Lines before the first data line are header; non-matching lines after it fail if they start with a
    digit (a botched data line), otherwise they are counted as trailer lines. ND/NA/'.' are counted missing.
    """
    text = raw.decode("utf-8-sig", "replace")
    if re.match(r"\s*<(!doctype|html)", text, re.I):
        pre = re.findall(r"(?is)<pre[^>]*>(.*?)</pre>", text)
        text = "\n".join(re.sub(r"<[^>]+>", "", p) for p in pre) if pre else re.sub(r"<[^>]+>", "\n", text)
    header, trailer, rows, seen_data = [], [], [], False
    for ln in text.splitlines():
        if not ln.strip():
            continue
        sp = _split_row(ln)
        if sp:
            seen_data = True
            rows.append(sp)
        elif seen_data:
            if ln.strip()[0].isdigit():
                raise NlgSourceError("UNPARSED_DATA_LINE " + json.dumps(ln.strip()[:50]))
            trailer.append(ln.strip()[:90])
        else:
            header.append(ln.strip()[:110])
    if not rows:
        raise NlgSourceError("NO_DATA_LINES " + json.dumps({"header_lines": len(header), "first": header[:2], "chars": len(text)}))
    if len(header) > 60:
        raise NlgSourceError("IMPLAUSIBLE_HEADER_LENGTH")
    orders = [slash_order] if slash_order else ["MDY", "DMY"]
    resolved = []
    for order in orders:
        try:
            ds = [_resolve(k, g, century, order) for k, g, _ in rows]
        except NlgSourceError as exc:
            if str(exc).startswith("TWO_DIGIT_YEAR"):
                raise
            continue
        if all(ds[i] <= ds[i + 1] for i in range(len(ds) - 1)):
            resolved.append((order, ds))
    if not any(k == "slash" for k, _, _ in rows):
        resolved = resolved[:1]
    if len(resolved) != 1:
        raise NlgSourceError("DATE_ORDER_UNRESOLVED_OR_NOT_CHRONOLOGICAL")
    order, ds = resolved[0]
    points, seen, missing = {}, set(), 0
    for d, (_, _, v) in zip(ds, rows):
        if d in seen:
            raise NlgSourceError("DUPLICATE_DATE")
        seen.add(d)
        if v in MISSING:
            missing += 1
            continue
        points[d] = to_decimal(v)
    clean = points
    if not clean:
        raise NlgSourceError("NO_OBSERVATIONS")
    return {"points": clean, "missing_markers": missing, "header": header, "trailer": trailer[:3], "trailer_count": len(trailer),
            "slash_order": order if any(k == "slash" for k, _, _ in rows) else None}


# ---------------------------------------------------------------- direction
def detect_direction(text, values):
    """Direction from header/definition text AND value plausibility. Conflict or unknown fails closed."""
    t = (text or "").upper()
    by_text = None
    if re.search(r"GUILDERS?\s*/\s*(U\.?S\.?\s*\$|US\$|USD|DOLLAR)|GUILDERS?\s+PER\s+(ONE\s+)?(U\.?S\.?\s*)?(\$|DOLLAR)|"
                 r"PER\s+1\s+(AMERIKAANSE|US)\s+DOLLAR\s*,?\s*IN\s+GULDEN|AMERIKAANSE\s+DOLLAR.{0,20}IN\s+GULDEN|"
                 r"GULDEN\s+PER\s+(1\s+)?(AMERIKAANSE|US)", t):
        by_text = "NLG_PER_USD"
    if re.search(r"(U\.?S\.?\s*\$|US\$|USD|DOLLARS?)\s*/\s*GUILDER|DOLLARS?\s+PER\s+(ONE\s+)?GUILDER", t):
        by_text = "USD_PER_NLG" if by_text is None else "CONFLICTING_TEXT"
    by_value = None
    if values:
        med = statistics.median(values)
        if BOUNDS["NLG_PER_USD"][0] <= med <= BOUNDS["NLG_PER_USD"][1]:
            by_value = "NLG_PER_USD"
        elif BOUNDS["USD_PER_NLG"][0] <= med <= BOUNDS["USD_PER_NLG"][1]:
            by_value = "USD_PER_NLG"
    if by_text == "CONFLICTING_TEXT":
        raise NlgSourceError("DIRECTION_TEXT_CONFLICT")
    if by_text and by_value and by_text != by_value:
        raise NlgSourceError("DIRECTION_TEXT_VS_VALUE_CONFLICT")
    direction = by_text or by_value
    if direction is None:
        raise NlgSourceError("DIRECTION_UNDETERMINED")
    lo, hi = BOUNDS[direction]
    if any(not lo <= v <= hi for v in values):
        raise NlgSourceError("VALUE_OUT_OF_RANGE_FOR_DIRECTION")
    return {"direction": direction, "evidence": "TEXT_AND_VALUE_RANGE" if by_text else "VALUE_RANGE_ONLY"}


# ---------------------------------------------------------------- aggregation
def month_keys(start=START, end=END):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def aggregate_daily(points, start=START, end=END):
    sums, counts = {}, {}
    for d, v in points.items():
        k = f"{d.year:04d}-{d.month:02d}"
        if start <= k <= end:
            sums[k] = sums.get(k, Decimal(0)) + v
            counts[k] = counts.get(k, 0) + 1
    return {k: sums[k] / counts[k] for k in sorted(sums)}, {k: counts[k] for k in sorted(counts)}


def coverage(monthly, counts=None, start=START, end=END):
    expected = month_keys(start, end)
    absent = [k for k in expected if k not in monthly]
    out = {"expected_months": len(expected), "present_months": len(expected) - len(absent), "missing_count": len(absent),
           "first_present": next((k for k in expected if k in monthly), None),
           "last_present": next((k for k in reversed(expected) if k in monthly), None),
           "missing_months": absent if len(absent) <= 36 else absent[:12] + ["..."] + absent[-12:]}
    if counts:
        vals = sorted(counts.values())
        out["obs_per_month"] = {"min": vals[0], "median": vals[len(vals) // 2], "max": vals[-1],
                                "months_below_15": sum(1 for c in vals if c < 15)}
        med = vals[len(vals) // 2]
        out["frequency_guess"] = "daily" if med >= 15 else "weekly" if med >= 3 else "monthly" if med >= 1 else "unknown"
    return out


ANCHORS = ("1975-01", "1980-01", "1985-01", "1990-01", "1995-01", "1998-12")


def anchors(monthly):
    return {k: str(monthly[k].quantize(Decimal("0.0001"))) for k in ANCHORS if k in monthly}


def compare_monthly(a, b):
    common = sorted(set(a) & set(b))
    if not common:
        return {"common_months": 0}
    rel = sorted(((abs(a[k] - b[k]) / b[k], k) for k in common), reverse=True)
    return {"common_months": len(common), "max_rel_diff": str(rel[0][0].quantize(Decimal("0.00001"))), "max_rel_diff_month": rel[0][1],
            "median_rel_diff": str(rel[len(rel) // 2][0].quantize(Decimal("0.00001"))),
            "months_rel_diff_above_1pct": sum(1 for r, _ in rel if r > Decimal("0.01"))}


def summarize_series(parsed, granularity, century=None):
    """parsed from parse_dated_text -> summary + monthly dict (quoted direction, mean-before-convert)."""
    pts = parsed["points"]
    d = detect_direction(" ".join(parsed["header"]), list(pts.values()))
    if granularity == "daily":
        monthly, counts = aggregate_daily(pts)
    else:
        monthly, counts = {}, {}
        for dt, v in pts.items():
            k = f"{dt.year:04d}-{dt.month:02d}"
            if START <= k <= END:
                if k in monthly:
                    raise NlgSourceError("DUPLICATE_MONTH")
                monthly[k], counts[k] = v, 1
    ds = sorted(pts)
    s = {"points": len(pts), "missing_markers": parsed["missing_markers"], "first_date": ds[0].isoformat(), "last_date": ds[-1].isoformat(),
         "direction": d, "slash_order": parsed["slash_order"], "header_head": parsed["header"][:10],
         "trailer_count": parsed["trailer_count"], "trailer_head": parsed["trailer"],
         "coverage_1975_1998": coverage(monthly, counts), "anchor_monthly_means": anchors(monthly),
         "aggregation": "arithmetic mean of quoted direction per calendar month; no filling" if granularity == "daily" else "provider monthly value"}
    return s, monthly, d["direction"]


# ---------------------------------------------------------------- CBS 7139SHFO (OData v3 JSON)
def _load_json(raw):
    try:
        return json.loads(raw.decode("utf-8-sig"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, ValueError) as exc:
        raise NlgSourceError("NOT_JSON") from exc


def parse_cbs(props_raw, data_raw, title_regex=r"amerikaanse dollar|us dollar"):
    props = _load_json(props_raw).get("value")
    data = _load_json(data_raw)
    if not isinstance(props, list) or not isinstance(data.get("value"), list):
        raise NlgSourceError("UNEXPECTED_ODATA_SHAPE")
    cands = [p for p in props if p.get("Type", "Topic") == "Topic" and re.search(title_regex, str(p.get("Title", "")), re.I)]
    if len(cands) != 1:
        raise NlgSourceError("AMBIGUOUS_OR_MISSING_USD_PROPERTY " + json.dumps([str(c.get("Title"))[:50] for c in cands][:5]))
    prop = cands[0]
    key = prop["Key"]
    text = " ".join(str(prop.get(f, "")) for f in ("Title", "Unit", "Description"))
    monthly, annual, missing = {}, {}, 0
    for row in data["value"]:
        per, val = str(row.get("Perioden", "")), row.get(key)
        mm = re.fullmatch(r"(\d{4})MM(\d{2})", per)
        yy = re.fullmatch(r"(\d{4})JJ00", per)
        if not (mm or yy):
            raise NlgSourceError("UNEXPECTED_PERIOD_CODE " + json.dumps(per[:12]))
        if val is None or (isinstance(val, str) and val.strip() in MISSING):
            missing += 1
            continue
        if not isinstance(val, Decimal) or val <= 0:
            raise NlgSourceError("INVALID_VALUE")
        if mm:
            k = f"{mm.group(1)}-{mm.group(2)}"
            if k in monthly:
                raise NlgSourceError("DUPLICATE_MONTH")
            monthly[k] = val
        else:
            annual[yy.group(1)] = val
    if not monthly:
        raise NlgSourceError("NO_MONTHLY_OBSERVATIONS")
    d = detect_direction(text, list(monthly.values()))
    inr = {k: v for k, v in monthly.items() if START <= k <= END}
    ks = sorted(monthly)
    return {"property_key": str(key), "property_title": str(prop.get("Title"))[:100], "property_unit": str(prop.get("Unit"))[:30],
            "property_description": str(prop.get("Description") or "")[:200], "direction": d, "rows": len(data["value"]),
            "missing_values": missing, "monthly_points": len(monthly), "annual_points": len(annual), "first_month": ks[0], "last_month": ks[-1],
            "next_link_present": any(k.endswith("nextLink") for k in data),
            "coverage_1975_1998": coverage(inr), "anchor_monthly_values": anchors(inr)}, inr, d["direction"]


def cbs_info_facts(raw):
    doc = _load_json(raw)
    row = (doc.get("value") or [{}])[0]
    return {k: str(row.get(k))[:260] for k in ("Title", "ShortDescription", "Summary", "Modified", "Frequency", "Period", "Language") if k in row}


# ---------------------------------------------------------------- SDMX-like / BIS CSV scanning
TIME_COLS = {"TIME_PERIOD", "Time period", "TIME"}
OBS_COLS = {"OBS_VALUE", "Observation value", "Value"}
PERIOD_RE = re.compile(r"\d{4}(-\d{2}(-\d{2})?|-Q\d|-A1)?")


def _is_nl(attrs):
    return any(v == "NL" or v == "NLG" or re.search(r"netherlands|dutch guilder", v, re.I) for v in attrs)


def _period_key(p):
    return p[:7] if len(p) >= 7 else None


def scan_sdmx_csv(rows, max_series=6):
    """rows: iterable of lists (csv.reader). Long (TIME_PERIOD/OBS_VALUE) or wide (period columns) layout."""
    it = iter(rows)
    header = None
    for r in it:
        if r and any(c.strip() for c in r):
            header = [c.strip() for c in r]
            break
    if header is None:
        raise NlgSourceError("EMPTY_CSV")
    tcol = next((i for i, c in enumerate(header) if c in TIME_COLS), None)
    ocol = next((i for i, c in enumerate(header) if c in OBS_COLS), None)
    wide = [i for i, c in enumerate(header) if PERIOD_RE.fullmatch(c)]
    if tcol is not None and ocol is not None:
        layout = "long"
    elif len(wide) >= 20:
        layout = "wide"
    else:
        raise NlgSourceError("CSV_LAYOUT_UNRECOGNISED " + json.dumps(header[:8]))
    attr_idx = [i for i in range(len(header)) if i not in set(wide) and i not in {tcol, ocol}]
    series, total, areas = {}, 0, set()
    area_col = next((i for i in attr_idx if header[i].upper() in {"REF_AREA", "REFERENCE AREA", "COUNTRY"}), None)
    for r in it:
        if not r:
            continue
        total += 1
        attrs = [r[i].strip() if i < len(r) else "" for i in attr_idx]
        if area_col is not None and area_col < len(r):
            areas.add(r[area_col].strip()[:30])
        if not _is_nl(attrs):
            continue
        key = tuple(a[:40] for a in attrs)
        s = series.setdefault(key, {})
        pairs = [(r[tcol].strip(), r[ocol].strip())] if layout == "long" else [(header[i], r[i].strip()) for i in wide if i < len(r)]
        for p, v in pairs:
            if v in MISSING:
                s.setdefault("_missing", 0)
                s["_missing"] += 1
                continue
            if p in s:
                raise NlgSourceError("DUPLICATE_PERIOD_IN_SERIES")
            s[p] = to_decimal(v)
    out = []
    for key, s in series.items():
        miss = s.pop("_missing", 0)
        if not s:
            out.append({"attrs": dict(zip([header[i] for i in attr_idx], key)), "observations": 0, "missing_markers": miss})
            continue
        ps = sorted(s)
        mon = {}
        for p in ps:
            k = _period_key(p)
            if k and START <= k <= END:
                mon.setdefault(k, []).append(s[p])
        monthly = {k: sum(v) / len(v) for k, v in mon.items()}
        counts = {k: len(v) for k, v in mon.items()}
        entry = {"attrs": dict(list(zip([header[i] for i in attr_idx], key))[:14]), "observations": len(s), "missing_markers": miss,
                 "first_period": ps[0], "last_period": ps[-1], "coverage_1975_1998": coverage(monthly, counts),
                 "anchor_monthly_means": anchors(monthly)}
        vals = [v for v in s.values()]
        try:
            entry["direction"] = detect_direction(" ".join(key), vals)
        except NlgSourceError as exc:
            entry["direction_error"] = str(exc)
        out.append(entry)
    return {"layout": layout, "rows_scanned": total, "distinct_areas": len(areas) if areas else None, "header": header[:12] if layout == "long" else header[:8],
            "nl_series_count": len(out), "nl_series": out[:max_series], "_monthly_for_cross": None}


def scan_csv_bytes(raw):
    return scan_sdmx_csv(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace"))))


def scan_zip_bytes(raw, max_member=400_000_000):
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise NlgSourceError("BAD_ZIP") from exc
    members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
    if not members:
        raise NlgSourceError("NO_CSV_IN_ZIP " + json.dumps([i.filename[:60] for i in zf.infolist()][:5]))
    big = members[0]
    if big.file_size > max_member:
        raise NlgSourceError("ZIP_MEMBER_TOO_LARGE")
    with zf.open(big) as fh:
        res = scan_sdmx_csv(csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")))
    res["zip_member"] = big.filename[:80]
    res["zip_members"] = len(members)
    return res


# ---------------------------------------------------------------- probes
def probe_status(url):
    """Diagnostic only for a failed fetch: first-response status/location/content-type, no redirect followed."""
    from urllib.error import HTTPError
    from urllib.parse import urlsplit
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        resp = build_opener(NoRedirect).open(Request(url, headers={"User-Agent": "Goud-btc-dashboard/HIST-04 probe"}), timeout=30)
        return {"status": resp.status, "content_type": resp.headers.get("Content-Type")}
    except HTTPError as exc:
        loc = exc.headers.get("Location")
        p = urlsplit(loc) if loc else None
        return {"status": exc.code, "location_host": p.hostname if p else None, "location_path": p.path if p else None,
                "server": exc.headers.get("Server"), "content_type": exc.headers.get("Content-Type")}
    except OSError as exc:
        return {"error_class": type(exc).__name__}


PAGE_KEYWORDS = r"noon buying|public domain|certified|discontinu|guilder|netherlands|historical|copyright|licen[cs]e|CC-BY|reuse|source|bron"
LINK_FILTERS = {"fed": r"_ne\.|neth|g5|g5a|hist|dat\d\d", "fred": r"exneus|download|csv|txt", "cbs": r"licen|copyright|cc-by|bron|7139",
                "dnb": r"wissel|exchange|koers|rate|statist|api|open|data", "fixed": r"2866|conversion", "bis": r"xru|bulk", "imf": r"exchange|xru"}


def run_candidate(sid, results, monthly_store):
    url, fmt, group = CANDIDATES[sid]
    entry = {"source_id": sid, "url": url, "group": group}
    try:
        raw, rec = hist_02_acquire.fetch(sid)
    except hist_02_acquire.AcquisitionError as exc:
        entry.update({"fetch": "FAILED", "error": str(exc)[:200], "probe": probe_status(url)})
        results.append(entry)
        return
    entry.update({"fetch": "HTTP_200", "bytes": rec["bytes"], "sha256": rec["sha256"]})
    defects = []
    try:
        if sid.endswith("-txt") and group in ("fed", "fred"):
            gran = "monthly" if group == "fred" else "daily"
            century = 1900
            parsed = parse_dated_text(raw, century=century)
            entry["two_digit_year_rule"] = "century 1900 (file span 1971-1999 only; chronological order enforced)"
            entry["parsed"], monthly, direction = summarize_series(parsed, gran)
            monthly_store[sid] = (monthly, direction)
        elif fmt == "html" and sid.endswith("-htm") and group == "fed":
            plain_pre = re.findall(r"(?is)<pre[^>]*>", raw.decode("utf-8", "replace"))
            entry["page"] = page_facts(raw, PAGE_KEYWORDS, LINK_FILTERS["fed"])
            entry["has_pre_block"] = bool(plain_pre)
        elif group == "fixed":
            entry["fixed_rate"] = extract_fixed_rate(raw)
        elif sid == "cbs-7139shfo-info":
            entry["info"] = cbs_info_facts(raw)
        elif sid == "cbs-7139shfo-props":
            pass  # consumed together with the data set below
        elif sid == "cbs-7139shfo-data":
            props_raw, _ = hist_02_acquire.fetch("cbs-7139shfo-props")
            entry["parsed"], monthly, direction = parse_cbs(props_raw, raw)
            monthly_store[sid] = (monthly, direction)
        elif fmt == "zip":
            entry["scan"] = scan_zip_bytes(raw)
        elif fmt == "csv":
            try:
                entry["scan"] = scan_csv_bytes(raw)
            except NlgSourceError as exc:  # exploratory API guesses: unparsed is a finding, not a defect
                head = raw[:160].decode("utf-8", "replace")
                entry["format_unparsed"] = str(exc)[:160]
                entry["head_snippet"] = re.sub(r"\s+", " ", head)
        elif fmt == "json" and group == "imf":
            entry["format_unparsed"] = "JSON_NOT_PARSED_EXPLORATORY"
            entry["head_snippet"] = re.sub(r"\s+", " ", raw[:160].decode("utf-8", "replace"))
        else:
            entry["page"] = page_facts(raw, PAGE_KEYWORDS, LINK_FILTERS.get(group, r"data"))
    except NlgSourceError as exc:
        entry["defect"] = str(exc)[:300]
        defects.append(sid)
    results.append(entry)
    return defects


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--only", action="append", choices=sorted(CANDIDATES))
    args = ap.parse_args(argv)
    results, monthly_store, defects = [], {}, []
    for sid in (args.only or list(CANDIDATES)):
        if sid in ("cbs-7139shfo-props",):
            continue
        try:
            d = run_candidate(sid, results, monthly_store)
        except (hist_02_acquire.AcquisitionError, OSError) as exc:
            results.append({"source_id": sid, "fetch": "FAILED_DURING_PARSE_DEPENDENCY", "error": str(exc)[:200]})
            d = None
        defects += d or []
        print(json.dumps({sid: {k: results[-1].get(k) for k in ("fetch", "bytes", "defect", "error")}}, sort_keys=True, default=str), flush=True)
    cross = {}
    ids = sorted(monthly_store)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if monthly_store[a][1] == monthly_store[b][1]:
                cross[f"{a} vs {b}"] = compare_monthly(monthly_store[a][0], monthly_store[b][0])
    fed = {}
    for sid in ("fed-h10-dat89-ne-txt", "fed-h10-dat96-ne-txt"):
        if sid in monthly_store:
            for k, v in monthly_store[sid][0].items():
                if k in fed and fed[k] != v:
                    cross.setdefault("fed_file_overlap_conflict", []).append(k)
                fed[k] = v
    fed_dir = {monthly_store[s][1] for s in ("fed-h10-dat89-ne-txt", "fed-h10-dat96-ne-txt") if s in monthly_store}
    summary = {"status": "DONE", "range": [START, END], "fixed_rate_expected": str(FIXED_NLG_PER_EUR), "rights_status": "UNVERIFIED",
               "publication_authorized": False, "source_approved": False, "results": results, "cross_checks": cross,
               "fed_h10_combined_monthly_coverage": coverage(fed) if fed and len(fed_dir) == 1 else None,
               "fixed_rate_verified_in": [r["source_id"] for r in results if r.get("fixed_rate", {}).get("status") == "FOUND"],
               "defects": defects}
    out = Path(args.summary_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("status", "cross_checks", "fed_h10_combined_monthly_coverage", "fixed_rate_verified_in", "defects")},
                     sort_keys=True, default=str))
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main())
